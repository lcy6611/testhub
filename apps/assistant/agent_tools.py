# -*- coding: utf-8 -*-
"""
Agent 工具注册表 —— 将现有 API 包装为 function calling 工具。

每个工具包含：
  - name:        工具名（LLM 调用时用）
  - description: 给 LLM 看的说明
  - parameters:  JSON Schema 参数定义
  - handler:     同步执行函数，返回 dict
"""

import logging
import re
from typing import Any, Dict, List, Callable
from django.db import models

logger = logging.getLogger(__name__)


# ────────────────────────────── 工具执行函数 ──────────────────────────────

def _list_projects(**kwargs) -> Dict[str, Any]:
    """查询项目列表"""
    from apps.projects.models import Project
    qs = Project.objects.all().order_by("-created_at")
    status_filter = kwargs.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values("id", "name", "description", "status", "created_at"))
    return {"total": qs.count(), "items": items}


def _list_testcases(**kwargs) -> Dict[str, Any]:
    """查询测试用例"""
    from apps.testcases.models import TestCase
    qs = TestCase.objects.select_related("project", "author").all()
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    priority = kwargs.get("priority")
    if priority:
        qs = qs.filter(priority=priority)
    status = kwargs.get("status")
    if status:
        qs = qs.filter(status=status)
    keyword = kwargs.get("keyword")
    if keyword:
        qs = qs.filter(models.Q(title__icontains=keyword) | models.Q(description__icontains=keyword))
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values("id", "title", "priority", "status", "test_type", "project__name", "author__username"))
    return {"total": qs.count(), "items": items}


def _create_testcase(**kwargs) -> Dict[str, Any]:
    """创建测试用例"""
    from apps.testcases.models import TestCase
    from apps.projects.models import Project
    from django.contrib.auth import get_user_model
    User = get_user_model()

    project_id = kwargs.get("project_id")
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return {"error": f"项目 {project_id} 不存在"}

    author = User.objects.first()
    tc = TestCase.objects.create(
        project=project,
        title=kwargs.get("title", "未命名用例"),
        description=kwargs.get("description", ""),
        preconditions=kwargs.get("preconditions", ""),
        steps=kwargs.get("steps", ""),
        expected_result=kwargs.get("expected_result", ""),
        priority=kwargs.get("priority", "medium"),
        test_type=kwargs.get("test_type", "functional"),
        author=author,
    )
    return {"id": tc.id, "title": tc.title, "project": project.name, "priority": tc.priority}


def _list_test_plans(**kwargs) -> Dict[str, Any]:
    """查询测试计划"""
    from apps.executions.models import TestPlan
    qs = TestPlan.objects.prefetch_related("projects").all().order_by("-created_at")
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(projects__id=project_id).distinct()
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values("id", "name", "description", "is_active", "created_at"))
    plan_ids = [i["id"] for i in items]
    projects_map = {}
    for plan in TestPlan.objects.filter(id__in=plan_ids).prefetch_related("projects"):
        p = plan.projects.first()
        projects_map[plan.id] = p.name if p else None
    for i in items:
        i["project_name"] = projects_map.get(i["id"])
    return {"total": qs.count(), "items": items}


def _create_test_plan(**kwargs) -> Dict[str, Any]:
    """创建测试计划"""
    from apps.executions.models import TestPlan, TestRun, TestRunCase
    from apps.testcases.models import TestCase
    from apps.projects.models import Project
    from django.contrib.auth import get_user_model
    User = get_user_model()

    creator = User.objects.first()
    plan = TestPlan.objects.create(
        name=kwargs.get("name", "未命名计划"),
        description=kwargs.get("description", ""),
        creator=creator,
    )

    project_ids = kwargs.get("project_ids", [])
    testcase_ids = kwargs.get("testcase_ids", [])

    if project_ids:
        plan.projects.set(project_ids)
        for pid in project_ids:
            try:
                project = Project.objects.get(id=pid)
                run = TestRun.objects.create(
                    name=f"{plan.name} - {project.name}",
                    test_plan=plan,
                    project=project,
                    creator=creator,
                    assignee=creator,
                )
                if testcase_ids:
                    valid_cases = TestCase.objects.filter(id__in=testcase_ids)
                    run_cases = [TestRunCase(test_run=run, testcase=tc) for tc in valid_cases]
                    TestRunCase.objects.bulk_create(run_cases)
                    run.testcases.set(valid_cases)
            except Project.DoesNotExist:
                continue

    return {"id": plan.id, "name": plan.name, "projects": project_ids, "testcases_count": len(testcase_ids)}


def _list_api_requests(**kwargs) -> Dict[str, Any]:
    """查询 API 接口列表"""
    from apps.api_testing.models import ApiRequest
    qs = ApiRequest.objects.select_related("project", "collection").all()
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    method = kwargs.get("method")
    if method:
        qs = qs.filter(method=method.upper())
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values("id", "name", "method", "url", "project__name"))
    return {"total": qs.count(), "items": items}


def _parse_curl_command(curl_command: str) -> Dict[str, Any]:
    """解析 curl 命令，提取 method/url/headers/body/params/auth。

    支持：
      - URL：curl 后第一个引号/非选项参数
      - 方法：-X / --request
      - 请求头：-H / --header
      - 请求体：-d / --data / --data-raw / --data-binary
      - 认证：-u / --user 或 Authorization Basic 头
      - 忽略 SSL：--insecure / -k
    """
    import re
    import json
    import base64
    from urllib.parse import urlparse, parse_qs

    cmd = (curl_command or "").strip()
    if not cmd:
        return {"error": "curl 命令为空"}

    # 提取 URL
    url = None
    m = re.search(r"curl\s+['\"]([^'\"]+)['\"]", cmd, re.IGNORECASE)
    if m:
        url = m.group(1)
    else:
        tokens = re.split(r"\s+", cmd)
        for i, t in enumerate(tokens):
            if t.lower() == "curl":
                for j in range(i + 1, len(tokens)):
                    if not tokens[j].startswith("-"):
                        url = tokens[j]
                        break
                break
    if not url:
        return {"error": "未从 curl 中提取到 URL"}

    # 方法：-X 优先级最高；如果有 -d/--data 且未指定 -X，默认 POST
    method = "GET"
    if re.search(r"(?:-d|--data|--data-raw|--data-binary)\s+", cmd):
        method = "POST"
    m = re.search(r"(?:-X|--request)\s+['\"]?([A-Za-z]+)['\"]?", cmd)
    if m:
        method = m.group(1).upper()

    # Headers
    headers = {}
    for m in re.finditer(r"(?:-H|--header)\s+['\"]([^'\"]+)['\"]", cmd):
        h = m.group(1)
        if ":" in h:
            key, value = h.split(":", 1)
            headers[key.strip()] = value.strip()

    # Body（支持引号包裹和无引号 JSON）
    body_raw = None
    m = re.search(r"(?:-d|--data|--data-raw|--data-binary)\s+['\"]([^'\"]*)['\"]", cmd)
    if m:
        body_raw = m.group(1)
    if body_raw is None:
        m = re.search(r"(?:-d|--data|--data-raw|--data-binary)\s+(\{.*?\}|\[.*?\])", cmd)
        if m:
            body_raw = m.group(1)

    # -u user:pass 支持
    m = re.search(r"(?:-u|--user)\s+['\"]?([^'\"\s]+)['\"]?", cmd)
    if m:
        creds = m.group(1)
        if ":" in creds:
            u, p = creds.split(":", 1)
            headers["Authorization"] = f"Basic {base64.b64encode(f'{u}:{p}'.encode()).decode()}"

    body = {}
    if body_raw:
        try:
            parsed = json.loads(body_raw)
            body = {"type": "json", "data": parsed}
        except Exception:
            if "=" in body_raw:
                body = {"type": "form-data", "data": []}
                for part in body_raw.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        body["data"].append({"key": k, "value": v, "enabled": True})
            else:
                body = {"type": "raw", "data": body_raw}

    # URL 参数
    parsed = urlparse(url)
    params = {}
    if parsed.query:
        for k, v in parse_qs(parsed.query).items():
            params[k] = v[0] if len(v) == 1 else v
    clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.scheme else url

    # Auth 信息（如果已有 Authorization Basic 头）
    auth = {}
    auth_header = headers.get("Authorization", "")
    if auth_header.lower().startswith("basic "):
        try:
            b64 = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
            username, password = decoded.split(":", 1)
            auth = {"type": "basic", "username": username, "password": password}
        except Exception:
            pass

    return {
        "method": method,
        "url": clean_url,
        "headers": headers,
        "params": params,
        "body": body,
        "auth": auth,
        "insecure": "--insecure" in cmd or " -k " in cmd or cmd.rstrip().endswith(" -k"),
    }


def _create_api_request(**kwargs) -> Dict[str, Any]:
    """解析 curl 命令并创建 API 请求定义，然后可直接用 execute_api_request 执行。"""
    from apps.api_testing.models import ApiRequest, ApiProject, ApiCollection
    from django.contrib.auth import get_user_model
    User = get_user_model()

    curl_command = kwargs.get("curl_command", "")
    if not curl_command:
        return {"error": "请提供 curl 命令"}

    parsed = _parse_curl_command(curl_command)
    if parsed.get("error"):
        return parsed

    project_id = kwargs.get("project_id")
    try:
        if project_id:
            project = ApiProject.objects.get(id=project_id)
        else:
            project = ApiProject.objects.order_by("created_at").first()
            if not project:
                return {"error": "系统中没有 API 项目，请先在接口测试模块创建项目后再试"}
    except Exception as e:
        return {"error": f"获取项目失败: {str(e)}"}

    collection = None
    if kwargs.get("collection_id"):
        try:
            collection = ApiCollection.objects.get(id=kwargs["collection_id"], project=project)
        except Exception:
            pass
    if not collection:
        collection = ApiCollection.objects.filter(project=project).order_by("created_at").first()

    # 自动生成名称
    name = kwargs.get("name")
    if not name:
        path = parsed["url"].split("?")[0].rstrip("/").split("/")[-1] or "api"
        name = f"{parsed['method']} {path}"

    # 避免重复创建
    existing = ApiRequest.objects.filter(
        project=project, method=parsed["method"], url=parsed["url"]
    ).first()
    if existing:
        return {
            "id": existing.id,
            "name": existing.name,
            "method": existing.method,
            "url": existing.url,
            "headers": existing.headers,
            "params": existing.params,
            "body": existing.body,
            "created": False,
            "message": "已存在相同接口，未重复创建",
        }

    user = User.objects.first()
    req = ApiRequest.objects.create(
        project=project,
        collection=collection,
        name=name,
        description=kwargs.get("description", "由 Hermes 从 curl 命令自动创建"),
        request_type="HTTP",
        method=parsed["method"],
        url=parsed["url"],
        headers=parsed["headers"],
        params=parsed["params"],
        body=parsed["body"],
        auth=parsed["auth"],
        created_by=user,
    )
    return {
        "id": req.id,
        "name": req.name,
        "method": req.method,
        "url": req.url,
        "headers": req.headers,
        "params": req.params,
        "body": req.body,
        "created": True,
        "message": "接口已创建",
    }


def _execute_api_request(**kwargs) -> Dict[str, Any]:
    """执行单个 API 请求"""
    from apps.api_testing.models import ApiRequest, Environment
    from apps.api_testing.utils import execute_api_request
    from django.contrib.auth import get_user_model
    User = get_user_model()

    request_id = kwargs.get("request_id")
    try:
        req = ApiRequest.objects.get(id=request_id)
    except ApiRequest.DoesNotExist:
        return {"error": f"API 请求 {request_id} 不存在"}

    env = Environment.objects.filter(is_active=True).first()
    user = User.objects.first()
    try:
        result = execute_api_request(req, env, user)
        return {
            "request_name": req.name,
            "method": req.method,
            "url": req.url,
            "status_code": result.get("status_code"),
            "response_time_ms": result.get("response_time"),
            "passed": result.get("passed", False),
            "response_body": str(result.get("response_body", ""))[:2000],
        }
    except Exception as e:
        return {"error": f"执行失败: {str(e)}"}


def _execute_api_suite(**kwargs) -> Dict[str, Any]:
    """执行 API 测试套件"""
    from apps.api_testing.models import TestSuite, Environment
    from apps.api_testing.utils import execute_test_suite
    from django.contrib.auth import get_user_model
    User = get_user_model()

    suite_id = kwargs.get("suite_id")
    try:
        suite = TestSuite.objects.get(id=suite_id)
    except TestSuite.DoesNotExist:
        return {"error": f"测试套件 {suite_id} 不存在"}

    env = suite.environment or Environment.objects.filter(is_active=True).first()
    user = User.objects.first()
    try:
        result = execute_test_suite(suite, env, user)
        return {
            "suite_name": suite.name,
            "total": result.get("total", 0),
            "passed": result.get("passed", 0),
            "failed": result.get("failed", 0),
            "duration_ms": result.get("duration"),
        }
    except Exception as e:
        return {"error": f"执行失败: {str(e)}"}


