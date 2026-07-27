# -*- coding: utf-8 -*-
"""
Native 知识中枢后端（自建）。

检索链路：query → Embedding → 全量余弦召回 → Rerank 精排 → 过滤 → 兼容 record
入库链路：文档 → 解析 → 分块 → Embedding → 落库
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .backend import KbBackend
from .embedding import call_embedding, call_rerank, cosine_similarity
from .parser import chunk_text, parse_file, parse_text, parse_uploaded_file

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 50
MAX_CONTEXT_CHARS = 48000


class NativeKbBackend(KbBackend):
    engine_name = "native"

    def __init__(self, config):
        self.config = config

    # ---------------- 检索 ----------------
    def _query_embedding(self, query: str) -> List[float]:
        vectors = call_embedding(
            [query],
            api_url=self.config.embedding_api_url,
            api_key=self.config.embedding_api_key,
            model_name=self.config.embedding_model_name,
        )
        return vectors[0] if vectors else []

    def _retrieve_chunks(
        self,
        query_vec: List[float],
        *,
        kb_id: Optional[str],
        document_ids: Optional[List[str]] = None,
        scope_mode: str = "full",
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """向量召回。返回候选 chunk 列表（含 score）。"""
        if not query_vec:
            return []
        from .models import NativeKbChunk

        qs = NativeKbChunk.objects.filter(enabled=True, embedding__isnull=False).exclude(
            embedding=[]
        ).select_related("document")
        if kb_id:
            qs = qs.filter(document__kb_id=kb_id)
        use_documents = scope_mode == "documents" and bool(document_ids)
        if use_documents:
            allowed = {str(x).strip() for x in document_ids if str(x).strip()}
            qs = qs.filter(document_id__in=[int(x) for x in allowed if x.isdigit()])

        candidates: List[Dict[str, Any]] = []
        for chunk in qs.iterator():
            emb = chunk.embedding or []
            if not emb or len(emb) != len(query_vec):
                continue
            score = cosine_similarity(query_vec, emb)
            candidates.append({
                "score": score,
                "content": chunk.content,
                "document_id": str(chunk.document_id),
                "document_name": chunk.document.title,
                "chunk_index": chunk.chunk_index,
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[: max(MAX_CANDIDATES, top_k * 4)]

    def _rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        *,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        if not (self.config.rerank_api_url or "").strip():
            # 未配置 rerank，直接用向量分
            return candidates[:top_k]
        docs = [c["content"] for c in candidates]
        ranked = call_rerank(
            query, docs,
            api_url=self.config.rerank_api_url,
            api_key=self.config.rerank_api_key,
            model_name=self.config.rerank_model_name,
            top_n=top_k,
        )
        out: List[Dict[str, Any]] = []
        for idx, r_score in ranked[:top_k]:
            c = candidates[idx]
            # 向量分与重排分融合
            c["score"] = round(float(r_score if r_score > 0 else c["score"]), 4)
            out.append(c)
        return out

    def _to_records(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            self.normalize_record(
                content=c["content"], doc_id=c["document_id"], doc_name=c["document_name"], score=c["score"]
            )
            for c in candidates
        ]

    def retrieve_for_chat(
        self,
        query: str,
        *,
        top_k: int = 5,
        document_ids: Optional[List[str]] = None,
        scope_mode: str = "full",
        kb_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        top_k = max(1, min(int(top_k or self.config.top_k or 5), 20))
        query_vec = self._query_embedding(query)
        candidates = self._retrieve_chunks(
            query_vec, kb_id=kb_id, document_ids=document_ids,
            scope_mode=scope_mode, top_k=top_k,
        )
        ranked = self._rerank(query, candidates, top_k=top_k)
        ranked = [c for c in ranked if float(c["score"]) >= self.config.min_score]
        records = self._to_records(ranked)
        meta: Dict[str, Any] = {
            "engine": self.engine_name,
            "mode": "native_vector_rerank",
            "scope_mode": scope_mode,
            "query": (query or "")[:250],
            "top_k": top_k,
            "retrieval_count": len(records),
            "sources": self.build_sources(records),
            "warnings": [] if records else ["未在知识中枢中检索到相关内容"],
        }
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
    ) -> Tuple[str, Dict[str, Any]]:
        top_k = max(1, min(int(top_k or self.config.top_k or 5), 20))
        query = f"{(title or '').strip()}\n{(requirement_text or '').strip()}".strip()[:250] or "测试用例生成参考"
        records, meta = self.retrieve_for_chat(
            query, top_k=top_k, document_ids=document_ids,
            scope_mode=("documents" if document_ids else "full"), kb_id=kb_id,
        )
        context = self._format_generation_context(records, kb_name=kb_name)
        meta["engine"] = self.engine_name
        meta["reference_mode"] = reference_mode
        meta["total_chars"] = len(context)
        meta["sources"] = self.build_sources(records)
        return context, meta

    @staticmethod
    def _format_generation_context(records: List[Dict[str, Any]], *, kb_name: str = "") -> str:
        if not records:
            return ""
        lines = [f"【知识中枢检索补充：{kb_name or '知识库'}】"]
        lines.append(
            "以下内容为知识中枢检索到的相关片段（次要参考）。"
            "须以主需求为准，仅补充与主需求相关的业务规则与边界："
        )
        for idx, rec in enumerate(records, start=1):
            seg = rec.get("segment") or {}
            content = (seg.get("content") or "").strip()
            if not content:
                continue
            doc = seg.get("document") or {}
            doc_name = doc.get("name") or "未知文档"
            score = rec.get("score")
            suffix = f"（相关度 {score:.2f}）" if isinstance(score, (int, float)) else ""
            lines.append(f"\n[参考{idx}] 文档：{doc_name}{suffix}\n{content}")
        if len(lines) <= 2:
            return ""
        text = "\n".join(lines)
        return text[:MAX_CONTEXT_CHARS]

    # ---------------- 知识库/文档管理 ----------------
    def list_knowledge_bases(self, *, keyword: str = "") -> List[Dict[str, Any]]:
        from .models import NativeKb

        qs = NativeKb.objects.all()
        if keyword:
            qs = qs.filter(name__icontains=keyword)
        return [
            {
                "id": kb.pk,
                "name": kb.name,
                "description": kb.description,
                "status": kb.status,
                "document_count": kb.document_count,
                "chunk_count": kb.chunk_count,
            }
            for kb in qs
        ]

    def list_documents(self, kb_id: str, *, keyword: str = "") -> List[Dict[str, Any]]:
        from .models import NativeKbDocument

        qs = NativeKbDocument.objects.filter(kb_id=kb_id)
        if keyword:
            qs = qs.filter(title__icontains=keyword)
        return [
            {
                "id": doc.pk,
                "name": doc.title,
                "indexing_status": doc.status,
                "word_count": doc.word_count,
                "enabled": doc.status == "parsed",
                "source_type": doc.source_type,
            }
            for doc in qs
        ]

    # ---------------- 入库 ----------------
    def ingest_document(self, doc) -> Dict[str, Any]:
        """解析 + 分块 + Embedding 入库。返回统计信息。"""
        from .models import NativeKbChunk

        config = self.config
        try:
            doc.status = "pending"
            doc.save(update_fields=["status", "updated_at"])

            if doc.source_type == "text":
                content = parse_text(doc.content_text)
            elif doc.file:
                content = parse_uploaded_file(doc.file, parser_type=config.parser_type)
            else:
                content = parse_text(doc.content_text)

            if not content.strip():
                doc.status = "failed"
                doc.error_message = "解析后内容为空"
                doc.save(update_fields=["status", "error_message", "updated_at"])
                return {"ok": False, "error": "解析后内容为空"}

            doc.content_md = content
            doc.word_count = len(content)
            chunks = chunk_text(content, chunk_size=config.chunk_size, overlap=config.chunk_overlap)
            if not chunks:
                doc.status = "failed"
                doc.error_message = "分块结果为空"
                doc.save(update_fields=["status", "error_message", "content_md", "word_count", "updated_at"])
                return {"ok": False, "error": "分块结果为空"}

            # 清理旧分块
            NativeKbChunk.objects.filter(document=doc).delete()

            # 批量 embedding
            vectors = call_embedding(
                chunks,
                api_url=config.embedding_api_url,
                api_key=config.embedding_api_key,
                model_name=config.embedding_model_name,
            )

            chunk_objs = []
            for idx, (text, vec) in enumerate(zip(chunks, vectors)):
                chunk_objs.append(NativeKbChunk(
                    document=doc, chunk_index=idx, content=text,
                    embedding=vec or [], token_count=len(text), enabled=True,
                ))
            NativeKbChunk.objects.bulk_create(chunk_objs)

            doc.status = "parsed"
            doc.error_message = ""
            doc.save(update_fields=["status", "error_message", "content_md", "word_count", "updated_at"])
            return {"ok": True, "chunks": len(chunk_objs), "chars": len(content)}
        except Exception as exc:
            logger.exception("Native 文档入库失败 doc=%s: %s", doc.pk, exc)
            doc.status = "failed"
            doc.error_message = str(exc)[:1000]
            doc.save(update_fields=["status", "error_message", "updated_at"])
            return {"ok": False, "error": str(exc)}
