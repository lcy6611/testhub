# -*- coding: utf-8 -*-
"""知识中枢 API 视图。"""

from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .backend import KbBackendFactory
from .models import (
    KnowledgeHubConfig,
    NativeKb,
    NativeKbDocument,
    NativeKbChunk,
    KbSource,
    ProjectDifyKbBinding,
    ProjectKbBinding,
    DocumentProjectBinding,
)
from .native_backend import NativeKbBackend
from .adapters import get_adapter
from .serializers import (
    KnowledgeHubConfigSerializer,
    NativeKbDocumentSerializer,
    NativeKbSerializer,
    KbSourceSerializer,
    ProjectDifyKbBindingSerializer,
)

logger = logging.getLogger(__name__)


def _kb_error_status(exc: Exception) -> int:
    """根据异常类型决定返回状态码：配置缺失/参数错误 400，网络/服务异常 503，其他 500。"""
    if isinstance(exc, ValueError):
        return 400
    import requests
    if isinstance(exc, requests.exceptions.RequestException):
        return 503
    return 500


class KnowledgeHubConfigViewSet(viewsets.ViewSet):
    """知识中枢配置（单例，5 项配置：解析 / Embedding / Rerank / 抽取 / 视觉）。"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        config = KnowledgeHubConfig.get_or_create_active()
        return Response(KnowledgeHubConfigSerializer(config).data)

    def retrieve(self, request, pk=None):
        return self.list(request)

    def update(self, request, pk=None):
        return self._save(request, partial=False)

    def partial_update(self, request, pk=None):
        return self._save(request, partial=True)

    def save_singleton(self, request):
        """PUT/PATCH /config/ 在 urls.py 直挂，无需 pk。"""
        partial = request.method.upper() == "PATCH"
        return self._save(request, partial=partial)

    def _save(self, request, *, partial: bool):
        config = KnowledgeHubConfig.get_or_create_active()
        serializer = KnowledgeHubConfigSerializer(config, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        # 切换引擎时只保留一个 active
        engine = serializer.validated_data.get("engine")
        if engine:
            KnowledgeHubConfig.objects.exclude(pk=config.pk).update(is_active=False)
            config.is_active = True
        serializer.save()
        return Response(KnowledgeHubConfigSerializer(config).data)

    @action(detail=False, methods=["post"], url_path="switch-engine")
    def switch_engine(self, request):
        engine = (request.data.get("engine") or "").strip().lower()
        if engine not in ("dify", "native"):
            return Response({"detail": "engine 必须为 dify 或 native"}, status=400)
        config = KnowledgeHubConfig.get_or_create_active()
        config.engine = engine
        config.is_active = True
        config.save(update_fields=["engine", "is_active", "updated_at"])
        return Response(KnowledgeHubConfigSerializer(config).data)

    @action(detail=False, methods=["post"], url_path="test-retrieval")
    def test_retrieval(self, request):
        query = (request.data.get("query") or "").strip()
        kb_id = request.data.get("kb_id")
        if not query:
            return Response({"detail": "请输入测试问题"}, status=400)
        try:
            backend = KbBackendFactory.get_backend()
            records, meta = backend.retrieve_for_chat(
                query, top_k=5, kb_id=str(kb_id) if kb_id else None,
            )
            return Response({"records": records, "meta": meta})
        except Exception as exc:
            logger.warning("知识中枢测试检索失败: %s", exc)
            return Response({"detail": str(exc)}, status=_kb_error_status(exc))

    @action(detail=False, methods=["get"], url_path="knowledge-bases")
    def knowledge_bases(self, request):
        """列出当前引擎下的知识库。"""
        try:
            backend = KbBackendFactory.get_backend()
            keyword = request.query_params.get("keyword", "")
            data = backend.list_knowledge_bases(keyword=keyword)
            return Response({"data": data, "engine": backend.engine_name})
        except Exception as exc:
            logger.warning("列出知识库失败: %s", exc)
            return Response({"detail": str(exc)}, status=_kb_error_status(exc))

    @action(detail=False, methods=["get"], url_path="documents")
    def documents(self, request):
        kb_id = request.query_params.get("kb_id")
        if not kb_id:
            return Response({"detail": "缺少 kb_id"}, status=400)
        try:
            backend = KbBackendFactory.get_backend()
            keyword = request.query_params.get("keyword", "")
            data = backend.list_documents(str(kb_id), keyword=keyword)
            return Response({"data": data, "engine": backend.engine_name})
        except Exception as exc:
            logger.warning("列出文档失败: %s", exc)
            return Response({"detail": str(exc)}, status=_kb_error_status(exc))

    @action(detail=False, methods=["get"], url_path="project-kbs")
    def project_kbs(self, request):
        """AI 用例生成专用：按项目自动合并可用知识库。

        自动判定引擎（与公众号 6.0 一致）：
          - 项目绑定了 Dify 数据集 → 引擎 = dify；返回 Dify 数据集列表
          - 项目下有已发布的本地 KB → 引擎 = native；返回本地 KB 列表
          - 都没有 → 引擎 = 全局默认（KnowledgeHubConfig.engine）；返回空列表

        返回结构：
          {
            "engine": "dify" | "native",
            "reason": "为什么选这个引擎",
            "kb_count": 3,
            "items": [
              {"id": ..., "name": ..., "type": "dify" | "native", "source": "dify-binding" | "global" | "shared" | "owned"}
            ]
          }
        """
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "缺少 project_id"}, status=400)

        # 1. 项目下 Dify 数据集
        dify_bindings = ProjectDifyKbBinding.objects.filter(project_id=project_id)
        dify_items = [
            {
                "id": f"dify:{b.dataset_id}",
                "dataset_id": b.dataset_id,
                "name": b.dataset_name or b.dataset_id,
                "type": "dify",
                "source": "dify-binding",
                "document_count": b.document_count,
            }
            for b in dify_bindings
        ]

        # 2. 项目下本地 KB（合并：直接归属 / 全局共享 / 显式绑定）
        local_kbs = NativeKb.available_for_project(project_id).filter(status="published")
        local_items = [
            {
                "id": f"native:{kb.pk}",
                "kb_id": kb.pk,
                "name": kb.name,
                "type": "native",
                "source": (
                    "owned" if str(kb.project_id) == str(project_id)
                    else ("global" if kb.is_global else "shared")
                ),
                "description": kb.description,
                "document_count": kb.document_count,
            }
            for kb in local_kbs
        ]

        # 自动判定引擎
        if dify_items:
            engine = "dify"
            reason = f"项目已绑定 {len(dify_items)} 个 Dify 数据集，优先使用 Dify 检索"
            items = dify_items
        elif local_items:
            engine = "native"
            reason = f"项目下有 {len(local_items)} 个已发布的本地知识库，使用自建知识中枢"
            items = local_items
        else:
            cfg = KnowledgeHubConfig.get_active()
            engine = cfg.engine if cfg else "dify"
            reason = "项目下尚无可用知识库，请先绑定 Dify 数据集或在知识库管理页创建并发布本地 KB"
            items = []

        return Response({
            "engine": engine,
            "reason": reason,
            "kb_count": len(items),
            "items": items,
        })

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        """知识中枢首页统计：KB 数 / 文档数 / 分块数 / 已发布数 / 各引擎状态。"""
        kb_total = NativeKb.objects.count()
        kb_published = NativeKb.objects.filter(status="published").count()
        doc_total = NativeKbDocument.objects.count()
        doc_parsed = NativeKbDocument.objects.filter(status="parsed").count()
        chunk_total = NativeKbChunk.objects.count()
        source_total = KbSource.objects.count()
        dify_binding_total = ProjectDifyKbBinding.objects.count()
        doc_binding_total = DocumentProjectBinding.objects.count()
        kb_binding_total = ProjectKbBinding.objects.count()

        cfg = KnowledgeHubConfig.get_or_create_active()
        return Response({
            "kb_total": kb_total,
            "kb_published": kb_published,
            "doc_total": doc_total,
            "doc_parsed": doc_parsed,
            "chunk_total": chunk_total,
            "source_total": source_total,
            "dify_binding_total": dify_binding_total,
            "kb_binding_total": kb_binding_total,
            "doc_binding_total": doc_binding_total,
            "default_engine": cfg.engine,
        })


class NativeKbViewSet(viewsets.ModelViewSet):
    """自建知识库管理。"""

    queryset = NativeKb.objects.all()
    serializer_class = NativeKbSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["project", "status"]
    ordering = ["-updated_at"]

    def get_queryset(self):
        project = self.request.query_params.get("project")
        include_global = self.request.query_params.get("include_global") in (
            "1", "true", "True", "yes", "y", "1",
        )
        if project and include_global:
            # 项目可用 KB = 直接归属该项目 + 全局共享 + 显式绑定到该项目的
            qs = NativeKb.available_for_project(project)
        else:
            qs = super().get_queryset()
            if project:
                qs = qs.filter(project_id=project)
            elif include_global:
                qs = qs.filter(is_global=True)
        status = self.request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        kb = self.get_object()
        kb.status = "published"
        kb.save(update_fields=["status", "updated_at"])
        return Response(NativeKbSerializer(kb).data)

    @action(detail=True, methods=["post"], url_path="unpublish")
    def unpublish(self, request, pk=None):
        """取消发布：退回草稿，停止在 AI 用例生成 / 知识问答中被检索。"""
        kb = self.get_object()
        kb.status = "draft"
        kb.save(update_fields=["status", "updated_at"])
        return Response(NativeKbSerializer(kb).data)

    @action(detail=True, methods=["get"], url_path="documents")
    def documents(self, request, pk=None):
        docs = NativeKbDocument.objects.filter(kb_id=pk)
        return Response({"data": NativeKbDocumentSerializer(docs, many=True).data})


class NativeKbDocumentViewSet(viewsets.ModelViewSet):
    """自建知识库文档管理（支持文件上传 + 入库）。"""

    queryset = NativeKbDocument.objects.all()
    serializer_class = NativeKbDocumentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        data = request.data.dict() if hasattr(request.data, "dict") else dict(request.data)
        # 文件上传时用文件名作为标题兜底
        file_obj = request.FILES.get("file")
        if file_obj and not data.get("title"):
            data["title"] = file_obj.name
        kb_id = data.get("kb")
        if not kb_id:
            return Response({"detail": "缺少知识库 kb"}, status=400)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="all")
    def list_all(self, request):
        """跨 KB 列出文档：可选 project（仅返回该项目可见 KB 下的文档），不选返回全部。"""
        project = request.query_params.get("project")
        qs = NativeKbDocument.objects.all().select_related("kb")
        if project:
            kb_ids = list(NativeKb.available_for_project(project).values_list("id", flat=True))
            qs = qs.filter(kb_id__in=kb_ids)
        qs = qs.order_by("-updated_at")[:500]
        return Response({"data": NativeKbDocumentSerializer(qs, many=True).data})

    @action(detail=True, methods=["post"], url_path="ingest")
    def ingest(self, request, pk=None):
        """解析 + 分块 + Embedding 入库。"""
        doc = self.get_object()
        config = KnowledgeHubConfig.get_active()
        if config is None or config.engine != "native":
            return Response({"detail": "当前知识中枢引擎非 native，无法入库。请先在配置中切换为知识中枢（自建）。"}, status=400)
        backend = NativeKbBackend(config)
        result = backend.ingest_document(doc)
        # 入库成功后自动把该 KB 同步到知识图谱（KB → 文档 contains 边）
        if result.get("ok"):
            try:
                from apps.knowledge_graph.builder import sync_native_kb
                sync_native_kb(doc.kb_id)
            except Exception as exc:
                logger.warning("知识库 %s 同步知识图谱失败: %s", doc.kb_id, exc)
        return Response(result, status=200 if result.get("ok") else 500)

    @action(detail=True, methods=["post"], url_path="reindex")
    def reindex(self, request, pk=None):
        return self.ingest(request, pk=pk)

    @action(detail=True, methods=["delete"], url_path="chunks")
    def clear_chunks(self, request, pk=None):
        doc = self.get_object()
        NativeKbChunk.objects.filter(document=doc).delete()
        doc.status = "pending"
        doc.save(update_fields=["status", "updated_at"])
        return Response({"detail": "已清空分块"})


class KbSourceViewSet(viewsets.ModelViewSet):
    """外部 SaaS 知识源（飞书等）管理 + 同步。"""

    queryset = KbSource.objects.all()
    serializer_class = KbSourceSerializer
    permission_classes = [IsAuthenticated]
    ordering = ["-updated_at"]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request, pk=None):
        """触发同步：把外部知识库内容拉取存储到本地自建知识库。"""
        source = self.get_object()
        try:
            adapter = get_adapter(source)
            result = adapter.sync_to_native()
            return Response({
                "ok": True,
                "doc_count": result.get("synced", 0),
                "failed_count": result.get("failed", 0),
                "detail": "同步完成",
                "result": result,
                "source": KbSourceSerializer(source).data,
            })
        except Exception as exc:
            logger.warning("同步外部知识源失败 source=%s: %s", source.pk, exc)
            return Response(
                {"ok": False, "error": str(exc), "detail": str(exc)},
                status=_kb_error_status(exc),
            )


class DifyKbBindingViewSet(viewsets.ViewSet):
    """项目 ↔ Dify 知识库（数据集）绑定管理。

    绑定后，AI 用例生成「启用知识库」时即可按所选项目列出这些 Dify 数据集。
    """

    permission_classes = [IsAuthenticated]

    def list(self, request):
        project = request.query_params.get("project")
        qs = ProjectDifyKbBinding.objects.all()
        if project:
            qs = qs.filter(project_id=project)
        return Response(ProjectDifyKbBindingSerializer(qs, many=True).data)

    def create(self, request):
        project = request.data.get("project")
        dataset_id = (request.data.get("dataset_id") or "").strip()
        if not project or not dataset_id:
            return Response({"detail": "project 与 dataset_id 均为必填"}, status=400)
        dataset_name = (request.data.get("dataset_name") or "").strip()
        try:
            document_count = int(request.data.get("document_count") or 0)
        except (TypeError, ValueError):
            document_count = 0
        dify_config_id = request.data.get("dify_config") or None
        binding, _created = ProjectDifyKbBinding.objects.update_or_create(
            project_id=project, dataset_id=dataset_id,
            defaults={
                "dataset_name": dataset_name,
                "document_count": document_count,
                "dify_config_id": dify_config_id,
            },
        )
        return Response(ProjectDifyKbBindingSerializer(binding).data, status=201)

    def destroy(self, request, pk=None):
        ProjectDifyKbBinding.objects.filter(pk=pk).delete()
        return Response(status=204)

    @action(detail=False, methods=["get"], url_path="available-datasets")
    def available_datasets(self, request):
        """列出当前激活 Dify 配置下的全部数据集，并标注是否已绑定到指定 project。

        无论知识中枢引擎是 dify 还是 native，只要存在可用的 Dify 配置即可列出，
        便于在「知识库管理」中预先把 Dify 数据集绑定到项目。
        """
        from apps.requirement_analysis.dify_kb_service import list_datasets, resolve_dify_config

        project = request.query_params.get("project")
        keyword = (request.query_params.get("keyword") or "").strip()
        config = resolve_dify_config(None)
        if not config:
            return Response(
                {"detail": "未找到可用的 Dify 配置，请先在配置中心添加并启用 Dify"},
                status=400,
            )
        try:
            payload = list_datasets(config, page=1, limit=200, keyword=keyword)
        except Exception as exc:
            logger.warning("列出 Dify 数据集失败: %s", exc)
            return Response({"detail": str(exc)}, status=_kb_error_status(exc))

        bound_map = {}
        if project:
            bound_map = {
                b.dataset_id: b.id
                for b in ProjectDifyKbBinding.objects.filter(project_id=project)
            }
        datasets = payload.get("data") or []
        for d in datasets:
            did = d.get("id")
            d["bound"] = did in bound_map
            d["bound_id"] = bound_map.get(did)
        return Response({
            "data": datasets,
            "dify_config_id": config.id,
            "total": payload.get("total", len(datasets)),
        })
