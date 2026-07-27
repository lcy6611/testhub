"""执行结果回写：将 API/UI 执行历史写入图谱节点 properties。"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .models import kg_enabled
from .registry import entity_key_api_request, entity_key_ui_page, get_entity

logger = logging.getLogger(__name__)


def _infer_api_execution_passed(history) -> bool:
    if getattr(history, "error_message", None):
        return False
    results = getattr(history, "assertions_results", None)
    if isinstance(results, list) and results:
        return all(bool(item.get("passed")) for item in results if isinstance(item, dict))
    status_code = getattr(history, "status_code", None)
    if status_code is not None:
        return 200 <= int(status_code) < 400
    return False


def build_api_execution_snapshot(history) -> Dict[str, Any]:
    """从 RequestHistory 构建 last_execution 快照。"""
    executed_at = getattr(history, "executed_at", None)
    executed_by = getattr(history, "executed_by", None)
    error_message = (getattr(history, "error_message", None) or "")[:500]
    return {
        "history_id": history.pk,
        "executed_at": executed_at.isoformat() if executed_at else None,
        "status_code": getattr(history, "status_code", None),
        "response_time_ms": getattr(history, "response_time", None),
        "passed": _infer_api_execution_passed(history),
        "error_message": error_message,
        "executed_by_id": getattr(executed_by, "pk", None),
    }


def writeback_api_request_execution(history) -> bool:
    """将 API 请求执行结果写入 api_req 节点 properties.last_execution。"""
    if not kg_enabled():
        return False
    request_id = getattr(history, "request_id", None)
    if not request_id:
        request = getattr(history, "request", None)
        request_id = getattr(request, "pk", None)
    if not request_id:
        return False

    try:
        entity = get_entity(entity_key_api_request(request_id))
        if not entity:
            from .builder import sync_api_request

            sync_api_request(request_id)
            entity = get_entity(entity_key_api_request(request_id))
        if not entity:
            return False

        props = dict(entity.properties or {})
        props["last_execution"] = build_api_execution_snapshot(history)
        entity.properties = props
        entity.save(update_fields=["properties", "updated_at"])
        return True
    except Exception as exc:
        logger.warning("知识图谱回写 ApiRequest 执行结果失败: %s", exc, exc_info=True)
        return False


def safe_writeback_api_request_execution(history) -> None:
    """安全调用回写，供 API 测试各执行入口使用。"""
    try:
        writeback_api_request_execution(history)
    except Exception as exc:
        logger.warning("知识图谱回写 API 执行结果失败: %s", exc, exc_info=True)


def _infer_ui_execution_passed(status: Optional[str], error_message: Optional[str] = None) -> bool:
    if error_message:
        return False
    return (status or "").strip().lower() in ("passed", "success")


def build_ui_page_execution_snapshot(
    *,
    execution_id: Optional[int] = None,
    status: str = "",
    passed: Optional[bool] = None,
    execution_time_sec: Optional[float] = None,
    error_message: str = "",
    executed_at=None,
    finished_at=None,
    executed_by_id: Optional[int] = None,
    source: str = "ui_test_case",
    source_id: Optional[int] = None,
) -> Dict[str, Any]:
    """构建 UI 页面对象 last_execution 快照。"""
    status_norm = (status or "").strip().lower()
    passed_val = _infer_ui_execution_passed(status_norm, error_message) if passed is None else bool(passed)
    return {
        "execution_id": execution_id,
        "source": source,
        "source_id": source_id,
        "status": status_norm or None,
        "passed": passed_val,
        "execution_time_sec": execution_time_sec,
        "error_message": (error_message or "")[:500],
        "executed_at": executed_at.isoformat() if executed_at else None,
        "finished_at": finished_at.isoformat() if finished_at else None,
        "executed_by_id": executed_by_id,
    }


def build_ui_page_execution_snapshot_from_case_execution(execution) -> Dict[str, Any]:
    created_by = getattr(execution, "created_by", None)
    return build_ui_page_execution_snapshot(
        execution_id=execution.pk,
        status=getattr(execution, "status", ""),
        execution_time_sec=getattr(execution, "execution_time", None),
        error_message=getattr(execution, "error_message", "") or "",
        executed_at=getattr(execution, "started_at", None) or getattr(execution, "created_at", None),
        finished_at=getattr(execution, "finished_at", None),
        executed_by_id=getattr(created_by, "pk", None),
        source="ui_test_case",
        source_id=getattr(execution, "test_case_id", None),
    )


def resolve_page_object_ids_for_ui_test_case(test_case_id: int) -> list[int]:
    from apps.ui_automation.models import PageObjectElement, TestCaseStep

    element_ids = TestCaseStep.objects.filter(
        test_case_id=test_case_id,
        element_id__isnull=False,
    ).values_list("element_id", flat=True).distinct()
    if not element_ids:
        return []
    return list(
        PageObjectElement.objects.filter(element_id__in=element_ids)
        .values_list("page_object_id", flat=True)
        .distinct()
    )


def resolve_page_object_ids_for_script(script_id: int) -> list[int]:
    from apps.ui_automation.models import ScriptStep

    return list(
        ScriptStep.objects.filter(script_id=script_id, page_object_id__isnull=False)
        .values_list("page_object_id", flat=True)
        .distinct()
    )


def writeback_ui_page_execution(page_id: int, snapshot: Dict[str, Any]) -> bool:
    """将 UI 执行结果写入 ui_page 节点 properties.last_execution。"""
    if not kg_enabled():
        return False
    try:
        entity = get_entity(entity_key_ui_page(page_id))
        if not entity:
            from .builder import sync_ui_page

            sync_ui_page(page_id)
            entity = get_entity(entity_key_ui_page(page_id))
        if not entity:
            return False

        props = dict(entity.properties or {})
        props["last_execution"] = snapshot
        entity.properties = props
        entity.save(update_fields=["properties", "updated_at"])
        return True
    except Exception as exc:
        logger.warning("知识图谱回写 UiPageObject 执行结果失败: %s", exc, exc_info=True)
        return False


def writeback_ui_test_case_execution(execution) -> int:
    """根据 UI 用例步骤关联的页面对象回写执行结果，返回更新节点数。"""
    test_case_id = getattr(execution, "test_case_id", None)
    if not test_case_id:
        return 0
    page_ids = resolve_page_object_ids_for_ui_test_case(int(test_case_id))
    if not page_ids:
        return 0
    snapshot = build_ui_page_execution_snapshot_from_case_execution(execution)
    return sum(1 for pid in page_ids if writeback_ui_page_execution(pid, snapshot))


def writeback_ui_script_execution_result(
    script_id: int,
    *,
    status: str,
    execution_time_sec: Optional[float] = None,
    error_message: str = "",
    started_at=None,
    finished_at=None,
    executed_by_id: Optional[int] = None,
) -> int:
    page_ids = resolve_page_object_ids_for_script(script_id)
    if not page_ids:
        return 0
    snapshot = build_ui_page_execution_snapshot(
        status=status,
        execution_time_sec=execution_time_sec,
        error_message=error_message,
        executed_at=started_at,
        finished_at=finished_at,
        executed_by_id=executed_by_id,
        source="ui_script",
        source_id=script_id,
    )
    return sum(1 for pid in page_ids if writeback_ui_page_execution(pid, snapshot))


def safe_writeback_ui_test_case_execution(execution) -> None:
    try:
        writeback_ui_test_case_execution(execution)
    except Exception as exc:
        logger.warning("知识图谱回写 UI 用例执行结果失败: %s", exc, exc_info=True)


def safe_writeback_ui_script_execution_result(script_id: int, **kwargs) -> None:
    try:
        writeback_ui_script_execution_result(script_id, **kwargs)
    except Exception as exc:
        logger.warning("知识图谱回写 UI 脚本执行结果失败: %s", exc, exc_info=True)
