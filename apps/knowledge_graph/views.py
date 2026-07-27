import logging

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .builder import (
    auto_cover_test_cases,
    extract_and_sync_cross_doc_relations,
    extract_and_sync_function_points,
    extract_function_points_from_requirements,
    sync_all_api_requests,
    sync_all_business_requirements,
    sync_all_generation_tasks,
    sync_all_kb_functions,
    sync_all_native_kbs,
    sync_all_requirement_documents,
    sync_all_test_cases,
    sync_all_ui_pages,
)
from .edge_ops import (
    confirm_suggested_kg_edges,
    create_manual_kg_edge,
    edge_to_response,
    list_kg_edges_for_entity,
    list_pending_suggested_edges,
    persist_kg_edge_suggestions,
    reject_suggested_kg_edges,
    resolve_manual_edge_entities,
)
from .coverage import get_project_coverage_report
from .export import (
    export_kg_graph,
    export_kg_html,
    export_kg_mermaid,
    export_kg_svg,
)
from .graph_suggest import suggest_kg_edges
from .models import kg_enabled, KgEntity, KgEdge
from .query import (
    build_graph_relations_prompt_summary_for_selection,
    expand_kb_references_via_graph,
    get_entity_neighbors,
    get_project_graph,
    get_subgraph,
    impact_test_cases_for_kb_document,
)
from .registry import get_entity

logger = logging.getLogger(__name__)


def _parse_csv_ints(raw: str) -> list[int]:
    items: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            items.append(int(part))
        except (TypeError, ValueError):
            continue
    return items


def _parse_csv_strings(raw: str) -> list[str]:
    return [part.strip() for part in (raw or "").split(",") if part.strip()]


def _parse_id_list(value) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        return _parse_csv_ints(",".join(str(x) for x in value))
    if isinstance(value, (int, float)):
        return [int(value)]
    return _parse_csv_ints(str(value))


