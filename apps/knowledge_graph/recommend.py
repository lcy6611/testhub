"""基于知识图谱的 AI 推荐执行：分析覆盖缺口和执行历史，推荐下一步测试目标。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from asgiref.sync import async_to_sync

from .constants import (
    ENTITY_API_REQUEST,
    ENTITY_BUSINESS_REQUIREMENT,
    ENTITY_GENERATION_TASK,
    ENTITY_KB_FUNCTION,
    ENTITY_TEST_CASE,
    ENTITY_UI_PAGE,
    REL_BELONGS_TO,
    REL_COVERS,
    REL_MAPS_TO,
    REL_USED_REFERENCE,
)
from .models import KgEdge, KgEntity, kg_enabled
from .query import _entity_to_dict

logger = logging.getLogger(__name__)


def _collect_project_graph_context(project_id: int) -> Dict[str, Any]:
    """收集项目图谱中与推荐相关的结构化上下文。"""
    # 1. 测试用例节点 + covers 关系
    tc_entities = list(
        KgEntity.objects.filter(project_id=project_id, entity_type=ENTITY_TEST_CASE).order_by("-updated_at")
    )
    tc_keys = {e.entity_key for e in tc_entities}

    covers_edges = list(
        KgEdge.objects.filter(relation_type=REL_COVERS, src__entity_key__in=tc_keys)
        .exclude(source="ai_suggested")
        .select_related("src", "dst")
    )
    tc_covers_map: Dict[str, List[str]] = {}
    covered_req_keys: set = set()
    covered_func_keys: set = set()
    for edge in covers_edges:
        src_key = edge.src.entity_key
        dst_type = edge.dst.entity_type
        tc_covers_map.setdefault(src_key, []).append(f"{dst_type}:{edge.dst.label}")
        if dst_type == ENTITY_BUSINESS_REQUIREMENT:
            covered_req_keys.add(edge.dst.entity_key)
        elif dst_type == ENTITY_KB_FUNCTION:
            covered_func_keys.add(edge.dst.entity_key)

    # 2. 已映射但未覆盖的需求
    task_keys = list(
        KgEntity.objects.filter(project_id=project_id, entity_type=ENTITY_GENERATION_TASK).values_list(
            "entity_key", flat=True
        )
    )
    project_func_keys: set = set()
    if task_keys:
        for edge in KgEdge.objects.filter(
            relation_type=REL_USED_REFERENCE,
            src__entity_key__in=task_keys,
            dst__entity_type=ENTITY_KB_FUNCTION,
        ).select_related("dst"):
            project_func_keys.add(edge.dst.entity_key)

    mapped_req_keys: set = set()
    if project_func_keys:
        for edge in KgEdge.objects.filter(
            relation_type=REL_MAPS_TO,
            dst__entity_key__in=project_func_keys,
            src__entity_type=ENTITY_BUSINESS_REQUIREMENT,
        ).select_related("src"):
            mapped_req_keys.add(edge.src.entity_key)

    uncovered_req_keys = mapped_req_keys - covered_req_keys
    uncovered_reqs = list(
        KgEntity.objects.filter(entity_key__in=uncovered_req_keys).values("entity_key", "label")
    )

    # 3. API 接口节点 + 最后执行结果
    api_entities = list(
        KgEntity.objects.filter(project_id=project_id, entity_type=ENTITY_API_REQUEST).order_by("-updated_at")
    )
    api_status = []
    for ent in api_entities:
        props = ent.properties or {}
        last_exec = props.get("last_execution")
        api_status.append({
            "label": ent.label,
            "ref_id": ent.ref_id,
            "last_execution_passed": last_exec.get("passed") if last_exec else None,
            "last_execution_at": last_exec.get("executed_at") if last_exec else None,
            "has_executed": bool(last_exec),
        })

    # 4. UI 页面节点 + 最后执行结果
    ui_entities = list(
        KgEntity.objects.filter(project_id=project_id, entity_type=ENTITY_UI_PAGE).order_by("-updated_at")
    )
    ui_status = []
    for ent in ui_entities:
        props = ent.properties or {}
        last_exec = props.get("last_execution")
        ui_status.append({
            "label": ent.label,
            "ref_id": ent.ref_id,
            "last_execution_passed": last_exec.get("passed") if last_exec else None,
            "last_execution_at": last_exec.get("executed_at") if last_exec else None,
            "has_executed": bool(last_exec),
        })

    # 5. 未覆盖的用例（没有 covers 边的）
    uncovered_test_cases = [
        {"entity_key": e.entity_key, "label": e.label, "ref_id": e.ref_id}
        for e in tc_entities
        if e.entity_key not in tc_covers_map
    ]

    return {
        "project_id": project_id,
        "stats": {
            "total_test_cases": len(tc_entities),
            "covered_test_cases": len(tc_covers_map),
            "total_api_requests": len(api_entities),
            "total_ui_pages": len(ui_entities),
            "mapped_requirements": len(mapped_req_keys),
            "uncovered_requirements": len(uncovered_req_keys),
            "failed_api_count": sum(1 for a in api_status if a["has_executed"] and a["last_execution_passed"] is False),
            "unexecuted_api_count": sum(1 for a in api_status if not a["has_executed"]),
            "failed_ui_count": sum(1 for u in ui_status if u["has_executed"] and u["last_execution_passed"] is False),
            "unexecuted_ui_count": sum(1 for u in ui_status if not u["has_executed"]),
        },
        "uncovered_requirements": uncovered_reqs[:20],
        "uncovered_test_cases": uncovered_test_cases[:20],
        "api_status": api_status[:30],
        "ui_status": ui_status[:30],
    }


def _build_recommend_prompt(context: Dict[str, Any]) -> List[Dict[str, str]]:
    """构建推荐 LLM 的消息列表。"""
    stats = context["stats"]
    system_prompt = (
        "你是测试质量分析专家。基于知识图谱的项目结构化数据，分析覆盖缺口和执行历史，"
        "推荐下一步应该优先执行的测试目标。\n\n"
        "输出要求：返回 JSON 数组，每项包含以下字段：\n"
        '- type: "api" | "ui" | "testcase" | "coverage_gap"\n'
        "- label: 目标名称\n"
        "- reason: 推荐理由（简短）\n"
        '- priority: "high" | "medium" | "low"\n'
        "- ref_id: 目标 ID（如有）\n\n"
        "推荐原则：\n"
        "1. 失败的 API/UI 执行优先重跑（high）\n"
        "2. 从未执行过的 API/UI 优先覆盖（high）\n"
        "3. 未覆盖的需求对应的用例优先补测（medium）\n"
        "4. 没有覆盖关系的测试用例需要补充关联（low）\n"
        "最多返回 10 条推荐，只返回 JSON 数组，不要其他文字。"
    )

    # 压缩上下文
    parts = [f"项目统计：{json.dumps(stats, ensure_ascii=False)}"]
    if context["uncovered_requirements"]:
        parts.append(f"未覆盖需求：{json.dumps(context['uncovered_requirements'], ensure_ascii=False)}")
    if context["uncovered_test_cases"]:
        parts.append(f"未关联用例：{json.dumps(context['uncovered_test_cases'][:10], ensure_ascii=False)}")
    # 只传有问题的 API/UI
    problematic_apis = [a for a in context["api_status"] if not a["has_executed"] or a["last_execution_passed"] is False]
    if problematic_apis:
        parts.append(f"需关注API：{json.dumps(problematic_apis[:15], ensure_ascii=False)}")
    problematic_uis = [u for u in context["ui_status"] if not u["has_executed"] or u["last_execution_passed"] is False]
    if problematic_uis:
        parts.append(f"需关注UI：{json.dumps(problematic_uis[:15], ensure_ascii=False)}")

    user_content = "\n".join(parts)
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


def _parse_llm_recommendations(content: str) -> List[Dict[str, Any]]:
    """解析 LLM 返回的推荐列表。"""
    text = content.strip()
    # 去掉可能的 markdown code fence
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        items = json.loads(text)
        if isinstance(items, list):
            return items
        if isinstance(items, dict) and "recommendations" in items:
            return items["recommendations"]
    except (json.JSONDecodeError, TypeError):
        pass
    # 尝试提取 JSON 数组
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            items = json.loads(text[start : end + 1])
            if isinstance(items, list):
                return items
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def _build_rule_based_recommendations(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """无 LLM 时的规则兜底推荐。"""
    recs: List[Dict[str, Any]] = []
    stats = context["stats"]

    # 失败的 API
    for api in context["api_status"]:
        if api["has_executed"] and api["last_execution_passed"] is False:
            recs.append({
                "type": "api",
                "label": api["label"],
                "ref_id": api["ref_id"],
                "reason": f"上次执行失败，需要重跑验证",
                "priority": "high",
            })

    # 未执行的 API
    for api in context["api_status"]:
        if not api["has_executed"]:
            recs.append({
                "type": "api",
                "label": api["label"],
                "ref_id": api["ref_id"],
                "reason": "从未执行过，建议首次覆盖",
                "priority": "high",
            })

    # 失败的 UI
    for ui in context["ui_status"]:
        if ui["has_executed"] and ui["last_execution_passed"] is False:
            recs.append({
                "type": "ui",
                "label": ui["label"],
                "ref_id": ui["ref_id"],
                "reason": "上次执行失败，需要重跑验证",
                "priority": "high",
            })

    # 未执行的 UI
    for ui in context["ui_status"]:
        if not ui["has_executed"]:
            recs.append({
                "type": "ui",
                "label": ui["label"],
                "ref_id": ui["ref_id"],
                "reason": "从未执行过，建议首次覆盖",
                "priority": "medium",
            })

    # 未覆盖的需求
    for req in context["uncovered_requirements"][:5]:
        recs.append({
            "type": "coverage_gap",
            "label": req.get("label", ""),
            "ref_id": "",
            "reason": "已映射但未被测试用例覆盖的需求",
            "priority": "medium",
        })

    return recs[:10]


def recommend_execution(project_id: int) -> Dict[str, Any]:
    """主入口：基于图谱数据 + LLM 生成执行推荐。"""
    if not kg_enabled():
        return {"detail": "知识图谱已禁用", "recommendations": [], "summary": ""}

    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return {"detail": "无效的项目 ID", "recommendations": [], "summary": ""}

    context = _collect_project_graph_context(project_id)
    stats = context["stats"]

    # 如果图谱里没有任何数据
    total = (
        stats["total_test_cases"]
        + stats["total_api_requests"]
        + stats["total_ui_pages"]
        + stats["mapped_requirements"]
    )
    if total == 0:
        return {
            "project_id": project_id,
            "detail": "该项目暂无图谱数据，请先同步节点",
            "recommendations": [],
            "summary": "图谱为空，请先在 Step 2 中同步业务对象或知识库。",
            "stats": stats,
        }

    recommendations: List[Dict[str, Any]] = []
    llm_used = False

    # 尝试调 LLM
    try:
        from apps.requirement_analysis.models import AIModelConfig, AIModelService

        writer_cfg = AIModelConfig.objects.filter(role="writer", is_active=True).first()
        if writer_cfg:
            messages = _build_recommend_prompt(context)
            resp = async_to_sync(AIModelService.call_openai_compatible_api)(writer_cfg, messages)
            choice0 = (resp.get("choices") or [{}])[0] or {}
            content = (choice0.get("message") or {}).get("content") or ""
            if content:
                recommendations = _parse_llm_recommendations(content)
                llm_used = True
    except Exception as exc:
        logger.warning("图谱推荐 LLM 调用失败，降级规则推荐: %s", exc, exc_info=True)

    # 兜底规则推荐
    if not recommendations:
        recommendations = _build_rule_based_recommendations(context)

    # 生成摘要
    summary_parts = []
    if stats["uncovered_requirements"] > 0:
        summary_parts.append(f"有 {stats['uncovered_requirements']} 个需求未被测试用例覆盖")
    failed_total = stats["failed_api_count"] + stats["failed_ui_count"]
    if failed_total > 0:
        summary_parts.append(f"有 {failed_total} 个目标上次执行失败")
    unexecuted_total = stats["unexecuted_api_count"] + stats["unexecuted_ui_count"]
    if unexecuted_total > 0:
        summary_parts.append(f"有 {unexecuted_total} 个目标从未执行")
    if not summary_parts:
        summary_parts.append("项目覆盖度良好，无紧急缺口")
    summary = "；".join(summary_parts) + f"。（{'AI 分析' if llm_used else '规则分析'}）"

    return {
        "project_id": project_id,
        "recommendations": recommendations[:10],
        "summary": summary,
        "stats": stats,
        "llm_used": llm_used,
    }
