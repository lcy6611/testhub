# -*- coding: utf-8 -*-
"""Dify 知识库后端——包装现有 dify_kb_service，作为可切换的引擎之一。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .backend import KbBackend

logger = logging.getLogger(__name__)


class DifyKbBackend(KbBackend):
    engine_name = "dify"

    def __init__(self, dify_config, dataset_id: Optional[str] = None):
        self.dify_config = dify_config
        self.dataset_id = dataset_id

    def _ensure_config(self):
        if self.dify_config is None:
            raise ValueError("未找到可用的 Dify 配置，请先在配置中心添加并启用 Dify，或切换知识中枢引擎")
        return self.dify_config

    def _resolve_dataset(self, kb_id: Optional[str]) -> str:
        ds = (kb_id or self.dataset_id or "").strip()
        if not ds:
            raise ValueError("请先选择知识库")
        return ds

    def retrieve_for_chat(
        self,
        query: str,
        *,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
        scope_mode: str = "full",
        kb_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        from apps.requirement_analysis.dify_kb_service import retrieve_for_chat as _retrieve

        config = self._ensure_config()
        dataset_id = self._resolve_dataset(kb_id)
        records, meta = _retrieve(
            config, dataset_id, query,
            top_k=top_k, document_ids=document_ids, scope_mode=scope_mode,
        )
        meta.setdefault("engine", self.engine_name)
        return records, meta

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
        document_names: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        from apps.requirement_analysis.dify_kb_service import (
            build_kb_reference_context,
            format_retrieval_sources,
            list_dataset_documents,
            MIN_RELEVANCE_SCORE,
        )

        config = self._ensure_config()
        dataset_id = self._resolve_dataset(kb_id)

        document_names = dict(document_names or {})
        if not document_names:
            try:
                docs_payload = list_dataset_documents(config, dataset_id, page=1, limit=100)
                for item in docs_payload.get("data") or []:
                    if isinstance(item, dict) and item.get("id"):
                        document_names[str(item["id"])] = item.get("name") or str(item["id"])
            except Exception as exc:
                logger.warning("Dify 后端加载文档名称失败: %s", exc)

        context, meta = build_kb_reference_context(
            config, dataset_id,
            title=title, requirement_text=requirement_text,
            dataset_name=kb_name, document_ids=document_ids,
            document_names=document_names, function_ids=function_ids,
            reference_mode=reference_mode, top_k=top_k,
        )
        meta["engine"] = self.engine_name
        # 补充引用溯源 sources
        if "sources" not in meta:
            retrieval_records = meta.get("retrieval_records") or []
            sources = format_retrieval_sources(
                retrieval_records, document_names=document_names, min_score=MIN_RELEVANCE_SCORE
            ) if retrieval_records else []
            if not sources:
                sources = [
                    {
                        "document_id": d.get("document_id"),
                        "document_name": d.get("document_name"),
                        "score": None,
                        "snippet": "",
                    }
                    for d in meta.get("documents") or []
                ]
            meta["sources"] = sources
        return context, meta

    def list_knowledge_bases(self, *, keyword: str = "") -> List[Dict[str, Any]]:
        from apps.requirement_analysis.dify_kb_service import list_datasets

        config = self._ensure_config()
        payload = list_datasets(config, page=1, limit=100, keyword=keyword)
        return payload.get("data") or []

    def list_documents(self, kb_id: str, *, keyword: str = "") -> List[Dict[str, Any]]:
        from apps.requirement_analysis.dify_kb_service import list_dataset_documents

        config = self._ensure_config()
        payload = list_dataset_documents(config, kb_id, page=1, limit=100, keyword=keyword)
        return payload.get("data") or []
