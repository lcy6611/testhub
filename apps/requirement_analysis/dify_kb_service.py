"""
Dify 知识库（Dataset）集成服务。

用于在 AI 生成测试用例时，从 Dify 知识库检索相关文档片段作为参考上下文。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException

from apps.assistant.models import DifyConfig

logger = logging.getLogger(__name__)

DIFY_QUERY_MAX_LEN = 250
DEFAULT_TOP_K = 5
REQUEST_TIMEOUT = 30
MAX_CHARS_PER_DOCUMENT = 12000
MAX_TOTAL_KB_CONTEXT = 48000
SEGMENT_PAGE_LIMIT = 100
MAX_SEGMENT_PAGES = 20
GENERIC_FOCUS_WORDS = frozenset(
    {
        "需求",
        "描述",
        "标题",
        "文档",
        "内容",
        "测试",
        "用例",
        "功能",
        "系统",
        "用户",
        "请",
        "根据",
        "以下",
        "生成",
    }
)
SECONDARY_DOC_MAX_CHARS = 6000
PRIMARY_DOC_MAX_CHARS = 20000
MIN_RELEVANCE_SCORE = 0.18
QUERY_STOP_SUFFIX_RE = re.compile(
    r"(怎么(用|办|做|样|处理|操作)?|如何(使用|操作)?|是什么|有哪些|怎样|吗|呢|的用法|用法)$"
)
QUERY_GENERIC_TERMS = frozenset(
    {"什么", "怎么", "如何", "哪些", "为什么", "是否", "能否", "可以", "使用", "用法", "介绍", "说明"}
)


def _extract_query_terms(query: str) -> List[str]:
    """从用户问题提取检索关键词。"""
    q = (query or "").strip().lower()
    if not q:
        return []
    cleaned = QUERY_STOP_SUFFIX_RE.sub("", q).strip()
    terms: set[str] = set()
    for src in (cleaned, q):
        if len(src) >= 2:
            terms.add(src)
        for part in re.split(r"[\s,，、/\\|？?！!。\.；;：:]+", src):
            part = part.strip()
            if len(part) >= 2:
                terms.add(part)
    return sorted(t for t in terms if t not in QUERY_GENERIC_TERMS and len(t) >= 2)


def _score_text_against_terms(text: str, terms: List[str]) -> float:
    """按关键词命中计算 0~1 相关度。"""
    if not text or not terms:
        return 0.0
    text_lower = text.lower()
    hit_terms = [t for t in terms if t in text_lower]
    if not hit_terms:
        return 0.0
    coverage = len(hit_terms) / len(terms)
    occurrences = sum(text_lower.count(t) for t in hit_terms)
    density = min(occurrences / max(len(text_lower) / 200, 1), 1.0)
    return min(1.0, coverage * 0.55 + density * 0.45)


def _score_document_against_query(
    text: str,
    terms: List[str],
    *,
    doc_name: str = "",
) -> tuple[float, str]:
    """计算文档相关度并抽取最相关片段。无命中时返回 (0, '')。"""
    text = (text or "").strip()
    if not text or not terms:
        return 0.0, ""

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return 0.0, ""

    scored: List[tuple[float, str]] = []
    for para in paragraphs:
        para_score = _score_text_against_terms(para, terms)
        if para_score > 0:
            scored.append((para_score, para))

    name_bonus = 0.0
    name_lower = (doc_name or "").lower()
    if name_lower:
        name_hits = sum(1 for t in terms if t in name_lower)
        if name_hits:
            name_bonus = min(0.12, name_hits / len(terms) * 0.12)

    if not scored:
        return 0.0, ""

    scored.sort(key=lambda x: x[0], reverse=True)
    best_para_score = scored[0][0]
    doc_score = min(1.0, best_para_score + name_bonus)
    snippet = "\n\n".join(p for _, p in scored[:5])[:4000]
    return doc_score, snippet


def _rescore_record_against_query(rec: Dict[str, Any], query: str) -> tuple[float, Dict[str, Any]]:
    """用问题关键词重新评估 Dify 检索片段的相关度。"""
    terms = _extract_query_terms(query)
    segment = rec.get("segment") or {}
    content = (segment.get("content") or "").strip()
    doc = segment.get("document") or {}
    doc_name = (doc.get("name") or "").strip()

    content_score = _score_text_against_terms(content, terms)
    if not terms:
        api_score = rec.get("score")
        if isinstance(api_score, (int, float)):
            val = float(api_score)
            if val > 1:
                val = val / 100.0
            return val, {**rec, "score": round(val, 4)}
        return 0.0, rec

    if content_score <= 0:
        return 0.0, rec

    name_bonus = 0.0
    if doc_name:
        name_hits = sum(1 for t in terms if t in doc_name.lower())
        if name_hits:
            name_bonus = min(0.12, name_hits / len(terms) * 0.12)

    api_score = rec.get("score")
    api_val = 0.0
    if isinstance(api_score, (int, float)):
        api_val = float(api_score)
        if api_val > 1:
            api_val = api_val / 100.0

    final = min(1.0, max(content_score + name_bonus, content_score * 0.7 + api_val * 0.3))
    return final, {**rec, "score": round(final, 4)}


def _validate_and_rescore_records(
    records: List[Dict[str, Any]],
    query: str,
    *,
    min_score: float = MIN_RELEVANCE_SCORE,
) -> List[Dict[str, Any]]:
    """过滤 Dify API 检索结果中内容与问题无关的片段。"""
    rescored: List[Dict[str, Any]] = []
    for rec in records or []:
        score, new_rec = _rescore_record_against_query(rec, query)
        if score >= min_score:
            rescored.append(new_rec)
    rescored.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
    return rescored


def _filter_records_by_score(
    records: List[Dict[str, Any]],
    *,
    min_absolute: float = MIN_RELEVANCE_SCORE,
) -> List[Dict[str, Any]]:
    """过滤低相关度片段；保留与最高分接近的结果。"""
    if not records:
        return []
    scored = [r for r in records if isinstance(r.get("score"), (int, float))]
    if not scored:
        return []
    best = max(float(r["score"]) for r in scored)
    threshold = max(min_absolute, best * 0.4)
    filtered = [
        r for r in records
        if isinstance(r.get("score"), (int, float)) and float(r["score"]) >= threshold
    ]
    return filtered if filtered else [max(scored, key=lambda r: float(r["score"]))]


def extract_requirement_focus(title: str, requirement_text: str) -> str:
    """从标题/需求文本提取主需求聚焦词（如 BOM）。"""
    title = (title or "").strip()
    text = (requirement_text or "").strip()

    for pattern in (
        r"需求标题[：:]\s*(.+)",
        r"文档标题[：:]\s*(.+)",
        r"需求描述[：:]\s*(.+)",
    ):
        m = re.search(pattern, text)
        if m:
            candidate = m.group(1).split("\n")[0].strip()
            if candidate and candidate not in GENERIC_FOCUS_WORDS:
                return candidate

    if title and title not in ("预览", "测试"):
        return title

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("需求") or len(line) > 80:
            continue
        if line not in GENERIC_FOCUS_WORDS:
            return line
    return title or text[:80] or "主需求"


def _focus_terms(focus: str) -> List[str]:
    focus = (focus or "").strip().lower()
    if not focus:
        return []
    terms = {focus}
    for part in re.split(r"[\s,，、/\\|]+", focus):
        part = part.strip().lower()
        if len(part) >= 2:
            terms.add(part)
    return list(terms)


def score_document_relevance(ref: Dict[str, Any], focus: str) -> float:
    terms = _focus_terms(focus)
    if not terms:
        return 0.0
    name = (ref.get("document_name") or ref.get("document_id") or "").lower()
    func = (ref.get("function_name") or "").lower()
    score = 0.0
    for term in terms:
        if term in name:
            score += 100
        if func and term in func:
            score += 80
    return score


def filter_content_by_focus(content: str, focus: str, max_chars: int) -> str:
    """按主需求关键词过滤文档段落，避免无关模块（如项目基线）占满上下文。"""
    content = (content or "").strip()
    if not content:
        return ""
    terms = _focus_terms(focus)
    if not terms:
        return content[:max_chars]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    if not paragraphs:
        return content[:max_chars]

    matched = [p for p in paragraphs if any(t in p.lower() for t in terms)]
    if matched:
        filtered = "\n\n".join(matched)
        return filtered[:max_chars]

    return content[: min(max_chars, 3000)]


def sort_document_refs_by_focus(refs: List[Dict[str, str]], focus: str) -> List[Dict[str, str]]:
    if not refs or not (focus or "").strip():
        return refs
    return sorted(refs, key=lambda r: score_document_relevance(r, focus), reverse=True)


def normalize_dify_api_base_url(raw: str) -> str:
    api_url = (raw or "").strip().rstrip("/")
    if api_url.endswith("/v1"):
        return api_url
    return f"{api_url}/v1"


def strip_bearer_prefix(key: str) -> str:
    api_key = (key or "").strip()
    for prefix in ("Bearer ", "bearer ", "Token ", "token "):
        if api_key.startswith(prefix):
            return api_key[len(prefix) :].strip()
    return api_key


def get_dataset_api_key(config: DifyConfig) -> str:
    """优先使用 dataset_api_key；兼容直接填写 dataset- 前缀的应用 Key。"""
    dataset_key = strip_bearer_prefix(getattr(config, "dataset_api_key", "") or "")
    if dataset_key:
        return dataset_key
    app_key = strip_bearer_prefix(config.api_key or "")
    if app_key.startswith("dataset-"):
        return app_key
    return ""


def build_retrieval_query(title: str, requirement_text: str) -> str:
    combined = f"{(title or '').strip()}\n{(requirement_text or '').strip()}".strip()
    if not combined:
        return "测试用例生成参考"
    if len(combined) <= DIFY_QUERY_MAX_LEN:
        return combined
    return combined[: DIFY_QUERY_MAX_LEN - 3] + "..."


def _auth_headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def list_datasets(
    config: DifyConfig,
    *,
    page: int = 1,
    limit: int = 100,
    keyword: str = "",
) -> Dict[str, Any]:
    api_key = get_dataset_api_key(config)
    if not api_key:
        raise ValueError("未配置 Dify 知识库 API Key（dataset- 开头）。请在配置中心填写。")

    base_url = normalize_dify_api_base_url(config.api_url)
    params: Dict[str, Any] = {"page": page, "limit": limit}
    if keyword:
        params["keyword"] = keyword

    try:
        resp = requests.get(
            f"{base_url}/datasets",
            headers=_auth_headers(api_key),
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
    except RequestException as exc:
        logger.warning("Dify 服务不可达: url=%s err=%s", base_url, exc)
        raise ValueError(
            f"Dify 服务不可达（地址：{base_url}）。可能原因：① Dify 服务未启动 ② 网络不通（容器内需 host.docker.internal 访问宿主机服务）"
            f" ③ 防火墙拦截。错误：{type(exc).__name__}: {exc}。"
            f"建议：到「配置中心 → 知识中枢配置」切换为「知识中枢（自建）」，无需 Dify 即可使用知识图谱。"
        ) from exc
    if resp.status_code in (401, 403):
        raise ValueError("Dify 知识库 API Key 无效或无权限，请检查 dataset API Key。")
    if not resp.ok:
        detail = (resp.text or "")[:500]
        raise ValueError(f"获取 Dify 知识库列表失败 ({resp.status_code}): {detail}")

    payload = resp.json() if resp.content else {}
    datasets = payload.get("data") or []
    simplified = []
    for item in datasets:
        if not isinstance(item, dict):
            continue
        simplified.append(
            {
                "id": item.get("id"),
                "name": item.get("name") or "",
                "description": item.get("description") or "",
                "document_count": item.get("document_count") or 0,
                "word_count": item.get("word_count") or 0,
                "enable_api": item.get("enable_api", True),
                "embedding_available": item.get("embedding_available", True),
            }
        )
    return {
        "data": simplified,
        "total": payload.get("total", len(simplified)),
        "page": payload.get("page", page),
        "limit": payload.get("limit", limit),
        "has_more": payload.get("has_more", False),
    }


def retrieve_from_dataset(
    config: DifyConfig,
    dataset_id: str,
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    search_method: str = "semantic_search",
) -> List[Dict[str, Any]]:
    api_key = get_dataset_api_key(config)
    if not api_key:
        raise ValueError("未配置 Dify 知识库 API Key（dataset- 开头）。")

    base_url = normalize_dify_api_base_url(config.api_url)
    body = {
        "query": (query or "")[:DIFY_QUERY_MAX_LEN],
        "retrieval_model": {
            "search_method": search_method or "semantic_search",
            "reranking_enable": False,
            "reranking_mode": None,
            "reranking_model": {
                "reranking_provider_name": "",
                "reranking_model_name": "",
            },
            "weights": None,
            "top_k": max(1, min(int(top_k or DEFAULT_TOP_K), 10)),
            "score_threshold_enabled": False,
            "score_threshold": 0.0,
        },
    }
    resp = requests.post(
        f"{base_url}/datasets/{dataset_id}/retrieve",
        headers=_auth_headers(api_key),
        json=body,
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code == 403:
        raise ValueError("该知识库未开启 API 访问，请在 Dify 知识库设置中启用 API。")
    if resp.status_code in (401, 403):
        raise ValueError("Dify 知识库 API Key 无效或无权限。")
    if not resp.ok:
        detail = (resp.text or "")[:500]
        raise ValueError(f"知识库检索失败 ({resp.status_code}): {detail}")

    payload = resp.json() if resp.content else {}
    return payload.get("records") or []


def _is_embedding_or_rate_limit_error(exc: Exception) -> bool:
    text = str(exc or "").lower()
    markers = (
        "rate_limit",
        "rate limit",
        "embedding",
        "429",
        "qwen3-embedding",
        "invalid_param",
    )
    return any(m in text for m in markers)


def _record_document_id(record: Dict[str, Any]) -> str:
    segment = record.get("segment") or {}
    doc = segment.get("document") or {}
    return str(doc.get("id") or "").strip()


def _retrieve_full_library(
    config: DifyConfig,
    dataset_id: str,
    query: str,
    *,
    top_k: int,
    meta: Dict[str, Any],
    document_names: Dict[str, str],
) -> List[Dict[str, Any]]:
    """全库检索：语义 → 关键词 → 全文 → 扫描全部文档正文。"""
    last_exc: Optional[Exception] = None
    api_attempted = False

    for method, _warn_msg in (
        ("semantic_search", ""),
        ("keyword_search", "semantic_unavailable"),
        ("full_text_search", "full_text_fallback"),
    ):
        try:
            batch = retrieve_from_dataset(
                config, dataset_id, query, top_k=top_k, search_method=method
            )
            api_attempted = True
            if not batch:
                logger.debug("全库检索 %s 无命中: query=%s", method, query[:80])
                continue
            validated = _validate_and_rescore_records(batch, query)
            if validated:
                meta["mode"] = method
                meta["warnings"] = []
                return validated[:top_k]
            logger.debug("全库检索 %s 片段与问题关键词匹配度不足: query=%s", method, query[:80])
        except ValueError as exc:
            last_exc = exc
            if method == "semantic_search" and _is_embedding_or_rate_limit_error(exc):
                logger.info("全库语义检索不可用，降级关键词/全文: %s", exc)
                continue
            if method == "full_text_search":
                raise

    if not document_names:
        try:
            docs_payload = list_dataset_documents(config, dataset_id, page=1, limit=100)
            for item in docs_payload.get("data") or []:
                if isinstance(item, dict) and item.get("id"):
                    document_names[str(item["id"])] = item.get("name") or str(item["id"])
        except Exception as exc:
            logger.warning("全库降级扫描：加载文档列表失败: %s", exc)

    all_ids = {str(k).strip() for k in document_names.keys() if str(k).strip()}
    if all_ids:
        if api_attempted:
            logger.info("Dify API 检索未命中，降级扫描知识库全部文档正文: query=%s", query[:80])
        meta["mode"] = "document_scan_fallback"
        meta["fallback"] = "scan_all_documents"
        meta["warnings"] = []
        return _retrieve_from_selected_documents(
            config,
            dataset_id,
            query,
            all_ids,
            top_k=top_k,
            document_names=document_names,
        )

    meta["warnings"] = ["未在知识库中找到与问题相关的内容，请尝试换种问法或指定文档检索。"]
    if last_exc:
        raise last_exc
    return []


def retrieve_for_chat(
    config: DifyConfig,
    dataset_id: str,
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    document_ids: Optional[List[str]] = None,
    scope_mode: str = "full",
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    知识库对话检索。
    scope_mode:
      - full: 全库检索（Dify retrieve + 降级）
      - documents: 仅检索勾选的文档正文
    """
    use_documents = scope_mode == "documents" and bool(document_ids)
    meta: Dict[str, Any] = {
        "query": (query or "")[:DIFY_QUERY_MAX_LEN],
        "top_k": top_k,
        "document_ids": document_ids or [],
        "scope_mode": scope_mode,
        "scope": "documents" if use_documents else "dataset",
    }
    document_names: Dict[str, str] = {}
    if document_ids or not use_documents:
        try:
            docs_payload = list_dataset_documents(config, dataset_id, page=1, limit=100)
            for item in docs_payload.get("data") or []:
                if isinstance(item, dict) and item.get("id"):
                    document_names[str(item["id"])] = item.get("name") or str(item["id"])
        except Exception as exc:
            logger.warning("加载文档名称失败: %s", exc)

    allowed = {str(x).strip() for x in (document_ids or []) if str(x).strip()}

    if use_documents and allowed:
        meta["mode"] = "document_text"
        records = _retrieve_from_selected_documents(
            config, dataset_id, query, allowed, top_k=top_k, document_names=document_names
        )
        meta["warnings"] = []
    else:
        records = _retrieve_full_library(
            config,
            dataset_id,
            query,
            top_k=top_k,
            meta=meta,
            document_names=document_names,
        )

    records = _filter_records_by_score(records)
    meta["retrieval_count"] = len(records)
    if records:
        meta["warnings"] = []
    elif not meta.get("warnings"):
        meta["warnings"] = ["未在知识库中找到与问题相关的内容，请尝试换种问法或指定文档检索。"]
    meta["sources"] = format_retrieval_sources(
        records,
        document_names=document_names,
        min_score=MIN_RELEVANCE_SCORE,
    )
    return records, meta