def _update_run_case_status(**kwargs) -> Dict[str, Any]:
    """更新测试执行用例状态"""
    from apps.executions.models import TestRunCase, TestRunCaseHistory
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    User = get_user_model()

    run_case_id = kwargs.get("run_case_id")
    new_status = kwargs.get("status")
    if new_status not in ("untested", "passed", "failed", "blocked", "retest"):
        return {"error": f"无效状态: {new_status}"}

    try:
        rc = TestRunCase.objects.get(id=run_case_id)
    except TestRunCase.DoesNotExist:
        return {"error": f"执行用例 {run_case_id} 不存在"}

    user = User.objects.first()
    actual_result = kwargs.get("actual_result", "")
    comments = kwargs.get("comments", "")

    TestRunCaseHistory.objects.create(
        run_case=rc, status=new_status, actual_result=actual_result,
        comments=comments, executed_by=user, executed_at=timezone.now(),
    )
    rc.status = new_status
    rc.actual_result = actual_result
    rc.comments = comments
    rc.executed_by = user
    rc.executed_at = timezone.now()
    rc.save()
    return {"id": rc.id, "status": rc.status, "testcase": rc.testcase.title}


def _list_test_reports(**kwargs) -> Dict[str, Any]:
    """查询 API 测试执行报告"""
    from apps.api_testing.models import TestExecution
    qs = TestExecution.objects.select_related("test_suite", "executed_by").all().order_by("-created_at")
    limit = min(int(kwargs.get("limit", 10)), 50)
    items = list(qs[:limit].values(
        "id", "status", "total_requests", "passed_requests", "failed_requests", "created_at",
        "test_suite__name",
    ))
    return {"total": qs.count(), "items": items}


def _generate_test_data(**kwargs) -> Dict[str, Any]:
    """生成测试数据"""
    from apps.data_factory.views import DataFactoryViewSet

    tool_name = kwargs.get("tool_name", "generate_chinese_name")
    tool_category = kwargs.get("tool_category", "test_data")
    input_data = kwargs.get("input_data", {"count": 1})

    view = DataFactoryViewSet()
    result = view.execute_tool(tool_name, tool_category, input_data)
    return result


def _list_data_tools(**kwargs) -> Dict[str, Any]:
    """查询数据工厂可用工具列表"""
    from apps.data_factory.tool_list import get_tool_list, get_categories
    return {"tools": get_tool_list(), "categories": get_categories()}


def _list_api_test_suites(**kwargs) -> Dict[str, Any]:
    """查询 API 测试套件列表（让 LLM 知道能跑哪些现成套件）"""
    from apps.api_testing.models import TestSuite
    qs = TestSuite.objects.select_related("project", "environment").all().order_by("-created_at")
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "name", "description", "created_at",
        "project__name", "environment__name",
    ))
    return {"total": qs.count(), "items": items}


def _list_ui_test_suites(**kwargs) -> Dict[str, Any]:
    """查询 UI 自动化测试套件列表"""
    from apps.ui_automation.models import TestSuite as UiTestSuite
    qs = UiTestSuite.objects.select_related("project").all().order_by("-created_at")
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "name", "description", "execution_status",
        "passed_count", "failed_count", "created_at",
        "project__name",
    ))
    return {"total": qs.count(), "items": items}


def _run_ui_automation(**kwargs) -> Dict[str, Any]:
    """执行 UI 自动化测试（AI 驱动浏览器操作）"""
    from apps.ui_automation.ai_agent import run_full_process_sync

    task_description = kwargs.get("task_description", "")
    if not task_description:
        return {"error": "请提供任务描述，如 '打开百度搜索TestHub'"}

    try:
        result = run_full_process_sync(task_description)
        return {
            "task": task_description,
            "status": result.get("status", "completed"),
            "steps": result.get("steps", []),
            "screenshots": result.get("screenshots", []),
        }
    except Exception as e:
        return {"error": f"UI 自动化执行失败: {str(e)}"}


def _run_ui_test_suite(**kwargs) -> Dict[str, Any]:
    """执行平台已有的 UI 自动化测试套件（不需用户重新写任务描述）"""
    import threading
    from apps.ui_automation.models import TestSuite as UiTestSuite
    from apps.ui_automation.test_executor import TestExecutor
    from django.contrib.auth import get_user_model
    User = get_user_model()

    suite_id = kwargs.get("suite_id")
    if not suite_id:
        return {"error": "请提供 suite_id（可先用 list_ui_test_suites 查询）"}

    try:
        suite = UiTestSuite.objects.select_related("project").get(id=suite_id)
    except UiTestSuite.DoesNotExist:
        return {"error": f"UI 测试套件 {suite_id} 不存在"}

    headless = bool(kwargs.get("headless", True))
    engine = kwargs.get("engine", "playwright")
    browser = kwargs.get("browser", "chrome")
    user = User.objects.first()

    # UI 套件执行通常分钟级，在后台线程跑避免阻塞 SSE 流
    holder = {}

    def _runner():
        try:
            executor = TestExecutor(
                test_suite=suite, engine=engine, browser=browser,
                headless=headless, executed_by=user,
            )
            executor.run()
            holder["result"] = {
                "suite_id": suite.id,
                "suite_name": suite.name,
                "execution_status": suite.execution_status,
                "passed_count": suite.passed_count,
                "failed_count": suite.failed_count,
                "hint": "查看完整报告：测试管理 → UI自动化 → 测试报告",
            }
        except Exception as e:
            holder["error"] = str(e)

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout=300)  # 最长等 5 分钟

    if "error" in holder:
        return {"error": f"UI 套件执行失败: {holder['error']}"}
    if "result" not in holder:
        return {
            "suite_id": suite.id,
            "suite_name": suite.name,
            "status": "running",
            "message": "执行超过 5 分钟仍在运行，请稍后用 list_ui_test_suites 查询最新状态，或到测试报告页面查看",
        }
    return holder["result"]


def _ai_generate_testcases(**kwargs) -> Dict[str, Any]:
    """AI 生成测试用例（异步任务）"""
    from apps.requirement_analysis.models import TestCaseGenerationTask
    import uuid

    requirement = kwargs.get("requirement", "")
    if not requirement:
        return {"error": "请提供需求描述"}

    task_id = f"agent_{uuid.uuid4().hex[:12]}"
    task = TestCaseGenerationTask.objects.create(
        task_id=task_id,
        title=kwargs.get("title", f"Agent生成-{task_id[:8]}"),
        requirement_text=requirement,
        status="pending",
    )

    # 异步触发 Celery 任务
    try:
        from apps.requirement_analysis.generation_task_runner import run_generation_task
        run_generation_task.delay(task.task_id)
    except Exception as e:
        logger.warning(f"Celery 任务触发失败，将同步执行: {e}")
        # 如果 Celery 不可用，直接返回任务 ID 让前端轮询
        pass

    return {"task_id": task.task_id, "status": "pending", "hint": "用 task_id 轮询 GET /api/requirement-analysis/testcase-generation/{task_id}/ 获取结果"}


def _list_knowledge_bases(**kwargs) -> Dict[str, Any]:
    """列出所有可用知识库及其文档数量，供检索前了解知识库结构"""
    from apps.requirement_analysis.dify_kb_service import resolve_dify_config, list_datasets
    from apps.assistant.models import DifyConfig

    config_id = kwargs.get("dify_config_id")
    config = resolve_dify_config(config_id) if config_id else DifyConfig.get_active_config()
    if not config:
        return {"error": "未配置 Dify 知识库连接"}

    try:
        ds_payload = list_datasets(config, limit=100)
        datasets = ds_payload.get("data") or []
        if not datasets:
            return {"error": "Dify 中未创建任何知识库"}
        items = [{
            "id": d["id"],
            "name": d["name"],
            "description": d.get("description", ""),
            "document_count": d.get("document_count", 0),
            "word_count": d.get("word_count", 0),
        } for d in datasets]
        return {"total": len(items), "datasets": items}
    except Exception as e:
        return {"error": f"获取知识库列表失败: {str(e)}"}


def _search_knowledge_base(**kwargs) -> Dict[str, Any]:
    """知识库检索 — 支持跨全部知识库搜索或指定知识库检索"""
    from apps.requirement_analysis.dify_kb_service import (
        resolve_dify_config, retrieve_from_dataset, list_datasets,
    )
    from apps.assistant.models import DifyConfig

    query = kwargs.get("query", "")
    if not query:
        return {"error": "请提供查询内容"}

    config_id = kwargs.get("dify_config_id")
    config = resolve_dify_config(config_id) if config_id else DifyConfig.get_active_config()
    if not config:
        return {"error": "未配置 Dify 知识库连接"}

    top_k = int(kwargs.get("top_k", 5))
    search_method = kwargs.get("search_method", "semantic_search")
    target_dataset_id = kwargs.get("dataset_id")

    # 获取全部知识库列表
    try:
        ds_payload = list_datasets(config, limit=100)
        all_datasets = ds_payload.get("data") or []
        if not all_datasets:
            return {"error": "Dify 中未创建任何知识库，请在 Dify 控制台创建知识库"}
    except Exception as e:
        return {"error": f"获取知识库列表失败: {str(e)}"}

    # 决定要搜索哪些知识库
    if target_dataset_id:
        datasets_to_search = [d for d in all_datasets if d["id"] == target_dataset_id]
        if not datasets_to_search:
            available = [{"id": d["id"], "name": d["name"]} for d in all_datasets]
            return {"error": f"未找到 dataset_id={target_dataset_id} 的知识库", "available": available}
    else:
        # 不指定则跨全部知识库检索
        datasets_to_search = all_datasets

    all_results = []
    searched_names = []
    errors = []
    # 多种检索方法轮询：先按用户指定的方法，再依次回退到更稳的方法
    # 原因：Dify 0.x 服务端 semantic_search / full_text_search 在没配 embedding 模型时返回 0，
    # 但 keyword_search 通常能命中关键词
    method_candidates = [search_method]
    for fallback in ("keyword_search", "full_text_search", "semantic_search", "hybrid_search"):
        if fallback not in method_candidates:
            method_candidates.append(fallback)

    # 把内容按"句号/分号/换行"切段，方便前端按段落渲染
    def _split_segments(text: str):
        text = (text or "").strip()
        if not text:
            return []
        # 优先按显式换行切；没有换行则按中文/英文句号、分号、问号、感叹号切
        if "\n" in text:
            parts = [p.strip() for p in re.split(r"[\r\n]+", text) if p.strip()]
        else:
            parts = [p.strip() for p in re.split(r"(?<=[。！？；!?;\.])\s*", text) if p.strip()]
        # 兜底：再按 **** 标题符切（Dify 文档常出现）
        final = []
        for p in parts:
            if "**" in p:
                sub = [s.strip() for s in p.split("**") if s.strip()]
                final.extend(sub)
            else:
                final.append(p)
        return final

    for ds in datasets_to_search:
        ds_id = ds["id"]
        ds_name = ds.get("name", ds_id)
        if ds_name not in searched_names:
            searched_names.append(ds_name)
        ds_records = []
        for method in method_candidates:
            try:
                records = retrieve_from_dataset(
                    config, ds_id, query, top_k=top_k, search_method=method,
                )
                if records:
                    ds_records = records
                    break  # 找到结果就跳出 method 循环
            except Exception as e:
                errors.append(f"{ds_name}/{method}: {str(e)[:100]}")
                continue
        for rec in ds_records:
            segment = rec.get("segment") or {}
            raw_content = segment.get("content") or ""
            doc = (segment.get("document") or {}).get("name") or ""
            score = rec.get("score")
            # 单条总长 1200 字以内，按段落切，paragraphs 是数组
            paragraphs = _split_segments(raw_content[:1200])
            all_results.append({
                "content": "\n".join(paragraphs) if paragraphs else raw_content[:200],
                "paragraphs": paragraphs,
                "document": doc,
                "dataset": ds_name,
                "score": round(score, 4) if isinstance(score, (int, float)) else None,
            })

    # 按 score 降序合并
    all_results.sort(key=lambda x: x.get("score") or 0, reverse=True)
    # 总结果数上限：每库 top_k 条，但最多 20 条
    max_results = min(top_k * len(datasets_to_search), 20)
    all_results = all_results[:max_results]

    result = {
        "query": query,
        "datasets_searched": searched_names,
        "search_method": search_method,
        "results": all_results,
        "total": len(all_results),
    }
    if errors:
        result["partial_errors"] = errors
    return result


def _list_execution_history(**kwargs) -> Dict[str, Any]:
    """查询测试执行历史"""
    from apps.executions.models import TestRunCaseHistory
    qs = TestRunCaseHistory.objects.select_related("run_case__testcase", "executed_by").all().order_by("-executed_at")
    run_case_id = kwargs.get("run_case_id")
    if run_case_id:
        qs = qs.filter(run_case_id=run_case_id)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "status", "actual_result", "comments", "executed_at",
        "run_case__testcase__title", "executed_by__username",
    ))
    return {"total": qs.count(), "items": items}


# ────────────────────────── APP 自动化 ──────────────────────────

def _list_app_test_suites(**kwargs) -> Dict[str, Any]:
    """查询 APP 自动化测试套件列表"""
    from apps.app_automation.models import AppTestSuite
    qs = AppTestSuite.objects.select_related("project").all().order_by("-created_at")
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "name", "description", "execution_status",
        "passed_count", "failed_count", "last_run_at", "created_at",
        "project__name",
    ))
    return {"total": qs.count(), "items": items}


