# -*- coding: utf-8 -*-
"""
知识中枢后端抽象层 + 工厂。

统一收口两类调用入口：
  - retrieve_for_chat():          知识库对话检索
  - build_generation_context():   AI 生成用例时的参考上下文构建

工厂按 KnowledgeHubConfig.engine 在 Dify / Native 后端间切换。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .models import KnowledgeHubConfig

logger = logging.getLogger(__name__)


class KbBackend:
    """知识中枢后端抽象基类。"""

    engine_name = "base"

    def retrieve_for_chat(
        self,
        query: str,
        *,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
        scope_mode: str = "full",
        kb_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """知识库对话检索。返回 (records, meta)。"""
        raise NotImplementedError

    def build_generation_context(
        self,
        *,
        title: str,
        requirement_text: str,
        kb_name: str = "",
        document_ids: Optional[List[str]] = None,
        function_ids: Optional[List[int]] = None,
        reference_mode: str = "hybrid",
        top_k: int = 5,
        kb_id: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """构建生成用例的参考上下文。返回 (context_text, meta)。"""
        raise NotImplementedError

    def list_knowledge_bases(self, *, keyword: str = "") -> List[Dict[str, Any]]:
        """列出可用知识库。"""
        raise NotImplementedError

    def list_documents(self, kb_id: str, *, keyword: str = "") -> List[Dict[str, Any]]:
        """列出知识库内文档。"""
        raise NotImplementedError

    # ---- 通用工具 ----
    @staticmethod
    def normalize_record(
        *, content: str, doc_id: str, doc_name: str, score: float
    ) -> Dict[str, Any]:
        """统一 record 结构，兼容下游 dify_kb_service 的格式化函数。

        顶层同时提供 score / content / document_id / document_name，方便前端
        检索结果展示（el-alert title 用 document_name、body 用 content），
        保留 segment 嵌套以兼容现有 build_sources / format_retrieval_sources。
        """
        safe_doc_name = (doc_name or doc_id or "未知文档")[:500]
        return {
            "score": round(float(score), 4),
            "content": content or "",
            "document_id": doc_id or "",
            "document_name": safe_doc_name,
            "segment": {
                "content": content or "",
                "document": {"id": doc_id or "", "name": safe_doc_name},
            },
        }

    @staticmethod
    def build_sources(records: List[Dict[str, Any]], *, min_score: float = 0.0) -> List[Dict[str, Any]]:
        """从 records 整理引用来源（去重），供前端溯源展示。"""
        merged: Dict[str, Dict[str, Any]] = {}
        for rec in records or []:
            score = rec.get("score")
            if isinstance(score, (int, float)) and float(score) < min_score:
                continue
            seg = rec.get("segment") or {}
            doc = seg.get("document") or {}
            doc_id = str(doc.get("id") or "").strip()
            doc_name = (doc.get("name") or "").strip() or doc_id or "未知文档"
            content = (seg.get("content") or "").strip()
            key = doc_id or doc_name
            item = merged.get(key)
            if not item:
                merged[key] = {
                    "document_id": doc_id or None,
                    "document_name": doc_name,
                    "score": score,
                    "snippet": content[:200] if content else "",
                }
                continue
            if isinstance(score, (int, float)) and (
                not isinstance(item.get("score"), (int, float)) or score > item["score"]
            ):
                item["score"] = score
            if content and len(content) > len(item.get("snippet") or ""):
                item["snippet"] = content[:200]
        result = list(merged.values())
        result.sort(
            key=lambda x: x.get("score") if isinstance(x.get("score"), (int, float)) else -1,
            reverse=True,
        )
        return result


class KbBackendFactory:
    """按配置返回知识中枢后端。"""

    @staticmethod
    def get_backend(config: Optional[KnowledgeHubConfig] = None) -> KbBackend:
        if config is None:
            config = KnowledgeHubConfig.get_active()

        if config is None or config.engine == "dify":
            from .dify_backend import DifyKbBackend

            dify_cfg = None
            if config and config.dify_config_id:
                from apps.assistant.models import DifyConfig

                dify_cfg = DifyConfig.objects.filter(pk=config.dify_config_id).first()
            if dify_cfg is None:
                from apps.assistant.models import DifyConfig

                dify_cfg = DifyConfig.objects.filter(is_active=True).order_by("-updated_at").first()
            return DifyKbBackend(dify_cfg)

        # native
        from .native_backend import NativeKbBackend

        return NativeKbBackend(config)

    @staticmethod
    def get_engine() -> str:
        config = KnowledgeHubConfig.get_active()
        if config is None:
            return "dify"
        return config.engine

    @staticmethod
    def get_source_backend(kb_source):
        """返回外部知识源（飞书等）对应的适配器实例，用于检索或触发同步。"""
        from .adapters import get_adapter

        return get_adapter(kb_source)
