"""项目覆盖度统计（需求 / 功能模块 ← covers 边）。"""

from __future__ import annotations

from typing import Any, Dict, List, Set

from .constants import (
    ENTITY_BUSINESS_REQUIREMENT,
    ENTITY_GENERATION_TASK,
    ENTITY_KB_DOCUMENT,
    ENTITY_KB_FUNCTION,
    ENTITY_TEST_CASE,
    REL_COVERS,
    REL_MAPS_TO,
    REL_USED_REFERENCE,
    SOURCE_AI,
)
from .models import KgEdge, KgEntity, kg_enabled
from .query import _entity_to_dict


def _entity_brief(entity: KgEntity) -> Dict[str, Any]:
    return _entity_to_dict(entity)


def _tc_brief(entity: KgEntity) -> Dict[str, Any]:
    data = _entity_brief(entity)
    data["ref_id"] = entity.ref_id
    return data


def get_project_coverage_report(
    project_id: int,
    *,
    limit: int = 100,
) -> Dict[str, Any]:
    """统计项目内用例对业务需求 / 功能模块的 covers 覆盖情况。"""
    empty: Dict[str, Any] = {
        "project_id": project_id,
        "summary": {
            "test_case_count": 0,
            "test_cases_with_covers": 0,
            "test_cases_without_covers_count": 0,
            "covered_requirement_count": 0,
            "covered_function_count": 0,
            "covered_document_count": 0,
            "generation_task_count": 0,
            "mapped_requirement_count": 0,
            "mapped_uncovered_requirement_count": 0,
        },
        "covered_requirements": [],
        "covered_functions": [],
        "covered_documents": [],
        "test_cases_without_covers": [],
        "test_cases_without_covers_truncated": False,
        "mapped_uncovered_requirements": [],
    }
    if not kg_enabled():
        empty["detail"] = "知识图谱已禁用"
        return empty

    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        empty["detail"] = "无效的项目 ID"
        return empty

    limit = max(1, min(int(limit or 100), 200))

    tc_entities = list(
        KgEntity.objects.filter(project_id=project_id, entity_type=ENTITY_TEST_CASE).order_by("-updated_at")
    )
    gen_task_count = KgEntity.objects.filter(
        project_id=project_id, entity_type=ENTITY_GENERATION_TASK
    ).count()

    if not tc_entities and gen_task_count == 0:
        empty["detail"] = "该项目暂无图谱数据"
        return empty

    tc_keys = [e.entity_key for e in tc_entities]
    tc_map = {e.entity_key: e for e in tc_entities}

    covers_edges = list(
        KgEdge.objects.filter(relation_type=REL_COVERS, src__entity_key__in=tc_keys)
        .exclude(source=SOURCE_AI)
        .select_related("src", "dst")
        .order_by("-created_at")
    )

    tc_with_covers: Set[str] = set()
    req_coverage: Dict[str, Dict[str, Any]] = {}
    func_coverage: Dict[str, Dict[str, Any]] = {}
    doc_coverage: Dict[str, Dict[str, Any]] = {}

    for edge in covers_edges:
        src_key = edge.src.entity_key
        tc_with_covers.add(src_key)
        dst = edge.dst
        tc_item = _tc_brief(edge.src)
        if dst.entity_type == ENTITY_BUSINESS_REQUIREMENT:
            bucket = req_coverage.setdefault(
                dst.entity_key,
                {**_entity_brief(dst), "test_cases": []},
            )
            if len(bucket["test_cases"]) < limit:
                bucket["test_cases"].append(tc_item)
        elif dst.entity_type == ENTITY_KB_FUNCTION:
            bucket = func_coverage.setdefault(
                dst.entity_key,
                {**_entity_brief(dst), "test_cases": []},
            )
            if len(bucket["test_cases"]) < limit:
                bucket["test_cases"].append(tc_item)
        elif dst.entity_type == ENTITY_KB_DOCUMENT:
            bucket = doc_coverage.setdefault(
                dst.entity_key,
                {**_entity_brief(dst), "test_cases": []},
            )
            if len(bucket["test_cases"]) < limit:
                bucket["test_cases"].append(tc_item)

    without_covers_all = [e for e in tc_entities if e.entity_key not in tc_with_covers]
    without_covers_count = len(without_covers_all)
    without_covers = [_tc_brief(e) for e in without_covers_all[:limit]]
    without_covers_truncated = without_covers_count > limit

    # 经 maps_to + 项目生成任务引用功能，找出「已映射但未覆盖」的需求
    task_keys = list(
        KgEntity.objects.filter(project_id=project_id, entity_type=ENTITY_GENERATION_TASK).values_list(
            "entity_key", flat=True
        )
    )
    project_func_keys: Set[str] = set()
    if task_keys:
        for edge in KgEdge.objects.filter(
            relation_type=REL_USED_REFERENCE,
            src__entity_key__in=task_keys,
            dst__entity_type=ENTITY_KB_FUNCTION,
        ).select_related("dst"):
            project_func_keys.add(edge.dst.entity_key)

    mapped_req_keys: Set[str] = set()
    mapped_req_map: Dict[str, KgEntity] = {}
    if project_func_keys:
        for edge in KgEdge.objects.filter(
            relation_type=REL_MAPS_TO,
            dst__entity_key__in=project_func_keys,
            src__entity_type=ENTITY_BUSINESS_REQUIREMENT,
        ).select_related("src", "dst"):
            mapped_req_keys.add(edge.src.entity_key)
            mapped_req_map[edge.src.entity_key] = edge.src

    covered_req_keys = set(req_coverage.keys())
    uncovered_mapped_keys = mapped_req_keys - covered_req_keys
    mapped_uncovered = [
        _entity_brief(mapped_req_map[key])
        for key in sorted(uncovered_mapped_keys)
        if key in mapped_req_map
    ][:limit]

    covered_req_list = list(req_coverage.values())[:limit]
    covered_func_list = list(func_coverage.values())[:limit]
    covered_doc_list = list(doc_coverage.values())[:limit]

    requirement_coverage_rate = None
    if mapped_req_keys:
        requirement_coverage_rate = round(len(covered_req_keys & mapped_req_keys) / len(mapped_req_keys), 3)

    test_case_coverage_rate = None
    if tc_entities:
        test_case_coverage_rate = round(len(tc_with_covers) / len(tc_entities), 3)

    return {
        "project_id": project_id,
        "summary": {
            "test_case_count": len(tc_entities),
            "test_cases_with_covers": len(tc_with_covers),
            "test_cases_without_covers_count": without_covers_count,
            "test_case_coverage_rate": test_case_coverage_rate,
            "covered_requirement_count": len(req_coverage),
            "covered_function_count": len(func_coverage),
            "covered_document_count": len(doc_coverage),
            "generation_task_count": gen_task_count,
            "mapped_requirement_count": len(mapped_req_keys),
            "mapped_uncovered_requirement_count": len(uncovered_mapped_keys),
            "mapped_requirement_coverage_rate": requirement_coverage_rate,
        },
        "covered_requirements": covered_req_list,
        "covered_functions": covered_func_list,
        "covered_documents": covered_doc_list,
        "test_cases_without_covers": without_covers,
        "test_cases_without_covers_truncated": without_covers_truncated,
        "mapped_uncovered_requirements": mapped_uncovered,
    }