def _list_app_devices(**kwargs) -> Dict[str, Any]:
    """查询可用的 APP 调试设备列表（执行 APP 套件必填 device_id）"""
    from apps.app_automation.models import AppDevice
    qs = AppDevice.objects.filter(is_active=True).order_by("-updated_at")
    limit = min(int(kwargs.get("limit", 30)), 100)
    items = list(qs[:limit].values(
        "id", "device_id", "device_name", "platform", "os_version",
        "status", "is_active",
    ))
    return {"total": qs.count(), "items": items}


def _run_app_test_suite(**kwargs) -> Dict[str, Any]:
    """执行 APP 自动化测试套件（需提供 device_id，可先用 list_app_devices 查询）"""
    from apps.app_automation.models import AppTestSuite, AppDevice, AppTestSuiteCase
    from apps.app_automation.tasks import execute_app_suite_task

    suite_id = kwargs.get("suite_id")
    device_id = kwargs.get("device_id")
    package_name = kwargs.get("package_name", "")

    if not suite_id:
        return {"error": "请提供 suite_id"}
    if not device_id:
        return {"error": "请提供 device_id（先用 list_app_devices 查询）"}

    try:
        suite = AppTestSuite.objects.select_related("project").get(id=suite_id)
    except AppTestSuite.DoesNotExist:
        return {"error": f"APP 测试套件 {suite_id} 不存在"}

    try:
        device = AppDevice.objects.get(device_id=device_id)
    except AppDevice.DoesNotExist:
        return {"error": f"设备 {device_id} 不存在"}

    suite_cases = suite.suite_cases.select_related("test_case").all()
    if not suite_cases.exists():
        return {"error": "该套件未包含任何测试用例"}

    # 同步调用 Celery（app_automation 的 run 接口是同步触发 Celery）
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.first()

        # 创建执行记录
        from apps.app_automation.models import AppTestExecution
        executions = []
        for sc in suite_cases:
            execution = AppTestExecution.objects.create(
                test_case=sc.test_case, test_suite=suite,
                device=device, user=user, status='pending',
            )
            executions.append(execution)

        suite.execution_status = 'running'
        suite.save(update_fields=['execution_status'])

        execution_ids = [e.id for e in executions]
        task = execute_app_suite_task.delay(
            suite_id=suite.id, execution_ids=execution_ids,
            package_name=package_name,
        )
        if executions:
            executions[0].task_id = task.id
            executions[0].save(update_fields=['task_id'])

        return {
            "suite_id": suite.id,
            "suite_name": suite.name,
            "task_id": task.id,
            "execution_ids": execution_ids,
            "test_case_count": len(executions),
            "device_id": device.device_id,
            "status": "submitted",
            "hint": "已在后台执行，可稍后用 list_app_test_suites 查询最新状态，或到 APP自动化→执行记录查看",
        }
    except Exception as e:
        logger.exception("APP 套件执行失败")
        return {"error": f"APP 套件执行失败: {str(e)}"}


# ────────────────────────── AI 评测师（配置中心 / Dify Chat） ──────────────────────────

def _list_dify_configs(**kwargs) -> Dict[str, Any]:
    """查询 Dify 配置列表（含 AI 评测师、对话应用、工作流等）"""
    from apps.assistant.models import DifyConfig
    qs = DifyConfig.objects.all().order_by("-is_active", "-created_at")
    items = list(qs.values("id", "api_url", "app_type", "invoke_mode", "is_active", "created_at"))
    return {
        "total": qs.count(),
        "active_id": qs.filter(is_active=True).values_list("id", flat=True).first(),
        "items": items,
    }


def _chat_ai_evaluator(**kwargs) -> Dict[str, Any]:
    """调用 AI 评测师（Dify chat 应用或 workflow）回答问题。

    评测师配置必须在「配置中心 → AI评测师配置」先填写应用 API Key（app- 开头）。
    """
    import requests as _req
    from apps.assistant.models import DifyConfig
    from django.contrib.auth import get_user_model
    User = get_user_model()

    message = (kwargs.get("message") or "").strip()
    if not message:
        return {
            "error": "message 不能为空。请把要问 AI 评测师的具体问题作为 message 参数传入。"
                     "例如：message='登录功能需要覆盖哪些测试场景？'",
            "hint": "chat_ai_evaluator 是一个问答工具，需要你先组织好问题再调用，不要传空字符串。",
        }

    config_id = kwargs.get("dify_config_id")
    if config_id:
        try:
            config = DifyConfig.objects.get(pk=config_id)
        except DifyConfig.DoesNotExist:
            return {"error": f"Dify 配置 {config_id} 不存在"}
    else:
        config = DifyConfig.get_active_config()
    if not config:
        return {"error": "未配置 Dify，请先在「配置中心 → AI评测师配置」中配置"}

    api_key = (config.api_key or "").strip()
    if api_key.startswith("Bearer "):
        api_key = api_key[7:].strip()
    for prefix in ("app-", "dataset-"):
        if api_key.startswith(prefix):
            api_key = api_key[len(prefix):]
            break

    if not api_key:
        return {"error": "该 Dify 配置未填写应用 API Key（app-），无法使用 AI 评测师"}

    api_url = (config.api_url or "").rstrip("/")
    # 归一化：补 /v1
    if not api_url.endswith("/v1") and "/v1/" not in api_url:
        api_url = f"{api_url}/v1"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    user = User.objects.first()
    user_id = str(user.id) if user else "agent"

    invoke_mode = (config.invoke_mode or "workflow").strip()

    # 用 streaming 模式，避免一次 blocking 60-120s 卡死 SSE 流
    # 边读边拼 answer，对前端体验更友好，且能在中途报错时立即返回
    try:
        if invoke_mode == "chat":
            url = f"{api_url}/chat-messages"
            payload = {
                "inputs": {},
                "query": message,
                "user": user_id,
                "response_mode": "streaming",
            }
        else:  # workflow
            url = f"{api_url}/workflows/run"
            payload = {
                "inputs": {"query": message, "question": message, "input": message},
                "user": user_id,
                "response_mode": "streaming",
            }

        answer_parts = []
        conversation_id = None
        message_id = None
        workflow_run_id = None
        last_error = None
        finished = False

        # 10 分钟总超时（workflow 慢），单 chunk 间隔 30s
        resp = _req.post(url, headers=headers, json=payload, timeout=(10, 30), stream=True)
        resp.raise_for_status()

        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            # SSE 格式: "data: {...}" 或 "event: ..."
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    finished = True
                    break
                try:
                    obj = json.loads(chunk)
                except Exception:
                    continue
                event = obj.get("event") or ""
                if event == "message" or event == "agent_message":
                    piece = obj.get("answer") or ""
                    if piece:
                        answer_parts.append(piece)
                elif event == "workflow_finished":
                    outputs = (obj.get("data") or {}).get("outputs") or {}
                    final = (
                        outputs.get("answer") or outputs.get("result")
                        or outputs.get("text") or outputs.get("output")
                    )
                    if final:
                        answer_parts.append(str(final))
                    workflow_run_id = obj.get("workflow_run_id")
                    finished = True
                    break
                elif event == "message_end":
                    conversation_id = obj.get("conversation_id")
                    message_id = obj.get("message_id")
                    finished = True
                    break
                elif event == "error":
                    last_error = obj.get("message") or "Dify 返回错误事件"
                elif event == "workflow_failed":
                    last_error = (obj.get("data") or {}).get("error") or "Workflow 执行失败"

        answer = "".join(answer_parts).strip()
        result = {
            "answer": answer,
            "mode": invoke_mode,
        }
        if conversation_id:
            result["conversation_id"] = conversation_id
        if message_id:
            result["message_id"] = message_id
        if workflow_run_id:
            result["workflow_run_id"] = workflow_run_id
        if last_error and not answer:
            result["error"] = last_error
        return result
    except _req.exceptions.Timeout:
        return {"error": "AI 评测师响应超时（>10 分钟）", "mode": invoke_mode}
    except _req.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else "?"
        body = (e.response.text[:300] if e.response is not None else "")
        return {"error": f"AI 评测师返回错误 {status_code}: {body}", "mode": invoke_mode}
    except Exception as e:
        logger.exception("AI 评测师调用失败")
        return {"error": f"AI 评测师调用失败: {str(e)}", "mode": invoke_mode}


def _list_ai_model_configs(**kwargs) -> Dict[str, Any]:
    """查询 AI 模型配置列表（配置中心）"""
    try:
        from apps.requirement_analysis.models import AIModelConfig
        qs = AIModelConfig.objects.all().order_by("-is_active", "-updated_at")
        items = list(qs.values("id", "name", "role", "provider", "model_name", "is_active", "base_url"))
        return {"total": qs.count(), "items": items}
    except Exception as e:
        return {"error": f"查询 AI 模型配置失败: {str(e)}"}


# ────────────────────────── 用例评审 ──────────────────────────

def _list_reviews(**kwargs) -> Dict[str, Any]:
    """查询用例评审列表"""
    from apps.reviews.models import TestCaseReview
    qs = TestCaseReview.objects.select_related("creator").all().order_by("-created_at")
    status = kwargs.get("status")
    if status:
        qs = qs.filter(status=status)
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(projects__id=project_id)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "title", "status", "priority", "deadline", "created_at", "creator__username",
    ))
    return {"total": qs.count(), "items": items}


def _create_review(**kwargs) -> Dict[str, Any]:
    """创建用例评审"""
    from apps.reviews.models import TestCaseReview, ReviewAssignment
    from django.contrib.auth import get_user_model
    User = get_user_model()

    creator = User.objects.first()
    review = TestCaseReview.objects.create(
        title=kwargs.get("title", "未命名评审"),
        description=kwargs.get("description", ""),
        creator=creator,
        priority=kwargs.get("priority", "medium"),
    )
    project_ids = kwargs.get("project_ids", [])
    if project_ids:
        review.projects.set(project_ids)
    testcase_ids = kwargs.get("testcase_ids", [])
    if testcase_ids:
        review.testcases.set(testcase_ids)
    reviewer_ids = kwargs.get("reviewer_ids", [])
    for rid in reviewer_ids:
        try:
            reviewer = User.objects.get(id=rid)
            ReviewAssignment.objects.get_or_create(review=review, reviewer=reviewer)
        except User.DoesNotExist:
            continue
    return {"id": review.id, "title": review.title, "status": review.status, "reviewers_count": len(reviewer_ids)}


def _submit_review_decision(**kwargs) -> Dict[str, Any]:
    """提交评审意见（通过/拒绝/弃权）"""
    from apps.reviews.models import TestCaseReview, ReviewAssignment
    from django.utils import timezone
    from django.contrib.auth import get_user_model
    User = get_user_model()

    review_id = kwargs.get("review_id")
    try:
        review = TestCaseReview.objects.get(id=review_id)
    except TestCaseReview.DoesNotExist:
        return {"error": f"评审 {review_id} 不存在"}

    user = User.objects.first()
    try:
        assignment = ReviewAssignment.objects.get(review=review, reviewer=user)
    except ReviewAssignment.DoesNotExist:
        return {"error": "当前用户未被分配为此评审的评审人"}

    new_status = kwargs.get("status", "approved")
    if new_status not in ("approved", "rejected", "abstained"):
        return {"error": f"无效状态: {new_status}"}

    assignment.status = new_status
    assignment.comment = kwargs.get("comment", "")
    assignment.reviewed_at = timezone.now()
    assignment.save()

    pending = ReviewAssignment.objects.filter(review=review, status="pending").count()
    if pending == 0:
        approved = ReviewAssignment.objects.filter(review=review, status="approved").count()
        total = ReviewAssignment.objects.filter(review=review).count()
        review.status = "approved" if approved == total else "rejected"
        review.completed_at = timezone.now()
        review.save()

    return {"review_id": review.id, "assignment_status": assignment.status, "review_status": review.status}


# ────────────────────────── 版本管理 ──────────────────────────

def _list_versions(**kwargs) -> Dict[str, Any]:
    """查询版本列表"""
    from apps.versions.models import Version
    qs = Version.objects.all().order_by("-created_at")
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(projects__id=project_id)
    is_baseline = kwargs.get("is_baseline")
    if is_baseline is not None:
        qs = qs.filter(is_baseline=is_baseline)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values("id", "name", "description", "is_baseline", "created_at"))
    return {"total": qs.count(), "items": items}


def _create_version(**kwargs) -> Dict[str, Any]:
    """创建版本"""
    from apps.versions.models import Version
    from django.contrib.auth import get_user_model
    User = get_user_model()

    creator = User.objects.first()
    version = Version.objects.create(
        name=kwargs.get("name", "未命名版本"),
        description=kwargs.get("description", ""),
        is_baseline=kwargs.get("is_baseline", False),
        created_by=creator,
    )
    project_ids = kwargs.get("project_ids", [])
    if project_ids:
        version.projects.set(project_ids)
    return {"id": version.id, "name": version.name, "is_baseline": version.is_baseline}


# ────────────────────────── 知识图谱 ──────────────────────────

