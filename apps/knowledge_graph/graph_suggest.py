"""AI / 启发式建议图谱边（maps_to、covers），供待确认队列使用。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .constants import (
    ENTITY_BUSINESS_REQUIREMENT,
    ENTITY_KB_FUNCTION,
    ENTITY_TEST_CASE,
    REL_COVERS,
    REL_MAPS_TO,
)
from .models import KgEdge, kg_enabled
from .registry import entity_key_biz_req, entity_key_kb_function, entity_key_test_case

logger = logging.getLogger(__name__)

SUPPORTED_RELATIONS = frozenset({REL_MAPS_TO, REL_COVERS})
_DEFAULT_TOP_K_MAPS = 5
_DEFAULT_TOP_K_COVERS = 4


def _clamp_confidence(value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, v)), 3)


def _normalize_text(text: str) -> str:
    s = (text or "").lower().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _token_set(text: str) -> Set[str]:
    s = _normalize_text(text)
    if not s:
        return set()
    parts = re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_]+", s)
    tokens: Set[str] = set()
    for part in parts:
        if len(part) >= 2:
            tokens.add(part)
        if re.fullmatch(r"[\u4e00-\u9fff]+", part) and len(part) >= 2:
            for i in range(len(part) - 1):
                tokens.add(part[i : i + 2])
    return tokens


def _text_similarity(left: str, right: str) -> float:
    a = _normalize_text(left)
    b = _normalize_text(right)
    if not a or not b:
        return 0.0
    ratio = SequenceMatcher(None, a, b).ratio()
    ta, tb = _token_set(a), _token_set(b)
    if ta and tb:
        jaccard = len(ta & tb) / len(ta | tb)
        ratio = max(ratio, jaccard)
    if a in b or b in a:
        ratio = max(ratio, 0.72)
    return ratio


def _suggestion_dict(
    *,
    relation_type: str,
    src_key: str,
    dst_key: str,
    src_type: str,
    dst_type: str,
    src_label: str,
    dst_label: str,
    src_ref_id: str,
    dst_ref_id: str,
    confidence: float,
    reason: str,
    method: str,
) -> Dict[str, Any]:
    return {
        "relation_type": relation_type,
        "src": src_key,
        "dst": dst_key,
        "src_entity_type": src_type,
        "dst_entity_type": dst_type,
        "src_label": src_label,
        "dst_label": dst_label,
        "src_ref_id": src_ref_id,
        "dst_ref_id": dst_ref_id,
        "confidence": _clamp_confidence(confidence),
        "reason": (reason or "")[:500],
        "method": method,
    }


def _existing_edge_pairs(relation_types: Iterable[str]) -> Set[Tuple[str, str]]:
    if not kg_enabled():
        return set()
    pairs: Set[Tuple[str, str]] = set()
    for src_key, dst_key in KgEdge.objects.filter(relation_type__in=list(relation_types)).values_list(
        "src__entity_key", "dst__entity_key"
    ):
        if src_key and dst_key:
            pairs.add((src_key, dst_key))
    return pairs


def _requirement_text(req) -> str:
    parts = [
        getattr(req, "requirement_id", ""),
        getattr(req, "requirement_name", ""),
        getattr(req, "module", ""),
        getattr(req, "description", ""),
        getattr(req, "acceptance_criteria", ""),
    ]
    return " ".join(str(p).strip() for p in parts if str(p).strip())


def _function_text(func) -> str:
    parts = [
        getattr(func, "name", ""),
        getattr(func, "code", ""),
        getattr(func, "description", ""),
    ]
    return " ".join(str(p).strip() for p in parts if str(p).strip())


def _test_case_text(case) -> str:
    parts = [
        getattr(case, "title", ""),
        getattr(case, "description", ""),
        getattr(case, "preconditions", ""),
        getattr(case, "steps", ""),
        getattr(case, "expected_result", ""),
    ]
    tags = getattr(case, "tags", None) or []
    if isinstance(tags, list):
        parts.extend(str(t) for t in tags if t)
    return " ".join(str(p).strip() for p in parts if str(p).strip())


def _score_maps_to(req, func) -> Tuple[float, str]:
    req_text = _requirement_text(req)
    func_text = _function_text(func)
    score = _text_similarity(req_text, func_text)
    func_name = _normalize_text(getattr(func, "name", ""))
    req_module = _normalize_text(getattr(req, "module", ""))
    if func_name and func_name in _normalize_text(req_text):
        score = max(score, 0.68)
    if req_module and func_name and (req_module in func_name or func_name in req_module):
        score = max(score, 0.62)
    reason = f"需求「{req.requirement_name}」与功能「{func.name}」文本相似度 {score:.2f}"
    return score, reason


def _score_covers(case, target_text: str, target_label: str) -> Tuple[float, str]:
    case_text = _test_case_text(case)
    score = _text_similarity(case_text, target_text)
    title = _normalize_text(getattr(case, "title", ""))
    if title and title in _normalize_text(target_text):
        score = max(score, 0.65)
    reason = f"用例「{case.title}」与「{target_label}」匹配度 {score:.2f}"
    return score, reason


def suggest_maps_to_heuristic(
    requirements: List[Any],
    functions: List[Any],
    *,
    min_confidence: float = 0.5,
    top_k_per_requirement: int = _DEFAULT_TOP_K_MAPS,
    existing_pairs: Optional[Set[Tuple[str, str]]] = None,
) -> List[Dict[str, Any]]:
    existing = existing_pairs or _existing_edge_pairs({REL_MAPS_TO})
    suggestions: List[Dict[str, Any]] = []
    for req in requirements:
        ranked: List[Tuple[float, str, Any]] = []
        for func in functions:
            score, reason = _score_maps_to(req, func)
            if score < min_confidence:
                continue
            src_key = entity_key_biz_req(req.pk)
            dst_key = entity_key_kb_function(func.pk)
            if (src_key, dst_key) in existing:
                continue
            ranked.append((score, reason, func))
        ranked.sort(key=lambda item: item[0], reverse=True)
        for score, reason, func in ranked[: max(1, top_k_per_requirement)]:
            suggestions.append(
                _suggestion_dict(
                    relation_type=REL_MAPS_TO,
                    src_key=entity_key_biz_req(req.pk),
                    dst_key=entity_key_kb_function(func.pk),
                    src_type=ENTITY_BUSINESS_REQUIREMENT,
                    dst_type=ENTITY_KB_FUNCTION,
                    src_label=f"{req.requirement_id} {req.requirement_name}".strip(),
                    dst_label=func.name,
                    src_ref_id=str(req.pk),
                    dst_ref_id=str(func.pk),
                    confidence=score,
                    reason=reason,
                    method="heuristic",
                )
            )
    suggestions.sort(key=lambda item: item["confidence"], reverse=True)
    return suggestions


def suggest_covers_heuristic(
    test_cases: List[Any],
    *,
    requirements: Optional[List[Any]] = None,
    functions: Optional[List[Any]] = None,
    min_confidence: float = 0.5,
    top_k_per_case: int = _DEFAULT_TOP_K_COVERS,
    existing_pairs: Optional[Set[Tuple[str, str]]] = None,
) -> List[Dict[str, Any]]:
    existing = existing_pairs or _existing_edge_pairs({REL_COVERS})
    requirements = requirements or []
    functions = functions or []
    suggestions: List[Dict[str, Any]] = []

    for case in test_cases:
        ranked: List[Tuple[float, str, str, str, str, str, str, str]] = []
        src_key = entity_key_test_case(case.pk)
        for req in requirements:
            score, reason = _score_covers(case, _requirement_text(req), req.requirement_name)
            if score < min_confidence:
                continue
            dst_key = entity_key_biz_req(req.pk)
            if (src_key, dst_key) in existing:
                continue
            ranked.append(
                (
                    score,
                    reason,
                    dst_key,
                    ENTITY_BUSINESS_REQUIREMENT,
                    f"{req.requirement_id} {req.requirement_name}".strip(),
                    str(req.pk),
                    REL_COVERS,
                    "heuristic",
                )
            )
        for func in functions:
            score, reason = _score_covers(case, _function_text(func), func.name)
            if score < min_confidence:
                continue
            dst_key = entity_key_kb_function(func.pk)
            if (src_key, dst_key) in existing:
                continue
            ranked.append(
                (
                    score,
                    reason,
                    dst_key,
                    ENTITY_KB_FUNCTION,
                    func.name,
                    str(func.pk),
                    REL_COVERS,
                    "heuristic",
                )
            )
        ranked.sort(key=lambda item: item[0], reverse=True)
        for score, reason, dst_key, dst_type, dst_label, dst_ref_id, rel, method in ranked[: max(1, top_k_per_case)]:
            suggestions.append(
                _suggestion_dict(
                    relation_type=rel,
                    src_key=src_key,
                    dst_key=dst_key,
                    src_type=ENTITY_TEST_CASE,
                    dst_type=dst_type,
                    src_label=(getattr(case, "title", "") or f"用例 #{case.pk}")[:500],
                    dst_label=dst_label,
                    src_ref_id=str(case.pk),
                    dst_ref_id=dst_ref_id,
                    confidence=score,
                    reason=reason,
                    method=method,
                )
            )
    suggestions.sort(key=lambda item: item["confidence"], reverse=True)
    return suggestions


def _strip_json_fence(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _parse_ai_suggestions(raw: str) -> List[Dict[str, Any]]:
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
        for key in ("suggestions", "items", "data"):
            val = payload.get(key)
            if isinstance(val, list):
                payload = val
                break
        else:
            payload = [payload]
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _build_ai_prompt(
    *,
    requirements: List[Any],
    functions: List[Any],
    test_cases: List[Any],
    relation_types: Set[str],
) -> str:
    lines = [
        "请根据以下实体文本，建议知识图谱边，并给出 0～1 的 confidence。",
        "仅输出 JSON 数组，每项字段：",
        "relation_type（maps_to 或 covers）、src_ref_id、dst_ref_id、",
        "src_entity_type、dst_entity_type、confidence、reason。",
        "",
        "规则：",
        "- maps_to：BusinessRequirement → KbFunction",
        "- covers：TestCase → BusinessRequirement 或 TestCase → KbFunction",
        "- confidence 低于 0.5 的不要输出",
        "",
    ]
    if REL_MAPS_TO in relation_types and requirements and functions:
        lines.append("【业务需求】")
        for req in requirements[:20]:
            lines.append(
                f"- id={req.pk} | {req.requirement_id} {req.requirement_name} | 模块={req.module} | "
                f"描述={(_requirement_text(req))[:240]}"
            )
        lines.append("")
        lines.append("【功能模块】")
        for func in functions[:30]:
            lines.append(f"- id={func.pk} | {func.name} | {_function_text(func)[:180]}")
        lines.append("")
    if REL_COVERS in relation_types and test_cases:
        lines.append("【测试用例】")
        for case in test_cases[:20]:
            lines.append(f"- id={case.pk} | {case.title} | {_test_case_text(case)[:240]}")
        if requirements:
            lines.append("")
            lines.append("【可覆盖需求】")
            for req in requirements[:20]:
                lines.append(f"- id={req.pk} | {req.requirement_name}")
        if functions:
            lines.append("")
            lines.append("【可覆盖功能】")
            for func in functions[:20]:
                lines.append(f"- id={func.pk} | {func.name}")
    return "\n".join(lines)


async def _suggest_via_ai_async(
    *,
    requirements: List[Any],
    functions: List[Any],
    test_cases: List[Any],
    relation_types: Set[str],
    min_confidence: float,
) -> List[Dict[str, Any]]:
    from apps.requirement_analysis.models import AIModelConfig, AIModelService

    config = AIModelConfig.objects.filter(role="writer", is_active=True).order_by("-updated_at").first()
    if not config:
        return []

    prompt = _build_ai_prompt(
        requirements=requirements,
        functions=functions,
        test_cases=test_cases,
        relation_types=relation_types,
    )
    messages = [
        {
            "role": "system",
            "content": "你是测试知识图谱对齐助手，只输出合法 JSON 数组，不要 Markdown 解释。",
        },
        {"role": "user", "content": prompt},
    ]
    try:
        response = await AIModelService.call_openai_compatible_api(
            config, messages, min_tokens=1024,
            meta={"module": "knowledge_graph", "feature": "graph_suggest"},
        )
        content = ((response.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    except Exception as exc:
        logger.warning("AI 图谱边建议失败: %s", exc, exc_info=True)
        return []

    req_map = {str(r.pk): r for r in requirements}
    func_map = {str(f.pk): f for f in functions}
    case_map = {str(c.pk): c for c in test_cases}
    existing = _existing_edge_pairs(relation_types)
    suggestions: List[Dict[str, Any]] = []

    for item in _parse_ai_suggestions(content):
        rel = str(item.get("relation_type") or "").strip()
        if rel not in relation_types:
            continue
        confidence = _clamp_confidence(item.get("confidence", 0))
        if confidence < min_confidence:
            continue
        src_type = str(item.get("src_entity_type") or "").strip()
        dst_type = str(item.get("dst_entity_type") or "").strip()
        src_ref = str(item.get("src_ref_id") or "").strip()
        dst_ref = str(item.get("dst_ref_id") or "").strip()
        reason = str(item.get("reason") or "AI 建议")

        if rel == REL_MAPS_TO:
            req = req_map.get(src_ref)
            func = func_map.get(dst_ref)
            if not req or not func:
                continue
            src_key = entity_key_biz_req(req.pk)
            dst_key = entity_key_kb_function(func.pk)
            suggestions.append(
                _suggestion_dict(
                    relation_type=REL_MAPS_TO,
                    src_key=src_key,
                    dst_key=dst_key,
                    src_type=ENTITY_BUSINESS_REQUIREMENT,
                    dst_type=ENTITY_KB_FUNCTION,
                    src_label=f"{req.requirement_id} {req.requirement_name}".strip(),
                    dst_label=func.name,
                    src_ref_id=str(req.pk),
                    dst_ref_id=str(func.pk),
                    confidence=confidence,
                    reason=reason,
                    method="ai",
                )
            )
        elif rel == REL_COVERS:
            case = case_map.get(src_ref)
            if not case:
                continue
            src_key = entity_key_test_case(case.pk)
            if dst_type == ENTITY_BUSINESS_REQUIREMENT:
                target = req_map.get(dst_ref)
                if not target:
                    continue
                dst_key = entity_key_biz_req(target.pk)
                dst_label = f"{target.requirement_id} {target.requirement_name}".strip()
            elif dst_type == ENTITY_KB_FUNCTION:
                target = func_map.get(dst_ref)
                if not target:
                    continue
                dst_key = entity_key_kb_function(target.pk)
                dst_label = target.name
            else:
                continue
            if (src_key, dst_key) in existing:
                continue
            suggestions.append(
                _suggestion_dict(
                    relation_type=REL_COVERS,
                    src_key=src_key,
                    dst_key=dst_key,
                    src_type=ENTITY_TEST_CASE,
                    dst_type=dst_type,
                    src_label=(case.title or f"用例 #{case.pk}")[:500],
                    dst_label=dst_label,
                    src_ref_id=str(case.pk),
                    dst_ref_id=str(dst_ref),
                    confidence=confidence,
                    reason=reason,
                    method="ai",
                )
            )
    suggestions.sort(key=lambda item: item["confidence"], reverse=True)
    return suggestions


def _merge_suggestions(
    primary: List[Dict[str, Any]],
    secondary: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    merged: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for item in primary + secondary:
        key = (item["relation_type"], item["src"], item["dst"])
        prev = merged.get(key)
        if not prev or item["confidence"] > prev["confidence"]:
            merged[key] = item
    result = list(merged.values())
    result.sort(key=lambda item: item["confidence"], reverse=True)
    return result


def suggest_kg_edges(
    *,
    business_requirement_ids: Optional[List[int]] = None,
    kb_function_ids: Optional[List[int]] = None,
    test_case_ids: Optional[List[int]] = None,
    dataset_id: Optional[str] = None,
    relation_types: Optional[List[str]] = None,
    min_confidence: float = 0.5,
    use_ai: bool = False,
    limit: int = 50,
) -> Dict[str, Any]:
    """建议 maps_to / covers 边，返回带 confidence 的列表（不写库）。"""
    empty = {"suggestions": [], "count": 0, "meta": {"methods": [], "relation_types": []}}
    if not kg_enabled():
        empty["detail"] = "知识图谱已禁用"
        return empty

    rels = {str(r).strip() for r in (relation_types or [REL_MAPS_TO, REL_COVERS]) if str(r).strip()}
    rels &= SUPPORTED_RELATIONS
    if not rels:
        empty["detail"] = "未指定有效的 relation_types"
        return empty

    min_confidence = _clamp_confidence(min_confidence)
    limit = max(1, min(int(limit or 50), 200))
    dataset_id = (dataset_id or "").strip()

    from apps.requirement_analysis.kb_models import KbFunction
    from apps.requirement_analysis.models import BusinessRequirement
    from apps.testcases.models import TestCase

    req_ids = [int(x) for x in (business_requirement_ids or [])]
    func_ids = [int(x) for x in (kb_function_ids or [])]
    case_ids = [int(x) for x in (test_case_ids or [])]

    requirements = list(BusinessRequirement.objects.filter(pk__in=req_ids)) if req_ids else []
    functions_qs = KbFunction.objects.filter(is_active=True)
    if func_ids:
        functions_qs = functions_qs.filter(pk__in=func_ids)
    elif dataset_id:
        functions_qs = functions_qs.filter(dify_dataset_id=dataset_id)
    functions = list(functions_qs[:80])
    test_cases = list(TestCase.objects.filter(pk__in=case_ids)) if case_ids else []

    if REL_MAPS_TO in rels and not requirements:
        requirements = list(BusinessRequirement.objects.all().order_by("-updated_at")[:30])
    if REL_COVERS in rels and test_cases and not requirements and not functions:
        requirements = list(BusinessRequirement.objects.all().order_by("-updated_at")[:30])
        if dataset_id:
            functions = list(functions_qs.filter(dify_dataset_id=dataset_id)[:30])

    suggestions: List[Dict[str, Any]] = []
    methods: List[str] = []

    if REL_MAPS_TO in rels and requirements and functions:
        suggestions.extend(
            suggest_maps_to_heuristic(
                requirements,
                functions,
                min_confidence=min_confidence,
            )
        )
        methods.append("heuristic")

    if REL_COVERS in rels and test_cases and (requirements or functions):
        suggestions.extend(
            suggest_covers_heuristic(
                test_cases,
                requirements=requirements,
                functions=functions,
                min_confidence=min_confidence,
            )
        )
        if "heuristic" not in methods:
            methods.append("heuristic")

    if use_ai and (requirements or functions or test_cases):
        ai_items = asyncio.run(
            _suggest_via_ai_async(
                requirements=requirements,
                functions=functions,
                test_cases=test_cases,
                relation_types=rels,
                min_confidence=min_confidence,
            )
        )
        if ai_items:
            suggestions = _merge_suggestions(ai_items, suggestions)
            methods.append("ai")

    suggestions.sort(key=lambda item: item["confidence"], reverse=True)
    suggestions = suggestions[:limit]

    return {
        "suggestions": suggestions,
        "count": len(suggestions),
        "meta": {
            "methods": methods,
            "relation_types": sorted(rels),
            "min_confidence": min_confidence,
            "use_ai": bool(use_ai),
        },
    }
