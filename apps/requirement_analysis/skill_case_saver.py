"""将 Skill 生成的用例文本保存为各模块的真实用例/脚本对象。

流程：
1. 解析：优先从生成文本中抽取 ```json 结构化块；若无则调用 LLM（复用 Skill 的 writer 模型）
   把文本解析为「通用用例 schema」；都失败则退回纯文本兜底。
2. 映射：按 module 把通用 schema 映射到对应模块的模型字段，直接 create 入库，
   created_by 统一写 request.user；project 关联由前端按模块传入对应的「模块项目 id」
   （性能测试直接传核心项目 id），后端不做 ProjectMapping 转换。
"""
import json
import logging
import re

from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

MODULE_LABELS = {
    "api_testing": "接口测试",
    "ui_automation": "UI自动化",
    "app_automation": "APP自动化",
    "performance_testing": "性能测试",
    "ai_mode": "AI智能模式",
}

# 前端保存对话框按 module 拉取项目列表的接口
PROJECT_API_BY_MODULE = {
    "api_testing": "/api/api-testing/projects/",
    "ui_automation": "/api/ui-automation/projects/",
    "app_automation": "/api/app-automation/projects/",
    "performance_testing": "/api/projects/",
    "ai_mode": "/api/ui-automation/projects/",
}

# 这些模块的项目关联为必填
PROJECT_REQUIRED_MODULES = {"ui_automation"}


def extract_json_block(text):
    """从文本中抽取 JSON 对象（支持 ```json 代码块或整段 JSON）。"""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    t = text.strip()
    if t.startswith("{") and t.endswith("}"):
        try:
            return json.loads(t)
        except Exception:
            pass
    return None


def _normalize_steps(steps):
    out = []
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        out.append({
            "action": str(s.get("action", s.get("operation", ""))).strip(),
            "target": str(s.get("target", s.get("element", s.get("selector", "")))).strip(),
            "value": str(s.get("value", s.get("input_value", ""))).strip(),
            "expected": str(s.get("expected", s.get("assert_value", s.get("assertion", "")))).strip(),
            "wait_time": int(s.get("wait_time", 1000) or 1000),
        })
    return out


def normalize_parsed(js):
    if not isinstance(js, dict):
        return {"name": "", "description": "", "steps": []}
    priority = str(js.get("priority", "medium")).strip().lower()
    if priority not in ("high", "medium", "low"):
        priority = "medium"
    method = str(js.get("method", "GET")).strip().upper() or "GET"
    return {
        "name": str(js.get("name", "")).strip(),
        "description": str(js.get("description", js.get("task_description", ""))).strip(),
        "priority": priority,
        "url": str(js.get("url", "")).strip(),
        "method": method,
        "headers": js.get("headers") or {},
        "body": js.get("body") or {},
        "assertions": js.get("assertions") or [],
        "variables": js.get("variables") or [],
        "jmx_config": _extract_jmx_config(js),
        "jmx_content": str(js.get("jmx_content", "")).strip(),
        "steps": _normalize_steps(js.get("steps")),
    }


def _extract_jmx_config(js):
    """从 Skill 生成结果抽取并规整为平台 jmx_config 结构。

    兼容两种来源：
    - 顶层直接含 thread_groups（「性能 JMX 脚本生成」Skill 的输出形态）
    - 嵌套在 jmx_config 键下（通用解析结果）
    字段命名同时兼容 Skill 习惯（threads/http_samplers/body 为 dict/assertions 为字符串数组）
    与平台习惯（thread_count/samplers/body 为字符串/assertions 为对象数组）。
    """
    if not isinstance(js, dict):
        return {}
    source = js
    nested = js.get("jmx_config")
    if isinstance(nested, dict) and nested.get("thread_groups"):
        source = nested
    tgs = source.get("thread_groups")
    if not isinstance(tgs, list) or not tgs:
        return {}
    return {
        "variables": source.get("variables") or [],
        "csv_datasets": source.get("csv_datasets") or [],
        "thread_groups": [_normalize_thread_group(tg) for tg in tgs],
    }


def _normalize_thread_group(tg):
    threads = tg.get("thread_count") or tg.get("threads") or tg.get("num_threads") or 10
    return {
        "name": tg.get("name") or "Thread Group",
        "thread_count": int(threads),
        "ramp_up": int(tg.get("ramp_up") or tg.get("ramp_time") or 5),
        "duration": int(tg.get("duration") or 60),
        "loops": tg.get("loops") if tg.get("loops") is not None else -1,
        "csv_datasets": [_normalize_csv(c) for c in (tg.get("csv_datasets") or [])],
        "samplers": [_normalize_sampler(s) for s in (tg.get("samplers") or tg.get("http_samplers") or [])],
    }