def _query_kg_subgraph(**kwargs) -> Dict[str, Any]:
    """查询知识图谱子图（以某个实体为中心，展开 N 层关系）"""
    from apps.knowledge_graph.query import get_subgraph

    entity_key = kwargs.get("entity_key", "")
    if not entity_key:
        return {"error": "请提供 entity_key"}

    depth = min(int(kwargs.get("depth", 2)), 5)
    max_nodes = min(int(kwargs.get("max_nodes", 200)), 500)

    data = get_subgraph(entity_key, depth=depth, max_nodes=max_nodes)
    return {
        "root": data.get("root"),
        "nodes_count": len(data.get("nodes", [])),
        "edges_count": len(data.get("edges", [])),
        "nodes": data.get("nodes", [])[:50],
        "edges": data.get("edges", [])[:50],
    }


def _get_project_coverage(**kwargs) -> Dict[str, Any]:
    """查询项目知识图谱覆盖度报告（用例对需求/功能模块的覆盖情况）"""
    from apps.knowledge_graph.coverage import get_project_coverage_report

    project_id = kwargs.get("project_id")
    if not project_id:
        return {"error": "请提供 project_id"}

    limit = min(int(kwargs.get("limit", 100)), 500)
    data = get_project_coverage_report(project_id, limit=limit)
    return data


def _recommend_execution(**kwargs) -> Dict[str, Any]:
    """基于知识图谱的 AI 推荐执行：分析覆盖缺口和执行历史，推荐下一步测试目标。"""
    from apps.knowledge_graph.recommend import recommend_execution

    project_id = kwargs.get("project_id")
    if not project_id:
        return {"error": "请提供 project_id"}
    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return {"error": "无效的 project_id"}

    return recommend_execution(project_id)


def _build_knowledge_graph(**kwargs) -> Dict[str, Any]:
    """从 Dify 知识库文档构建知识图谱（LLM 抽取功能点 + 跨文档关联）。"""
    from apps.knowledge_graph.builder import (
        extract_and_sync_function_points,
        extract_and_sync_cross_doc_relations,
        sync_all_kb_functions,
    )

    dataset_id = (kwargs.get("dataset_id") or "").strip()
    if not dataset_id:
        return {"error": "请提供 dataset_id（Dify 知识库 ID）"}

    project_id = kwargs.get("project_id")
    try:
        project_id = int(project_id) if project_id is not None else None
    except (TypeError, ValueError):
        project_id = None

    # 步骤 1: 同步已有 KbFunction 到图谱
    synced = sync_all_kb_functions(dataset_id=dataset_id, project_id=project_id)

    # 步骤 2: LLM 抽取功能点
    result = extract_and_sync_function_points(
        dataset_id,
        dify_config_id=kwargs.get("dify_config_id"),
        document_ids=kwargs.get("document_ids"),
        project_id=project_id,
    )

    # 步骤 3: 跨文档关联
    cross_doc = extract_and_sync_cross_doc_relations(
        dataset_id,
        project_id=project_id,
        min_confidence=0.6,
        persist=True,
    )

    return {
        "dataset_id": dataset_id,
        "project_id": project_id,
        "kb_functions_synced": synced,
        "function_points_extraction": result,
        "cross_doc_relations": {
            "suggestions_count": cross_doc.get("count", 0),
            "persisted": cross_doc.get("persist"),
        },
        "detail": (
            f"知识图谱构建完成：同步 {synced} 个功能模块，"
            f"处理 {result.get('documents_processed', 0)} 个文档，"
            f"抽取 {result.get('points_extracted', 0)} 个功能点，"
            f"生成 {cross_doc.get('count', 0)} 条跨文档关联。"
        ),
    }


# ────────────────────────── 测试执行（扩展） ──────────────────────────

def _list_test_runs(**kwargs) -> Dict[str, Any]:
    """查询测试执行记录列表"""
    from apps.executions.models import TestRun
    qs = TestRun.objects.select_related("test_plan", "project", "assignee").all().order_by("-created_at")
    plan_id = kwargs.get("plan_id")
    if plan_id:
        qs = qs.filter(test_plan_id=plan_id)
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    status = kwargs.get("status")
    if status:
        qs = qs.filter(status=status)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "name", "status", "started_at", "completed_at", "created_at",
        "test_plan__name", "project__name", "assignee__username",
    ))
    return {"total": qs.count(), "items": items}


def _start_test_run(**kwargs) -> Dict[str, Any]:
    """启动测试执行（将状态改为进行中）"""
    from apps.executions.models import TestRun
    from django.utils import timezone

    run_id = kwargs.get("run_id")
    try:
        run = TestRun.objects.get(id=run_id)
    except TestRun.DoesNotExist:
        return {"error": f"测试执行 {run_id} 不存在"}

    if run.status not in ("untested", "blocked"):
        return {"error": f"当前状态 {run.status} 无法启动"}

    run.status = "in_progress"
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at"])
    return {"id": run.id, "name": run.name, "status": run.status}


# ────────────────────────── 测试套件（通用） ──────────────────────────

def _list_test_suites(**kwargs) -> Dict[str, Any]:
    """查询通用测试套件列表（testsuites 应用）"""
    from apps.testsuites.models import TestSuite
    qs = TestSuite.objects.select_related("project", "author").all().order_by("-created_at")
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "name", "description", "project__name", "author__username", "created_at",
    ))
    return {"total": qs.count(), "items": items}


def _create_test_suite(**kwargs) -> Dict[str, Any]:
    """创建通用测试套件并关联用例"""
    from apps.testsuites.models import TestSuite, TestSuiteCase
    from apps.projects.models import Project
    from apps.testcases.models import TestCase
    from django.contrib.auth import get_user_model
    User = get_user_model()

    project_id = kwargs.get("project_id")
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return {"error": f"项目 {project_id} 不存在"}

    author = User.objects.first()
    suite = TestSuite.objects.create(
        project=project,
        name=kwargs.get("name", "未命名套件"),
        description=kwargs.get("description", ""),
        author=author,
    )
    testcase_ids = kwargs.get("testcase_ids", [])
    if testcase_ids:
        valid_cases = TestCase.objects.filter(id__in=testcase_ids)
        for idx, tc in enumerate(valid_cases):
            TestSuiteCase.objects.create(testsuite=suite, testcase=tc, order=idx)
    return {"id": suite.id, "name": suite.name, "testcases_count": len(testcase_ids)}


# ────────────────────────── 报告仪表盘 ──────────────────────────

def _get_dashboard_stats(**kwargs) -> Dict[str, Any]:
    """查询测试管理仪表盘统计数据"""
    from apps.executions.models import TestPlan, TestRun
    from apps.testcases.models import TestCase
    from apps.projects.models import Project

    project_id = kwargs.get("project_id")
    cases_qs = TestCase.objects.all()
    plans_qs = TestPlan.objects.filter(is_active=True)
    if project_id:
        cases_qs = cases_qs.filter(project_id=project_id)
        plans_qs = plans_qs.filter(projects__id=project_id)

    total_projects = Project.objects.count()
    total_cases = cases_qs.count()
    total_plans = plans_qs.count()
    runs_qs = TestRun.objects.all()
    if project_id:
        runs_qs = runs_qs.filter(project_id=project_id)
    total_runs = runs_qs.count()

    status_dist = {s: cases_qs.filter(status=s).count() for s in ("draft", "active", "deprecated")}
    priority_dist = {p: cases_qs.filter(priority=p).count() for p in ("low", "medium", "high", "critical")}

    recent_runs = list(runs_qs.order_by("-created_at").values(
        "id", "name", "status", "created_at", "project__name"
    )[:10])

    return {
        "total_projects": total_projects,
        "total_cases": total_cases,
        "total_plans": total_plans,
        "total_runs": total_runs,
        "case_status_distribution": status_dist,
        "case_priority_distribution": priority_dist,
        "recent_runs": recent_runs,
    }


# ────────────────────────── 用户 ──────────────────────────

def _list_users(**kwargs) -> Dict[str, Any]:
    """查询系统用户列表（用于指派评审人/执行人）"""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    qs = User.objects.filter(is_active=True).order_by("username")
    keyword = kwargs.get("keyword")
    if keyword:
        qs = qs.filter(models.Q(username__icontains=keyword) | models.Q(first_name__icontains=keyword))
    limit = min(int(kwargs.get("limit", 30)), 100)
    items = list(qs[:limit].values("id", "username", "email", "department", "position"))
    return {"total": qs.count(), "items": items}


# ────────────────────────── 测试用例（扩展） ──────────────────────────

def _get_testcase_detail(**kwargs) -> Dict[str, Any]:
    """查询单条测试用例详情"""
    from apps.testcases.models import TestCase
    tc_id = kwargs.get("testcase_id")
    try:
        tc = TestCase.objects.select_related("project", "author", "assignee").get(id=tc_id)
    except TestCase.DoesNotExist:
        return {"error": f"用例 {tc_id} 不存在"}
    return {
        "id": tc.id,
        "title": tc.title,
        "description": tc.description,
        "preconditions": tc.preconditions,
        "steps": tc.steps,
        "expected_result": tc.expected_result,
        "priority": tc.priority,
        "status": tc.status,
        "test_type": tc.test_type,
        "tags": tc.tags,
        "project": tc.project.name,
        "author": tc.author.username,
        "assignee": tc.assignee.username if tc.assignee else None,
        "created_at": tc.created_at.isoformat(),
    }


def _update_testcase(**kwargs) -> Dict[str, Any]:
    """更新测试用例字段（优先级、状态、指派人等）"""
    from apps.testcases.models import TestCase
    from django.contrib.auth import get_user_model
    User = get_user_model()

    tc_id = kwargs.get("testcase_id")
    try:
        tc = TestCase.objects.get(id=tc_id)
    except TestCase.DoesNotExist:
        return {"error": f"用例 {tc_id} 不存在"}

    updated_fields = []
    for field in ("title", "description", "preconditions", "steps", "expected_result", "priority", "status", "test_type"):
        val = kwargs.get(field)
        if val is not None:
            setattr(tc, field, val)
            updated_fields.append(field)
    if kwargs.get("assignee_id"):
        try:
            tc.assignee = User.objects.get(id=kwargs["assignee_id"])
            updated_fields.append("assignee")
        except User.DoesNotExist:
            pass
    if updated_fields:
        tc.save(update_fields=updated_fields)
    return {"id": tc.id, "title": tc.title, "updated_fields": updated_fields}


def _delete_testcase(**kwargs) -> Dict[str, Any]:
    """删除测试用例"""
    from apps.testcases.models import TestCase
    tc_id = kwargs.get("testcase_id")
    try:
        tc = TestCase.objects.get(id=tc_id)
    except TestCase.DoesNotExist:
        return {"error": f"用例 {tc_id} 不存在"}
    title = tc.title
    tc.delete()
    return {"id": tc_id, "title": title, "deleted": True}


# ────────────────────────── 需求分析（扩展） ──────────────────────────

def _list_requirement_docs(**kwargs) -> Dict[str, Any]:
    """查询需求文档列表"""
    from apps.requirement_analysis.models import RequirementDocument
    qs = RequirementDocument.objects.select_related("uploaded_by", "project").all().order_by("-created_at")
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    status = kwargs.get("status")
    if status:
        qs = qs.filter(status=status)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "title", "document_type", "status", "file_size",
        "uploaded_by__username", "project__name", "created_at",
    ))
    return {"total": qs.count(), "items": items}


def _get_generation_task_status(**kwargs) -> Dict[str, Any]:
    """查询 AI 用例生成任务的状态和结果"""
    from apps.requirement_analysis.models import TestCaseGenerationTask
    task_id = kwargs.get("task_id")
    if not task_id:
        return {"error": "请提供 task_id"}
    try:
        task = TestCaseGenerationTask.objects.get(task_id=task_id)
    except TestCaseGenerationTask.DoesNotExist:
        return {"error": f"任务 {task_id} 不存在"}
    result = {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status,
        "progress": task.progress,
        "requirement_preview": (task.requirement_text or "")[:200],
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }
    if task.status == "completed":
        result["generated_preview"] = (task.generated_test_cases or "")[:500]
        result["review_feedback"] = (task.review_feedback or "")[:300]
        result["hint"] = "可在「需求分析 → 用例生成」页面查看完整用例"
    elif task.status == "failed":
        result["error"] = "生成失败，请检查 AI 模型配置"
    return result


# ────────────────────────── API 环境 ──────────────────────────

def _list_api_environments(**kwargs) -> Dict[str, Any]:
    """查询 API 测试环境列表"""
    from apps.api_testing.models import Environment
    qs = Environment.objects.all().order_by("-is_active", "-updated_at")
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    is_active = kwargs.get("is_active")
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values("id", "name", "scope", "is_active", "project__name", "updated_at"))
    return {"total": qs.count(), "items": items}


# ────────────────────────── 项目（扩展） ──────────────────────────

def _create_project(**kwargs) -> Dict[str, Any]:
    """创建项目"""
    from apps.projects.models import Project
    from django.contrib.auth import get_user_model
    User = get_user_model()

    owner = User.objects.first()
    project = Project.objects.create(
        name=kwargs.get("name", "未命名项目"),
        description=kwargs.get("description", ""),
        status=kwargs.get("status", "active"),
        owner=owner,
    )
    return {"id": project.id, "name": project.name, "status": project.status}


