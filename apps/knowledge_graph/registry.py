"""实体键生成与注册。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .constants import (
    ENTITY_FUNCTION_POINT,
    ENTITY_GENERATION_TASK,
    ENTITY_KB_CHAT_SESSION,
    ENTITY_KB_DOCUMENT,
    ENTITY_BUSINESS_REQUIREMENT,
    ENTITY_KB_FUNCTION,
    ENTITY_PROJECT,
    ENTITY_REQUIREMENT_DOCUMENT,
    ENTITY_TEST_CASE,
)
from .models import KgEntity, kg_enabled


def entity_key_project(project_id: int) -> str:
    return f"project:{project_id}"


def entity_key_gen_task(task_id: str) -> str:
    return f"gen_task:{task_id}"


def entity_key_test_case(case_id: int) -> str:
    return f"tc:{case_id}"


def entity_key_kb_function(func_id: int) -> str:
    return f"kb_func:{func_id}"


def entity_key_kb_document(dataset_id: str, document_id: str) -> str:
    return f"kb_doc:{dataset_id}:{document_id}"


def entity_key_kb_chat(session_id: str) -> str:
    return f"kb_chat:{session_id}"


def entity_key_req_doc(doc_id: int) -> str:
    return f"req_doc:{doc_id}"


def entity_key_biz_req(req_id: int) -> str:
    return f"biz_req:{req_id}"


def entity_key_api_request(req_id: int) -> str:
    return f"api_req:{req_id}"


def entity_key_ui_page(page_id: int) -> str:
    return f"ui_page:{page_id}"


def entity_key_function_point(dataset_id: str, document_id: str, point_index: int) -> str:
    return f"fp:{dataset_id}:{document_id}:{point_index}"


def entity_key_native_kb(native_kb_id: int) -> str:
    return f"native_kb:{native_kb_id}"


def entity_key_native_doc(native_doc_id: int) -> str:
    return f"native_doc:{native_doc_id}"


def ensure_entity(
    entity_key: str,
    entity_type: str,
    *,
    label: str = "",
    ref_app: str = "",
    ref_id: str = "",
    dataset_id: str = "",
    project_id: Optional[int] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Optional[KgEntity]:
    if not kg_enabled():
        return None
    props = properties or {}
    entity, _ = KgEntity.objects.update_or_create(
        entity_key=entity_key,
        defaults={
            "entity_type": entity_type,
            "label": (label or entity_key)[:500],
            "ref_app": ref_app or "",
            "ref_id": str(ref_id or ""),
            "dataset_id": dataset_id or "",
            "project_id": project_id,
            "properties": props,
        },
    )
    return entity


def get_entity(entity_key: str) -> Optional[KgEntity]:
    if not kg_enabled():
        return None
    return KgEntity.objects.filter(entity_key=entity_key).first()