def _normalize_sampler(s):
    raw_body = s.get("body")
    if isinstance(raw_body, (dict, list)):
        body = json.dumps(raw_body, ensure_ascii=False)
    else:
        body = raw_body or ""
    assertions = []
    for a in s.get("assertions") or []:
        assertions.append(a if isinstance(a, dict) else _parse_skill_assertion(str(a)))
    return {
        "name": s.get("name") or "HTTP Request",
        "method": (s.get("method") or "GET").upper(),
        "url": s.get("url") or "",
        "path": s.get("path") or "/",
        "headers": s.get("headers") or [],
        "params": s.get("params") or [],
        "body": body,
        "assertions": assertions,
    }


def _normalize_csv(csv):
    return {
        "filename": csv.get("file") or csv.get("path") or csv.get("filename") or "data.csv",
        "variable_names": csv.get("variable_names") or csv.get("vars") or csv.get("variable") or "",
        "delimiter": csv.get("delimiter") or ",",
    }


def _parse_skill_assertion(text):
    """把 Skill 的断言字符串（status==200 / rt<500 / contains("成功")）转平台断言对象。

    响应时间类（rt<...）平台无原生断言组件，退回 contains 便于在 UI 修正，不丢信息。
    """
    t = text.strip()
    if "status" in t or "code" in t:
        m = re.search(r"(\d{3})", t)
        return {"type": "response_code", "value": m.group(1) if m else "200"}
    if "contains" in t:
        m = re.search(r"contains\(\s*[\"']?(.+?)[\"']?\s*\)", t)
        return {"type": "contains", "value": m.group(1) if m else t}
    return {"type": "contains", "value": t}


def _build_parse_prompt(module):
    base = (
        "你是一个测试用例结构化解析器。请把用户提供的测试用例文本解析为严格的 JSON 对象，"
        "不要输出任何解释文字，只返回 JSON。通用字段如下：\n"
        "{\n"
        '  "name": "用例名称",\n'
        '  "description": "用例描述",\n'
        '  "priority": "high|medium|low",\n'
        '  "url": "接口地址(仅接口测试填)",\n'
        '  "method": "GET|POST|...",\n'
        '  "headers": {}, "body": {}, "assertions": [], "variables": [],\n'
        '  "steps": [{"action":"点击/输入/等待/断言等","target":"元素或说明","value":"输入值","expected":"预期结果","wait_time":1000}],\n'
        '  "jmx_config": {}\n'
        "}\n"
    )
    focus = {
        "api_testing": "当前为接口测试模块：重点填充 url、method、headers、body、assertions。steps 可不填。",
        "ui_automation": "当前为 UI 自动化模块：重点填充 steps 数组，每步用 action(点击/输入/等待/断言)、target(元素)、value(输入值)、expected(预期)。",
        "app_automation": "当前为 APP 自动化模块：重点填充 steps 数组(Airtest/UI 步骤)，可含 value/expected。",
        "performance_testing": "当前为性能测试模块：重点填充 jmx_config(线程组/HTTP 采样器/断言结构) 或 description 中的场景说明。",
        "ai_mode": "当前为 AI 智能模式：重点填充 name 与 description(自然语言任务描述)，steps 可省略。",
    }
    return base + "\n" + focus.get(module, "")


def parse_to_universal(content, module, model_config):
    """把生成文本解析为通用 schema dict。"""
    js = extract_json_block(content)
    if isinstance(js, dict):
        return normalize_parsed(js)
    if model_config:
        try:
            from .models import AIModelService
            messages = [
                {"role": "system", "content": _build_parse_prompt(module)},
                {"role": "user", "content": content},
            ]
            resp = async_to_sync(AIModelService.call_openai_compatible_api)(model_config, messages)
            text = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            js2 = extract_json_block(text)
            if isinstance(js2, dict):
                return normalize_parsed(js2)
        except Exception as exc:
            logger.exception("LLM 解析用例失败: %s", exc)
    # 兜底：纯文本
    return {"name": "", "description": content, "steps": []}


ACTION_MAP = [
    (("click", "点击", "单击"), "click"),
    (("fill", "输入", "填写", "input"), "fill"),
    (("gettext", "获取文本", "获取"), "getText"),
    (("waitfor", "等待元素", "等待出现"), "waitFor"),
    (("hover", "悬停"), "hover"),
    (("scroll", "滚动"), "scroll"),
    (("screenshot", "截图"), "screenshot"),
    (("assert", "断言", "验证", "verify"), "assert"),
    (("wait", "等待"), "wait"),
    (("switchtab", "切换标签", "切换页"), "switchTab"),
]


def map_action(action_str):
    a = (action_str or "").lower()
    for keys, val in ACTION_MAP:
        if any(k in a for k in keys):
            return val
    return "click"