def _get_project_detail(**kwargs) -> Dict[str, Any]:
    """查询项目详情（含统计）"""
    from apps.projects.models import Project
    from apps.testcases.models import TestCase
    from apps.executions.models import TestPlan, TestRun

    project_id = kwargs.get("project_id")
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return {"error": f"项目 {project_id} 不存在"}

    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "owner": project.owner.username,
        "created_at": project.created_at.isoformat(),
        "stats": {
            "testcases": TestCase.objects.filter(project=project).count(),
            "test_plans": TestPlan.objects.filter(projects=project).count(),
            "test_runs": TestRun.objects.filter(project=project).count(),
        },
    }


# ────────────────────────────── Skill 技能工具 ──────────────────────────────

def _list_skills(**kwargs) -> Dict[str, Any]:
    """查询可用的 Skill 技能列表"""
    from apps.requirement_analysis.models import TestCaseSkill

    skill_type = kwargs.get("skill_type")
    qs = TestCaseSkill.objects.filter(is_active=True)
    if skill_type:
        qs = qs.filter(skill_type=skill_type)
    qs = qs.order_by("sort_order", "-created_at")
    items = list(qs.values(
        "id", "name", "icon", "skill_type", "description",
        "output_format", "is_builtin",
    ))
    # 补充 display 字段
    type_map = dict(TestCaseSkill.SKILL_TYPE_CHOICES)
    for item in items:
        item["skill_type_display"] = type_map.get(item["skill_type"], item["skill_type"])
    return {"count": len(items), "items": items}


def _use_skill(**kwargs) -> Dict[str, Any]:
    """使用指定 Skill 处理输入内容"""
    from asgiref.sync import async_to_sync
    from apps.requirement_analysis.models import TestCaseSkill, AIModelService

    skill_id = kwargs.get("skill_id")
    input_text = kwargs.get("input_text", "")

    if not skill_id:
        return {"error": "skill_id 不能为空"}
    if not input_text.strip():
        return {"error": "input_text 不能为空"}

    try:
        skill = TestCaseSkill.objects.get(pk=skill_id, is_active=True)
    except TestCaseSkill.DoesNotExist:
        return {"error": f"Skill {skill_id} 不存在或未启用"}

    # 解析模型配置
    model_config = skill.resolve_model_config()
    if not model_config:
        return {"error": "未配置可用的 AI 模型，请先在配置中心添加 writer 角色的模型"}

    # 解析系统提示词
    system_prompt = skill.resolve_prompt_content()
    if not system_prompt.strip():
        return {"error": "该 Skill 没有配置系统提示词"}

    # 调用 LLM
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": input_text},
    ]

    try:
        response = async_to_sync(AIModelService.call_openai_compatible_api)(model_config, messages)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "skill_name": skill.name,
            "skill_type": skill.get_skill_type_display(),
            "output": content,
            "output_format": skill.output_format,
        }
    except Exception as e:
        return {"error": f"Skill 执行失败: {str(e)}"}


# ────────────────────────────── 性能测试工具 ──────────────────────────────

def _list_performance_scripts(**kwargs) -> Dict[str, Any]:
    """查询性能测试脚本列表。"""
    from apps.performance_testing.models import PerformanceScript
    qs = PerformanceScript.objects.prefetch_related("projects", "created_by").all()
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(projects__id=project_id)
    script_type = kwargs.get("script_type")
    if script_type:
        qs = qs.filter(script_type=script_type)
    status_filter = kwargs.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    keyword = kwargs.get("keyword")
    if keyword:
        qs = qs.filter(models.Q(name__icontains=keyword) | models.Q(description__icontains=keyword))
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "name", "description", "status", "script_type",
        "thread_count", "ramp_up", "duration", "realtime_enabled", "created_at",
    ))
    # PerformanceScript.projects 是 M2M，批量取每个脚本的第一个关联项目名
    script_ids = [i["id"] for i in items]
    projects_map = {}
    for script in PerformanceScript.objects.filter(id__in=script_ids).prefetch_related("projects"):
        p = script.projects.first()
        projects_map[script.id] = p.name if p else None
    for item in items:
        item["project"] = projects_map.get(item["id"])
    return {"total": qs.count(), "items": items}


def _get_performance_script_detail(**kwargs) -> Dict[str, Any]:
    """获取性能测试脚本详情。"""
    from apps.performance_testing.models import PerformanceScript
    script_id = kwargs.get("script_id")
    try:
        s = PerformanceScript.objects.prefetch_related("projects").select_related("created_by").get(pk=script_id)
    except PerformanceScript.DoesNotExist:
        return {"error": f"脚本 {script_id} 不存在"}
    project = s.projects.first()
    result = {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "project": project.name if project else None,
        "status": s.status,
        "script_type": s.script_type,
        "thread_count": s.thread_count,
        "ramp_up": s.ramp_up,
        "duration": s.duration,
        "realtime_enabled": s.realtime_enabled,
        "variables": s.variables,
        "csv_datasets": s.csv_datasets,
        "jmx_config": s.jmx_config if s.script_type == "ONLINE" else None,
        "jmx_content": s.jmx_content[:500] + "..." if s.script_type == "JMX_RAW" and len(s.jmx_content) > 500 else s.jmx_content if s.script_type == "JMX_RAW" else None,
        "has_jmx_file": bool(s.jmx_file) if s.script_type == "JMX_UPLOAD" else None,
        "created_by": s.created_by.username if s.created_by else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
    return result


def _create_performance_script(**kwargs) -> Dict[str, Any]:
    """创建性能测试脚本（ONLINE 模式）。"""
    from apps.performance_testing.models import PerformanceScript
    from apps.projects.models import Project
    from django.contrib.auth import get_user_model
    User = get_user_model()

    project_id = kwargs.get("project_id")
    try:
        project = Project.objects.get(id=project_id) if project_id else None
    except Project.DoesNotExist:
        return {"error": f"项目 {project_id} 不存在"}

    name = kwargs.get("name", "未命名性能脚本")
    thread_count = int(kwargs.get("thread_count", 10))
    ramp_up = int(kwargs.get("ramp_up", 5))
    duration = int(kwargs.get("duration", 60))

    # 构建 jmx_config
    url = kwargs.get("url", "")
    method = kwargs.get("method", "GET").upper()
    sampler_name = kwargs.get("sampler_name", f"{method} {url}")

    jmx_config = {
        "thread_groups": [{
            "name": kwargs.get("thread_group_name", "Thread Group 1"),
            "thread_count": thread_count,
            "ramp_up": ramp_up,
            "loops": kwargs.get("loops", 1),
            "duration": duration,
            "variables": [],
            "csv_datasets": [],
            "samplers": [{
                "name": sampler_name,
                "method": method,
                "url": url,
                "headers": [],
                "params": [],
                "body": kwargs.get("body", ""),
                "assertions": [{"type": "response_code", "value": kwargs.get("expected_code", "200")}] if kwargs.get("expected_code") else [],
            }],
        }],
        "variables": [{"name": k, "value": v} for k, v in kwargs.get("variables", {}).items()],
        "csv_datasets": [],
    }

    creator = User.objects.first()
    script = PerformanceScript.objects.create(
        name=name,
        description=kwargs.get("description", ""),
        status="draft",
        script_type="ONLINE",
        jmx_config=jmx_config,
        thread_count=thread_count,
        ramp_up=ramp_up,
        duration=duration,
        realtime_enabled=bool(kwargs.get("realtime_enabled", False)),
        created_by=creator,
    )
    if project:
        script.projects.add(project)
    return {"id": script.id, "name": script.name, "script_type": script.script_type, "status": script.status}


def _execute_performance_script(**kwargs) -> Dict[str, Any]:
    """执行性能测试脚本。"""
    from apps.performance_testing.models import PerformanceScript
    from apps.performance_testing.executor import create_execution, validate_load
    from django.contrib.auth import get_user_model
    User = get_user_model()

    script_id = kwargs.get("script_id")
    try:
        script = PerformanceScript.objects.get(pk=script_id)
    except PerformanceScript.DoesNotExist:
        return {"error": f"脚本 {script_id} 不存在"}

    thread_count = kwargs.get("thread_count")
    ramp_up = kwargs.get("ramp_up")
    duration = kwargs.get("duration")
    realtime_enabled = kwargs.get("realtime_enabled")

    tc = int(thread_count) if thread_count else script.thread_count
    du = int(duration) if duration else script.duration
    err = validate_load(tc, du)
    if err:
        return {"error": err}

    creator = User.objects.first()
    try:
        execution = create_execution(
            script,
            created_by=creator,
            thread_count=thread_count,
            ramp_up=ramp_up,
            duration=duration,
            realtime_enabled=realtime_enabled,
        )
    except ValueError as e:
        return {"error": str(e)}

    return {
        "execution_id": execution.execution_id,
        "execution_pk": execution.id,
        "script_id": script.id,
        "script_name": script.name,
        "status": execution.status,
        "thread_count": execution.thread_count,
        "ramp_up": execution.ramp_up,
        "duration": execution.duration,
        "message": f"性能测试脚本 '{script.name}' 已开始执行，预计 {execution.duration} 秒后完成",
    }


def _get_performance_execution_status(**kwargs) -> Dict[str, Any]:
    """查询性能测试执行状态。"""
    from apps.performance_testing.models import PerformanceExecution
    execution_id = kwargs.get("execution_id")
    pk = kwargs.get("execution_pk")

    qs = PerformanceExecution.objects.select_related("script")
    if pk:
        execution = qs.filter(pk=pk).first()
    elif execution_id:
        execution = qs.filter(execution_id=execution_id).first()
    else:
        # 返回最近的执行记录
        execution = qs.first()

    if not execution:
        return {"error": "未找到执行记录"}

    return {
        "execution_id": execution.execution_id,
        "execution_pk": execution.id,
        "script_name": execution.script.name if execution.script else None,
        "status": execution.status,
        "thread_count": execution.thread_count,
        "ramp_up": execution.ramp_up,
        "duration": execution.duration,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "error_message": execution.error_message[:300] if execution.error_message else "",
        "has_report": bool(execution.report_path),
    }


def _get_performance_execution_summary(**kwargs) -> Dict[str, Any]:
    """获取性能测试执行汇总指标。"""
    from apps.performance_testing.models import PerformanceExecution, PerformanceSummary, PerformanceMetric

    execution_id = kwargs.get("execution_id")
    pk = kwargs.get("execution_pk")

    qs = PerformanceExecution.objects.select_related("script")
    if pk:
        execution = qs.filter(pk=pk).first()
    elif execution_id:
        execution = qs.filter(execution_id=execution_id).first()
    else:
        execution = qs.filter(status="COMPLETED").first()

    if not execution:
        return {"error": "未找到执行记录"}

    result = {
        "execution_id": execution.execution_id,
        "status": execution.status,
        "script_name": execution.script.name if execution.script else None,
    }

    try:
        s = execution.summary
        result["summary"] = {
            "total_samples": s.total_samples,
            "error_count": s.error_count,
            "error_rate": round(s.error_rate, 2),
            "avg_response_time": round(s.avg_response_time, 1),
            "min_response_time": round(s.min_response_time, 1),
            "max_response_time": round(s.max_response_time, 1),
            "p90": round(s.p90, 1),
            "p95": round(s.p95, 1),
            "p99": round(s.p99, 1),
            "throughput": round(s.throughput, 2),
        }
    except PerformanceSummary.DoesNotExist:
        result["summary"] = None

    metrics = execution.metrics.all().order_by("-sample_count")
    result["metrics"] = [
        {
            "sample_label": m.sample_label,
            "sample_count": m.sample_count,
            "error_count": m.error_count,
            "error_rate": round(m.error_rate, 2),
            "avg": round(m.avg, 1),
            "p95": round(m.p95, 1),
            "p99": round(m.p99, 1),
            "throughput": round(m.throughput, 2),
        }
        for m in metrics[:20]
    ]

    return result


def _get_performance_dashboard(**kwargs) -> Dict[str, Any]:
    """获取性能测试数据看板（最新执行的汇总 + 指标）。"""
    from apps.performance_testing.models import (
        PerformanceExecution, PerformanceScript, PerformanceScheduledTask,
        PerformanceSummary,
    )

    # 统计概览
    total_scripts = PerformanceScript.objects.count()
    total_executions = PerformanceExecution.objects.count()
    running = PerformanceExecution.objects.filter(status="RUNNING").count()
    completed = PerformanceExecution.objects.filter(status="COMPLETED").count()
    failed = PerformanceExecution.objects.filter(status="FAILED").count()
    scheduled = PerformanceScheduledTask.objects.filter(status="enabled").count()

    # 最新执行
    latest = PerformanceExecution.objects.select_related("script", "summary").order_by("-created_at").first()
    latest_info = None
    if latest:
        latest_info = {
            "execution_id": latest.execution_id,
            "script_name": latest.script.name if latest.script else None,
            "status": latest.status,
            "started_at": latest.started_at.isoformat() if latest.started_at else None,
            "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
        }
        try:
            s = latest.summary
            latest_info["summary"] = {
                "total_samples": s.total_samples,
                "error_rate": round(s.error_rate, 2),
                "avg_response_time": round(s.avg_response_time, 1),
                "p95": round(s.p95, 1),
                "throughput": round(s.throughput, 2),
            }
        except PerformanceSummary.DoesNotExist:
            pass

    # 最近 5 条执行记录
    recent = PerformanceExecution.objects.select_related("script").order_by("-created_at")[:5]
    recent_list = [
        {
            "execution_id": e.execution_id,
            "script_name": e.script.name if e.script else None,
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in recent
    ]

    return {
        "overview": {
            "total_scripts": total_scripts,
            "total_executions": total_executions,
            "running": running,
            "completed": completed,
            "failed": failed,
            "scheduled_tasks": scheduled,
        },
        "latest_execution": latest_info,
        "recent_executions": recent_list,
    }


def _list_performance_scheduled_tasks(**kwargs) -> Dict[str, Any]:
    """查询性能测试定时任务列表。"""
    from apps.performance_testing.models import PerformanceScheduledTask
    qs = PerformanceScheduledTask.objects.select_related("script", "created_by").all()
    status_filter = kwargs.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "name", "script__name", "cron", "status",
        "thread_count", "ramp_up", "duration", "realtime_enabled",
        "created_at", "updated_at",
    ))
    return {"total": qs.count(), "items": items}


