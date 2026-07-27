"""注入知识图谱演示数据，便于浏览/覆盖度/用例详情等页面查看效果。"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.knowledge_graph.builder import (
    index_adopted_test_case,
    index_generation_task,
    sync_api_request,
    sync_kb_function,
    sync_ui_page,
)
from apps.knowledge_graph.constants import (
    ENTITY_BUSINESS_REQUIREMENT,
    ENTITY_PROJECT,
    REL_AUTOMATES,
)
from apps.knowledge_graph.edge_ops import create_manual_kg_edge
from apps.knowledge_graph.models import kg_enabled
from apps.knowledge_graph.registry import (
    ensure_entity,
    entity_key_biz_req,
    entity_key_project,
    get_entity,
)
from apps.knowledge_graph.writeback import build_api_execution_snapshot, writeback_ui_page_execution
from apps.projects.models import Project
from apps.testcases.models import TestCase

User = get_user_model()

DEMO_DATASET = "demo_kg_dataset"
DEMO_TASK_ID = "TASK_KGDEMO01"
DEMO_BIZ_REQ_IDS = (9001, 9002)


class Command(BaseCommand):
    help = "为指定项目注入知识图谱演示数据（功能模块、生成任务、采纳用例、API/UI 自动化关联等）"

    def add_arguments(self, parser):
        parser.add_argument("--project-id", type=int, default=1, help="目标项目 ID（默认 1）")
        parser.add_argument("--user", type=str, default="admin", help="操作用户名（默认 admin）")

    def handle(self, *args, **options):
        if not kg_enabled():
            self.stderr.write(self.style.ERROR("知识图谱已禁用，请设置 KNOWLEDGE_GRAPH_ENABLED=true"))
            return

        project_id = int(options["project_id"])
        username = options["user"]

        try:
            project = Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"项目不存在: {project_id}"))
            return

        user = User.objects.filter(username=username).first()
        if not user:
            user = User.objects.order_by("id").first()
        if not user:
            self.stderr.write(self.style.ERROR("无可用用户"))
            return

        summary: Dict[str, Any] = {}

        with transaction.atomic():
            summary.update(self._seed_kb_functions())
            summary.update(self._seed_project_root(project))
            summary.update(self._seed_business_requirements(project_id, user, summary["func_ids"]))
            task = self._seed_generation_task(project, user, summary["func_ids"])
            summary["task_id"] = task.task_id
            index_generation_task(task, created_by=user)
            summary.update(self._seed_adopted_cases(project_id, user, task))
            summary.update(self._seed_api_automation(project_id, user, summary.get("case_ids", [])))
            summary.update(self._seed_ui_pages(user, summary.get("case_ids", [])))

        self.stdout.write(self.style.SUCCESS("知识图谱演示数据已就绪："))
        for key, val in summary.items():
            self.stdout.write(f"  - {key}: {val}")
        self.stdout.write("")
        self.stdout.write("请打开：配置中心 → 知识图谱浏览 → 选择项目 → 加载图谱")
        self.stdout.write("用例详情可查看：覆盖范围 / 自动化关联 / 来源与任务引用")

    def _seed_kb_functions(self) -> Dict[str, Any]:
        from apps.requirement_analysis.kb_models import KbFunction, KbFunctionDocument, KbFunctionRelation

        specs = [
            {
                "code": "KG_DEMO_LOGIN",
                "name": "【演示】用户登录",
                "docs": [("doc_login_001", "登录模块需求说明"), ("doc_login_002", "登录接口规范")],
            },
            {
                "code": "KG_DEMO_ORDER",
                "name": "【演示】订单管理",
                "docs": [("doc_order_001", "订单业务流程")],
            },
            {
                "code": "KG_DEMO_PAY",
                "name": "【演示】支付结算",
                "docs": [("doc_pay_001", "支付对接文档")],
            },
        ]
        func_ids: List[int] = []
        for spec in specs:
            func, _ = KbFunction.objects.get_or_create(
                code=spec["code"],
                defaults={
                    "name": spec["name"],
                    "description": "知识图谱演示数据，可安全删除",
                    "dify_dataset_id": DEMO_DATASET,
                    "is_active": True,
                },
            )
            if func.name != spec["name"]:
                func.name = spec["name"]
                func.dify_dataset_id = DEMO_DATASET
                func.is_active = True
                func.save(update_fields=["name", "dify_dataset_id", "is_active"])
            func_ids.append(func.pk)
            for idx, (doc_id, doc_name) in enumerate(spec["docs"]):
                KbFunctionDocument.objects.get_or_create(
                    function=func,
                    dify_document_id=doc_id,
                    defaults={
                        "dify_document_name": doc_name,
                        "is_primary": idx == 0,
                        "sort_order": idx,
                    },
                )

        if len(func_ids) >= 2:
            KbFunctionRelation.objects.get_or_create(
                from_function_id=func_ids[0],
                to_function_id=func_ids[1],
                defaults={"relation_type": "depends_on"},
            )
        if len(func_ids) >= 3:
            KbFunctionRelation.objects.get_or_create(
                from_function_id=func_ids[2],
                to_function_id=func_ids[1],
                defaults={"relation_type": "impacts"},
            )

        for fid in func_ids:
            sync_kb_function(fid, project_id=1)

        return {"func_ids": func_ids, "kb_functions": len(func_ids)}

    def _seed_project_root(self, project: Project) -> Dict[str, Any]:
        ensure_entity(
            entity_key_project(project.pk),
            ENTITY_PROJECT,
            label=project.name,
            ref_app="projects",
            ref_id=str(project.pk),
            project_id=project.pk,
        )
        return {"project": project.name}

    def _seed_business_requirements(self, project_id: int, user) -> Dict[str, Any]:
        demo_reqs = [
            (9001, "REQ-DEMO-001", "用户登录与鉴权"),
            (9002, "REQ-DEMO-002", "订单创建与查询"),
        ]
        func_ent = get_entity("kb_func:1") or get_entity(f"kb_func:{self._first_func_id()}")
        maps_count = 0
        for rid, req_code, req_name in demo_reqs:
            req_ent = ensure_entity(
                entity_key_biz_req(rid),
                ENTITY_BUSINESS_REQUIREMENT,
                label=f"{req_code} {req_name}",
                ref_app="requirement_analysis",
                ref_id=str(rid),
                project_id=project_id,
                properties={"requirement_id": req_code, "module": "演示模块", "demo": True},
            )
            if func_ent and req_ent and rid == 9001:
                try:
                    create_manual_kg_edge(
                        src=req_ent,
                        dst=func_ent,
                        relation_type="maps_to",
                        project_id=project_id,
                        created_by=user,
                    )
                    maps_count += 1
                except Exception:
                    pass
        return {"demo_business_requirements": len(demo_reqs), "maps_to_edges": maps_count}

    def _first_func_id(self) -> int:
        from apps.requirement_analysis.kb_models import KbFunction

        func = KbFunction.objects.filter(code__startswith="KG_DEMO_").order_by("id").first()
        return func.pk if func else 1

    def _seed_generation_task(self, project: Project, user, func_ids: List[int]):
        from apps.requirement_analysis.models import TestCaseGenerationTask

        doc_ids = ["doc_login_001", "doc_order_001"]
        kb_context_meta = {
            "document_names": {
                "doc_login_001": "登录模块需求说明",
                "doc_order_001": "订单业务流程",
            },
            "graph_expansion": {
                "added_function_ids": func_ids[1:3] if len(func_ids) > 1 else [],
                "added_document_ids": ["doc_login_002"],
                "added_via_maps_to_function_ids": func_ids[:1],
            },
            "graph_summary": "演示：扩展 2 个关联功能、1 份参考文档",
            "graph_prompt_injected": True,
            "graph_prompt_summary_chars": 256,
        }
        task, _ = TestCaseGenerationTask.objects.update_or_create(
            task_id=DEMO_TASK_ID,
            defaults={
                "title": "【演示】登录与订单用例生成",
                "requirement_text": "演示知识图谱：覆盖登录、订单、支付相关测试场景。",
                "status": "completed",
                "progress": 100,
                "output_mode": "complete",
                "project": project,
                "dify_dataset_id": DEMO_DATASET,
                "dify_dataset_name": "演示知识库",
                "kb_context": "（演示）知识库参考片段：登录需校验用户名密码；订单需校验库存。",
                "kb_context_meta": kb_context_meta,
                "kb_document_ids": doc_ids,
                "kb_function_ids": func_ids[:2],
                "kb_reference_mode": "documents",
                "created_by": user,
            },
        )
        return task

    def _seed_adopted_cases(self, project_id: int, user, task) -> Dict[str, Any]:
        cases = list(
            TestCase.objects.filter(project_id=project_id).order_by("id")[:3]
        )
        if not cases:
            cases = list(TestCase.objects.order_by("id")[:3])
        linked = 0
        case_ids = []
        for case in cases:
            index_adopted_test_case(case, task, created_by=user)
            linked += 1
            case_ids.append(case.pk)
        return {"adopted_cases": linked, "case_ids": case_ids}

    def _seed_api_automation(self, project_id: int, user, case_ids: List[int]) -> Dict[str, Any]:
        from apps.api_testing.models import ApiRequest

        api_ids = list(ApiRequest.objects.order_by("id").values_list("id", flat=True)[:4])
        for rid in api_ids:
            sync_api_request(rid)

        automates = 0
        for i, case_id in enumerate(case_ids[:2]):
            if i >= len(api_ids):
                break
            tc_ent = get_entity(f"tc:{case_id}")
            api_ent = get_entity(f"api_req:{api_ids[i]}")
            if not tc_ent or not api_ent:
                continue
            try:
                create_manual_kg_edge(
                    src=tc_ent,
                    dst=api_ent,
                    relation_type=REL_AUTOMATES,
                    project_id=project_id,
                    created_by=user,
                )
                automates += 1
            except Exception:
                pass

        for i, rid in enumerate(api_ids[:2]):
            ent = get_entity(f"api_req:{rid}")
            if not ent:
                continue
            props = dict(ent.properties or {})
            props["last_execution"] = build_api_execution_snapshot(
                type(
                    "H",
                    (),
                    {
                        "pk": 1000 + i,
                        "executed_at": None,
                        "status_code": 200 if i == 0 else 401,
                        "response_time": 120.5 + i * 10,
                        "error_message": "" if i == 0 else "Unauthorized",
                        "assertions_results": [{"passed": i == 0}],
                        "executed_by": user,
                        "request_id": rid,
                    },
                )()
            )
            from datetime import datetime, timezone as tz

            props["last_execution"]["executed_at"] = datetime.now(tz.utc).isoformat()
            ent.properties = props
            ent.save(update_fields=["properties", "updated_at"])

        return {"api_requests_synced": len(api_ids), "automates_edges": automates}

    def _seed_ui_pages(self, user, case_ids: List[int]) -> Dict[str, Any]:
        from apps.ui_automation.models import PageObject, UiProject

        ui_project = UiProject.objects.order_by("id").first()
        if not ui_project:
            ui_project = UiProject.objects.create(
                name="【演示】UI 自动化项目",
                description="知识图谱演示",
                status="IN_PROGRESS",
                base_url="https://demo.testhub.local",
                owner=user,
            )

        pages = []
        for name, url in [("登录页", "/login"), ("订单列表页", "/orders")]:
            page, _ = PageObject.objects.get_or_create(
                project=ui_project,
                name=f"【演示】{name}",
                defaults={
                    "class_name": name.replace("页", "Page"),
                    "url_pattern": url,
                    "description": "知识图谱演示页面对象",
                },
            )
            pages.append(page)

        for page in pages:
            sync_ui_page(page.pk)
            writeback_ui_page_execution(
                page.pk,
                build_api_execution_snapshot(
                    type(
                        "H",
                        (),
                        {
                            "pk": page.pk,
                            "executed_at": None,
                            "status_code": None,
                            "response_time": None,
                            "error_message": "",
                            "assertions_results": None,
                            "executed_by": user,
                            "request_id": None,
                        },
                    )()
                )
                if False
                else {
                    "execution_id": page.pk,
                    "source": "ui_demo",
                    "source_id": page.pk,
                    "status": "passed",
                    "passed": True,
                    "execution_time_sec": 2.3,
                    "error_message": "",
                    "executed_at": None,
                    "finished_at": None,
                    "executed_by_id": user.pk,
                },
            )

        automates = 0
        if case_ids:
            tc_ent = get_entity(f"tc:{case_ids[0]}")
            ui_ent = get_entity(f"ui_page:{pages[0].pk}")
            if tc_ent and ui_ent:
                try:
                    create_manual_kg_edge(
                        src=tc_ent,
                        dst=ui_ent,
                        relation_type=REL_AUTOMATES,
                        project_id=tc_ent.project_id,
                        created_by=user,
                    )
                    automates += 1
                except Exception:
                    pass

        return {"ui_pages": len(pages), "ui_automates": automates}
