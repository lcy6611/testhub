"""
层次3：AI 内容理解 —— 从 Dify 文档正文中抽取功能点，并跨文档做语义匹配。

流程：
1. fetch_document_text() 拉文档全文（已有，dify_kb_service 里）
2. extract_function_points() 调 LLM 抽取功能点列表
3. sync_function_points_to_graph() 将功能点写入图谱（document → contains → function_point）
4. suggest_cross_doc_relations() 跨文档功能点语义匹配 → 生成 similar_to 边建议
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from .constants import (
    ENTITY_FUNCTION_POINT,
    ENTITY_KB_DOCUMENT,
    REL_CONTAINS,
    REL_SIMILAR_TO,
)
from .models import KgEdge, KgEntity, kg_enabled
from .registry import (
    ensure_entity,
    entity_key_function_point,
    entity_key_kb_document,
    get_entity,
)

logger = logging.getLogger(__name__)

# 每篇文档最多抽取的功能点数量
MAX_POINTS_PER_DOC = 30
# 单篇文档送入 LLM 的最大字符数
MAX_DOC_CHARS_FOR_LLM = 8000
# 跨文档匹配时，每批送入 LLM 的功能点对数
MAX_PAIRS_PER_BATCH = 60
# 语义匹配置信度阈值
DEFAULT_SIMILARITY_THRESHOLD = 0.6


def _strip_json_fence(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_json_list(raw: str) -> List[Dict[str, Any]]:
    text = _strip_json_fence(raw)
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
    if isinstance(payload, dict):
        for key in ("function_points", "points", "items", "data"):
            val = payload.get(key)
            if isinstance(val, list):
                payload = val
                break
        else:
            payload = [payload]
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _build_extraction_prompt(doc_name: str, doc_content: str) -> List[Dict[str, str]]:
    """构建功能点抽取的 LLM prompt。"""
    truncated = doc_content[:MAX_DOC_CHARS_FOR_LLM]
    system_msg = (
        "你是需求分析专家。从给定的文档内容中识别出独立的功能点（feature points）。\n"
        "每个功能点应包含：\n"
        "- name: 功能名称（简洁，10-30字）\n"
        "- description: 功能描述（50-200字，说明该功能做什么、输入输出、关键规则）\n"
        "- keywords: 关键词列表（3-5个，用于跨文档匹配）\n"
        "- category: 分类（如：数据管理/流程审批/报表查询/接口集成/权限控制/其他）\n\n"
        "只输出 JSON 数组，不要 Markdown 解释。每项字段：name, description, keywords, category。"
    )
    user_msg = f"文档名称：{doc_name}\n\n文档内容：\n{truncated}\n\n请抽取其中的功能点列表。"
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _build_cross_match_prompt(points_a: List[Dict], points_b: List[Dict], doc_a: str, doc_b: str) -> List[Dict[str, str]]:
    """构建跨文档功能点匹配的 LLM prompt。"""
    system_msg = (
        "你是功能对齐专家。判断两组来自不同文档的功能点是否在语义上指向同一或关联的功能。\n"
        "对于每对你认为匹配的功能点，输出：\n"
        "- src_name: 文档A中的功能名称\n"
        "- dst_name: 文档B中的功能名称\n"
        "- confidence: 0-1 的置信度（0.6以上才输出）\n"
        "- reason: 简短理由\n"
        "- relation: similar_to（功能相同或高度相似）或 depends_on（有依赖关系）\n\n"
        "只输出 JSON 数组，不要 Markdown。"
    )
    lines_a = [f"- {p.get('name', '')}：{(p.get('description', '') or '')[:100]}" for p in points_a[:20]]
    lines_b = [f"- {p.get('name', '')}：{(p.get('description', '') or '')[:100]}" for p in points_b[:20]]
    user_msg = (
        f"文档A《{doc_a}》功能点：\n" + "\n".join(lines_a) + "\n\n"
        f"文档B《{doc_b}》功能点：\n" + "\n".join(lines_b) + "\n\n"
        "请找出跨文档的匹配对。"
    )
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _call_llm(messages: List[Dict[str, str]]) -> str:
    """
    同步调用 OpenAI 兼容接口，返回 assistant 文本响应。

    之前用 async + asyncio.run() 在 DRF 同步视图里调 AIModelService.call_openai_compatible_api，
    但该 async 函数内部会同步调 Django ORM (AIModelConfig.objects.filter(...))，
    触发 Django 4+ 的 "You cannot call this from an async context" 异常。
    改用 requests 同步直接 POST，彻底绕开 async / ORM 混用问题。
    """
    from apps.requirement_analysis.models import AIModelConfig, AIModelService

    config = AIModelConfig.objects.filter(role="writer", is_active=True).order_by("-updated_at").first()
    if not config:
        raise RuntimeError("未配置活跃的 AI 模型（role=writer）")

    api_key = config.api_key
    if not (config.base_url or "").strip():
        raise RuntimeError("AI 模型配置缺少 base_url")

    url = AIModelService._resolve_chat_completions_url(config)
    payload = {
        "model": config.model_name or "gpt-3.5-turbo",
        "messages": messages,
        "temperature": getattr(config, "temperature", 0.2) or 0.2,
        "max_tokens": 4096,
    }
    # Qwen3 / DeepSeek 推理模型默认开启 thinking，会把 max_tokens 全部吃光导致 content 为空
    # 显式关闭思考模式，让模型直接输出 JSON
    payload["chat_template_kwargs"] = {"enable_thinking": False}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = None
    last_exc: Optional[Exception] = None
    # 最多重试 4 次：0s / 2s / 4s / 8s（指数退避），主要应对 429 限流
    for attempt in range(4):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=60)
            if resp.status_code == 429:
                # 限流：按 Retry-After 头或指数退避
                retry_after = resp.headers.get("Retry-After")
                try:
                    wait_s = float(retry_after) if retry_after else (2 ** attempt)
                except (TypeError, ValueError):
                    wait_s = 2 ** attempt
                wait_s = min(max(wait_s, 1.0), 15.0)
                logger.warning("LLM 抽取触发限流(429)，%ss 后重试 attempt=%d", wait_s, attempt + 1)
                time.sleep(wait_s)
                continue
            resp.raise_for_status()
            break  # 成功
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise
    if resp is None:
        raise last_exc or RuntimeError("LLM 调用失败：未发起请求")
    data = resp.json()
    # 调试日志：看 LLM 完整响应，便于排查空返回
    logger.info("[KG-LLM-DEBUG] status=%s model=%s choices_len=%d", resp.status_code, data.get("model"), len(data.get("choices") or []))
    choice0 = (data.get("choices") or [{}])[0]
    message = choice0.get("message") or {}
    # 推理模型（Qwen3-35B-A3B、DeepSeek-R1 等）把正文输出放到 reasoning 字段，
    # message.content 通常为 null。优先取 content，否则回退到 reasoning/reasoning_content。
    content = (message.get("content") or "").strip()
    if not content:
        # Qwen3 / DeepSeek 推理模式的字段名
        reasoning = (message.get("reasoning") or message.get("reasoning_content") or "").strip()
        if reasoning:
            logger.info("[KG-LLM-DEBUG] content empty, fallback to reasoning field (len=%d)", len(reasoning))
            content = reasoning
        else:
            # 把完整响应 dump 出来排查
            logger.warning("[KG-LLM-DEBUG] empty content, full response head: %s", str(data)[:500])
    return content


def extract_function_points(doc_name: str, doc_content: str) -> List[Dict[str, Any]]:
    """
    调 LLM 从文档正文中抽取功能点列表。

    返回格式：[{"name": "...", "description": "...", "keywords": [...], "category": "..."}]
    """
    if not doc_content or not doc_content.strip():
        return []
    messages = _build_extraction_prompt(doc_name, doc_content)
    try:
        raw = _call_llm(messages)
    except Exception as exc:
        logger.warning("LLM 抽取功能点失败: %s", exc, exc_info=True)
        return []
    # 调试日志：把 LLM 原始返回记录到日志，方便排查"未抽取出功能点"问题
    logger.info("[KG-DEBUG] doc=%s raw_len=%d raw_head=%s", doc_name, len(raw or ""), (raw or "")[:300])
    points = _parse_json_list(raw)
    # 清洗 & 截断
    cleaned: List[Dict[str, Any]] = []
    for p in points[:MAX_POINTS_PER_DOC]:
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        desc = str(p.get("description") or "").strip()
        keywords = p.get("keywords") or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",") if k.strip()]
        category = str(p.get("category") or "其他").strip()
        cleaned.append({
            "name": name[:200],
            "description": desc[:500],
            "keywords": keywords[:10],
            "category": category[:50],
        })
    return cleaned


def sync_function_points_to_graph(
    dataset_id: str,
    document_id: str,
    document_name: str,
    points: List[Dict[str, Any]],
    *,
    project_id: Optional[int] = None,
) -> int:
    """
    将抽取出的功能点写入知识图谱。

    - 每个功能点 = 一个 FunctionPoint 节点
    - document → contains → function_point
    """
    if not kg_enabled() or not points:
        return 0

    doc_key = entity_key_kb_document(dataset_id, document_id)
    doc_entity = get_entity(doc_key)
    if not doc_entity:
        # 文档节点不存在，先创建
        doc_entity = ensure_entity(
            doc_key,
            ENTITY_KB_DOCUMENT,
            label=document_name or document_id,
            ref_app="dify",
            ref_id=document_id,
            dataset_id=dataset_id,
            project_id=project_id,
        )
    if not doc_entity:
        return 0

    # 先删除该文档下旧的功能点节点和边（增量重建）
    old_fp_keys = list(
        KgEntity.objects.filter(
            entity_type=ENTITY_FUNCTION_POINT,
            dataset_id=dataset_id,
        ).values_list("entity_key", flat=True)
    )
    # 只删属于本文档的（entity_key 包含 document_id）
    doc_fp_keys = [k for k in old_fp_keys if f":{document_id}:" in k]
    if doc_fp_keys:
        KgEdge.objects.filter(
            src=doc_entity,
            relation_type=REL_CONTAINS,
            dst__entity_key__in=doc_fp_keys,
        ).delete()
        KgEntity.objects.filter(entity_key__in=doc_fp_keys).delete()

    created = 0
    for idx, point in enumerate(points):
        fp_key = entity_key_function_point(dataset_id, document_id, idx)
        fp_entity = ensure_entity(
            fp_key,
            ENTITY_FUNCTION_POINT,
            label=point["name"],
            ref_app="dify",
            ref_id=f"{document_id}:{idx}",
            dataset_id=dataset_id,
            project_id=project_id,
            properties={
                "name": point["name"],
                "description": point["description"],
                "keywords": point["keywords"],
                "category": point["category"],
                "source_document_id": document_id,
                "source_document_name": document_name,
                "point_index": idx,
            },
        )
        if not fp_entity:
            continue
        # document → contains → function_point
        KgEdge.objects.update_or_create(
            src=doc_entity,
            dst=fp_entity,
            relation_type=REL_CONTAINS,
            defaults={
                "source": "system",
                "dataset_id": dataset_id,
                "project_id": project_id,
                "meta": {"document_name": document_name, "point_name": point["name"]},
            },
        )
        created += 1

    return created


def suggest_cross_doc_relations(
    dataset_id: str,
    *,
    min_confidence: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    跨文档功能点语义匹配：对所有 FunctionPoint 两两配对，调 LLM 判断相似性。

    返回建议列表：[{"src_key": "...", "dst_key": "...", "confidence": 0.8, "reason": "...", "relation": "similar_to"}]
    """
    if not kg_enabled():
        return []

    # 拉取该 dataset 下所有功能点，按文档分组
    fps = list(
        KgEntity.objects.filter(
            entity_type=ENTITY_FUNCTION_POINT,
            dataset_id=dataset_id,
        ).values("entity_key", "label", "properties", "ref_id")
    )
    if len(fps) < 2:
        return []

    # 按文档分组
    doc_groups: Dict[str, List[Dict]] = {}
    for fp in fps:
        props = fp.get("properties") or {}
        doc_id = props.get("source_document_id") or ""
        if not doc_id:
            continue
        doc_groups.setdefault(doc_id, []).append(fp)

    doc_ids = list(doc_groups.keys())
    if len(doc_ids) < 2:
        return []

    suggestions: List[Dict[str, Any]] = []
    existing_pairs = set(
        KgEdge.objects.filter(relation_type__in=[REL_SIMILAR_TO, "depends_on"]).values_list(
            "src__entity_key", "dst__entity_key"
        )
    )

    # 两两文档组合
    for i in range(len(doc_ids)):
        for j in range(i + 1, len(doc_ids)):
            doc_a_id = doc_ids[i]
            doc_b_id = doc_ids[j]
            points_a = doc_groups[doc_a_id]
            points_b = doc_groups[doc_b_id]

            # 提取名称和描述供 LLM 匹配
            raw_a = [
                {
                    "name": fp.get("label") or "",
                    "description": (fp.get("properties") or {}).get("description") or "",
                }
                for fp in points_a
            ]
            raw_b = [
                {
                    "name": fp.get("label") or "",
                    "description": (fp.get("properties") or {}).get("description") or "",
                }
                for fp in points_b
            ]

            doc_a_name = (points_a[0].get("properties") or {}).get("source_document_name") or doc_a_id
            doc_b_name = (points_b[0].get("properties") or {}).get("source_document_name") or doc_b_id

            try:
                messages = _build_cross_match_prompt(raw_a, raw_b, doc_a_name, doc_b_name)
                raw_resp = _call_llm(messages)
                matches = _parse_json_list(raw_resp)
            except Exception as exc:
                logger.warning("跨文档匹配 LLM 调用失败 %s ↔ %s: %s", doc_a_name, doc_b_name, exc)
                continue

            # 建立 name → entity_key 映射
            map_a = {fp.get("label"): fp.get("entity_key") for fp in points_a}
            map_b = {fp.get("label"): fp.get("entity_key") for fp in points_b}

            for m in matches:
                src_name = str(m.get("src_name") or "").strip()
                dst_name = str(m.get("dst_name") or "").strip()
                confidence = float(m.get("confidence") or 0)
                if confidence < min_confidence:
                    continue
                src_key = map_a.get(src_name)
                dst_key = map_b.get(dst_name)
                if not src_key or not dst_key:
                    continue
                if (src_key, dst_key) in existing_pairs or (dst_key, src_key) in existing_pairs:
                    continue
                relation = str(m.get("relation") or "similar_to").strip()
                if relation not in (REL_SIMILAR_TO, "depends_on"):
                    relation = REL_SIMILAR_TO
                suggestions.append({
                    "src_key": src_key,
                    "dst_key": dst_key,
                    "confidence": round(confidence, 3),
                    "reason": str(m.get("reason") or "")[:500],
                    "relation": relation,
                    "doc_a": doc_a_name,
                    "doc_b": doc_b_name,
                })

    suggestions.sort(key=lambda x: x["confidence"], reverse=True)
    return suggestions


def persist_cross_doc_relations(
    suggestions: List[Dict[str, Any]],
    *,
    project_id: Optional[int] = None,
    created_by=None,
) -> Dict[str, int]:
    """将跨文档匹配建议写入图谱（source=ai_suggested，待确认）。"""
    if not kg_enabled():
        return {"created": 0, "skipped": 0}

    created = 0
    skipped = 0
    for s in suggestions:
        src = get_entity(s["src_key"])
        dst = get_entity(s["dst_key"])
        if not src or not dst:
            skipped += 1
            continue
        _, was_created = KgEdge.objects.update_or_create(
            src=src,
            dst=dst,
            relation_type=s.get("relation", REL_SIMILAR_TO),
            defaults={
                "source": "ai_suggested",
                "dataset_id": src.dataset_id or "",
                "project_id": project_id,
                "meta": {
                    "confidence": s.get("confidence", 0),
                    "reason": s.get("reason", ""),
                    "doc_a": s.get("doc_a", ""),
                    "doc_b": s.get("doc_b", ""),
                },
            },
        )
        if was_created:
            created += 1
        else:
            skipped += 1

    return {"created": created, "skipped": skipped}
