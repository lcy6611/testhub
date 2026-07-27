# -*- coding: utf-8 -*-
"""
Embedding / Rerank 客户端。

支持 OpenAI 兼容的 /embeddings 接口（如硅基流动 Qwen3-Embedding-8B）
与 /rerank 接口（如 Qwen3-Reranker-8B / bge-reranker）。
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

EMBED_TIMEOUT = 60
RERANK_TIMEOUT = 30
MAX_EMBED_BATCH = 32


def _normalize_base_url(url: str, suffix: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith(suffix):
        return url
    if url.endswith("/v1"):
        return f"{url}{suffix}"
    if "/v1/" in url:
        return f"{url.split('/v1/')[0]}/v1{suffix}"
    return f"{url}/v1{suffix}"


def call_embedding(
    texts: List[str],
    *,
    api_url: str,
    api_key: str,
    model_name: str,
) -> List[List[float]]:
    """批量获取向量。返回与 texts 等长的向量列表。"""
    if not texts:
        return []
    api_url = (api_url or "").strip()
    if not api_url:
        raise ValueError("未配置 Embedding API 地址")
    url = _normalize_base_url(api_url, "/embeddings")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    vectors: List[List[float]] = []
    for i in range(0, len(texts), MAX_EMBED_BATCH):
        batch = texts[i : i + MAX_EMBED_BATCH]
        body = {"model": model_name, "input": batch}
        resp = requests.post(url, headers=headers, json=body, timeout=EMBED_TIMEOUT)
        if not resp.ok:
            raise ValueError(f"Embedding 调用失败 ({resp.status_code}): {resp.text[:300]}")
        data = resp.json().get("data") or []
        data.sort(key=lambda x: x.get("index", 0))
        for item in data:
            vectors.append(item.get("embedding") or [])
    return vectors


def call_rerank(
    query: str,
    documents: List[str],
    *,
    api_url: str,
    api_key: str,
    model_name: str,
    top_n: Optional[int] = None,
) -> List[Tuple[int, float]]:
    """重排。返回 [(原索引, 分数), ...] 按分数降序。"""
    if not documents:
        return []
    api_url = (api_url or "").strip()
    if not api_url:
        # 未配置 rerank，直接返回原序（分数 0）
        return [(i, 0.0) for i in range(len(documents))]
    url = _normalize_base_url(api_url, "/rerank")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: Dict[str, Any] = {
        "model": model_name,
        "query": query,
        "documents": documents,
    }
    if top_n:
        body["top_n"] = top_n
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=RERANK_TIMEOUT)
        if not resp.ok:
            logger.warning("Rerank 调用失败 (%s): %s，跳过重排", resp.status_code, resp.text[:300])
            return [(i, 0.0) for i in range(len(documents))]
        results = resp.json().get("results") or []
        out: List[Tuple[int, float]] = []
        for item in results:
            idx = item.get("index")
            score = float(item.get("relevance_score") or item.get("score") or 0.0)
            if isinstance(idx, int):
                out.append((idx, score))
        out.sort(key=lambda x: x[1], reverse=True)
        return out
    except Exception as exc:
        logger.warning("Rerank 异常，跳过重排: %s", exc)
        return [(i, 0.0) for i in range(len(documents))]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))