def _retrieve_from_selected_documents(
    config: DifyConfig,
    dataset_id: str,
    query: str,
    document_ids: set,
    *,
    top_k: int,
    document_names: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """从文档正文中按关键词匹配抽取片段，并计算真实相关度。"""
    document_names = document_names or {}
    terms = _extract_query_terms(query)
    if not terms:
        return []

    candidates: List[Dict[str, Any]] = []
    doc_id_list = list(document_ids)
    for doc_id in doc_id_list:
        doc_name = document_names.get(doc_id) or doc_id
        try:
            text = fetch_document_text(config, dataset_id, doc_id, max_chars=MAX_CHARS_PER_DOCUMENT)
        except Exception as exc:
            logger.warning("对话检索拉取文档失败 doc_id=%s: %s", doc_id, exc)
            continue
        score, snippet = _score_document_against_query(text, terms, doc_name=doc_name)
        if score < MIN_RELEVANCE_SCORE or not snippet:
            continue
        candidates.append(
            {
                "score": round(score, 4),
                "segment": {
                    "content": snippet,
                    "document": {"id": doc_id, "name": doc_name},
                },
            }
        )

    candidates.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
    return candidates[:top_k]


def format_chat_retrieval_context(
    records: List[Dict[str, Any]],
    *,
    dataset_name: str = "",
) -> str:
    """格式化对话 RAG 上下文。"""
    if not records:
        return "（未检索到相关知识库片段）"

    lines = [f"【知识库检索结果：{dataset_name or '知识库'}】"]
    for idx, rec in enumerate(records, start=1):
        segment = rec.get("segment") or {}
        content = (segment.get("content") or "").strip()
        if not content:
            continue
        doc = segment.get("document") or {}
        doc_name = doc.get("name") or doc.get("id") or "未知文档"
        score = rec.get("score")
        if isinstance(score, (int, float)):
            if score <= 1:
                score_suffix = f" 相关度 {score * 100:.1f}%"
            else:
                score_suffix = f" 相关度 {score:.1f}%"
        else:
            score_suffix = ""
        lines.append(f"\n[片段{idx}] 《{doc_name}》{score_suffix}\n{content}")
    return "\n".join(lines)


def format_retrieval_sources(
    records: List[Dict[str, Any]],
    *,
    document_names: Optional[Dict[str, str]] = None,
    min_score: float = MIN_RELEVANCE_SCORE,
) -> List[Dict[str, Any]]:
    """去重并整理引用来源，供前端展示。"""
    document_names = document_names or {}
    merged: Dict[str, Dict[str, Any]] = {}

    for rec in records or []:
        score = rec.get("score")
        if isinstance(score, (int, float)) and float(score) < min_score:
            continue
        segment = rec.get("segment") or {}
        doc = segment.get("document") or {}
        doc_id = str(doc.get("id") or "").strip()
        raw_name = (doc.get("name") or document_names.get(doc_id) or "").strip()
        if raw_name and raw_name == doc_id and document_names.get(doc_id):
            raw_name = document_names[doc_id]
        doc_name = raw_name or doc_id or "未知文档"
        content = (segment.get("content") or "").strip()
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


def format_kb_context(records: List[Dict[str, Any]], dataset_name: str = "") -> str:
    if not records:
        return ""

    lines: List[str] = []
    title = dataset_name or "知识库"
    lines.append(f"【知识库语义检索补充：{title}】")
    lines.append(
        "以下内容为语义检索到的相关片段（次要参考）。"
        "须以主需求为准，仅补充与主需求相关的业务规则与边界："
    )

    for idx, rec in enumerate(records, start=1):
        if not isinstance(rec, dict):
            continue
        segment = rec.get("segment") or {}
        content = (segment.get("content") or "").strip()
        if not content:
            child_chunks = rec.get("child_chunks") or []
            parts = [
                (c.get("content") or "").strip()
                for c in child_chunks
                if isinstance(c, dict) and (c.get("content") or "").strip()
            ]
            content = "\n".join(parts).strip()
        if not content:
            continue

        doc = segment.get("document") or {}
        doc_name = doc.get("name") or "未知文档"
        score = rec.get("score")
        score_suffix = f"（相关度 {score:.2f}）" if isinstance(score, (int, float)) else ""
        lines.append(f"\n[参考{idx}] 文档：{doc_name}{score_suffix}\n{content}")

    if len(lines) <= 2:
        return ""
    return "\n".join(lines)


def resolve_dify_config(dify_config_id: Optional[int]) -> Optional[DifyConfig]:
    if dify_config_id:
        return DifyConfig.objects.filter(pk=dify_config_id).first()
    return DifyConfig.objects.filter(is_active=True).order_by("-updated_at").first()


def list_dataset_documents(
    config: DifyConfig,
    dataset_id: str,
    *,
    page: int = 1,
    limit: int = 100,
    keyword: str = "",
) -> Dict[str, Any]:
    """列出知识库内文档。"""
    api_key = get_dataset_api_key(config)
    if not api_key:
        raise ValueError("未配置 Dify 知识库 API Key（dataset- 开头）。")

    base_url = normalize_dify_api_base_url(config.api_url)
    params: Dict[str, Any] = {"page": page, "limit": limit}
    if keyword:
        params["keyword"] = keyword

    try:
        resp = requests.get(
            f"{base_url}/datasets/{dataset_id}/documents",
            headers=_auth_headers(api_key),
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
    except RequestException as exc:
        logger.warning("Dify 服务不可达（documents）: url=%s err=%s", base_url, exc)
        raise ValueError(
            f"Dify 服务不可达（地址：{base_url}）。可能原因：① Dify 服务未启动 ② 网络不通"
            f" ③ 防火墙拦截。错误：{type(exc).__name__}: {exc}。"
            f"建议：到「配置中心 → 知识中枢配置」切换为「知识中枢（自建）」。"
        ) from exc
    if resp.status_code in (401, 403):
        raise ValueError("Dify 知识库 API Key 无效或无权限。")
    if not resp.ok:
        detail = (resp.text or "")[:500]
        raise ValueError(f"获取知识库文档列表失败 ({resp.status_code}): {detail}")

    payload = resp.json() if resp.content else {}
    docs = payload.get("data") or []
    simplified = []
    for item in docs:
        if not isinstance(item, dict):
            continue
        simplified.append(
            {
                "id": item.get("id"),
                "name": item.get("name") or "",
                "indexing_status": item.get("indexing_status") or "",
                "word_count": item.get("word_count") or 0,
                "enabled": item.get("enabled", True),
            }
        )
    return {
        "data": simplified,
        "total": payload.get("total", len(simplified)),
        "page": payload.get("page", page),
        "limit": payload.get("limit", limit),
        "has_more": payload.get("has_more", False),
    }


def fetch_document_text(
    config: DifyConfig,
    dataset_id: str,
    document_id: str,
    *,
    max_chars: int = MAX_CHARS_PER_DOCUMENT,
) -> str:
    """拉取单篇文档的全部分段文本（按顺序拼接）。"""
    api_key = get_dataset_api_key(config)
    if not api_key:
        raise ValueError("未配置 Dify 知识库 API Key。")

    base_url = normalize_dify_api_base_url(config.api_url)
    parts: List[str] = []
    total_len = 0
    page = 1

    while page <= MAX_SEGMENT_PAGES:
        resp = requests.get(
            f"{base_url}/datasets/{dataset_id}/documents/{document_id}/segments",
            headers=_auth_headers(api_key),
            params={"page": page, "limit": SEGMENT_PAGE_LIMIT},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code in (401, 403):
            raise ValueError("Dify 知识库 API Key 无效或无权限。")
        if not resp.ok:
            detail = (resp.text or "")[:300]
            raise ValueError(f"获取文档分段失败 ({resp.status_code}): {detail}")

        payload = resp.json() if resp.content else {}
        segments = payload.get("data") or []
        if not segments:
            break

        for seg in segments:
            if not isinstance(seg, dict):
                continue
            content = (seg.get("content") or "").strip()
            if not content:
                continue
            if total_len + len(content) > max_chars:
                remain = max_chars - total_len
                if remain > 0:
                    parts.append(content[:remain])
                    total_len += remain
                return "\n\n".join(parts)
            parts.append(content)
            total_len += len(content)

        if not payload.get("has_more"):
            break
        page += 1

    return "\n\n".join(parts)


def _resolve_document_refs_from_functions(
    function_ids: List[int],
    *,
    expand_relations: bool = True,
) -> List[Dict[str, str]]:
    """从功能模块解析参考文档（含一级关联功能）。"""
    from .kb_models import KbFunction, KbFunctionDocument, KbFunctionRelation

    if not function_ids:
        return []

    functions = list(
        KbFunction.objects.filter(id__in=function_ids, is_active=True).prefetch_related("documents")
    )
    if not functions:
        return []

    all_function_ids = {f.id for f in functions}
    if expand_relations:
        relations = KbFunctionRelation.objects.filter(from_function_id__in=all_function_ids).select_related(
            "to_function"
        )
        related_ids = {rel.to_function_id for rel in relations if rel.to_function.is_active}
        all_function_ids |= related_ids
        if related_ids:
            functions.extend(
                list(KbFunction.objects.filter(id__in=related_ids, is_active=True).prefetch_related("documents"))
            )

    seen: set[str] = set()
    refs: List[Dict[str, str]] = []
    for func in functions:
        for doc in func.documents.all():
            doc_id = str(doc.dify_document_id)
            if doc_id in seen:
                continue
            seen.add(doc_id)
            refs.append(
                {
                    "document_id": doc_id,
                    "document_name": doc.dify_document_name or doc_id,
                    "source": "function",
                    "function_name": func.name,
                    "is_primary": doc.is_primary,
                }
            )
    return refs


def _merge_document_refs(
    manual_ids: List[str],
    manual_names: Optional[Dict[str, str]],
    function_refs: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    """合并手动选择与功能关联解析出的文档。"""
    manual_names = manual_names or {}
    merged: List[Dict[str, str]] = []
    seen: set[str] = set()

    for doc_id in manual_ids:
        doc_id = str(doc_id).strip()
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        merged.append(
            {
                "document_id": doc_id,
                "document_name": manual_names.get(doc_id) or doc_id,
                "source": "manual",
            }
        )

    for ref in function_refs:
        doc_id = ref.get("document_id") or ""
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        merged.append(ref)

    return merged


def format_document_context(
    doc_sections: List[Dict[str, Any]],
    dataset_name: str = "",
    requirement_focus: str = "",
) -> str:
    if not doc_sections:
        return ""

    focus = (requirement_focus or "").strip() or "主需求"
    lines = [
        f"【知识库增强参考文档：{dataset_name or '知识库'}】",
        f"【主需求聚焦：{focus}】以下材料仅作补充，用例必须围绕「{focus}」编写；"
        f"勿写与「{focus}」无关的模块（例如主需求为 BOM 时，不要写项目计划基线类用例）：",
    ]
    for idx, item in enumerate(doc_sections, start=1):
        content = (item.get("content") or "").strip()
        if not content:
            continue
        name = item.get("document_name") or "未知文档"
        source = item.get("source") or ""
        func = item.get("function_name") or ""
        suffix = ""
        if source == "function" and func:
            suffix = f"（功能：{func}）"
        elif source == "manual":
            suffix = "（手动选择）"
        lines.append(f"\n[文档{idx}] {name}{suffix}\n{content}")

    if len(lines) <= 2:
        return ""
    return "\n".join(lines)


def build_kb_reference_context(
    config: DifyConfig,
    dataset_id: str,
    *,
    title: str,
    requirement_text: str,
    dataset_name: str = "",
    document_ids: Optional[List[str]] = None,
    document_names: Optional[Dict[str, str]] = None,
    function_ids: Optional[List[int]] = None,
    reference_mode: str = "hybrid",
    top_k: int = DEFAULT_TOP_K,
) -> tuple[str, Dict[str, Any]]:
    """
    构建知识库参考上下文。

    reference_mode:
      - documents: 仅指定文档 + 功能关联文档
      - retrieval: 仅语义检索
      - hybrid: 文档优先，并补充语义检索（默认）
    """
    reference_mode = (reference_mode or "hybrid").strip().lower()
    if reference_mode not in ("documents", "retrieval", "hybrid"):
        reference_mode = "hybrid"

    meta: Dict[str, Any] = {
        "reference_mode": reference_mode,
        "documents": [],
        "retrieval_count": 0,
    }
    requirement_focus = extract_requirement_focus(title, requirement_text)
    meta["requirement_focus"] = requirement_focus
    parts: List[str] = []

    function_refs = _resolve_document_refs_from_functions(function_ids or [])
    doc_refs = _merge_document_refs(document_ids or [], document_names, function_refs)
    doc_refs = sort_document_refs_by_focus(doc_refs, requirement_focus)
    use_documents = reference_mode in ("documents", "hybrid") and bool(doc_refs)

    doc_sections: List[Dict[str, Any]] = []
    total_chars = 0

    if use_documents:
        for ref in doc_refs:
            doc_id = ref["document_id"]
            rel_score = score_document_relevance(ref, requirement_focus)
            per_doc_limit = PRIMARY_DOC_MAX_CHARS if rel_score >= 50 else SECONDARY_DOC_MAX_CHARS
            try:
                content = fetch_document_text(config, dataset_id, doc_id, max_chars=MAX_CHARS_PER_DOCUMENT)
            except Exception as exc:
                logger.warning("拉取文档失败 doc_id=%s: %s", doc_id, exc)
                meta.setdefault("warnings", []).append(f"文档 {ref.get('document_name') or doc_id} 拉取失败: {exc}")
                continue
            if not content:
                continue

            filtered = filter_content_by_focus(content, requirement_focus, per_doc_limit)
            if rel_score < 50:
                meta.setdefault("warnings", []).append(
                    f"文档「{ref.get('document_name') or doc_id}」与主需求「{requirement_focus}」关联较弱，已按关键词过滤/压缩"
                )
            content = filtered
            if not content.strip():
                meta.setdefault("warnings", []).append(
                    f"文档「{ref.get('document_name') or doc_id}」未找到与「{requirement_focus}」相关内容，已跳过"
                )
                continue

            if total_chars + len(content) > MAX_TOTAL_KB_CONTEXT:
                content = content[: max(0, MAX_TOTAL_KB_CONTEXT - total_chars)]
            total_chars += len(content)
            section = {**ref, "content": content, "relevance_score": rel_score}
            doc_sections.append(section)
            meta["documents"].append(
                {
                    "document_id": doc_id,
                    "document_name": ref.get("document_name"),
                    "source": ref.get("source"),
                    "function_name": ref.get("function_name"),
                    "chars": len(content),
                }
            )
            if total_chars >= MAX_TOTAL_KB_CONTEXT:
                break

        doc_context = format_document_context(
            doc_sections, dataset_name=dataset_name, requirement_focus=requirement_focus
        )
        if doc_context:
            parts.append(doc_context)

    use_retrieval = reference_mode in ("retrieval", "hybrid")
    # 已选手动/功能关联文档时，混合模式不再触发语义检索（避免 Embedding 依赖与限流）
    skip_retrieval_for_selected_docs = reference_mode == "hybrid" and bool(doc_refs)
    if skip_retrieval_for_selected_docs:
        meta["retrieval_skipped"] = "已选择参考文档，跳过语义检索"

    if use_retrieval and not skip_retrieval_for_selected_docs and (
        reference_mode == "retrieval" or total_chars < MAX_TOTAL_KB_CONTEXT // 2
    ):
        query = build_retrieval_query(title, requirement_text)
        try:
            records = retrieve_from_dataset(config, dataset_id, query, top_k=top_k)
            retrieval_context = format_kb_context(records, dataset_name=dataset_name)
            if retrieval_context:
                if reference_mode == "hybrid" and parts:
                    parts.append("\n---\n\n【语义检索补充片段】\n" + retrieval_context.split("\n", 2)[-1])
                else:
                    parts.append(retrieval_context)
                meta["retrieval_count"] = len(records)
        except (RequestException, ValueError) as exc:
            if parts:
                meta.setdefault("warnings", []).append(f"语义检索失败，已使用文档参考继续: {exc}")
                logger.warning("语义检索失败，已使用文档参考继续: %s", exc)
            else:
                logger.exception("Dify 知识库检索失败且无文档参考可回退")
                raise ValueError(f"知识库检索失败: {exc}") from exc

    context = "\n\n---\n\n".join(p for p in parts if p.strip())
    meta["total_chars"] = len(context)
    return context, meta


def fetch_kb_context_for_generation(
    config: DifyConfig,
    dataset_id: str,
    *,
    title: str,
    requirement_text: str,
    dataset_name: str = "",
    top_k: int = DEFAULT_TOP_K,
    document_ids: Optional[List[str]] = None,
    document_names: Optional[Dict[str, str]] = None,
    function_ids: Optional[List[int]] = None,
    reference_mode: str = "hybrid",
) -> str:
    """兼容旧调用：返回参考上下文字符串。"""
    context, _meta = build_kb_reference_context(
        config,
        dataset_id,
        title=title,
        requirement_text=requirement_text,
        dataset_name=dataset_name,
        document_ids=document_ids,
        document_names=document_names,
        function_ids=function_ids,
        reference_mode=reference_mode,
        top_k=top_k,
    )
    if not context:
        logger.warning(
            "知识库参考上下文为空 dataset_id=%s mode=%s docs=%s functions=%s",
            dataset_id,
            reference_mode,
            document_ids,
            function_ids,
        )
    return context