# ────────────────────────────── 运维工具 ──────────────────────────────

def _list_ops_environments(**kwargs) -> Dict[str, Any]:
    """查询运维工具中的环境配置列表（SSH/本地/数据库）。"""
    from apps.ops_tools.models import OpsEnvironment
    qs = OpsEnvironment.objects.all().order_by("-created_at")
    env_type = kwargs.get("env_type")
    if env_type:
        qs = qs.filter(access_method=env_type)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "name", "access_method", "host", "port", "db_type", "db_host", "db_port",
        "db_name", "status", "created_at",
    ))
    return {"total": qs.count(), "items": items}


def _text2sql_generate(**kwargs) -> Dict[str, Any]:
    """Text2SQL：根据自然语言问题生成 SQL。需要 environment_id 和 question。"""
    from django.contrib.auth import get_user_model
    from apps.ops_tools.models import OpsEnvironment, Text2SQLRecord
    from apps.requirement_analysis.models import AIModelConfig, AIModelService
    from asgiref.sync import async_to_sync

    User = get_user_model()
    env_id = kwargs.get("environment_id")
    question = kwargs.get("question", "").strip()
    mode = kwargs.get("mode", "query")
    if not env_id or not question:
        return {"error": "请提供 environment_id 和 question"}
    try:
        env = OpsEnvironment.objects.get(pk=env_id)
    except OpsEnvironment.DoesNotExist:
        return {"error": f"运维环境 {env_id} 不存在"}

    config = AIModelConfig.objects.filter(role='writer', is_active=True).order_by('-updated_at').first()
    if not config:
        return {"error": "未配置 writer 角色 AI 模型，无法生成 SQL"}

    record = Text2SQLRecord.objects.create(
        environment=env,
        mode=mode,
        question=question,
        created_by=User.objects.first(),
    )
    system_prompt = (
        "你是一个 SQL 专家。请根据用户的问题和数据库信息，生成一条安全、可执行的 SQL。"
        "如果是查询模式，只返回 SELECT 语句；如果是数据变更模式，可返回 INSERT/UPDATE/DELETE。"
        "只返回 SQL 代码，不要解释。"
    )
    db_hint = f"数据库类型：{env.db_type or 'mysql'}，数据库名：{env.db_name or 'testhub'}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{db_hint}\n\n问题：{question}\n模式：{mode}"},
    ]
    try:
        response = async_to_sync(AIModelService.call_openai_compatible_api)(config, messages)
        sql = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if sql.startswith("```"):
            sql = "\n".join(sql.split("\n")[1:-1] if sql.endswith("```") else sql.split("\n")[1:])
        record.generated_sql = sql.strip()
        record.status = "generated"
        record.save()
        return {"record_id": record.id, "generated_sql": record.generated_sql, "status": record.status}
    except Exception as e:
        record.status = "failed"
        record.error_message = str(e)
        record.save()
        return {"error": f"SQL 生成失败: {str(e)}"}


def _text2sql_execute(**kwargs) -> Dict[str, Any]:
    """执行 Text2SQL 已生成的 SQL（演示模式返回示例数据，未真实连接数据库）。"""
    from apps.ops_tools.models import Text2SQLRecord
    record_id = kwargs.get("record_id")
    if not record_id:
        return {"error": "请提供 record_id"}
    try:
        record = Text2SQLRecord.objects.get(pk=record_id)
    except Text2SQLRecord.DoesNotExist:
        return {"error": f"Text2SQL 记录 {record_id} 不存在"}

    sql = kwargs.get("sql") or record.validated_sql or record.generated_sql
    record.result = {
        "sql": sql,
        "rows": [
            {"id": 1, "name": "示例数据 A", "count": 10},
            {"id": 2, "name": "示例数据 B", "count": 20},
        ],
        "row_count": 2,
        "message": "演示模式：未真实连接数据库",
    }
    record.status = "executed"
    record.save()
    return {"record_id": record.id, "sql": sql, "result": record.result, "status": record.status}


def _query_logs(**kwargs) -> Dict[str, Any]:
    """查询远程/本地日志。需要 environment_id，可选 path/keywords/tail_lines。"""
    from apps.ops_tools.models import OpsEnvironment, LogQuerySession
    from apps.users.models import User

    env_id = kwargs.get("environment_id")
    path = kwargs.get("path", "")
    keywords = kwargs.get("keywords", [])
    tail_lines = min(int(kwargs.get("tail_lines", 200)), 5000)
    if not env_id:
        return {"error": "请提供 environment_id"}
    try:
        env = OpsEnvironment.objects.get(pk=env_id)
    except OpsEnvironment.DoesNotExist:
        return {"error": f"运维环境 {env_id} 不存在"}

    base = path or env.current_dir or "/var/log"
    sample = []
    for i in range(tail_lines):
        sample.append(f"2026-04-23 20:31:{37 + i % 60:02d},274 - [apps.knowledge_base.services] INFO - 示例日志行 {i+1}")
    session, _ = LogQuerySession.objects.update_or_create(
        environment=env,
        current_file=base,
        defaults={
            "log_dir": __import__("os").path.dirname(base),
            "content": "\n".join(sample),
            "keywords": keywords if isinstance(keywords, list) else [keywords],
            "tail_lines": tail_lines,
            "created_by": User.objects.first(),
        },
    )
    return {
        "environment_id": env.id,
        "path": base,
        "tail_lines": tail_lines,
        "session_id": session.id,
        "preview": "\n".join(sample[:10]),
        "total_lines": len(sample),
    }


def _list_transfer_tasks(**kwargs) -> Dict[str, Any]:
    """查询内网文件传输任务列表。"""
    from apps.ops_tools.models import FileTransferTask
    qs = FileTransferTask.objects.all().order_by("-created_at")
    env_id = kwargs.get("environment_id")
    if env_id:
        qs = qs.filter(environment_id=env_id)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "name", "direction", "remote_path", "size", "status", "created_at",
    ))
    return {"total": qs.count(), "items": items}


def _create_defect(**kwargs) -> Dict[str, Any]:
    """创建一个缺陷（BUG）。供数字人在对话中识别到 bug 描述时调用。

    必填：title, project_id；可选：severity, description, steps_to_reproduce, environment, assigned_to
    """
    from apps.defects.models import Defect
    title = (kwargs.get("title") or "").strip()
    project_id = kwargs.get("project_id")
    if not title:
        return {"error": "title 必填"}
    if not project_id:
        return {"error": "project_id 必填（用 list_projects 查询）"}
    severity = kwargs.get("severity", "S3")
    if severity not in ("S1", "S2", "S3", "S4"):
        severity = "S3"

    user = kwargs.get("_user")
    if not user:
        from apps.users.models import User
        user = User.objects.first()

    try:
        defect = Defect.objects.create(
            title=title,
            project_id=project_id,
            severity=severity,
            description=kwargs.get("description", ""),
            steps_to_reproduce=kwargs.get("steps_to_reproduce", ""),
            environment=kwargs.get("environment", ""),
            assigned_to_id=kwargs.get("assigned_to") or None,
            source="hermes",
            reported_by=user,
        )
        return {
            "defect_id": defect.id,
            "title": defect.title,
            "severity": defect.severity,
            "status": defect.status,
            "message": f"已创建 BUG #{defect.id}，请在问题管理页查看详情。",
        }
    except Exception as e:
        return {"error": f"创建失败: {e}"}


def _list_defects(**kwargs) -> Dict[str, Any]:
    """查询缺陷列表。可按项目/状态/严重度过滤。"""
    from apps.defects.models import Defect
    qs = Defect.objects.all().order_by("-created_at")
    project_id = kwargs.get("project_id")
    if project_id:
        qs = qs.filter(project_id=project_id)
    status = kwargs.get("status")
    if status:
        qs = qs.filter(status=status)
    severity = kwargs.get("severity")
    if severity:
        qs = qs.filter(severity=severity)
    limit = min(int(kwargs.get("limit", 20)), 100)
    items = list(qs[:limit].values(
        "id", "title", "severity", "status", "project_id", "source", "created_at",
    ))
    return {"total": qs.count(), "items": items}


# ────────────────────────────── 工具注册表 ──────────────────────────────

