"""从业务对象自动建边。"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model

from .constants import (
    ENTITY_API_REQUEST,
    ENTITY_BUSINESS_REQUIREMENT,
    ENTITY_FUNCTION_POINT,
    ENTITY_GENERATION_TASK,
    ENTITY_KB_CHAT_SESSION,
    ENTITY_KB_DOCUMENT,
    ENTITY_KB_FUNCTION,
    ENTITY_NATIVE_KB,
    ENTITY_NATIVE_KB_DOCUMENT,
    ENTITY_PROJECT,
    ENTITY_REQUIREMENT_DOCUMENT,
    ENTITY_TEST_CASE,
    ENTITY_UI_PAGE,
    REL_COVERS,
    REL_BELONGS_TO,
    REL_CONTAINS,
    REL_DERIVED_FROM,
    REL_DEPENDS_ON,
    REL_IMPACTS,
    REL_MAPS_TO,
    REL_PROVENANCE,
    REL_REFERENCES,
    REL_RELATED,
    REL_USED_REFERENCE,
    SOURCE_SYSTEM,
    CONF_LEVEL_EXTRACTED,
)
from .models import KgEdge, KgEntity, kg_enabled
from .registry import (
    ensure_entity,
    get_entity,
    entity_key_api_request,
    entity_key_biz_req,
    entity_key_gen_task,
    entity_key_kb_chat,
    entity_key_kb_document,
    entity_key_kb_function,
    entity_key_native_doc,
    entity_key_native_kb,
    entity_key_project,
    entity_key_req_doc,
    entity_key_test_case,
    entity_key_ui_page,
)

User = get_user_model()
logger = logging.getLogger(__name__)


def _resolve_mapped_ids(project_id: int, module: str) -> List[int]:
    """通过 ProjectMapping 表查核心项目关联的模块项目 ID 列表。"""
    try:
        from apps.projects.models import ProjectMapping

        return list(
            ProjectMapping.objects.filter(
                project_id=project_id, module=module,
            ).values_list("external_project_id", flat=True)
        )
    except Exception as exc:
        logger.warning("查询 ProjectMapping 失败: %s", exc)
        return []

_KB_RELATION_MAP = {
    "depends_on": REL_DEPENDS_ON,
    "impacts": REL_IMPACTS,
    "related": REL_RELATED,
}


def _link(
    src: Optional[KgEntity],
    dst: Optional[KgEntity],
    relation_type: str,
    *,
    dataset_id: str = "",
    project_id: Optional[int] = None,
    created_by=None,
    meta: Optional[Dict[str, Any]] = None,
    confidence_level: Optional[str] = None,
) -> None:
    if not kg_enabled() or not src or not dst:
        return
    meta = meta or {}
    if dataset_id:
        meta["dataset_id"] = dataset_id
    if confidence_level is None:
        confidence_level = CONF_LEVEL_EXTRACTED
    KgEdge.objects.update_or_create(
        src=src,
        dst=dst,
        relation_type=relation_type,
        defaults={
            "dataset_id": dataset_id or "",
            "project_id": project_id,
            "source": SOURCE_SYSTEM,
            "confidence_level": confidence_level,
            "meta": meta,
            "created_by": created_by,
        },
    )


def index_generation_task(task, *, created_by=None, kb_chat_session_id: Optional[str] = None) -> None:
    """为 AI 生成任务建立溯源边。"""
    if not kg_enabled():
        return
    try:
        project_id = getattr(task, "project_id", None)
        task_ent = ensure_entity(
            entity_key_gen_task(task.task_id),
            ENTITY_GENERATION_TASK,
            label=getattr(task, "title", "") or task.task_id,
            ref_app="requirement_analysis",
            ref_id=task.task_id,
            project_id=project_id,
            properties={
                "status": getattr(task, "status", ""),
                "dify_dataset_id": getattr(task, "dify_dataset_id", "") or "",
            },
        )
        if not task_ent:
            return

        if project_id:
            proj_ent = ensure_entity(
                entity_key_project(project_id),
                ENTITY_PROJECT,
                label=f"Project #{project_id}",
                ref_app="projects",
                ref_id=str(project_id),
                project_id=project_id,
            )
            _link(task_ent, proj_ent, REL_BELONGS_TO, project_id=project_id, created_by=created_by)

        source_doc_id = getattr(task, "source_document_id", None)
        if source_doc_id:
            doc_ent = ensure_entity(
                entity_key_req_doc(source_doc_id),
                ENTITY_REQUIREMENT_DOCUMENT,
                label=f"需求文档 #{source_doc_id}",
                ref_app="requirement_analysis",
                ref_id=str(source_doc_id),
                project_id=project_id,
            )
            _link(task_ent, doc_ent, REL_DERIVED_FROM, project_id=project_id, created_by=created_by)

        dataset_id = (getattr(task, "dify_dataset_id", None) or "").strip()
        doc_names = {}
        kb_meta = getattr(task, "kb_context_meta", None) or {}
        if isinstance(kb_meta, dict):
            doc_names = dict(kb_meta.get("document_names") or {})
            for doc in kb_meta.get("documents") or []:
                if not isinstance(doc, dict):
                    continue
                doc_id = str(doc.get("document_id") or "").strip()
                doc_name = str(doc.get("document_name") or "").strip()
                if doc_id and doc_name:
                    doc_names.setdefault(doc_id, doc_name)

        doc_ids_to_index = [str(x).strip() for x in (getattr(task, "kb_document_ids", None) or []) if str(x).strip()]
        if not doc_ids_to_index and isinstance(kb_meta, dict):
            for doc in kb_meta.get("documents") or []:
                if not isinstance(doc, dict):
                    continue
                doc_id = str(doc.get("document_id") or "").strip()
                if doc_id and doc_id not in doc_ids_to_index:
                    doc_ids_to_index.append(doc_id)

        for doc_id in doc_ids_to_index:
            if not doc_id or not dataset_id:
                continue
            doc_ent = ensure_entity(
                entity_key_kb_document(dataset_id, doc_id),
                ENTITY_KB_DOCUMENT,
                label=str(doc_names.get(doc_id) or doc_id)[:500],
                ref_app="dify",
                ref_id=doc_id,
                project_id=project_id,
                properties={"dataset_id": dataset_id},
            )
            _link(task_ent, doc_ent, REL_USED_REFERENCE, project_id=project_id, created_by=created_by)

        for func_id in getattr(task, "kb_function_ids", None) or []:
            try:
                fid = int(func_id)
            except (TypeError, ValueError):
                continue
            sync_kb_function(fid, project_id=project_id)
            func_ent = ensure_entity(
                entity_key_kb_function(fid),
                ENTITY_KB_FUNCTION,
                ref_app="requirement_analysis",
                ref_id=str(fid),
                project_id=project_id,
            )
            _link(task_ent, func_ent, REL_USED_REFERENCE, project_id=project_id, created_by=created_by)

        session_id = kb_chat_session_id
        if not session_id:
            from apps.requirement_analysis.kb_chat_models import KbChatSession

            session = (
                KbChatSession.objects.filter(last_generation_task_id=task.task_id)
                .order_by("-updated_at")
                .first()
            )
            session_id = session.session_id if session else None
        if session_id:
            from apps.requirement_analysis.kb_chat_models import KbChatSession

            chat_session = KbChatSession.objects.filter(session_id=session_id).first()
            chat_title = (chat_session.title or "").strip() if chat_session else ""
            chat_label = chat_title[:500] if chat_title else f"KB 对话 {session_id[:8]}"
            chat_ent = ensure_entity(
                entity_key_kb_chat(session_id),
                ENTITY_KB_CHAT_SESSION,
                label=chat_label,
                ref_app="requirement_analysis",
                ref_id=session_id,
                project_id=project_id,
                properties={
                    "dify_dataset_id": getattr(chat_session, "dify_dataset_id", "") or "",
                    "dify_dataset_name": getattr(chat_session, "dify_dataset_name", "") or "",
                }
                if chat_session
                else {},
            )
            _link(task_ent, chat_ent, REL_DERIVED_FROM, project_id=project_id, created_by=created_by)

        if getattr(task, "refinement_notes", None):
            props = {
                **(task_ent.properties or {}),
                "has_refinement": True,
                "refinement_preview": (task.refinement_notes or "")[-500:],
                "refinement_count": (task.refinement_notes or "").count("--- 迭代补充"),
            }
            if getattr(task, "status", "") == "completed" and getattr(task, "completed_at", None):
                props["last_refined_at"] = str(task.completed_at)
            task_ent.properties = props
            task_ent.save(update_fields=["properties", "updated_at"])
    except Exception as exc:
        logger.warning("知识图谱索引生成任务失败: %s", exc, exc_info=True)


def _index_adopted_covers(
    tc_ent: KgEntity,
    task,
    *,
    project_id: Optional[int],
    created_by=None,
) -> None:
    """采纳用例时建立 covers 边：→ 任务关联功能；→ maps_to 映射的业务需求。"""
    function_ids: List[int] = []
    for raw in getattr(task, "kb_function_ids", None) or []:
        try:
            function_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    if not function_ids:
        return

    from apps.requirement_analysis.kb_models import KbFunction

    func_entity_keys: List[str] = []
    for fid in function_ids:
        func = KbFunction.objects.filter(pk=fid, is_active=True).first()
        if not func:
            continue
        func_ent = ensure_entity(
            entity_key_kb_function(func.pk),
            ENTITY_KB_FUNCTION,
            label=func.name,
            ref_app="requirement_analysis",
            ref_id=str(func.pk),
            project_id=project_id,
            properties={"code": func.code, "dify_dataset_id": func.dify_dataset_id},
        )
        if not func_ent:
            continue
        _link(
            tc_ent,
            func_ent,
            REL_COVERS,
            project_id=project_id,
            created_by=created_by,
            meta={"origin": "adopt", "task_id": getattr(task, "task_id", "")},
        )
        func_entity_keys.append(func_ent.entity_key)

    if not func_entity_keys:
        return

    seen_req_keys: set[str] = set()
    for edge in KgEdge.objects.filter(
        relation_type=REL_MAPS_TO,
        dst__entity_key__in=func_entity_keys,
        src__entity_type=ENTITY_BUSINESS_REQUIREMENT,
    ).select_related("src"):
        req_ent = edge.src
        if req_ent.entity_key in seen_req_keys:
            continue
        seen_req_keys.add(req_ent.entity_key)
        _link(
            tc_ent,
            req_ent,
            REL_COVERS,
            project_id=project_id,
            created_by=created_by,
            meta={"origin": "adopt", "via": "maps_to", "task_id": getattr(task, "task_id", "")},
        )


def index_adopted_test_case(test_case, task, *, created_by=None) -> None:
    """采纳用例后建立 provenance 边。"""
    if not kg_enabled():
        return
    try:
        project_id = getattr(test_case, "project_id", None) or getattr(task, "project_id", None)
        tc_ent = ensure_entity(
            entity_key_test_case(test_case.pk),
            ENTITY_TEST_CASE,
            label=(getattr(test_case, "title", "") or f"用例 #{test_case.pk}")[:500],
            ref_app="testcases",
            ref_id=str(test_case.pk),
            project_id=project_id,
        )
        task_ent = ensure_entity(
            entity_key_gen_task(task.task_id),
            ENTITY_GENERATION_TASK,
            label=getattr(task, "title", "") or task.task_id,
            ref_app="requirement_analysis",
            ref_id=task.task_id,
            project_id=project_id,
        )
        _link(
            tc_ent,
            task_ent,
            REL_PROVENANCE,
            project_id=project_id,
            created_by=created_by,
            meta={"adopted_at": str(getattr(task, "saved_at", "") or "")},
        )
        if project_id:
            proj_ent = ensure_entity(
                entity_key_project(project_id),
                ENTITY_PROJECT,
                ref_app="projects",
                ref_id=str(project_id),
                project_id=project_id,
            )
            _link(tc_ent, proj_ent, REL_BELONGS_TO, project_id=project_id, created_by=created_by)
        _index_adopted_covers(tc_ent, task, project_id=project_id, created_by=created_by)
    except Exception as exc:
        logger.warning("知识图谱索引采纳用例失败: %s", exc, exc_info=True)


def sync_kb_function(func_id: int, *, dataset_id: str = "", project_id: Optional[int] = None) -> None:
    """同步 KbFunction 及其文档、功能间关系到图谱。"""
    if not kg_enabled():
        return
    try:
        from apps.requirement_analysis.kb_models import KbFunction

        func = (
            KbFunction.objects.filter(pk=func_id)
            .prefetch_related("documents", "outgoing_relations__to_function")
            .first()
        )
        if not func:
            return

        # 优先使用传入的dataset_id，否则从func获取
        if not dataset_id:
            dataset_id = func.dify_dataset_id or ""

        func_ent = ensure_entity(
            entity_key_kb_function(func.pk),
            ENTITY_KB_FUNCTION,
            label=func.name,
            ref_app="requirement_analysis",
            ref_id=str(func.pk),
            dataset_id=dataset_id,
            project_id=project_id,
            properties={"code": func.code, "dify_dataset_id": dataset_id},
        )
        if not func_ent:
            return

        for doc in func.documents.all():
            doc_ent = ensure_entity(
                entity_key_kb_document(dataset_id, doc.dify_document_id),
                ENTITY_KB_DOCUMENT,
                label=doc.dify_document_name or doc.dify_document_id,
                ref_app="dify",
                ref_id=doc.dify_document_id,
                dataset_id=dataset_id,
                project_id=project_id,
                properties={"dataset_id": dataset_id, "is_primary": doc.is_primary},
            )
            _link(func_ent, doc_ent, REL_REFERENCES, dataset_id=dataset_id, project_id=project_id)

        for rel in func.outgoing_relations.all():
            to_ent = ensure_entity(
                entity_key_kb_function(rel.to_function_id),
                ENTITY_KB_FUNCTION,
                label=rel.to_function.name,
                ref_app="requirement_analysis",
                ref_id=str(rel.to_function_id),
                dataset_id=dataset_id,
                project_id=project_id,
            )
            rel_type = _KB_RELATION_MAP.get(rel.relation_type, REL_RELATED)
            _link(func_ent, to_ent, rel_type, dataset_id=dataset_id, project_id=project_id)
    except Exception as exc:
        logger.warning("知识图谱同步 KbFunction 失败: %s", exc, exc_info=True)


def sync_all_kb_functions(*, dataset_id: str = "", project_id: Optional[int] = None) -> int:
    from apps.requirement_analysis.kb_models import KbFunction

    count = 0
    qs = KbFunction.objects.filter(is_active=True)
    if dataset_id:
        qs = qs.filter(dify_dataset_id=dataset_id)
    for func in qs:
        sync_kb_function(func.id, dataset_id=dataset_id, project_id=project_id)
        count += 1
    return count


def _resolve_api_project_id(api_request) -> Optional[int]:
    if api_request.project_id:
        return api_request.project_id
    collection = getattr(api_request, "collection", None)
    if collection and collection.project_id:
        return collection.project_id
    return None


def sync_api_request(req_id: int, *, project_id: Optional[int] = None) -> None:
    """将 API 接口同步为图谱节点。"""
    if not kg_enabled():
        return
    try:
        from apps.api_testing.models import ApiRequest

        req = (
            ApiRequest.objects.filter(pk=req_id)
            .select_related("collection__project", "project")
            .first()
        )
        if not req:
            return

        api_project_id = _resolve_api_project_id(req)
        label = f"{req.method} {req.name}"[:500]
        url = (req.url or "")[:500]
        ensure_entity(
            entity_key_api_request(req.pk),
            ENTITY_API_REQUEST,
            label=label,
            ref_app="api_testing",
            ref_id=str(req.pk),
            project_id=project_id,
            properties={
                "name": req.name,
                "method": req.method,
                "url": url,
                "request_type": req.request_type,
                "api_project_id": api_project_id,
            },
        )
    except Exception as exc:
        logger.warning("知识图谱同步 ApiRequest 失败: %s", exc, exc_info=True)


def sync_all_api_requests(*, project_id: Optional[int] = None) -> int:
    from apps.api_testing.models import ApiRequest

    qs = ApiRequest.objects.all()
    if project_id is not None:
        ext_ids = _resolve_mapped_ids(project_id, "api_testing")
        if ext_ids:
            qs = qs.filter(project_id__in=ext_ids)
        else:
            return 0

    count = 0
    for rid in qs.values_list("id", flat=True):
        sync_api_request(rid, project_id=project_id)
        count += 1
    return count


def sync_ui_page(page_id: int, *, project_id: Optional[int] = None) -> None:
    """将 UI 页面对象同步为图谱节点。"""
    if not kg_enabled():
        return
    try:
        from apps.ui_automation.models import PageObject

        page = PageObject.objects.filter(pk=page_id).select_related("project").first()
        if not page:
            return

        label = page.name[:500]
        ensure_entity(
            entity_key_ui_page(page.pk),
            ENTITY_UI_PAGE,
            label=label,
            ref_app="ui_automation",
            ref_id=str(page.pk),
            project_id=project_id,
            properties={
                "name": page.name,
                "class_name": page.class_name,
                "url_pattern": (page.url_pattern or "")[:500],
                "ui_project_id": page.project_id,
            },
        )
    except Exception as exc:
        logger.warning("知识图谱同步 PageObject 失败: %s", exc, exc_info=True)


def sync_all_ui_pages(*, project_id: Optional[int] = None) -> int:
    from apps.ui_automation.models import PageObject

    qs = PageObject.objects.all()
    if project_id is not None:
        ext_ids = _resolve_mapped_ids(project_id, "ui_automation")
        if ext_ids:
            qs = qs.filter(project_id__in=ext_ids)
        else:
            return 0

    count = 0
    for pid in qs.values_list("id", flat=True):
        sync_ui_page(pid, project_id=project_id)
        count += 1
    return count


# ---------------------------------------------------------------------------
# 层次2（补全）：业务对象同步 —— 需求 / 用例 / 生成任务
# ---------------------------------------------------------------------------

def _resolve_requirement_project_id(req) -> Optional[int]:
    """BusinessRequirement → analysis → document → project_id。"""
    try:
        analysis = req.analysis
        if analysis and getattr(analysis, "document", None):
            return getattr(analysis.document, "project_id", None)
    except Exception:
        return None
    return None


def sync_business_requirement(req_id: int, *, project_id: Optional[int] = None) -> None:
    """将一条业务需求同步为图谱节点。"""
    if not kg_enabled():
        return
    try:
        from apps.requirement_analysis.models import BusinessRequirement

        req = BusinessRequirement.objects.filter(pk=req_id).first()
        if not req:
            return
        if project_id is None:
            project_id = _resolve_requirement_project_id(req)
        label = f"{req.requirement_id} {req.requirement_name}".strip()[:500]
        ensure_entity(
            entity_key_biz_req(req.pk),
            ENTITY_BUSINESS_REQUIREMENT,
            label=label,
            ref_app="requirement_analysis",
            ref_id=str(req.pk),
            project_id=project_id,
            properties={
                "requirement_id": req.requirement_id,
                "module": req.module,
                "requirement_type": getattr(req, "requirement_type", ""),
                "requirement_level": getattr(req, "requirement_level", ""),
                "acceptance_criteria": (req.acceptance_criteria or "")[:500],
            },
        )
    except Exception as exc:
        logger.warning("知识图谱同步业务需求失败: %s", exc, exc_info=True)


def sync_all_business_requirements(*, project_id: Optional[int] = None) -> int:
    from apps.requirement_analysis.models import BusinessRequirement

    qs = BusinessRequirement.objects.all()
    if project_id is not None:
        qs = qs.filter(analysis__document__project_id=project_id)
    count = 0
    for rid in qs.values_list("id", flat=True):
        sync_business_requirement(rid, project_id=project_id)
        count += 1
    return count


def sync_requirement_document(doc_id: int, *, project_id: Optional[int] = None) -> None:
    """将需求文档同步为图谱节点。"""
    if not kg_enabled():
        return
    try:
        from apps.requirement_analysis.models import RequirementDocument

        doc = RequirementDocument.objects.filter(pk=doc_id).first()
        if not doc:
            return
        if project_id is None:
            project_id = getattr(doc, "project_id", None)
        ensure_entity(
            entity_key_req_doc(doc.pk),
            ENTITY_REQUIREMENT_DOCUMENT,
            label=(doc.title or f"需求文档 #{doc.pk}")[:500],
            ref_app="requirement_analysis",
            ref_id=str(doc.pk),
            project_id=project_id,
            properties={"document_type": getattr(doc, "document_type", "")},
        )
    except Exception as exc:
        logger.warning("知识图谱同步需求文档失败: %s", exc, exc_info=True)


def sync_all_requirement_documents(*, project_id: Optional[int] = None) -> int:
    from apps.requirement_analysis.models import RequirementDocument

    qs = RequirementDocument.objects.all()
    if project_id is not None:
        qs = qs.filter(project_id=project_id)
    count = 0
    for did in qs.values_list("id", flat=True):
        sync_requirement_document(did, project_id=project_id)
        count += 1
    return count


def sync_test_case(case_id: int, *, project_id: Optional[int] = None, created_by=None) -> None:
    """将一条测试用例同步为图谱节点。"""
    if not kg_enabled():
        return
    try:
        from apps.testcases.models import TestCase

        case = TestCase.objects.filter(pk=case_id).select_related("project").first()
        if not case:
            return
        if project_id is None:
            project_id = getattr(case, "project_id", None)
        props = {
            "priority": getattr(case, "priority", ""),
            "status": getattr(case, "status", ""),
            "test_type": getattr(case, "test_type", ""),
        }
        desc = getattr(case, "description", "") or ""
        if desc:
            props["description"] = desc[:500]
        ensure_entity(
            entity_key_test_case(case.pk),
            ENTITY_TEST_CASE,
            label=(case.title or f"用例 #{case.pk}")[:500],
            ref_app="testcases",
            ref_id=str(case.pk),
            project_id=project_id,
            properties=props,
        )
    except Exception as exc:
        logger.warning("知识图谱同步测试用例失败: %s", exc, exc_info=True)


def sync_all_test_cases(*, project_id: Optional[int] = None) -> int:
    from apps.testcases.models import TestCase

    qs = TestCase.objects.all()
    if project_id is not None:
        qs = qs.filter(project_id=project_id)
    count = 0
    for cid in qs.values_list("id", flat=True):
        sync_test_case(cid, project_id=project_id)
        count += 1
    return count


def sync_generation_task(task, *, project_id: Optional[int] = None) -> None:
    """为生成任务建立溯源边（gen_task → project/doc/kb_function）。

    :param task: TestCaseGenerationTask 对象，或字符串 task_id。
    """
    from apps.requirement_analysis.models import TestCaseGenerationTask

    if not isinstance(task, TestCaseGenerationTask):
        task = TestCaseGenerationTask.objects.filter(task_id=str(task)).first()
    if not task:
        return
    index_generation_task(task, project_id=project_id)


def sync_all_generation_tasks(*, project_id: Optional[int] = None) -> int:
    from apps.requirement_analysis.models import TestCaseGenerationTask

    qs = TestCaseGenerationTask.objects.all()
    if project_id is not None:
        qs = qs.filter(project_id=project_id)
    count = 0
    for task in qs:
        index_generation_task(task)
        count += 1
    return count


# ---------------------------------------------------------------------------
# 自建知识中枢（kb_hub.NativeKb / NativeKbDocument）入图
# ---------------------------------------------------------------------------


def sync_native_kb(native_kb_id: int, *, project_id: Optional[int] = None) -> int:
    """将一条 NativeKb（及其文档）同步为图谱节点 + 内部 contains 边。

    dataset_id 用 `native:{kb_id}` 占位，与 Dify 的真实 dataset_id 区分开，
    便于图谱按知识源过滤。
    返回写入的文档实体数。
    """
    if not kg_enabled():
        return 0

    from apps.requirement_analysis.kb_hub.models import NativeKb

    kb = NativeKb.objects.filter(pk=native_kb_id).first()
    if not kb:
        return 0
    pid = project_id if project_id is not None else (kb.project_id or None)
    dataset_key = f"native:{kb.pk}"
    props: Dict[str, Any] = {
        "description": (kb.description or "")[:500],
        "status": kb.status,
        "doc_count": kb.documents.count(),
        "chunk_count": kb.chunk_count,
    }
    kb_ent = ensure_entity(
        entity_key_native_kb(kb.pk),
        ENTITY_NATIVE_KB,
        label=kb.name[:500],
        ref_app="requirement_analysis.kb_hub",
        ref_id=str(kb.pk),
        dataset_id=dataset_key,
        project_id=pid,
        properties=props,
    )
    if not kb_ent:
        return 0

    # Project → NativeKb contains 边
    if pid:
        proj_ent = ensure_entity(
            entity_key_project(pid),
            ENTITY_PROJECT,
            label=f"Project #{pid}",
            ref_app="projects",
            ref_id=str(pid),
            project_id=pid,
        )
        if proj_ent:
            _link(
                proj_ent,
                kb_ent,
                REL_CONTAINS,
    project_id=pid,
    created_by=None,
    confidence_level=CONF_LEVEL_EXTRACTED,
)

    # NativeKbDocument → NativeKb contains 边
    doc_count = 0
    for doc in kb.documents.all():
        doc_ent = ensure_entity(
            entity_key_native_doc(doc.pk),
            ENTITY_NATIVE_KB_DOCUMENT,
            label=(doc.title or f"文档 #{doc.pk}")[:500],
            ref_app="requirement_analysis.kb_hub",
            ref_id=str(doc.pk),
            dataset_id=dataset_key,
            project_id=pid,
            properties={
                "source_type": doc.source_type,
                "status": doc.status,
                "word_count": doc.word_count,
                "kb_id": kb.pk,
            },
        )
        if doc_ent:
            _link(
                kb_ent,
                doc_ent,
                REL_CONTAINS,
    project_id=pid,
    created_by=None,
    confidence_level=CONF_LEVEL_EXTRACTED,
)
            doc_count += 1
    return doc_count


def sync_all_native_kbs(
    *,
    project_id: Optional[int] = None,
    status: str = "",
) -> int:
    """同步全部自建知识中枢到图谱。

    - 按 project_id 过滤（kb.project_id 匹配）
    - status 可选：draft/published/archived
    返回同步的 KB 数。
    """
    if not kg_enabled():
        return 0

    from apps.requirement_analysis.kb_hub.models import NativeKb

    qs = NativeKb.objects.all()
    if project_id is not None:
        qs = qs.filter(project_id=project_id)
    if status:
        qs = qs.filter(status=status)

    count = 0
    for kb in qs:
        sync_native_kb(kb.pk, project_id=project_id if project_id is not None else kb.project_id)
        count += 1
    return count


# ---------------------------------------------------------------------------
# 自动覆盖：为已同步的测试用例建立 covers 边（TestCase → BusinessRequirement）
# ---------------------------------------------------------------------------

def _requirement_entity_for_test_case(case_pk: int, tc_entity: KgEntity) -> List[KgEntity]:
    """返回该用例覆盖的业务需求实体（按优先级：GeneratedTestCase 关联 > provenance 链 > 文本匹配）。"""
    found: List[KgEntity] = []

    # ① GeneratedTestCase.case_id 关联
    try:
        from apps.requirement_analysis.models import GeneratedTestCase

        gen = GeneratedTestCase.objects.filter(case_id=str(case_pk)).first()
        if gen and gen.requirement_id:
            br_ent = get_entity(entity_key_biz_req(gen.requirement_id))
            if br_ent:
                found.append(br_ent)
    except Exception:
        pass
    if found:
        return found

    # ② provenance 链：tc → gen_task → used_reference → KbFunction ← maps_to ← BusinessRequirement
    try:
        gen_edges = KgEdge.objects.filter(
            src=tc_entity, relation_type=REL_PROVENANCE,
        ).select_related("dst")
        gen_task_entities = [e.dst for e in gen_edges]
        func_keys = list(
            KgEdge.objects.filter(
                src__in=gen_task_entities, relation_type=REL_USED_REFERENCE,
            ).values_list("dst__entity_key", flat=True)
        )
        if func_keys:
            br_edges = KgEdge.objects.filter(
                dst__entity_key__in=func_keys,
                relation_type=REL_MAPS_TO,
                src__entity_type=ENTITY_BUSINESS_REQUIREMENT,
            ).select_related("src")
            for e in br_edges:
                if e.src not in found:
                    found.append(e.src)
    except Exception:
        pass
    if found:
        return found

    # ③ 文本匹配：用例标题/描述里出现需求编号或需求模块
    try:
        case = None
        from apps.testcases.models import TestCase

        case = TestCase.objects.filter(pk=case_pk).first()
        if case:
            haystack = f"{case.title or ''} {case.description or ''}".lower()
            br_entities = KgEntity.objects.filter(
                entity_type=ENTITY_BUSINESS_REQUIREMENT,
                project_id=tc_entity.project_id,
            ).select_related()
            for br in br_entities:
                props = br.properties or {}
                rid = str(props.get("requirement_id") or "").lower()
                module = str(props.get("module") or "").lower()
                if (rid and rid in haystack) or (module and module in haystack):
                    if br not in found:
                        found.append(br)
    except Exception:
        pass
    return found


def auto_cover_test_cases(*, project_id: Optional[int] = None, created_by=None) -> Dict[str, int]:
    """为项目内已同步的测试用例自动建立 covers 边。"""
    result = {"test_cases": 0, "covered": 0, "edges_created": 0, "edges_skipped": 0}
    if not kg_enabled():
        return result

    tc_qs = KgEntity.objects.filter(entity_type=ENTITY_TEST_CASE)
    if project_id is not None:
        tc_qs = tc_qs.filter(project_id=project_id)

    for tc in tc_qs.select_related():
        result["test_cases"] += 1
        req_entities = _requirement_entity_for_test_case(tc.ref_id, tc)
        if not req_entities:
            continue
        result["covered"] += 1
        for br in req_entities:
            edge, created = _cover_link(tc, br, project_id=project_id, created_by=created_by)
            if created:
                result["edges_created"] += 1
            else:
                result["edges_skipped"] += 1
    return result


def _cover_link(src: KgEntity, dst: KgEntity, *, project_id=None, created_by=None) -> tuple:
    """建立 covers 边（src=TestCase → dst=BusinessRequirement/KbFunction/FunctionPoint）。"""
    edge, created = KgEdge.objects.update_or_create(
        src=src,
        dst=dst,
        relation_type=REL_COVERS,
        defaults={
            "project_id": project_id or src.project_id or dst.project_id,
            "source": SOURCE_SYSTEM,
            "confidence_level": CONF_LEVEL_EXTRACTED,
            "meta": {"origin": "auto_cover"},
            "created_by": created_by,
        },
    )
    return edge, created


# ---------------------------------------------------------------------------
# 层次3（补全）：AI 从业务需求直接抽取功能点（不依赖 Dify，直接对需求记录调 LLM）
# ---------------------------------------------------------------------------

def _build_req_fp_prompt(module: str, reqs: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    lines = "\n".join(
        f"- [{r.get('requirement_id', '')}] {r.get('requirement_name', '')}：{(r.get('description') or '')[:200]}"
        for r in reqs
    )
    system_msg = (
        "你是需求分析专家。下面是一组属于同一业务模块的需求条目，请从中抽象出独立的功能点（feature points）。\n"
        "每个功能点包含：\n"
        "- name: 功能名称（简洁，10-30字）\n"
        "- description: 功能描述（50-200字）\n"
        "- keywords: 关键词列表（3-5个）\n"
        "- category: 分类（数据管理/流程审批/报表查询/接口集成/权限控制/其他）\n\n"
        "只输出 JSON 数组，不要 Markdown 解释。每项字段：name, description, keywords, category。"
    )
    user_msg = (
        f"业务模块：{module}\n\n需求条目：\n{lines}\n\n请抽取其中的功能点列表。"
    )
    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def extract_function_points_from_requirements(*, project_id: Optional[int] = None, created_by=None) -> Dict[str, Any]:
    """
    端到端：拉取项目的业务需求 → 按模块分组 → LLM 抽取功能点 → 写入图谱。
    不依赖 Dify，直接复用 content_extractor._call_llm（role=writer 模型）。

    产出：FunctionPoint 节点 + BusinessRequirement → maps_to → FunctionPoint 边。
    """
    if not kg_enabled():
        return {"detail": "知识图谱已禁用"}

    from apps.requirement_analysis.models import BusinessRequirement
    from .content_extractor import _call_llm, _parse_json_list

    qs = BusinessRequirement.objects.all()
    if project_id is not None:
        qs = qs.filter(analysis__document__project_id=project_id)
    reqs = list(qs)
    if not reqs:
        return {"detail": "该项目暂无业务需求，请先同步需求", "points_extracted": 0}

    # 按模块分组
    groups: Dict[str, List[Dict[str, Any]]] = {}
    req_entity_map: Dict[str, KgEntity] = {}
    for req in reqs:
        module = (req.module or "未分类").strip() or "未分类"
        groups.setdefault(module, []).append({
            "requirement_id": req.requirement_id,
            "requirement_name": req.requirement_name,
            "description": req.description or req.acceptance_criteria or "",
        })
        br_ent = get_entity(entity_key_biz_req(req.pk))
        if br_ent:
            req_entity_map[req.requirement_id] = br_ent

    result: Dict[str, Any] = {
        "modules_processed": 0,
        "points_extracted": 0,
        "edges_created": 0,
        "errors": [],
        "details": [],
    }

    import re as _re

    def _slug(s: str) -> str:
        return _re.sub(r"[^0-9a-zA-Z\u4e00-\u9fa5]+", "_", (s or "x"))[:40]

    for module, module_reqs in groups.items():
        result["modules_processed"] += 1
        try:
            messages = _build_req_fp_prompt(module, module_reqs)
            raw = _call_llm(messages)
        except Exception as exc:
            logger.warning("LLM 抽取功能点失败 module=%s: %s", module, exc)
            result["errors"].append(f"模块《{module}》功能点抽取失败: {exc}")
            continue

        points = _parse_json_list(raw)
        if not points:
            result["errors"].append(f"模块《{module}》未抽取出功能点")
            continue

        created_in_module = 0
        for idx, point in enumerate(points[:20]):
            name = str(point.get("name") or "").strip()
            if not name:
                continue
            desc = str(point.get("description") or "").strip()
            keywords = point.get("keywords") or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(",") if k.strip()]
            category = str(point.get("category") or "其他").strip()
            fp_key = f"fp:req:{project_id}:{_slug(module)}:{idx}"
            fp_ent = ensure_entity(
                fp_key,
                ENTITY_FUNCTION_POINT,
                label=name[:500],
                ref_app="requirement_analysis",
                ref_id=f"{module}:{idx}",
                project_id=project_id,
                properties={
                    "name": name,
                    "description": desc[:500],
                    "keywords": keywords[:10],
                    "category": category[:50],
                    "module": module,
                    "source": "business_requirement",
                },
            )
            if not fp_ent:
                continue
            # BusinessRequirement → maps_to → FunctionPoint
            for req in module_reqs:
                br_ent = req_entity_map.get(req["requirement_id"])
                if not br_ent:
                    continue
                _, was_created = KgEdge.objects.update_or_create(
                    src=br_ent,
                    dst=fp_ent,
                    relation_type=REL_MAPS_TO,
                    defaults={
                        "project_id": project_id or br_ent.project_id,
                        "source": SOURCE_SYSTEM,
                        "confidence_level": CONF_LEVEL_EXTRACTED,
                        "meta": {"origin": "ai_extract_fp"},
                    },
                )
                if was_created:
                    result["edges_created"] += 1
            created_in_module += 1
        result["points_extracted"] += created_in_module
        result["details"].append({"module": module, "points_count": created_in_module})

    return result



# ---------------------------------------------------------------------------
# 层次3：AI 内容理解 —— 文档功能点抽取与跨文档关联
# ---------------------------------------------------------------------------

def extract_and_sync_function_points(
    dataset_id: str,
    *,
    dify_config_id: Optional[int] = None,
    document_ids: Optional[List[str]] = None,
    project_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    端到端：拉 Dify 文档正文 → LLM 抽取功能点 → 写入图谱。

    :param dataset_id: Dify 知识库 ID
    :param dify_config_id: Dify 配置 ID（必传）
    :param document_ids: 指定文档 ID 列表，为空则处理该知识库下所有文档
    :param project_id: 关联项目 ID
    :return: {"documents_processed": N, "points_extracted": M, "errors": [...]}
    """
    if not kg_enabled():
        return {"detail": "知识图谱已禁用"}

    from apps.assistant.models import DifyConfig
    from apps.requirement_analysis.dify_kb_service import (
        fetch_document_text,
        list_dataset_documents,
        resolve_dify_config,
    )
    from .content_extractor import (
        extract_function_points,
        sync_function_points_to_graph,
    )

    config = resolve_dify_config(dify_config_id)
    if not config:
        return {"detail": "未找到对应的 Dify 配置，请先在 Dify 配置页创建"}

    # 拉文档列表
    try:
        docs_payload = list_dataset_documents(config, dataset_id, page=1, limit=100)
    except Exception as exc:
        return {"detail": f"获取文档列表失败: {exc}"}

    all_docs = docs_payload.get("data") or []
    if document_ids:
        target_set = {str(did).strip() for did in document_ids}
        all_docs = [d for d in all_docs if str(d.get("id") or "").strip() in target_set]

    if not all_docs:
        return {"detail": "未找到待处理的文档", "documents_processed": 0, "points_extracted": 0}

    results: Dict[str, Any] = {
        "documents_processed": 0,
        "points_extracted": 0,
        "errors": [],
        "details": [],
    }

    for doc in all_docs:
        doc_id = str(doc.get("id") or "").strip()
        doc_name = doc.get("name") or doc_id
        if not doc_id:
            continue

        # 拉文档正文
        try:
            content = fetch_document_text(config, dataset_id, doc_id, max_chars=8000)
        except Exception as exc:
            logger.warning("拉取文档正文失败 doc_id=%s: %s", doc_id, exc)
            results["errors"].append(f"文档《{doc_name}》拉取失败: {exc}")
            continue

        if not content or not content.strip():
            results["errors"].append(f"文档《{doc_name}》内容为空")
            continue

        # LLM 抽取功能点
        try:
            points = extract_function_points(doc_name, content)
        except Exception as exc:
            logger.warning("LLM 抽取功能点失败 doc_id=%s: %s", doc_id, exc)
            results["errors"].append(f"文档《{doc_name}》功能点抽取失败: {exc}")
            continue

        if not points:
            results["errors"].append(f"文档《{doc_name}》未抽取出功能点")
            continue

        # 写入图谱
        created = sync_function_points_to_graph(
            dataset_id, doc_id, doc_name, points, project_id=project_id,
        )
        results["documents_processed"] += 1
        results["points_extracted"] += created
        results["details"].append({
            "document_id": doc_id,
            "document_name": doc_name,
            "points_count": created,
        })

    return results


def extract_and_sync_cross_doc_relations(
    dataset_id: str,
    *,
    project_id: Optional[int] = None,
    min_confidence: float = 0.6,
    persist: bool = True,
    created_by=None,
) -> Dict[str, Any]:
    """
    跨文档功能点语义匹配 → 生成 similar_to / depends_on 边。

    :param dataset_id: 知识库 ID
    :param min_confidence: 置信度阈值
    :param persist: 是否直接写入图谱（True=写库, False=只返回建议）
    """
    if not kg_enabled():
        return {"detail": "知识图谱已禁用"}

    from .content_extractor import (
        DEFAULT_SIMILARITY_THRESHOLD,
        persist_cross_doc_relations,
        suggest_cross_doc_relations,
    )

    threshold = max(min_confidence, DEFAULT_SIMILARITY_THRESHOLD)
    suggestions = suggest_cross_doc_relations(dataset_id, min_confidence=threshold)

    result: Dict[str, Any] = {
        "suggestions": suggestions,
        "count": len(suggestions),
        "min_confidence": threshold,
    }

    if persist and suggestions:
        persist_result = persist_cross_doc_relations(
            suggestions, project_id=project_id, created_by=created_by,
        )
        result["persist"] = persist_result

    return result

