"""手动建边与边查询辅助。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from django.utils import timezone

from .constants import (
    ENTITY_API_REQUEST,
    ENTITY_BUSINESS_REQUIREMENT,
    ENTITY_KB_FUNCTION,
    ENTITY_TEST_CASE,
    ENTITY_UI_PAGE,
    REL_AUTOMATES,
    REL_COVERS,
    REL_MAPS_TO,
    SOURCE_AI,
    SOURCE_MANUAL,
    SOURCE_SYSTEM,
    CONF_LEVEL_EXTRACTED,
    CONF_LEVEL_INFERRED,
    CONF_LEVEL_AMBIGUOUS,
)
from .models import KgEdge, KgEntity, kg_enabled
from .query import _edge_to_dict, _entity_to_dict
from .registry import (
    ensure_entity,
    entity_key_api_request,
    entity_key_biz_req,
    entity_key_kb_function,
    entity_key_test_case,
    entity_key_ui_page,
    get_entity,
)

MANUAL_RELATION_TYPES = frozenset({REL_MAPS_TO, REL_AUTOMATES})
SUGGESTED_RELATION_TYPES = frozenset({REL_MAPS_TO, REL_COVERS})


def _ensure_business_requirement_entity(req_id: int) -> Optional[KgEntity]:
    from apps.requirement_analysis.models import BusinessRequirement

    req = BusinessRequirement.objects.filter(pk=req_id).first()
    if not req:
        return None
    label = f"{req.requirement_id} {req.requirement_name}".strip()[:500]
    return ensure_entity(
        entity_key_biz_req(req.pk),
        ENTITY_BUSINESS_REQUIREMENT,
        label=label,
        ref_app="requirement_analysis",
        ref_id=str(req.pk),
        properties={
            "requirement_id": req.requirement_id,
            "module": req.module,
        },
    )


def _ensure_kb_function_entity(func_id: int) -> Optional[KgEntity]:
    from apps.requirement_analysis.kb_models import KbFunction

    func = KbFunction.objects.filter(pk=func_id, is_active=True).first()
    if not func:
        return None
    return ensure_entity(
        entity_key_kb_function(func.pk),
        ENTITY_KB_FUNCTION,
        label=func.name,
        ref_app="requirement_analysis",
        ref_id=str(func.pk),
        properties={"code": func.code, "dify_dataset_id": func.dify_dataset_id},
    )


def _ensure_test_case_entity(case_id: int) -> Optional[KgEntity]:
    from apps.testcases.models import TestCase

    case = TestCase.objects.filter(pk=case_id).first()
    if not case:
        return None
    return ensure_entity(
        entity_key_test_case(case.pk),
        ENTITY_TEST_CASE,
        label=(case.title or f"用例 #{case.pk}")[:500],
        ref_app="testcases",
        ref_id=str(case.pk),
        project_id=getattr(case, "project_id", None),
    )


def _ensure_api_request_entity(req_id: int) -> Optional[KgEntity]:
    from .builder import sync_api_request

    sync_api_request(req_id)
    return get_entity(entity_key_api_request(req_id))


def _ensure_ui_page_entity(page_id: int) -> Optional[KgEntity]:
    from .builder import sync_ui_page

    sync_ui_page(page_id)
    return get_entity(entity_key_ui_page(page_id))


def resolve_manual_edge_entities(payload: Dict[str, Any]) -> Tuple[Optional[KgEntity], Optional[KgEntity], str]:
    """解析手动建边请求体，返回 (src, dst, error_message)。"""
    src_key = (payload.get("src") or payload.get("src_entity_key") or "").strip()
    dst_key = (payload.get("dst") or payload.get("dst_entity_key") or "").strip()

    biz_req_id = payload.get("business_requirement_id")
    kb_func_id = payload.get("kb_function_id")
    if biz_req_id is not None and not src_key:
        try:
            src_ent = _ensure_business_requirement_entity(int(biz_req_id))
        except (TypeError, ValueError):
            src_ent = None
        if not src_ent:
            return None, None, f"业务需求不存在: {biz_req_id}"
        src_key = src_ent.entity_key
    if kb_func_id is not None and not dst_key:
        try:
            dst_ent = _ensure_kb_function_entity(int(kb_func_id))
        except (TypeError, ValueError):
            dst_ent = None
        if not dst_ent:
            return None, None, f"功能模块不存在或未启用: {kb_func_id}"
        dst_key = dst_ent.entity_key

    test_case_id = payload.get("test_case_id")
    api_request_id = payload.get("api_request_id")
    ui_page_id = payload.get("ui_page_id")
    relation_type = (payload.get("relation_type") or "").strip()

    if test_case_id is not None and not src_key:
        try:
            src_ent = _ensure_test_case_entity(int(test_case_id))
        except (TypeError, ValueError):
            src_ent = None
        if not src_ent:
            return None, None, f"测试用例不存在: {test_case_id}"
        src_key = src_ent.entity_key
    if api_request_id is not None and not dst_key:
        try:
            dst_ent = _ensure_api_request_entity(int(api_request_id))
        except (TypeError, ValueError):
            dst_ent = None
        if not dst_ent:
            return None, None, f"API 接口不存在: {api_request_id}"
        dst_key = dst_ent.entity_key
    if ui_page_id is not None and not dst_key:
        try:
            dst_ent = _ensure_ui_page_entity(int(ui_page_id))
        except (TypeError, ValueError):
            dst_ent = None
        if not dst_ent:
            return None, None, f"UI 页面不存在: {ui_page_id}"
        dst_key = dst_ent.entity_key

    if relation_type == REL_AUTOMATES and test_case_id is None and api_request_id is None and ui_page_id is None:
        if src_key and not get_entity(src_key):
            try:
                case_id = int(str(src_key).split(":", 1)[1])
            except (IndexError, TypeError, ValueError):
                case_id = None
            if case_id is not None:
                src_ent = _ensure_test_case_entity(case_id)
                if src_ent:
                    src_key = src_ent.entity_key
        if dst_key and not get_entity(dst_key):
            dst_ent = None
            if str(dst_key).startswith("api_req:"):
                try:
                    dst_ent = _ensure_api_request_entity(int(str(dst_key).split(":", 1)[1]))
                except (IndexError, TypeError, ValueError):
                    dst_ent = None
            elif str(dst_key).startswith("ui_page:"):
                try:
                    dst_ent = _ensure_ui_page_entity(int(str(dst_key).split(":", 1)[1]))
                except (IndexError, TypeError, ValueError):
                    dst_ent = None
            if dst_ent:
                dst_key = dst_ent.entity_key

    if not src_key or not dst_key:
        return None, None, (
            "请提供 src/dst 实体键，或 business_requirement_id + kb_function_id，"
            "或 test_case_id + api_request_id/ui_page_id（relation_type=automates）"
        )

    src = get_entity(src_key)
    dst = get_entity(dst_key)
    if not src:
        return None, None, f"源实体不存在: {src_key}"
    if not dst:
        return None, None, f"目标实体不存在: {dst_key}"
    return src, dst, ""


def resolve_suggestion_entities(payload: Dict[str, Any]) -> Tuple[Optional[KgEntity], Optional[KgEntity], str]:
    """从建议项解析实体，必要时自动 ensure 注册。"""
    relation_type = (payload.get("relation_type") or "").strip()
    src_key = (payload.get("src") or payload.get("src_entity_key") or "").strip()
    dst_key = (payload.get("dst") or payload.get("dst_entity_key") or "").strip()
    src_type = (payload.get("src_entity_type") or "").strip()
    dst_type = (payload.get("dst_entity_type") or "").strip()

    if relation_type == REL_MAPS_TO:
        src_ref = payload.get("src_ref_id")
        dst_ref = payload.get("dst_ref_id")
        if src_ref is not None and not src_key:
            try:
                src_ent = _ensure_business_requirement_entity(int(src_ref))
            except (TypeError, ValueError):
                src_ent = None
            if not src_ent:
                return None, None, f"业务需求不存在: {src_ref}"
            src_key = src_ent.entity_key
        if dst_ref is not None and not dst_key:
            try:
                dst_ent = _ensure_kb_function_entity(int(dst_ref))
            except (TypeError, ValueError):
                dst_ent = None
            if not dst_ent:
                return None, None, f"功能模块不存在或未启用: {dst_ref}"
            dst_key = dst_ent.entity_key
    elif relation_type == REL_COVERS:
        src_ref = payload.get("src_ref_id")
        dst_ref = payload.get("dst_ref_id")
        if src_ref is not None and not src_key:
            try:
                src_ent = _ensure_test_case_entity(int(src_ref))
            except (TypeError, ValueError):
                src_ent = None
            if not src_ent:
                return None, None, f"测试用例不存在: {src_ref}"
            src_key = src_ent.entity_key
        if dst_ref is not None and not dst_key:
            if dst_type == ENTITY_BUSINESS_REQUIREMENT:
                try:
                    dst_ent = _ensure_business_requirement_entity(int(dst_ref))
                except (TypeError, ValueError):
                    dst_ent = None
                if not dst_ent:
                    return None, None, f"业务需求不存在: {dst_ref}"
                dst_key = dst_ent.entity_key
            elif dst_type == ENTITY_KB_FUNCTION:
                try:
                    dst_ent = _ensure_kb_function_entity(int(dst_ref))
                except (TypeError, ValueError):
                    dst_ent = None
                if not dst_ent:
                    return None, None, f"功能模块不存在或未启用: {dst_ref}"
                dst_key = dst_ent.entity_key

    if not src_key or not dst_key:
        return None, None, "建议项缺少 src/dst 或 ref_id"

    src = get_entity(src_key)
    dst = get_entity(dst_key)
    if not src:
        return None, None, f"源实体不存在: {src_key}"
    if not dst:
        return None, None, f"目标实体不存在: {dst_key}"
    return src, dst, ""


def _validate_suggested_edge_endpoints(src: KgEntity, dst: KgEntity, relation_type: str) -> None:
    if relation_type == REL_MAPS_TO:
        if src.entity_type != ENTITY_BUSINESS_REQUIREMENT or dst.entity_type != ENTITY_KB_FUNCTION:
            raise ValueError("maps_to 边仅支持 BusinessRequirement → KbFunction")
    elif relation_type == REL_COVERS:
        if src.entity_type != ENTITY_TEST_CASE:
            raise ValueError("covers 边源节点须为 TestCase")
        if dst.entity_type not in (ENTITY_BUSINESS_REQUIREMENT, ENTITY_KB_FUNCTION):
            raise ValueError("covers 边目标须为 BusinessRequirement 或 KbFunction")
    else:
        raise ValueError(f"暂不支持建议关系: {relation_type}")


def create_suggested_kg_edge(
    *,
    src: KgEntity,
    dst: KgEntity,
    relation_type: str,
    confidence: Optional[float] = None,
    project_id: Optional[int] = None,
    created_by=None,
    meta: Optional[Dict[str, Any]] = None,
) -> KgEdge:
    """写入 AI 建议边（source=ai_suggested）；不覆盖 manual/system 边。"""
    if not kg_enabled():
        raise ValueError("知识图谱已禁用")

    relation_type = (relation_type or "").strip()
    if relation_type not in SUGGESTED_RELATION_TYPES:
        raise ValueError(f"暂不支持建议关系: {relation_type}")
    _validate_suggested_edge_endpoints(src, dst, relation_type)

    try:
        confidence_val = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence_val = None
    if confidence_val is not None:
        confidence_val = max(0.0, min(1.0, round(confidence_val, 3)))
    # 置信度等级：>=0.6 视为推断，否则歧义（对齐 content_extractor 阈值）
    if confidence_val is not None and confidence_val < 0.6:
        conf_level = CONF_LEVEL_AMBIGUOUS
    else:
        conf_level = CONF_LEVEL_INFERRED

    meta_payload = dict(meta or {})
    existing = KgEdge.objects.filter(src=src, dst=dst, relation_type=relation_type).first()
    if existing:
        if existing.source in (SOURCE_MANUAL, SOURCE_SYSTEM):
            existing._kg_skipped = True  # type: ignore[attr-defined]
            existing._kg_created = False  # type: ignore[attr-defined]
            return existing
        existing.source = SOURCE_AI
        if confidence_val is not None:
            existing.confidence = confidence_val
        existing.confidence_level = conf_level
        existing.meta = {**(existing.meta or {}), **meta_payload}
        existing.project_id = project_id or existing.project_id or src.project_id or dst.project_id
        if created_by is not None:
            existing.created_by = created_by
        existing.save(
            update_fields=["source", "confidence", "confidence_level", "meta", "project_id", "created_by"]
        )
        existing._kg_skipped = False  # type: ignore[attr-defined]
        existing._kg_created = False  # type: ignore[attr-defined]
        return existing

    edge = KgEdge.objects.create(
        src=src,
        dst=dst,
        relation_type=relation_type,
        project_id=project_id or src.project_id or dst.project_id,
        source=SOURCE_AI,
        confidence=confidence_val,
        confidence_level=conf_level,
        meta=meta_payload,
        created_by=created_by,
    )
    edge._kg_skipped = False  # type: ignore[attr-defined]
    edge._kg_created = True  # type: ignore[attr-defined]
    return edge


def persist_kg_edge_suggestions(
    suggestions: list[Dict[str, Any]],
    *,
    created_by=None,
    min_confidence: float = 0.0,
) -> Dict[str, Any]:
    """批量持久化建议边，返回 created / updated / skipped / errors。"""
    created: list[Dict[str, Any]] = []
    updated: list[Dict[str, Any]] = []
    skipped: list[Dict[str, Any]] = []
    errors: list[Dict[str, Any]] = []

    try:
        min_confidence = max(0.0, min(1.0, float(min_confidence)))
    except (TypeError, ValueError):
        min_confidence = 0.0

    for index, item in enumerate(suggestions or []):
        if not isinstance(item, dict):
            errors.append({"index": index, "detail": "建议项格式无效"})
            continue
        try:
            confidence_raw = item.get("confidence", 0)
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            errors.append({"index": index, "detail": "confidence 无效"})
            continue
        if confidence < min_confidence:
            skipped.append(
                {
                    "index": index,
                    "src": item.get("src"),
                    "dst": item.get("dst"),
                    "relation_type": item.get("relation_type"),
                    "detail": f"confidence {confidence} 低于阈值 {min_confidence}",
                }
            )
            continue

        src, dst, err = resolve_suggestion_entities(item)
        if err:
            errors.append({"index": index, "detail": err})
            continue

        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        meta = {
            **meta,
            "reason": item.get("reason") or meta.get("reason") or "",
            "method": item.get("method") or meta.get("method") or "",
        }
        try:
            edge = create_suggested_kg_edge(
                src=src,
                dst=dst,
                relation_type=str(item.get("relation_type") or "").strip(),
                confidence=confidence,
                project_id=item.get("project_id"),
                created_by=created_by,
                meta=meta,
            )
        except ValueError as exc:
            errors.append({"index": index, "detail": str(exc)})
            continue

        response = edge_to_response(edge)
        if getattr(edge, "_kg_skipped", False):
            skipped.append({**response, "detail": "已存在 manual/system 边，未覆盖"})
        elif getattr(edge, "_kg_created", True):
            created.append(response)
        else:
            updated.append(response)

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "count": {
            "created": len(created),
            "updated": len(updated),
            "skipped": len(skipped),
            "errors": len(errors),
        },
    }


def list_pending_suggested_edges(
    *,
    relation_type: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """列出待确认的 AI 建议边（source=ai_suggested）。"""
    if not kg_enabled():
        return {"edges": [], "count": 0, "detail": "知识图谱已禁用"}

    limit = max(1, min(int(limit or 100), 200))
    qs = (
        KgEdge.objects.filter(source=SOURCE_AI)
        .select_related("src", "dst")
        .order_by("-confidence", "-created_at")
    )
    rel_filter = (relation_type or "").strip()
    if rel_filter:
        qs = qs.filter(relation_type=rel_filter)

    edges = list(qs[:limit])
    return {
        "edges": [edge_to_response(edge) for edge in edges],
        "count": len(edges),
        "source": SOURCE_AI,
    }


def confirm_suggested_kg_edges(
    edge_ids: list[int],
    *,
    created_by=None,
) -> Dict[str, Any]:
    """确认 AI 建议边：maps_to → manual，covers → system。"""
    confirmed: list[Dict[str, Any]] = []
    errors: list[Dict[str, Any]] = []

    for edge_id in edge_ids or []:
        try:
            pk = int(edge_id)
        except (TypeError, ValueError):
            errors.append({"edge_id": edge_id, "detail": "无效的边 ID"})
            continue
        edge = (
            KgEdge.objects.filter(pk=pk, source=SOURCE_AI)
            .select_related("src", "dst")
            .first()
        )
        if not edge:
            errors.append({"edge_id": pk, "detail": "待确认边不存在或已处理"})
            continue

        new_source = SOURCE_MANUAL if edge.relation_type == REL_MAPS_TO else SOURCE_SYSTEM
        meta = dict(edge.meta or {})
        meta["confirmed_at"] = timezone.now().isoformat()
        if created_by is not None:
            meta["confirmed_by"] = getattr(created_by, "pk", None)
        edge.source = new_source
        edge.confidence_level = CONF_LEVEL_EXTRACTED
        edge.meta = meta
        edge.save(update_fields=["source", "confidence_level", "meta"])
        edge._kg_created = False  # type: ignore[attr-defined]
        confirmed.append(edge_to_response(edge))

    return {
        "confirmed": confirmed,
        "errors": errors,
        "count": {"confirmed": len(confirmed), "errors": len(errors)},
    }


def reject_suggested_kg_edges(edge_ids: list[int]) -> Dict[str, Any]:
    """拒绝 AI 建议边（删除 source=ai_suggested 的记录）。"""
    rejected: list[int] = []
    errors: list[Dict[str, Any]] = []

    for edge_id in edge_ids or []:
        try:
            pk = int(edge_id)
        except (TypeError, ValueError):
            errors.append({"edge_id": edge_id, "detail": "无效的边 ID"})
            continue
        deleted, _ = KgEdge.objects.filter(pk=pk, source=SOURCE_AI).delete()
        if deleted:
            rejected.append(pk)
        else:
            errors.append({"edge_id": pk, "detail": "待确认边不存在或已处理"})

    return {
        "rejected": rejected,
        "errors": errors,
        "count": {"rejected": len(rejected), "errors": len(errors)},
    }


def create_manual_kg_edge(
    *,
    src: KgEntity,
    dst: KgEntity,
    relation_type: str = REL_MAPS_TO,
    project_id: Optional[int] = None,
    created_by=None,
    meta: Optional[Dict[str, Any]] = None,
) -> KgEdge:
    if not kg_enabled():
        raise ValueError("知识图谱已禁用")
    relation_type = (relation_type or REL_MAPS_TO).strip()
    if relation_type not in MANUAL_RELATION_TYPES:
        raise ValueError(f"暂不支持手动创建关系: {relation_type}")

    if src.entity_type == ENTITY_BUSINESS_REQUIREMENT and dst.entity_type == ENTITY_KB_FUNCTION:
        pass
    elif relation_type == REL_MAPS_TO:
        raise ValueError("maps_to 边当前仅支持 BusinessRequirement → KbFunction")
    elif relation_type == REL_AUTOMATES:
        if src.entity_type != ENTITY_TEST_CASE:
            raise ValueError("automates 边源节点须为 TestCase")
        if dst.entity_type not in (ENTITY_API_REQUEST, ENTITY_UI_PAGE):
            raise ValueError("automates 边目标须为 ApiRequest 或 UiPageObject")
    else:
        raise ValueError(f"暂不支持手动创建关系: {relation_type}")

    edge, created = KgEdge.objects.update_or_create(
        src=src,
        dst=dst,
        relation_type=relation_type,
        defaults={
            "project_id": project_id or src.project_id or dst.project_id,
            "source": SOURCE_MANUAL,
            "confidence": None,
            "confidence_level": CONF_LEVEL_EXTRACTED,
            "meta": meta or {},
            "created_by": created_by,
        },
    )
    edge._kg_created = created  # type: ignore[attr-defined]
    return edge


def edge_to_response(edge: KgEdge) -> Dict[str, Any]:
    return {
        "id": edge.pk,
        **_edge_to_dict(edge),
        "source": edge.source,
        "confidence": edge.confidence,
        "confidence_level": edge.confidence_level,
        "src_node": _entity_to_dict(edge.src),
        "dst_node": _entity_to_dict(edge.dst),
        "created": getattr(edge, "_kg_created", True),
        "skipped": getattr(edge, "_kg_skipped", False),
    }


def list_kg_edges_for_entity(
    entity_key: str,
    *,
    direction: str = "both",
    source: Optional[str] = None,
    relation_type: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """列出与某实体相关的边（默认仅 manual / maps_to）。"""
    entity = get_entity(entity_key)
    if not entity:
        return {"entity": None, "edges": [], "count": 0, "detail": "实体不存在"}

    direction = (direction or "both").strip().lower()
    if direction not in ("both", "out", "in"):
        direction = "both"

    source_filter = (source or SOURCE_MANUAL).strip().lower()
    rel_filter = (relation_type or "").strip() or None
    limit = max(1, min(int(limit or 100), 200))

    qs_parts = []
    if direction in ("both", "out"):
        qs_out = KgEdge.objects.filter(src=entity).select_related("src", "dst")
        if rel_filter:
            qs_out = qs_out.filter(relation_type=rel_filter)
        if source_filter and source_filter != "all":
            qs_out = qs_out.filter(source=source_filter)
        qs_parts.append(qs_out)
    if direction in ("both", "in"):
        qs_in = KgEdge.objects.filter(dst=entity).select_related("src", "dst")
        if rel_filter:
            qs_in = qs_in.filter(relation_type=rel_filter)
        if source_filter and source_filter != "all":
            qs_in = qs_in.filter(source=source_filter)
        qs_parts.append(qs_in)

    seen: set[int] = set()
    edges: list[KgEdge] = []
    for qs in qs_parts:
        for edge in qs.order_by("-created_at")[:limit]:
            if edge.pk in seen:
                continue
            seen.add(edge.pk)
            edges.append(edge)
            if len(edges) >= limit:
                break
        if len(edges) >= limit:
            break

    return {
        "entity": _entity_to_dict(entity),
        "edges": [edge_to_response(e) for e in edges],
        "count": len(edges),
    }