class KnowledgeGraphViewSet(viewsets.ViewSet):
    """知识图谱查询 API。"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="subgraph")
    def subgraph(self, request):
        entity_key = (request.query_params.get("entity") or "").strip()
        if not entity_key:
            return Response({"detail": "请提供 entity 参数"}, status=status.HTTP_400_BAD_REQUEST)
        depth = request.query_params.get("depth", 2)
        max_nodes = request.query_params.get("max_nodes", 200)
        dataset_id = (request.query_params.get("dataset_id") or "").strip()
        data = get_subgraph(entity_key, depth=int(depth), max_nodes=int(max_nodes))
        # 如果指定了dataset_id，过滤结果
        if dataset_id and data.get("edges"):
            data["edges"] = [e for e in data["edges"] if e.get("meta", {}).get("dataset_id") == dataset_id]
        return Response(data)

    @action(detail=False, methods=["get"], url_path="project-graph")
    def project_graph(self, request):
        """项目级图谱（nodes/edges，供 ECharts 力导向图）。
        
        支持按 dataset_id 过滤（只看某个知识库的图谱）。
        """
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        raw_project_id = request.query_params.get("project_id")
        if raw_project_id in (None, ""):
            return Response({"detail": "请提供 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project_id = int(raw_project_id)
        except (TypeError, ValueError):
            return Response({"detail": "无效的 project_id"}, status=status.HTTP_400_BAD_REQUEST)

        dataset_id = (request.query_params.get("dataset_id") or "").strip()

        try:
            depth = int(request.query_params.get("depth", 2))
        except (TypeError, ValueError):
            depth = 2
        try:
            max_nodes = int(request.query_params.get("max_nodes", 300))
        except (TypeError, ValueError):
            max_nodes = 300

        data = get_project_graph(project_id, dataset_id=dataset_id, depth=depth, max_nodes=max_nodes)
        if not data.get("nodes") and data.get("detail"):
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="kb-graph")
    def kb_graph(self, request):
        """按知识库 ID 拉取其关联项目的完整业务图谱（同知识图谱浏览同源）。

        流程：
        1. 先 sync_native_kb(kb_id) 确保 KB+Document 入图；
        2. 收集 KB 关联的所有 project_id（KB 归属 + ProjectKbBinding + DocumentProjectBinding）；
        3. 默认取 project_ids[0]（可被 ?project_id= 覆盖），调用 get_project_graph(pid, dataset_id="", depth=3)
           拉**项目级完整图谱**（含 Project + Requirement + TestCase + FunctionPoint + NativeKb + NativeKbDocument 等）；
        4. 合并所有 project 的图谱节点/边；
        5. KB 无项目时 fallback：直接查 KgEntity dataset_id=native:{kb_id}（仅 KB 子图）。
        """
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        raw_kb_id = request.query_params.get("kb_id")
        if raw_kb_id in (None, ""):
            return Response({"detail": "请提供 kb_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            kb_id = int(raw_kb_id)
        except (TypeError, ValueError):
            return Response({"detail": "无效的 kb_id"}, status=status.HTTP_400_BAD_REQUEST)

        # 触发一次同步，确保最新文档/分块都进图谱
        try:
            from .builder import sync_native_kb

            sync_native_kb(kb_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("kb_graph 同步知识库 %s 失败: %s", kb_id, exc)

        from apps.requirement_analysis.kb_hub.models import (
            NativeKb, ProjectKbBinding, DocumentProjectBinding,
        )

        kb = NativeKb.objects.filter(pk=kb_id).first()
        if not kb:
            return Response({"detail": f"知识库 #{kb_id} 不存在"}, status=status.HTTP_404_NOT_FOUND)

        dataset_id = f"native:{kb_id}"
        # 收集要查的 project_id 集合（KB 归属项目 + 共享项目 + 文档共享项目）
        project_ids: set = set()
        if kb.project_id:
            project_ids.add(kb.project_id)
        try:
            for pid in ProjectKbBinding.objects.filter(kb_id=kb_id).values_list("project_id", flat=True):
                project_ids.add(pid)
            for pid in DocumentProjectBinding.objects.filter(
                document__kb_id=kb_id,
            ).values_list("project_id", flat=True):
                project_ids.add(pid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("kb_graph 收集项目 ID 失败: %s", exc)

        try:
            max_nodes = int(request.query_params.get("max_nodes", 400))
        except (TypeError, ValueError):
            max_nodes = 400

        # 可选：调用方显式指定 project_id（弹窗项目切换器）
        explicit_pid = request.query_params.get("project_id")
        if explicit_pid:
            try:
                pid_int = int(explicit_pid)
                project_ids = {pid_int}
            except (TypeError, ValueError):
                pass

        # 多 project 时分别拉，再合并（项目级完整图谱，与知识图谱浏览同源）
        all_nodes: Dict[str, Dict[str, Any]] = {}
        all_edges: Dict[str, Dict[str, Any]] = {}  # key 用 (src, dst, relation) 去重
        root = None
        for pid in project_ids:
            data = get_project_graph(pid, dataset_id="", depth=3, max_nodes=max_nodes)
            for n in data.get("nodes") or []:
                all_nodes[n.get("entity_key")] = n
            for e in data.get("edges") or []:
                key = f"{e.get('src')}::{e.get('dst')}::{e.get('relation_type')}"
                all_edges[key] = e
            if data.get("root") and not root:
                root = data["root"]

        if not all_nodes:
            # KB 没有挂到任何项目时，至少直接查 KgEntity
            from .models import KgEdge, KgEntity
            ents = list(KgEntity.objects.filter(dataset_id=dataset_id).order_by("-updated_at")[:max_nodes])
            for n in ents:
                all_nodes[n.entity_key] = {
                    "entity_key": n.entity_key,
                    "entity_type": n.entity_type,
                    "label": n.label,
                    "ref_app": n.ref_app,
                    "ref_id": n.ref_id,
                    "dataset_id": n.dataset_id,
                    "project_id": n.project_id,
                    "properties": n.properties or {},
                    "created_at": n.created_at,
                    "updated_at": n.updated_at,
                }
                if not root:
                    root = all_nodes[n.entity_key]
            if all_nodes:
                pk_set = {e.pk for e in KgEntity.objects.filter(dataset_id=dataset_id)}
                edge_qs = KgEdge.objects.filter(
                    Q(src_id__in=pk_set) | Q(dst_id__in=pk_set)
                ).select_related("src", "dst")[: max_nodes * 3]
                for e in edge_qs:
                    all_edges[e.pk] = {
                        "id": e.pk,
                        "src": e.src.entity_key,
                        "dst": e.dst.entity_key,
                        "relation_type": e.relation_type,
                        "project_id": e.project_id,
                        "dataset_id": e.dataset_id,
                        "confidence_level": e.confidence_level,
                    }

        return Response({
            "root": root,
            "nodes": list(all_nodes.values()),
            "edges": list(all_edges.values()),
            "kb_id": kb_id,
            "kb_name": kb.name,
            "dataset_id": dataset_id,
            "project_ids": sorted(project_ids),
        })

    @action(detail=False, methods=["get"], url_path="coverage-report")
    def coverage_report(self, request):
        """项目覆盖度：用例 covers 需求/功能，及 maps_to 映射缺口。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        raw_project_id = request.query_params.get("project_id")
        if raw_project_id in (None, ""):
            return Response({"detail": "请提供 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project_id = int(raw_project_id)
        except (TypeError, ValueError):
            return Response({"detail": "无效的 project_id"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            limit = int(request.query_params.get("limit", 100))
        except (TypeError, ValueError):
            limit = 100

        data = get_project_coverage_report(project_id, limit=limit)
        if data.get("detail") and not data.get("summary", {}).get("test_case_count") and not data.get(
            "summary", {}
        ).get("generation_task_count"):
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="neighbors")
    def neighbors(self, request):
        entity_key = (request.query_params.get("entity") or "").strip()
        if not entity_key:
            return Response({"detail": "请提供 entity 参数"}, status=status.HTTP_400_BAD_REQUEST)
        direction = request.query_params.get("direction", "both")
        dataset_id = (request.query_params.get("dataset_id") or "").strip()
        return Response(get_entity_neighbors(entity_key, direction=direction, dataset_id=dataset_id))

    @action(detail=False, methods=["get"], url_path="impact")
    def impact(self, request):
        dataset_id = (request.query_params.get("dataset_id") or "").strip()
        document_id = (request.query_params.get("document_id") or "").strip()
        if not dataset_id or not document_id:
            return Response(
                {"detail": "请提供 dataset_id 与 document_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        items = impact_test_cases_for_kb_document(dataset_id, document_id)
        return Response({"impacts": items, "count": len(items)})

    @action(detail=False, methods=["get"], url_path="expand-refs")
    def expand_refs(self, request):
        """预览图谱扩展后的功能模块与 KB 文档集合（混合检索）。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        dataset_id = (request.query_params.get("dataset_id") or "").strip()
        if not dataset_id:
            return Response({"detail": "请提供 dataset_id"}, status=status.HTTP_400_BAD_REQUEST)

        function_ids = _parse_csv_ints(request.query_params.get("function_ids", ""))
        document_ids = _parse_csv_strings(request.query_params.get("document_ids", ""))
        if not function_ids and not document_ids:
            return Response(
                {"detail": "请提供 function_ids 或 document_ids"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            max_depth = int(request.query_params.get("depth", 2))
        except (TypeError, ValueError):
            max_depth = 2

        data = expand_kb_references_via_graph(
            dataset_id=dataset_id,
            function_ids=function_ids,
            document_ids=document_ids,
            max_depth=max_depth,
        )
        prompt_summary = build_graph_relations_prompt_summary_for_selection(
            function_ids=data.get("function_ids") or function_ids,
            document_ids=data.get("document_ids") or document_ids,
            expansion_meta=data.get("meta") or {},
            graph_summary=data.get("graph_summary") or "",
            document_names=data.get("document_names") or {},
        )
        data["prompt_summary"] = prompt_summary
        data["prompt_summary_chars"] = len(prompt_summary)
        return Response(data)

    @action(detail=False, methods=["post"], url_path="suggest-edges")
    def suggest_edges(self, request):
        """建议 maps_to / covers 边（含 confidence，不写库）。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        payload = request.data if isinstance(request.data, dict) else {}
        relation_types = payload.get("relation_types")
        if isinstance(relation_types, str):
            relation_types = [part.strip() for part in relation_types.split(",") if part.strip()]

        try:
            min_confidence = float(payload.get("min_confidence", 0.5))
        except (TypeError, ValueError):
            min_confidence = 0.5
        try:
            limit = int(payload.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50

        data = suggest_kg_edges(
            business_requirement_ids=_parse_id_list(payload.get("business_requirement_ids")),
            kb_function_ids=_parse_id_list(payload.get("kb_function_ids")),
            test_case_ids=_parse_id_list(payload.get("test_case_ids")),
            dataset_id=str(payload.get("dataset_id") or "").strip(),
            relation_types=relation_types,
            min_confidence=min_confidence,
            use_ai=bool(payload.get("use_ai")),
            limit=limit,
        )
        if data.get("detail") and not data.get("suggestions"):
            return Response(data, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if bool(payload.get("persist")):
            persist_result = persist_kg_edge_suggestions(
                data.get("suggestions") or [],
                created_by=request.user,
                min_confidence=min_confidence,
            )
            data["persist"] = persist_result

        return Response(data)

    @action(detail=False, methods=["get", "post"], url_path="suggested-edges")
    def suggested_edges(self, request):
        """GET：待确认 AI 建议边；POST：持久化建议边（source=ai_suggested）。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if request.method == "GET":
            relation_type = (request.query_params.get("relation_type") or "").strip() or None
            try:
                limit = int(request.query_params.get("limit", 100))
            except (TypeError, ValueError):
                limit = 100
            return Response(list_pending_suggested_edges(relation_type=relation_type, limit=limit))

        payload = request.data if isinstance(request.data, dict) else {}
        suggestions = payload.get("suggestions")
        if not isinstance(suggestions, list) or not suggestions:
            return Response({"detail": "请提供 suggestions 数组"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            min_confidence = float(payload.get("min_confidence", 0.0))
        except (TypeError, ValueError):
            min_confidence = 0.0

        result = persist_kg_edge_suggestions(
            suggestions,
            created_by=request.user,
            min_confidence=min_confidence,
        )
        status_code = status.HTTP_201_CREATED if result["count"]["created"] else status.HTTP_200_OK
        return Response(result, status=status_code)

    @action(detail=False, methods=["post"], url_path="suggested-edges/confirm")
    def confirm_suggested_edges(self, request):
        """确认 AI 建议边（maps_to→manual，covers→system）。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        payload = request.data if isinstance(request.data, dict) else {}
        edge_ids = _parse_id_list(payload.get("edge_ids"))
        if not edge_ids:
            return Response({"detail": "请提供 edge_ids"}, status=status.HTTP_400_BAD_REQUEST)

        result = confirm_suggested_kg_edges(edge_ids, created_by=request.user)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="suggested-edges/reject")
    def reject_suggested_edges(self, request):
        """拒绝 AI 建议边（删除待确认记录）。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        payload = request.data if isinstance(request.data, dict) else {}
        edge_ids = _parse_id_list(payload.get("edge_ids"))
        if not edge_ids:
            return Response({"detail": "请提供 edge_ids"}, status=status.HTTP_400_BAD_REQUEST)

        result = reject_suggested_kg_edges(edge_ids)
        return Response(result)

    @action(detail=False, methods=["get", "post"], url_path="edges")
    def edges(self, request):
        """GET：列出实体关联边；POST：手动创建 maps_to / automates 边。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if request.method == "GET":
            entity_key = (request.query_params.get("entity") or "").strip()
            if not entity_key:
                return Response({"detail": "请提供 entity 参数"}, status=status.HTTP_400_BAD_REQUEST)
            direction = request.query_params.get("direction", "both")
            source = request.query_params.get("source", "manual")
            relation_type = (request.query_params.get("relation_type") or "").strip() or None
            try:
                limit = int(request.query_params.get("limit", 100))
            except (TypeError, ValueError):
                limit = 100
            data = list_kg_edges_for_entity(
                entity_key,
                direction=direction,
                source=source,
                relation_type=relation_type,
                limit=limit,
            )
            if data.get("entity") is None:
                return Response(data, status=status.HTTP_404_NOT_FOUND)
            return Response(data)

        payload = request.data if isinstance(request.data, dict) else {}
        src, dst, err = resolve_manual_edge_entities(payload)
        if err:
            return Response({"detail": err}, status=status.HTTP_400_BAD_REQUEST)

        relation_type = (payload.get("relation_type") or "maps_to").strip()
        project_id = payload.get("project_id")
        try:
            project_id = int(project_id) if project_id is not None else None
        except (TypeError, ValueError):
            project_id = None

        try:
            edge = create_manual_kg_edge(
                src=src,
                dst=dst,
                relation_type=relation_type,
                project_id=project_id,
                created_by=request.user,
                meta=payload.get("meta") if isinstance(payload.get("meta"), dict) else {},
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(edge_to_response(edge), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="sync-kb-functions")
    def sync_kb_functions(self, request):
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                project_id = None
        
        dataset_id = (request.data.get("dataset_id") or request.query_params.get("dataset_id") or "").strip()
        
        count = sync_all_kb_functions(dataset_id=dataset_id, project_id=project_id)
        return Response({"synced": count, "dataset_id": dataset_id})

    @action(detail=False, methods=["post"], url_path="sync-native-kbs")
    def sync_native_kbs(self, request):
        """将自建知识中枢（kb_hub.NativeKb + NativeKbDocument）同步为图谱节点。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                project_id = None
        status_filter = (request.data.get("status") or "").strip()
        count = sync_all_native_kbs(project_id=project_id, status=status_filter)
        return Response({"synced": count, "project_id": project_id, "status": status_filter})

    @action(detail=False, methods=["post"], url_path="sync-api-requests")
    def sync_api_requests(self, request):
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                project_id = None
        count = sync_all_api_requests(project_id=project_id)
        return Response({"synced": count, "project_id": project_id})

    @action(detail=False, methods=["post"], url_path="sync-ui-pages")
    def sync_ui_pages(self, request):
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                project_id = None
        count = sync_all_ui_pages(project_id=project_id)
        return Response({"synced": count, "project_id": project_id})

    @action(detail=False, methods=["post"], url_path="sync-requirements")
    def sync_requirements(self, request):
        """将项目的业务需求(及需求文档)同步为图谱节点。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                project_id = None
        req_count = sync_all_business_requirements(project_id=project_id)
        doc_count = sync_all_requirement_documents(project_id=project_id)
        return Response({
            "synced_requirements": req_count,
            "synced_documents": doc_count,
            "project_id": project_id,
        })

    @action(detail=False, methods=["post"], url_path="sync-testcases")
    def sync_testcases(self, request):
        """将项目的测试用例同步为图谱节点，并自动建立 covers 覆盖边。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                project_id = None
        synced = sync_all_test_cases(project_id=project_id)
        auto_cover = bool(request.data.get("auto_cover", True))
        cover_result = auto_cover_test_cases(project_id=project_id) if auto_cover else None
        payload = {"synced_test_cases": synced, "project_id": project_id}
        if cover_result is not None:
            payload["auto_cover"] = cover_result
        return Response(payload)

    @action(detail=False, methods=["post"], url_path="sync-generation-tasks")
    def sync_generation_tasks(self, request):
        """将项目的 AI 生成任务同步为图谱节点(溯源边)。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                project_id = None
        count = sync_all_generation_tasks(project_id=project_id)
        return Response({"synced": count, "project_id": project_id})

    @action(detail=False, methods=["post"], url_path="auto-cover")
    def auto_cover(self, request):
        """为已同步的测试用例自动建立 covers 覆盖边。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                project_id = None
        result = auto_cover_test_cases(project_id=project_id)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="extract-function-points-from-requirements")
    def extract_function_points_from_requirements(self, request):
        """层次3(补全)：直接对项目的业务需求调 LLM 抽取功能点写入图谱（不依赖 Dify）。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id") or request.query_params.get("project_id")
        if project_id is not None:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                project_id = None
        result = extract_function_points_from_requirements(project_id=project_id)
        if result.get("detail") and not result.get("points_extracted"):
            return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="extract-function-points")
    def extract_function_points(self, request):
        """层次3：AI 内容理解 —— 拉取文档正文，LLM 抽取功能点写入图谱。

        POST body:
            dify_config_id: 必填，Dify 配置 ID
            dataset_id: 必填，知识库 ID
            document_ids: 可选，指定文档 ID 列表（不传则处理全部）
            project_id: 可选
        """
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        dataset_id = (request.data.get("dataset_id") or "").strip()
        if not dataset_id:
            return Response({"detail": "请提供 dataset_id"}, status=status.HTTP_400_BAD_REQUEST)

        dify_config_id = request.data.get("dify_config_id")
        try:
            dify_config_id = int(dify_config_id) if dify_config_id is not None else None
        except (TypeError, ValueError):
            dify_config_id = None
        if not dify_config_id:
            return Response({"detail": "请提供 dify_config_id"}, status=status.HTTP_400_BAD_REQUEST)

        document_ids = request.data.get("document_ids")
        if document_ids and not isinstance(document_ids, list):
            document_ids = [str(document_ids)]

        project_id = request.data.get("project_id")
        try:
            project_id = int(project_id) if project_id is not None else None
        except (TypeError, ValueError):
            project_id = None

        result = extract_and_sync_function_points(
            dataset_id,
            dify_config_id=dify_config_id,
            document_ids=document_ids,
            project_id=project_id,
        )
        if result.get("detail") and not result.get("documents_processed"):
            return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="cross-doc-relations")
    def cross_doc_relations(self, request):
        """层次3：跨文档功能点语义匹配 → 生成 similar_to / depends_on 边。

        POST body:
            dify_config_id: 必填，Dify 配置 ID
            dataset_id: 必填
            min_confidence: 可选，默认 0.6
            persist: 可选，是否直接写入图谱（默认 true）
            project_id: 可选
        """
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        dataset_id = (request.data.get("dataset_id") or "").strip()
        if not dataset_id:
            return Response({"detail": "请提供 dataset_id"}, status=status.HTTP_400_BAD_REQUEST)

        dify_config_id = request.data.get("dify_config_id")
        try:
            dify_config_id = int(dify_config_id) if dify_config_id is not None else None
        except (TypeError, ValueError):
            dify_config_id = None
        if not dify_config_id:
            return Response({"detail": "请提供 dify_config_id"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            min_confidence = float(request.data.get("min_confidence", 0.6))
        except (TypeError, ValueError):
            min_confidence = 0.6

        persist = request.data.get("persist", True)
        if isinstance(persist, str):
            persist = persist.lower() in ("true", "1", "yes")

        project_id = request.data.get("project_id")
        try:
            project_id = int(project_id) if project_id is not None else None
        except (TypeError, ValueError):
            project_id = None

        result = extract_and_sync_cross_doc_relations(
            dataset_id,
            project_id=project_id,
            min_confidence=min_confidence,
            persist=persist,
            created_by=request.user,
        )
        if result.get("detail") and not result.get("suggestions"):
            return Response(result, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="parse-code")
    def parse_code(self, request):
        """层次4：本地代码解析 —— 用 tree-sitter 把目录代码结构入谱（零 LLM 成本）。

        POST body:
            path: 待解析目录（容器可读路径，如 /app）
            project_id: 可选
            max_files: 可选，默认 200
        """
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        path = (request.data.get("path") or "").strip()
        if not path:
            return Response({"detail": "请提供 path（待解析目录）"}, status=status.HTTP_400_BAD_REQUEST)
        project_id = request.data.get("project_id")
        try:
            project_id = int(project_id) if project_id is not None else None
        except (TypeError, ValueError):
            project_id = None
        try:
            max_files = int(request.data.get("max_files", 200))
        except (TypeError, ValueError):
            max_files = 200
        from .code_parser import parse_directory

        result = parse_directory(path, project_id=project_id, max_files=max_files)
        if result.get("detail") and not result.get("files_parsed"):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="cluster")
    def cluster(self, request):
        """层次5：图聚类 —— Louvain 社区发现，community_id 写回实体。

        POST body:
            project_id: 可选
            resolution: 可选，默认 1.0
        """
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        project_id = request.data.get("project_id")
        try:
            project_id = int(project_id) if project_id is not None else None
        except (TypeError, ValueError):
            project_id = None
        try:
            resolution = float(request.data.get("resolution", 1.0))
        except (TypeError, ValueError):
            resolution = 1.0
        from .clustering import cluster_graph

        data = cluster_graph(project_id=project_id, resolution=resolution)
        if data.get("detail") and not data.get("communities"):
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    @action(detail=False, methods=["post"], url_path="recommend-execution")
    def recommend_execution(self, request):
        """基于知识图谱的 AI 推荐执行：分析覆盖缺口和执行历史，推荐下一步测试目标。

        POST body:
            project_id: 必填
        """
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        project_id = request.data.get("project_id")
        if project_id is None:
            return Response({"detail": "请提供 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            project_id = int(project_id)
        except (TypeError, ValueError):
            return Response({"detail": "无效的 project_id"}, status=status.HTTP_400_BAD_REQUEST)

        from .recommend import recommend_execution as do_recommend

        data = do_recommend(project_id)
        if data.get("detail") and not data.get("recommendations"):
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    @action(detail=False, methods=["get"], url_path="export")
    def export_graph(self, request):
        """导出图谱：json（默认）/ mermaid / svg / html。"""
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        project_id = request.query_params.get("project_id")
        parsed_project_id = None
        if project_id not in (None, ""):
            try:
                parsed_project_id = int(project_id)
            except (TypeError, ValueError):
                return Response({"detail": "无效的项目 ID"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            max_nodes = int(request.query_params.get("max_nodes", 5000))
        except (TypeError, ValueError):
            max_nodes = 5000
        try:
            max_edges = int(request.query_params.get("max_edges", 10000))
        except (TypeError, ValueError):
            max_edges = 10000

        fmt = (request.query_params.get("export_format") or "json").lower()
        data = export_kg_graph(
            project_id=parsed_project_id,
            max_nodes=max_nodes,
            max_edges=max_edges,
        )
        if fmt == "json":
            if data.get("detail") and not data.get("nodes"):
                return Response(data, status=status.HTTP_404_NOT_FOUND)
            return Response(data)
        if fmt == "mermaid":
            text = export_kg_mermaid(parsed_project_id, max_nodes, max_edges)
            return HttpResponse(text, content_type="text/plain; charset=utf-8")
        if fmt == "svg":
            text = export_kg_svg(parsed_project_id, max_nodes, max_edges)
            return HttpResponse(text, content_type="image/svg+xml; charset=utf-8")
        if fmt == "html":
            text = export_kg_html(parsed_project_id, max_nodes, max_edges)
            return HttpResponse(text, content_type="text/html; charset=utf-8")
        return Response({"detail": f"不支持的格式: {fmt}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="mcp")
    def mcp(self, request):
        """MCP (Model Context Protocol) 端点 —— 让外部 AI Agent 通过 JSON-RPC 查询图谱。

        支持 initialize / tools/list / tools/call。
        tools: query_subgraph(entity, depth) / get_neighbors(entity, direction) / list_projects()
        """
        if not kg_enabled():
            return Response({"detail": "知识图谱已禁用"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        from .mcp_server import handle_mcp_request

        payload = request.data if isinstance(request.data, dict) else {}
        result = handle_mcp_request(payload)
        rpc_id = payload.get("id")
        if rpc_id is not None:
            result["id"] = rpc_id
        result["jsonrpc"] = "2.0"
        return Response(result)


class KnowledgeGraphStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        enabled = kg_enabled()
        entity = None
        entity_key = (request.query_params.get("entity") or "").strip()
        if entity_key:
            ent = get_entity(entity_key)
            entity = ent.entity_key if ent else None
        return Response(
            {
                "enabled": enabled,
                "entity_exists": bool(entity),
                "rollback_hint": "切换回 main 分支或设置 KNOWLEDGE_GRAPH_ENABLED=false",
            }
        )


# ============================================================================
# 项目概览（配置中心 /configuration/project-overview）
# 按 project_id 聚合 8 大维度的统计指标，供前端 dashboard 一次渲染。
# 所有子聚合用 try/except 包裹，单点失败不影响整体返回。
# 2026-07-24 新增。
# ============================================================================
from django.db.models import Count  # noqa: E402


class ProjectOverviewView(APIView):
    """GET /api/kg/project-overview/?project_id=X
    一次性返回项目维度的聚合数据：
    - project               项目基本信息
    - knowledge_hub         知识库/文档/绑定/外部数据源
    - retrieval_pipeline    检索链路 5 步配置状态
    - test_types            按测试类型 5 桶独立统计：
        · functional_test       功能测试（需求/用例/生成任务/覆盖率）
        · api_automation        接口自动化（脚本/集合/套件/执行通过率）
        · ui_automation         UI 自动化（页面/脚本/套件/执行通过率）
        · app_automation        APP 自动化（包/套件/用例/执行通过率）
        · performance_evaluation 性能 + 评测（脚本/执行/AI 报告/评测均分）
    - knowledge_graph       图谱节点/边/类型分布（覆盖率供功能测试复用）
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get("project_id")
        if not project_id:
            return Response({"detail": "project_id required"}, status=400)
        try:
            project_id = int(project_id)
        except (TypeError, ValueError):
            return Response({"detail": "project_id must be integer"}, status=400)

        # ---------- 1. 项目基本信息 ----------
        try:
            from apps.projects.models import Project
            project = Project.objects.get(id=project_id)
            project_info = {
                "id": project.id,
                "name": project.name,
                "description": getattr(project, "description", "") or "",
                "code": getattr(project, "code", "") or "",
            }
        except Exception:
            return Response({"detail": "project not found"}, status=404)

        # ---------- 2. 知识中枢统计 ----------
        knowledge_hub = self._agg_knowledge_hub(project_id)

        # ---------- 3. 检索链路配置状态 ----------
        retrieval_pipeline = self._agg_retrieval_pipeline()

        # ---------- 4. 知识图谱（先聚合，供功能测试复用 coverage_pct） ----------
        knowledge_graph_data = self._agg_knowledge_graph(project_id)

        # ---------- 5. 测试类型独立聚合（含 AI 智能模式） ----------
        test_types = {
            "functional_test": self._agg_functional_test(project_id, knowledge_graph_data),
            "api_automation": self._agg_api_automation(project_id, project_info.get("name")),
            "ui_automation": self._agg_ui_automation(project_id, project_info.get("name")),
            "app_automation": self._agg_app_automation(project_id, project_info.get("name")),
            "performance": self._agg_performance(project_id),
            "review": self._agg_review(project_id),
            "ai_smart": self._agg_ai_smart(project_id),
        }

        # 拼装返回值
        return Response({
            "project": project_info,
            "knowledge_hub": knowledge_hub,
            "retrieval_pipeline": retrieval_pipeline,
            "test_types": test_types,
            "knowledge_graph": knowledge_graph_data,
        })

    # ------------------------------------------------------------------
    # 各区块聚合方法（每个方法独立 try/except，失败返回空 dict / 0）
    # ------------------------------------------------------------------
    def _agg_knowledge_hub(self, project_id):
        try:
            from apps.requirement_analysis.kb_hub.models import (
                NativeKb, NativeKbDocument, NativeKbChunk, KbSource,
                ProjectKbBinding, DocumentProjectBinding, ProjectDifyKbBinding,
            )
            own_kb_ids = list(NativeKb.objects.filter(project_id=project_id).values_list("id", flat=True))
            shared_kb_ids = list(ProjectKbBinding.objects.filter(project_id=project_id).values_list("kb_id", flat=True))
            kb_ids = list(set(own_kb_ids + shared_kb_ids))
            kb_total = len(kb_ids)
            kb_published = NativeKb.objects.filter(id__in=kb_ids, status="published").count() if kb_ids else 0
            kb_draft = max(0, kb_total - kb_published)
            docs_qs = NativeKbDocument.objects.filter(kb_id__in=kb_ids) if kb_ids else NativeKbDocument.objects.none()
            doc_total = docs_qs.count()
            doc_parsed = docs_qs.filter(status="parsed").count() if kb_ids else 0
            chunk_total = NativeKbChunk.objects.filter(document__kb_id__in=kb_ids).count() if kb_ids else 0
            source_total = KbSource.objects.filter(target_kb_id__in=kb_ids).count() if kb_ids else 0
            return {
                "kb_total": kb_total,
                "kb_published": kb_published,
                "kb_draft": kb_draft,
                "doc_total": doc_total,
                "doc_parsed": doc_parsed,
                "chunk_total": chunk_total,
                "source_total": source_total,
                "kb_bindings": ProjectKbBinding.objects.filter(project_id=project_id).count(),
                "doc_bindings": DocumentProjectBinding.objects.filter(project_id=project_id).count(),
                "dify_bindings": ProjectDifyKbBinding.objects.filter(project_id=project_id).count(),
                "pending_review": 0,
                "published_card": 0,
            }
        except Exception as e:
            logger.warning("knowledge_hub 聚合失败: %s", e)
            return {}

    def _agg_retrieval_pipeline(self):
        try:
            from apps.requirement_analysis.kb_hub.models import KnowledgeHubConfig
            cfg = KnowledgeHubConfig.get_active()
            return {
                "embedding": bool(getattr(cfg, "embedding_api_url", "") and getattr(cfg, "embedding_api_key", "")),
                "rerank": bool(getattr(cfg, "rerank_api_url", "") and getattr(cfg, "rerank_api_key", "")),
                "recall": True,
                "acl": True,
                "context": True,
            }
        except Exception as e:
            logger.warning("retrieval_pipeline 聚合失败: %s", e)
            return {"embedding": False, "rerank": False, "recall": False, "acl": False, "context": False}

    # ---------- 5.1 功能测试 ----------
    def _agg_functional_test(self, project_id, kg_data):
        """功能测试：通过率基于 TestRunCase（实际执行历史）计算。
        注意：TestCase.status 只有 draft/active/deprecated，**不算"通过"**。
        "用例通过"应在 apps.executions.TestRunCase.status='passed' 中统计。
        """
        out = {
            "requirement_documents": 0,
            "business_requirements": 0,
            "testcases": 0,
            "testcases_executed": 0,
            "testcases_passed": 0,
            "testcases_failed": 0,
            "pass_rate": 0,
            "generation_tasks": 0,
            "generation_tasks_done": 0,
            "generation_pass_rate": 0,
            "coverage_pct": kg_data.get("coverage_pct", 0) if kg_data else 0,
        }
        try:
            from apps.requirement_analysis.models import (
                RequirementDocument, BusinessRequirement, TestCaseGenerationTask,
            )
            out["requirement_documents"] = RequirementDocument.objects.filter(project_id=project_id).count()
            out["business_requirements"] = BusinessRequirement.objects.filter(
                analysis__document__project_id=project_id
            ).count()
            gen_total = TestCaseGenerationTask.objects.filter(project_id=project_id).count()
            gen_done = TestCaseGenerationTask.objects.filter(
                project_id=project_id, status="completed"
            ).count()
            out["generation_tasks"] = gen_total
            out["generation_tasks_done"] = gen_done
            out["generation_pass_rate"] = round(gen_done / gen_total * 100, 1) if gen_total > 0 else None
        except Exception as e:
            logger.warning("functional_test 需求部分聚合失败: %s", e)
        try:
            from apps.testcases.models import TestCase
            from apps.executions.models import TestRun, TestRunCase
            out["testcases"] = TestCase.objects.filter(project_id=project_id).count()
            # 通过率：取该项目所有 TestRun 下的 TestRunCase 状态
            run_ids = list(TestRun.objects.filter(project_id=project_id).values_list("id", flat=True))
            if run_ids:
                rc_qs = TestRunCase.objects.filter(test_run_id__in=run_ids)
                executed = rc_qs.exclude(status__in=["untested"]).count()
                passed = rc_qs.filter(status="passed").count()
                failed = rc_qs.filter(status="failed").count()
                out["testcases_executed"] = executed
                out["testcases_passed"] = passed
                out["testcases_failed"] = failed
                out["pass_rate"] = round(passed / executed * 100, 1) if executed > 0 else None
        except Exception as e:
            logger.warning("functional_test 用例执行聚合失败: %s", e)
        return out

    # ---------- 5.2 接口自动化 ----------
    def _agg_api_automation(self, project_id, project_name=None):
        out = {
            "api_requests": 0,
            "api_collections": 0,
            "api_test_suites": 0,
            "executions_total": 0,
            "executions_passed": 0,
            "pass_rate": 0,
            "last_execution": None,
        }
        try:
            from apps.api_testing.models import (
                ApiProject, ApiRequest, ApiCollection,
                TestSuite as ApiTestSuite, TestExecution as ApiTestExecution,
            )
            from django.db.models import Q
            # 子项目先按主项目 FK 关联；兜底按 name 匹配（兼容历史数据未填 FK 的情况）
            sub_ids = list(ApiProject.objects.filter(project_id=project_id).values_list("id", flat=True))
            if not sub_ids and project_name:
                sub_ids = list(ApiProject.objects.filter(name=project_name).values_list("id", flat=True))
            if not sub_ids:
                return out
            out["api_requests"] = ApiRequest.objects.filter(
                Q(projects__id__in=sub_ids) | Q(project_id__in=sub_ids)
            ).distinct().count()
            out["api_collections"] = ApiCollection.objects.filter(project_id__in=sub_ids).count()
            out["api_test_suites"] = ApiTestSuite.objects.filter(project_id__in=sub_ids).count()
            exec_qs = ApiTestExecution.objects.filter(test_suite__project_id__in=sub_ids)
            total = exec_qs.count()
            passed = exec_qs.filter(status="COMPLETED").count()
            out["executions_total"] = total
            out["executions_passed"] = passed
            out["pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0
            last = exec_qs.order_by("-created_at").values("id", "created_at", "status").first()
            if last and last.get("created_at"):
                last["created_at"] = last["created_at"].isoformat()
            out["last_execution"] = last
        except Exception as e:
            logger.debug("api_automation 聚合失败: %s", e)
        return out

    # ---------- 5.3 UI 自动化 ----------
    def _agg_ui_automation(self, project_id, project_name=None):
        out = {
            "ui_pages": 0,
            "ui_scripts": 0,
            "ui_test_suites": 0,
            "executions_total": 0,
            "executions_passed": 0,
            "pass_rate": 0,
            "last_execution": None,
        }
        try:
            from apps.ui_automation.models import (
                UiProject, PageObject, TestScript as UiTestScript,
                TestSuite as UiTestSuite, TestExecution as UiTestExecution,
            )
            sub_ids = list(UiProject.objects.filter(project_id=project_id).values_list("id", flat=True))
            if not sub_ids and project_name:
                sub_ids = list(UiProject.objects.filter(name=project_name).values_list("id", flat=True))
            if not sub_ids:
                return out
            out["ui_pages"] = PageObject.objects.filter(project_id__in=sub_ids).count()
            out["ui_scripts"] = UiTestScript.objects.filter(project_id__in=sub_ids).count()
            out["ui_test_suites"] = UiTestSuite.objects.filter(project_id__in=sub_ids).count()
            exec_qs = UiTestExecution.objects.filter(project_id__in=sub_ids)
            total = exec_qs.count()
            passed = exec_qs.filter(status="SUCCESS").count()
            out["executions_total"] = total
            out["executions_passed"] = passed
            out["pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0
            last = exec_qs.order_by("-created_at").values("id", "created_at", "status").first()
            if last and last.get("created_at"):
                last["created_at"] = last["created_at"].isoformat()
            out["last_execution"] = last
        except Exception as e:
            logger.debug("ui_automation 聚合失败: %s", e)
        return out

    # ---------- 5.4 APP 自动化 ----------
    def _agg_app_automation(self, project_id, project_name=None):
        out = {
            "app_packages": 0,
            "app_test_suites": 0,
            "app_test_cases": 0,
            "executions_total": 0,
            "executions_passed": 0,
            "pass_rate": 0,
            "last_execution": None,
        }
        try:
            from apps.app_automation.models import (
                AppProject, AppPackage, AppTestSuite, AppTestCase, AppTestExecution,
            )
            sub_ids = list(AppProject.objects.filter(project_id=project_id).values_list("id", flat=True))
            if not sub_ids and project_name:
                sub_ids = list(AppProject.objects.filter(name=project_name).values_list("id", flat=True))
            if not sub_ids:
                return out
            out["app_packages"] = AppPackage.objects.filter(project_id__in=sub_ids).count()
            out["app_test_suites"] = AppTestSuite.objects.filter(project_id__in=sub_ids).count()
            out["app_test_cases"] = AppTestCase.objects.filter(project_id__in=sub_ids).count()
            exec_qs = AppTestExecution.objects.filter(test_suite__project_id__in=sub_ids)
            total = exec_qs.count()
            passed = exec_qs.filter(result="PASSED").count()
            out["executions_total"] = total
            out["executions_passed"] = passed
            out["pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0
            last = exec_qs.order_by("-created_at").values("id", "created_at", "status", "result").first()
            if last and last.get("created_at"):
                last["created_at"] = last["created_at"].isoformat()
            out["last_execution"] = last
        except Exception as e:
            logger.debug("app_automation 聚合失败: %s", e)
        return out

    # ---------- 5.5 性能测试 ----------
    def _agg_performance(self, project_id):
        out = {
            "performance_scripts": 0,
            "performance_executions_total": 0,
            "performance_passed": 0,
            "performance_pass_rate": 0,
            "last_performance": None,
        }
        try:
            from apps.performance_testing.models import PerformanceScript, PerformanceExecution
            out["performance_scripts"] = PerformanceScript.objects.filter(project_id=project_id).count()
            pe_qs = PerformanceExecution.objects.filter(project_id=project_id)
            total = pe_qs.count()
            passed = pe_qs.filter(status="completed").count()
            out["performance_executions_total"] = total
            out["performance_passed"] = passed
            out["performance_pass_rate"] = round(passed / total * 100, 1) if total > 0 else 0
            last = pe_qs.order_by("-created_at").values(
                "id", "created_at", "status", "avg_response_time"
            ).first()
            if last and last.get("created_at"):
                last["created_at"] = last["created_at"].isoformat()
            out["last_performance"] = last
        except Exception as e:
            logger.debug("performance 聚合失败: %s", e)
        return out

    # ---------- 5.6 评审（含 checklist 通过率作为评分） ----------
    def _agg_review(self, project_id):
        """测试用例评审：apps.reviews.TestCaseReview
        评分 = checklist_results JSON 中 pass/total 的平均（替代缺失的 score 字段）。
        """
        out = {
            "review_total": 0,
            "review_approved": 0,
            "review_approval_rate": 0,
            "checklist_total": 0,
            "checklist_passed": 0,
            "checklist_pass_rate": 0,
            "avg_score": None,
            "last_review": None,
        }
        try:
            from apps.reviews.models import TestCaseReview, ReviewAssignment
            from apps.projects.models import ProjectMember

            # TestCaseReview.projects 是 M2M，先取该项目下的 review ids
            rev_ids = list(TestCaseReview.objects.filter(projects__id=project_id).values_list("id", flat=True))
            rev_qs = TestCaseReview.objects.filter(id__in=rev_ids) if rev_ids else TestCaseReview.objects.none()
            total = rev_qs.count()
            approved = rev_qs.filter(status="approved").count()
            out["review_total"] = total
            out["review_approved"] = approved
            out["review_approval_rate"] = round(approved / total * 100, 1) if total > 0 else 0

            # 真实评分：TestCaseReview.score 字段（0-100），无 score 时保持 None
            try:
                from django.db.models import Avg
                scored = rev_qs.exclude(score__isnull=True)
                avg = scored.aggregate(avg=Avg("score"))["avg"]
                out["avg_score"] = round(avg, 1) if avg is not None else None
            except Exception:
                out["avg_score"] = None

            # checklist 通过率：从 ReviewAssignment.checklist_results JSON 聚合
            assign_qs = ReviewAssignment.objects.filter(review_id__in=rev_ids) if rev_ids else ReviewAssignment.objects.none()
            assign_total = assign_qs.count()
            chk_total = 0
            chk_passed = 0
            for cr in assign_qs.values_list("checklist_results", flat=True):
                if not cr:
                    continue
                if isinstance(cr, str):
                    try:
                        import json
                        cr = json.loads(cr)
                    except Exception:
                        continue
                if isinstance(cr, dict):
                    for v in cr.values():
                        chk_total += 1
                        if v in (True, "pass", "passed", "yes", "1", 1):
                            chk_passed += 1
            out["checklist_total"] = chk_total
            out["checklist_passed"] = chk_passed
            out["checklist_pass_rate"] = round(chk_passed / chk_total * 100, 1) if chk_total > 0 else 0

            last = rev_qs.order_by("-created_at").values("id", "title", "status", "created_at", "priority").first()
            if last and last.get("created_at"):
                last["created_at"] = last["created_at"].isoformat()
            out["last_review"] = last
        except Exception as e:
            logger.debug("review 聚合失败: %s", e)
        return out

    # ---------- 5.7 AI 智能模式 ----------
    def _agg_ai_smart(self, project_id):
        """AI 智能模式 = AI 用例生成 + Dify 智能助手 + Hermes 数字人。
        助手/数字人无 project 字段，按项目成员 user 过滤。
        """
        out = {
            "generation_tasks": 0,
            "generation_tasks_done": 0,
            "generation_pass_rate": 0,
            "dify_sessions": 0,
            "dify_messages": 0,
            "hermes_conversations": 0,
            "hermes_messages": 0,
            "ai_total_active": 0,
        }
        # 5.7.1 AI 用例生成（已有 project_id）
        try:
            from apps.requirement_analysis.models import TestCaseGenerationTask
            qs = TestCaseGenerationTask.objects.filter(project_id=project_id)
            total = qs.count()
            done = qs.filter(status="completed").count()
            out["generation_tasks"] = total
            out["generation_tasks_done"] = done
            out["generation_pass_rate"] = round(done / total * 100, 1) if total > 0 else 0
        except Exception as e:
            logger.debug("ai_smart 用例生成聚合失败: %s", e)

        # 5.7.2 项目成员 user ids（助手/数字人无 project 字段）
        user_ids = None
        try:
            from apps.projects.models import ProjectMember
            user_ids = list(ProjectMember.objects.filter(project_id=project_id).values_list("user_id", flat=True))
        except Exception:
            user_ids = []

        # 5.7.3 Dify 智能助手（AssistantSession / ChatMessage）
        try:
            from apps.assistant.models import AssistantSession, ChatMessage
            if user_ids:
                ses_qs = AssistantSession.objects.filter(user_id__in=user_ids)
                out["dify_sessions"] = ses_qs.count()
                out["dify_messages"] = ChatMessage.objects.filter(session_id__in=ses_qs.values_list("id", flat=True)).count()
            else:
                out["dify_sessions"] = 0
                out["dify_messages"] = 0
        except Exception as e:
            logger.debug("ai_smart dify 聚合失败: %s", e)

        # 5.7.4 Hermes 数字人（HermesConversation / HermesMessage）
        try:
            from apps.assistant.models import HermesConversation, HermesMessage
            if user_ids:
                conv_qs = HermesConversation.objects.filter(user_id__in=user_ids)
                out["hermes_conversations"] = conv_qs.count()
                out["hermes_messages"] = HermesMessage.objects.filter(
                    conversation_id__in=conv_qs.values_list("id", flat=True)
                ).count()
            else:
                out["hermes_conversations"] = 0
                out["hermes_messages"] = 0
        except Exception as e:
            logger.debug("ai_smart hermes 聚合失败: %s", e)

        # 总活跃 = AI用例生成 + 助手会话 + 数字人会话
        out["ai_total_active"] = (
            out["generation_tasks"] + out["dify_sessions"] + out["hermes_conversations"]
        )
        return out

    def _agg_knowledge_graph(self, project_id):
        try:
            nodes = KgEntity.objects.filter(project_id=project_id)
            edges = KgEdge.objects.filter(project_id=project_id)
            node_total = nodes.count()
            edge_total = edges.count()
            node_by_type = list(nodes.values("entity_type").annotate(count=Count("id")).order_by("-count"))
            edge_by_type = list(edges.values("relation_type").annotate(count=Count("id")).order_by("-count"))
            # 社区数：KgEntity 没有 community_id 字段，社区信息存于 properties JSON 中，跳过聚合
            community_total = 0
            # 覆盖率：被 covers 边指向的 BusinessRequirement 占比
            biz_req_total = 0
            covered_req_total = 0
            try:
                from apps.requirement_analysis.models import BusinessRequirement
                biz_req_total = BusinessRequirement.objects.filter(project_id=project_id).count()
                covered_req_ids = set(edges.filter(relation_type="covers").values_list("dst", flat=True))
                # 这里 dst 可能是 entity_key，转成 entity_id 再去重
                if covered_req_ids:
                    covered_keys = KgEntity.objects.filter(
                        entity_key__in=covered_req_ids, entity_type="BusinessRequirement", project_id=project_id
                    ).values_list("entity_id", flat=True)
                    covered_req_total = len(set(covered_keys))
            except Exception:
                pass
            coverage_pct = round(covered_req_total / biz_req_total * 100, 1) if biz_req_total > 0 else 0
            return {
                "nodes": node_total,
                "edges": edge_total,
                "communities": community_total,
                "coverage_pct": coverage_pct,
                "node_by_type": node_by_type,
                "edge_by_type": edge_by_type,
            }
        except Exception as e:
            logger.warning("knowledge_graph 聚合失败: %s", e)
            return {"nodes": 0, "edges": 0, "communities": 0, "coverage_pct": 0, "node_by_type": [], "edge_by_type": []}