def save_case(module, content, name, project_id, user, skill=None):
    """把生成文本保存为对应模块的真实用例对象，返回 {id, name, module, detail_path, ...}。"""
    from .models import AIModelConfig

    model_config = None
    if skill:
        model_config = skill.resolve_model_config()
    if not model_config:
        model_config = AIModelConfig.objects.filter(
            role="writer", is_active=True
        ).order_by("-updated_at").first()

    parsed = parse_to_universal(content, module, model_config)
    final_name = (name or parsed.get("name") or "").strip()
    if not final_name:
        final_name = f"AI生成{MODULE_LABELS.get(module, '')}用例"

    if module == "api_testing":
        return _save_api(final_name, parsed, project_id, user)
    if module == "ui_automation":
        return _save_ui(final_name, parsed, project_id, user)
    if module == "app_automation":
        return _save_app(final_name, parsed, project_id, user)
    if module == "performance_testing":
        return _save_perf(final_name, parsed, project_id, user)
    if module == "ai_mode":
        return _save_ai(final_name, parsed, content, project_id, user)
    raise ValueError(f"未知模块: {module}")


def _save_api(name, parsed, project_id, user):
    from apps.api_testing.models import ApiRequest
    url = parsed.get("url") or ""
    if not url:
        raise ValueError(
            "接口用例需要请求地址(URL)，但生成结果中未解析到。请补充接口地址后，"
            "在接口测试模块手动创建，或让 Skill 输出包含 url 的结构化用例。"
        )
    obj = ApiRequest.objects.create(
        name=name,
        url=url,
        project_id=project_id or None,
        method=parsed.get("method", "GET"),
        headers=parsed.get("headers") or {},
        body=parsed.get("body") or {},
        assertions=parsed.get("assertions") or [],
        created_by=user,
    )
    return {
        "id": obj.id, "name": obj.name, "module": "api_testing",
        "detail_path": "/api-testing/requests", "saved_fields": ["url", "method", "headers", "body", "assertions"],
    }


def _save_ui(name, parsed, project_id, user):
    from apps.ui_automation.models import TestCase, TestCaseStep
    if not project_id:
        raise ValueError("UI 自动化用例必须选择所属项目")
    tc = TestCase.objects.create(
        name=name,
        project_id=project_id,
        description=parsed.get("description", ""),
        priority=parsed.get("priority", "medium"),
        created_by=user,
    )
    steps = parsed.get("steps") or []
    objs = []
    for i, s in enumerate(steps, start=1):
        expected = s.get("expected", "")
        objs.append(TestCaseStep(
            test_case=tc,
            step_number=i,
            action_type=map_action(s.get("action", "")),
            input_value=s.get("value", ""),
            wait_time=int(s.get("wait_time", 1000) or 1000),
            assert_type="textContains" if expected else "",
            assert_value=expected,
            description=s.get("target", ""),
        ))
    if objs:
        TestCaseStep.objects.bulk_create(objs)
    return {
        "id": tc.id, "name": tc.name, "module": "ui_automation",
        "detail_path": "/ui-automation/test-cases", "step_count": len(objs),
    }


def _save_app(name, parsed, project_id, user):
    from apps.app_automation.models import AppTestCase
    ui_flow = parsed.get("steps") or parsed.get("ui_flow") or []
    obj = AppTestCase.objects.create(
        name=name,
        project_id=project_id or None,
        description=parsed.get("description", ""),
        ui_flow=ui_flow,
        variables=parsed.get("variables") or [],
        created_by=user,
    )
    return {
        "id": obj.id, "name": obj.name, "module": "app_automation",
        "detail_path": "/app-automation/test-cases",
    }


def _save_perf(name, parsed, project_id, user):
    from apps.performance_testing.models import PerformanceScript
    script = PerformanceScript.objects.create(
        name=name,
        description=parsed.get("description", ""),
        script_type="ONLINE",
        jmx_config=parsed.get("jmx_config") or {},
        jmx_content=parsed.get("jmx_content") or "",
        created_by=user,
    )
    if project_id:
        script.projects.add(project_id)
    return {
        "id": script.id, "name": script.name, "module": "performance_testing",
        "detail_path": "/performance-testing/scripts",
    }


def _save_ai(name, parsed, content, project_id, user):
    from apps.ui_automation.models import AICase
    task_description = parsed.get("description") or content
    obj = AICase.objects.create(
        name=name,
        task_description=task_description,
        description=parsed.get("description", ""),
        project_id=project_id or None,
        created_by=user,
    )
    return {
        "id": obj.id, "name": obj.name, "module": "ai_mode",
        "detail_path": "/ui-automation/ai-cases",
    }