TOOL_REGISTRY: List[Dict[str, Any]] = [
    {
        "name": "list_projects",
        "description": "查询系统中的项目列表。可按状态过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "项目状态: active/paused/completed/archived", "enum": ["active", "paused", "completed", "archived"]},
                "limit": {"type": "integer", "description": "返回数量，默认20，最大100", "default": 20},
            },
            "required": [],
        },
        "handler": _list_projects,
    },
    {
        "name": "list_testcases",
        "description": "查询测试用例列表。可按项目、优先级、状态、关键词过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID"},
                "priority": {"type": "string", "description": "优先级", "enum": ["low", "medium", "high", "critical"]},
                "status": {"type": "string", "description": "用例状态", "enum": ["draft", "active", "deprecated"]},
                "keyword": {"type": "string", "description": "标题或描述关键词"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_testcases,
    },
    {
        "name": "create_testcase",
        "description": "创建一条测试用例。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "所属项目ID（必填）"},
                "title": {"type": "string", "description": "用例标题"},
                "description": {"type": "string", "description": "用例描述"},
                "preconditions": {"type": "string", "description": "前置条件"},
                "steps": {"type": "string", "description": "操作步骤"},
                "expected_result": {"type": "string", "description": "预期结果"},
                "priority": {"type": "string", "description": "优先级", "enum": ["low", "medium", "high", "critical"], "default": "medium"},
                "test_type": {"type": "string", "description": "测试类型", "enum": ["functional", "integration", "api", "ui", "performance", "security"], "default": "functional"},
            },
            "required": ["project_id", "title", "expected_result"],
        },
        "handler": _create_testcase,
    },
    {
        "name": "list_test_plans",
        "description": "查询测试计划列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_test_plans,
    },
    {
        "name": "create_test_plan",
        "description": "创建测试计划，可同时关联项目和用例，自动创建测试执行记录。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "计划名称"},
                "description": {"type": "string", "description": "计划描述"},
                "project_ids": {"type": "array", "items": {"type": "integer"}, "description": "关联项目ID列表"},
                "testcase_ids": {"type": "array", "items": {"type": "integer"}, "description": "关联用例ID列表"},
            },
            "required": ["name"],
        },
        "handler": _create_test_plan,
    },
    {
        "name": "list_api_requests",
        "description": "查询 API 接口定义列表。可按项目和请求方法过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "API项目ID"},
                "method": {"type": "string", "description": "HTTP方法", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_api_requests,
    },
    {
        "name": "create_api_request",
        "description": "解析 curl 命令并在 API 测试模块创建接口请求定义。支持 -H/--header、-X/--request、-d/--data-raw/--data-binary、-u/--user、--insecure 等参数。如果用户给出完整 curl 且想直接执行接口测试，先创建再执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "curl_command": {"type": "string", "description": "完整的 curl 命令字符串（可包含多行和反斜杠）"},
                "project_id": {"type": "integer", "description": "所属 API 项目 ID，不提供则使用第一个项目"},
                "collection_id": {"type": "integer", "description": "所属集合 ID"},
                "name": {"type": "string", "description": "请求名称，不提供则根据 URL 自动生成"},
                "description": {"type": "string", "description": "请求描述"},
            },
            "required": ["curl_command"],
        },
        "handler": _create_api_request,
    },
    {
        "name": "execute_api_request",
        "description": "执行单个 API 请求并返回响应结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {"type": "integer", "description": "API请求ID"},
            },
            "required": ["request_id"],
        },
        "handler": _execute_api_request,
    },
    {
        "name": "execute_api_suite",
        "description": "执行 API 测试套件（批量执行多个接口）。",
        "parameters": {
            "type": "object",
            "properties": {
                "suite_id": {"type": "integer", "description": "测试套件ID"},
            },
            "required": ["suite_id"],
        },
        "handler": _execute_api_suite,
    },
    {
        "name": "update_run_case_status",
        "description": "更新测试执行用例的状态（通过/失败/阻塞/重测）。",
        "parameters": {
            "type": "object",
            "properties": {
                "run_case_id": {"type": "integer", "description": "执行用例ID"},
                "status": {"type": "string", "description": "执行状态", "enum": ["untested", "passed", "failed", "blocked", "retest"]},
                "actual_result": {"type": "string", "description": "实际结果"},
                "comments": {"type": "string", "description": "备注"},
            },
            "required": ["run_case_id", "status"],
        },
        "handler": _update_run_case_status,
    },
    {
        "name": "list_test_reports",
        "description": "查询 API 测试执行报告列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回数量，默认10", "default": 10},
            },
            "required": [],
        },
        "handler": _list_test_reports,
    },
    {
        "name": "generate_test_data",
        "description": "使用数据工厂生成测试数据（如姓名、手机号、身份证、邮箱等）。",
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string", "description": "工具名，如 generate_chinese_name, generate_chinese_phone, generate_id_card 等"},
                "tool_category": {"type": "string", "description": "工具分类", "default": "test_data"},
                "input_data": {"type": "object", "description": "工具输入参数，如 {\"count\": 5}"},
            },
            "required": ["tool_name"],
        },
        "handler": _generate_test_data,
    },
    {
        "name": "list_data_tools",
        "description": "查询数据工厂所有可用工具列表。",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _list_data_tools,
    },
    {
        "name": "run_ui_automation",
        "description": "执行 UI 自动化测试（AI 驱动浏览器自动操作，传入自然语言任务描述）。如果平台已有 UI 测试套件，优先用 run_ui_test_suite。",
        "parameters": {
            "type": "object",
            "properties": {
                "task_description": {"type": "string", "description": "任务描述，如 '打开百度搜索TestHub并截图'"},
            },
            "required": ["task_description"],
        },
        "handler": _run_ui_automation,
    },
    {
        "name": "list_ui_test_suites",
        "description": "查询平台已创建的 UI 自动化测试套件列表，可按项目过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "UI项目ID"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_ui_test_suites,
    },
    {
        "name": "run_ui_test_suite",
        "description": "直接执行平台已存在的 UI 自动化测试套件（suite_id），不需要重新写任务描述。后台异步执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "suite_id": {"type": "integer", "description": "UI测试套件ID（用 list_ui_test_suites 查询）"},
                "engine": {"type": "string", "enum": ["playwright", "selenium"], "default": "playwright"},
                "browser": {"type": "string", "enum": ["chrome", "firefox", "edge", "safari"], "default": "chrome"},
                "headless": {"type": "boolean", "description": "是否无头模式", "default": True},
            },
            "required": ["suite_id"],
        },
        "handler": _run_ui_test_suite,
    },
    {
        "name": "list_api_test_suites",
        "description": "查询平台已创建的 API 测试套件列表，可按项目过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "API项目ID"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_api_test_suites,
    },
    {
        "name": "ai_generate_testcases",
        "description": "根据需求描述使用 AI 自动生成测试用例（异步任务，返回 task_id 供轮询）。",
        "parameters": {
            "type": "object",
            "properties": {
                "requirement": {"type": "string", "description": "需求描述文本"},
                "title": {"type": "string", "description": "任务标题"},
            },
            "required": ["requirement"],
        },
        "handler": _ai_generate_testcases,
    },
    {
        "name": "list_knowledge_bases",
        "description": "列出所有可用知识库及其文档数量。检索前先调用此工具了解知识库结构，再决定是否按知识库分别检索。",
        "parameters": {
            "type": "object",
            "properties": {
                "dify_config_id": {"type": "integer", "description": "Dify配置ID（不传则使用默认配置）"},
            },
        },
        "handler": _list_knowledge_bases,
    },
    {
        "name": "search_knowledge_base",
        "description": "在 Dify 知识库中检索相关文档。不传 dataset_id 时自动跨全部知识库检索并按相关度合并结果。传 dataset_id 可精准检索指定知识库。建议先用 list_knowledge_bases 了解知识库列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索关键词或问题"},
                "top_k": {"type": "integer", "description": "每个知识库返回结果数，默认5，最大10", "default": 5},
                "dataset_id": {"type": "string", "description": "指定知识库ID（不传则跨全部知识库检索）"},
                "search_method": {"type": "string", "description": "检索方式：semantic_search（语义，默认）、full_text_search（全文）、hybrid_search（混合）", "default": "semantic_search"},
                "dify_config_id": {"type": "integer", "description": "Dify配置ID（不传则使用默认配置）"},
            },
            "required": ["query"],
        },
        "handler": _search_knowledge_base,
    },
    {
        "name": "list_execution_history",
        "description": "查询测试执行历史记录。可按执行用例ID过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "run_case_id": {"type": "integer", "description": "执行用例ID"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_execution_history,
    },
    # ===== APP 自动化 =====
    {
        "name": "list_app_test_suites",
        "description": "查询 APP 自动化测试套件列表（Airtest + OCR），可按项目过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "APP项目ID"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_app_test_suites,
    },
    {
        "name": "list_app_devices",
        "description": "查询当前可用的 APP 调试设备（执行 APP 套件前先查这个获取 device_id）。",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回数量，默认30", "default": 30},
            },
            "required": [],
        },
        "handler": _list_app_devices,
    },
    {
        "name": "run_app_test_suite",
        "description": "执行 APP 自动化测试套件（需先调用 list_app_devices 获取 device_id）。后台异步执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "suite_id": {"type": "integer", "description": "APP测试套件ID"},
                "device_id": {"type": "string", "description": "设备ID（用 list_app_devices 查询）"},
                "package_name": {"type": "string", "description": "Android 包名（可选）"},
            },
            "required": ["suite_id", "device_id"],
        },
        "handler": _run_app_test_suite,
    },
    # ===== 配置中心 =====
    {
        "name": "list_dify_configs",
        "description": "查询配置中心中的 Dify 配置列表（AI 评测师、对话应用、工作流应用等）。",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _list_dify_configs,
    },
    {
        "name": "list_ai_model_configs",
        "description": "查询配置中心中的 AI 大模型配置（OpenAI/DeepSeek/Qwen 等）。",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _list_ai_model_configs,
    },
    # ===== AI 评测师 =====
    {
        "name": "chat_ai_evaluator",
        "description": (
            "调用「AI 评测师」（配置中心配置的 Dify chat / workflow 应用）回答问题。"
            "适用场景：业务规则问答、测试评审建议、测试方法咨询、相似用例推荐等。"
            "注意：message 参数必须是一个完整、具体的问题，不能为空。"
            "若 Dify 未配置或缺 app- API Key，会返回明确错误。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "发给 AI 评测师的问题"},
                "dify_config_id": {"type": "integer", "description": "指定 Dify 配置（不传则用激活的配置）"},
            },
            "required": ["message"],
        },
        "handler": _chat_ai_evaluator,
    },
    # ===== 用例评审 =====
    {
        "name": "list_reviews",
        "description": "查询用例评审列表。可按状态、项目过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "评审状态", "enum": ["pending", "in_progress", "approved", "rejected", "cancelled"]},
                "project_id": {"type": "integer", "description": "项目ID"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_reviews,
    },
    {
        "name": "create_review",
        "description": "创建用例评审，可同时关联项目、用例和评审人。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "评审标题"},
                "description": {"type": "string", "description": "评审描述"},
                "priority": {"type": "string", "description": "优先级", "enum": ["low", "medium", "high", "urgent"], "default": "medium"},
                "project_ids": {"type": "array", "items": {"type": "integer"}, "description": "关联项目ID列表"},
                "testcase_ids": {"type": "array", "items": {"type": "integer"}, "description": "评审用例ID列表"},
                "reviewer_ids": {"type": "array", "items": {"type": "integer"}, "description": "评审人用户ID列表（可用 list_users 查询）"},
            },
            "required": ["title"],
        },
        "handler": _create_review,
    },
    {
        "name": "submit_review_decision",
        "description": "提交评审意见（通过/拒绝/弃权）。",
        "parameters": {
            "type": "object",
            "properties": {
                "review_id": {"type": "integer", "description": "评审ID"},
                "status": {"type": "string", "description": "评审决定", "enum": ["approved", "rejected", "abstained"]},
                "comment": {"type": "string", "description": "评审意见"},
            },
            "required": ["review_id", "status"],
        },
        "handler": _submit_review_decision,
    },
    # ===== 版本管理 =====
    {
        "name": "list_versions",
        "description": "查询版本列表。可按项目、是否基线过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID"},
                "is_baseline": {"type": "boolean", "description": "是否基线版本"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_versions,
    },
    {
        "name": "create_version",
        "description": "创建版本。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "版本名称"},
                "description": {"type": "string", "description": "版本描述"},
                "is_baseline": {"type": "boolean", "description": "是否基线版本", "default": False},
                "project_ids": {"type": "array", "items": {"type": "integer"}, "description": "关联项目ID列表"},
            },
            "required": ["name"],
        },
        "handler": _create_version,
    },
    # ===== 知识图谱 =====
    {
        "name": "query_kg_subgraph",
        "description": "查询知识图谱子图（以某个实体为中心，展开 N 层关系）。entity_key 可从 get_project_coverage 获取。",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_key": {"type": "string", "description": "实体标识"},
                "depth": {"type": "integer", "description": "展开层数，默认2，最大5", "default": 2},
                "max_nodes": {"type": "integer", "description": "最大节点数，默认200", "default": 200},
            },
            "required": ["entity_key"],
        },
        "handler": _query_kg_subgraph,
    },
    {
        "name": "get_project_coverage",
        "description": "查询项目知识图谱覆盖度报告（用例对需求/功能模块的覆盖情况、缺口分析）。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID（必填）"},
                "limit": {"type": "integer", "description": "返回条数上限，默认100", "default": 100},
            },
            "required": ["project_id"],
        },
        "handler": _get_project_coverage,
    },
    {
        "name": "recommend_execution",
        "description": "基于知识图谱的 AI 推荐执行：分析项目覆盖缺口和执行历史，推荐下一步应优先执行的测试目标（API/UI/用例/覆盖缺口）。优先调 LLM 分析，降级规则推荐。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID（必填）"},
            },
            "required": ["project_id"],
        },
        "handler": _recommend_execution,
    },
    {
        "name": "build_knowledge_graph",
        "description": "从 Dify 知识库构建知识图谱：LLM 抽取文档功能点 → 写入图谱节点和边 → 跨文档语义关联。需要 dataset_id（先用 list_knowledge_bases 获取）。可选传 document_ids 指定文档，不传则处理该知识库全部文档。",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dify 知识库 ID（必填）"},
                "project_id": {"type": "integer", "description": "关联项目 ID（可选）"},
                "document_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "指定文档 ID 列表，不传则处理全部文档",
                },
            },
            "required": ["dataset_id"],
        },
        "handler": _build_knowledge_graph,
    },
    # ===== 测试执行（扩展） =====
    {
        "name": "list_test_runs",
        "description": "查询测试执行记录列表。可按计划、项目、状态过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "integer", "description": "测试计划ID"},
                "project_id": {"type": "integer", "description": "项目ID"},
                "status": {"type": "string", "description": "执行状态", "enum": ["untested", "in_progress", "completed", "blocked"]},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_test_runs,
    },
    {
        "name": "start_test_run",
        "description": "启动测试执行（将状态从'未测试'改为'进行中'）。",
        "parameters": {
            "type": "object",
            "properties": {
                "run_id": {"type": "integer", "description": "测试执行ID"},
            },
            "required": ["run_id"],
        },
        "handler": _start_test_run,
    },
    # ===== 通用测试套件 =====
    {
        "name": "list_test_suites",
        "description": "查询通用测试套件列表（testsuites 应用，独立于 API/UI/APP 套件）。可按项目过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_test_suites,
    },
    {
        "name": "create_test_suite",
        "description": "创建通用测试套件并关联用例。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "所属项目ID（必填）"},
                "name": {"type": "string", "description": "套件名称"},
                "description": {"type": "string", "description": "套件描述"},
                "testcase_ids": {"type": "array", "items": {"type": "integer"}, "description": "关联用例ID列表"},
            },
            "required": ["project_id", "name"],
        },
        "handler": _create_test_suite,
    },
    # ===== 报告仪表盘 =====
    {
        "name": "get_dashboard_stats",
        "description": "查询测试管理仪表盘统计数据（项目数、用例数、计划数、执行数、状态分布、优先级分布等）。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID（不传则统计全部）"},
            },
            "required": [],
        },
        "handler": _get_dashboard_stats,
    },
    # ===== 用户 =====
    {
        "name": "list_users",
        "description": "查询系统用户列表（用于指派评审人/执行人）。",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "用户名关键词"},
                "limit": {"type": "integer", "description": "返回数量，默认30", "default": 30},
            },
            "required": [],
        },
        "handler": _list_users,
    },
    # ===== 测试用例（扩展） =====
    {
        "name": "get_testcase_detail",
        "description": "查询单条测试用例详情（含完整步骤、预期结果、标签等）。",
        "parameters": {
            "type": "object",
            "properties": {
                "testcase_id": {"type": "integer", "description": "用例ID"},
            },
            "required": ["testcase_id"],
        },
        "handler": _get_testcase_detail,
    },
    {
        "name": "update_testcase",
        "description": "更新测试用例字段（优先级、状态、指派人、步骤等）。只传需要改的字段。",
        "parameters": {
            "type": "object",
            "properties": {
                "testcase_id": {"type": "integer", "description": "用例ID"},
                "title": {"type": "string", "description": "用例标题"},
                "description": {"type": "string", "description": "用例描述"},
                "preconditions": {"type": "string", "description": "前置条件"},
                "steps": {"type": "string", "description": "操作步骤"},
                "expected_result": {"type": "string", "description": "预期结果"},
                "priority": {"type": "string", "description": "优先级", "enum": ["low", "medium", "high", "critical"]},
                "status": {"type": "string", "description": "用例状态", "enum": ["draft", "active", "deprecated"]},
                "test_type": {"type": "string", "description": "测试类型", "enum": ["functional", "integration", "api", "ui", "performance", "security"]},
                "assignee_id": {"type": "integer", "description": "指派人用户ID"},
            },
            "required": ["testcase_id"],
        },
        "handler": _update_testcase,
    },
    {
        "name": "delete_testcase",
        "description": "删除测试用例。",
        "parameters": {
            "type": "object",
            "properties": {
                "testcase_id": {"type": "integer", "description": "用例ID"},
            },
            "required": ["testcase_id"],
        },
        "handler": _delete_testcase,
    },
    # ===== 需求分析（扩展） =====
    {
        "name": "list_requirement_docs",
        "description": "查询需求文档列表。可按项目、状态过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID"},
                "status": {"type": "string", "description": "文档状态", "enum": ["uploaded", "analyzing", "analyzed", "failed"]},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_requirement_docs,
    },
    {
        "name": "get_generation_task_status",
        "description": "查询 AI 用例生成任务的状态和结果（ai_generate_testcases 返回的 task_id 用这个轮询）。",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务ID（ai_generate_testcases 返回的）"},
            },
            "required": ["task_id"],
        },
        "handler": _get_generation_task_status,
    },
    # ===== API 环境 =====
    {
        "name": "list_api_environments",
        "description": "查询 API 测试环境列表。可按项目、是否激活过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "API项目ID"},
                "is_active": {"type": "boolean", "description": "是否激活"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_api_environments,
    },
    # ===== 项目（扩展） =====
    {
        "name": "create_project",
        "description": "创建项目。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "项目名称"},
                "description": {"type": "string", "description": "项目描述"},
                "status": {"type": "string", "description": "项目状态", "enum": ["active", "paused", "completed", "archived"], "default": "active"},
            },
            "required": ["name"],
        },
        "handler": _create_project,
    },
    {
        "name": "get_project_detail",
        "description": "查询项目详情（含用例数、计划数、执行数统计）。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID"},
            },
            "required": ["project_id"],
        },
        "handler": _get_project_detail,
    },
    # ── Skill 技能系统 ──
    {
        "name": "list_skills",
        "description": "查询可用的 Skill 技能列表。可按技能类型过滤（需求分析/需求评审/用例评审/用例生成/自定义）。",
        "parameters": {
            "type": "object",
            "properties": {
                "skill_type": {
                    "type": "string",
                    "description": "技能类型过滤",
                    "enum": ["requirements_analysis", "requirement_reviewer", "testcase_reviewer", "testcase_generator", "custom"],
                },
            },
            "required": [],
        },
        "handler": _list_skills,
    },
    {
        "name": "use_skill",
        "description": "使用指定 Skill 技能处理输入内容。先 list_skills 找到 skill_id，再用本工具执行。Skill 会用自己的系统提示词和约束规则处理输入，返回结构化输出。",
        "parameters": {
            "type": "object",
            "properties": {
                "skill_id": {"type": "integer", "description": "Skill ID（从 list_skills 获取）"},
                "input_text": {"type": "string", "description": "要处理的输入内容（需求文档文本/用例文本等）"},
            },
            "required": ["skill_id", "input_text"],
        },
        "handler": _use_skill,
    },
    # ===== 性能测试 =====
    {
        "name": "list_performance_scripts",
        "description": "查询性能测试脚本列表。可按项目、脚本模式(ONLINE/JMX_RAW/JMX_UPLOAD)、状态(draft/published)、关键词过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目ID"},
                "script_type": {"type": "string", "description": "脚本模式", "enum": ["ONLINE", "JMX_RAW", "JMX_UPLOAD"]},
                "status": {"type": "string", "description": "状态", "enum": ["draft", "published"]},
                "keyword": {"type": "string", "description": "名称或描述关键词"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_performance_scripts,
    },
    {
        "name": "get_performance_script_detail",
        "description": "获取性能测试脚本详情，包括线程组、HTTP请求、变量、CSV数据集等配置。",
        "parameters": {
            "type": "object",
            "properties": {
                "script_id": {"type": "integer", "description": "脚本ID"},
            },
            "required": ["script_id"],
        },
        "handler": _get_performance_script_detail,
    },
    {
        "name": "create_performance_script",
        "description": "创建性能测试脚本（ONLINE 在线编排模式）。支持配置线程数、Ramp-Up、持续时间、HTTP请求等。创建后可用 execute_performance_script 执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "脚本名称"},
                "project_id": {"type": "integer", "description": "所属项目ID"},
                "description": {"type": "string", "description": "脚本描述"},
                "url": {"type": "string", "description": "被测URL，如 http://httpbin.org/get"},
                "method": {"type": "string", "description": "HTTP方法", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"], "default": "GET"},
                "sampler_name": {"type": "string", "description": "采样器名称（默认为 方法+URL）"},
                "thread_count": {"type": "integer", "description": "线程数（虚拟用户数）", "default": 10},
                "ramp_up": {"type": "integer", "description": "Ramp-Up时间（秒）", "default": 5},
                "duration": {"type": "integer", "description": "持续时间（秒）", "default": 60},
                "loops": {"type": "integer", "description": "循环次数（0=无限，与duration二选一）", "default": 1},
                "body": {"type": "string", "description": "请求体（POST/PUT时使用）"},
                "expected_code": {"type": "string", "description": "预期响应码（自动添加断言），如 200"},
                "variables": {"type": "object", "description": "用户变量键值对，如 {\"host\": \"http://example.com\"}"},
                "realtime_enabled": {"type": "boolean", "description": "是否启用实时报告", "default": False},
            },
            "required": ["name", "url"],
        },
        "handler": _create_performance_script,
    },
    {
        "name": "execute_performance_script",
        "description": "执行性能测试脚本（后台异步执行，返回后可用 get_performance_execution_status 轮询状态，get_performance_execution_summary 查看结果）。",
        "parameters": {
            "type": "object",
            "properties": {
                "script_id": {"type": "integer", "description": "脚本ID"},
                "thread_count": {"type": "integer", "description": "覆盖线程数（不传用脚本默认值）"},
                "ramp_up": {"type": "integer", "description": "覆盖Ramp-Up（不传用脚本默认值）"},
                "duration": {"type": "integer", "description": "覆盖持续时间（不传用脚本默认值）"},
                "realtime_enabled": {"type": "boolean", "description": "覆盖实时报告开关"},
            },
            "required": ["script_id"],
        },
        "handler": _execute_performance_script,
    },
    {
        "name": "get_performance_execution_status",
        "description": "查询性能测试执行状态（QUEUED/RUNNING/COMPLETED/FAILED/CANCELLED）。不传参数则返回最近一条执行记录。",
        "parameters": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "description": "执行ID（如 PERF_XXXXXX）"},
                "execution_pk": {"type": "integer", "description": "执行记录主键ID"},
            },
            "required": [],
        },
        "handler": _get_performance_execution_status,
    },
    {
        "name": "get_performance_execution_summary",
        "description": "获取性能测试执行汇总指标（总样本、错误率、平均/P95/P99响应时间、吞吐量）和按请求名分组的明细指标。不传参数则返回最近一条已完成的执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "execution_id": {"type": "string", "description": "执行ID"},
                "execution_pk": {"type": "integer", "description": "执行记录主键ID"},
            },
            "required": [],
        },
        "handler": _get_performance_execution_summary,
    },
    {
        "name": "get_performance_dashboard",
        "description": "获取性能测试数据看板：脚本总数、执行总数、运行中/已完成/失败数量、定时任务数、最新执行概览、最近5条执行记录。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "handler": _get_performance_dashboard,
    },
    {
        "name": "list_performance_scheduled_tasks",
        "description": "查询性能测试定时任务列表。可按状态(enabled/disabled)过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "任务状态", "enum": ["enabled", "disabled"]},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_performance_scheduled_tasks,
    },
    # ===== 运维工具 =====
    {
        "name": "list_ops_environments",
        "description": "查询运维工具中的环境配置列表（SSH/本地/数据库）。使用 Text2SQL、日志查询、文件传输前先用它获取 environment_id。",
        "parameters": {
            "type": "object",
            "properties": {
                "env_type": {"type": "string", "description": "环境类型过滤", "enum": ["ssh", "local", "db"]},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_ops_environments,
    },
    {
        "name": "text2sql_generate",
        "description": "Text2SQL：根据自然语言问题生成 SQL。先调用 list_ops_environments 获取数据库类型环境的 environment_id。",
        "parameters": {
            "type": "object",
            "properties": {
                "environment_id": {"type": "integer", "description": "数据库运维环境ID"},
                "question": {"type": "string", "description": "自然语言问题，如 '统计最近7天注册用户数'"},
                "mode": {"type": "string", "description": "查询模式或数据变更模式", "enum": ["query", "dml"], "default": "query"},
            },
            "required": ["environment_id", "question"],
        },
        "handler": _text2sql_generate,
    },
    {
        "name": "text2sql_execute",
        "description": "执行 Text2SQL 已生成的 SQL（当前为演示模式，返回示例数据）。",
        "parameters": {
            "type": "object",
            "properties": {
                "record_id": {"type": "integer", "description": "Text2SQL 记录ID（text2sql_generate 返回）"},
                "sql": {"type": "string", "description": "可选，覆盖要执行的 SQL"},
            },
            "required": ["record_id"],
        },
        "handler": _text2sql_execute,
    },
    {
        "name": "query_logs",
        "description": "查询远程或本地日志内容。先调用 list_ops_environments 获取 environment_id。",
        "parameters": {
            "type": "object",
            "properties": {
                "environment_id": {"type": "integer", "description": "运维环境ID"},
                "path": {"type": "string", "description": "日志文件或目录路径，不传则使用环境默认目录"},
                "keywords": {"type": "array", "items": {"type": "string"}, "description": "过滤关键字列表"},
                "tail_lines": {"type": "integer", "description": "返回最近行数，默认200，最大5000", "default": 200},
            },
            "required": ["environment_id"],
        },
        "handler": _query_logs,
    },
    {
        "name": "list_transfer_tasks",
        "description": "查询内网文件传输任务列表。",
        "parameters": {
            "type": "object",
            "properties": {
                "environment_id": {"type": "integer", "description": "运维环境ID"},
                "limit": {"type": "integer", "description": "返回数量，默认20", "default": 20},
            },
            "required": [],
        },
        "handler": _list_transfer_tasks,
    },
    {
        "name": "create_defect",
        "description": "在 TestHub 问题管理模块创建一个 BUG。数字人在用户描述了某个缺陷时调用。必填：title（一句话标题）和 project_id（先用 list_projects 获取）。可选：severity(S1致命/S2严重/S3一般/S4轻微)、description、steps_to_reproduce、environment、assigned_to(用户ID)。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "BUG 一句话标题"},
                "project_id": {"type": "integer", "description": "所属项目 ID"},
                "severity": {"type": "string", "enum": ["S1", "S2", "S3", "S4"], "default": "S3"},
                "description": {"type": "string", "description": "详细描述"},
                "steps_to_reproduce": {"type": "string", "description": "复现步骤"},
                "environment": {"type": "string", "description": "环境信息如：Chrome 125 / Win11"},
                "assigned_to": {"type": "integer", "description": "指派给的用户 ID"},
            },
            "required": ["title", "project_id"],
        },
        "handler": _create_defect,
    },
    {
        "name": "list_defects",
        "description": "查询缺陷列表。可按项目/状态/严重度过滤。",
        "parameters": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "项目 ID"},
                "status": {"type": "string", "enum": ["open", "in_progress", "resolved", "closed", "reopened"]},
                "severity": {"type": "string", "enum": ["S1", "S2", "S3", "S4"]},
                "limit": {"type": "integer", "default": 20},
            },
            "required": [],
        },
        "handler": _list_defects,
    },
]

# 快速查找表
TOOL_MAP: Dict[str, Dict[str, Any]] = {t["name"]: t for t in TOOL_REGISTRY}


def get_tools_for_llm() -> List[Dict[str, Any]]:
    """返回给 LLM 的 tools 定义（去掉 handler）"""
    return [
        {"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}}
        for t in TOOL_REGISTRY
    ]


def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """执行指定工具"""
    tool = TOOL_MAP.get(name)
    if not tool:
        return {"error": f"未知工具: {name}"}
    try:
        return tool["handler"](**arguments)
    except Exception as e:
        logger.error(f"工具 {name} 执行失败: {e}", exc_info=True)
        return {"error": f"工具执行失败: {str(e)}"}
