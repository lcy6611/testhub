"""
用例 → UI 自动化脚本 生成服务（增量功能，独立文件，可整体删除）。

流程：
  1. 读取 testcases.TestCase 的步骤（结构化 step_details 优先，回退自由文本 steps）
  2. 用 writer 模型把用例拆解为浏览器可执行的结构化动作序列
  3. 拼成 browser-use 任务描述，复用现有 browser-use 智能体（ai_agent.run_full_process_sync）在真实系统操作
  4. 从 AgentHistoryList.state.interacted_element 抽取每步智能体实际交互的元素，去重后落库 Element
  5. 基于抓取到的稳定定位器生成 Playwright(Python) 脚本，落库 TestScript + ScriptStep
  6. 用现有 PlaywrightTestEngine 回放脚本自验证，更新 Element.validation_status

约束：绝不修改 ai_base.py / 现有 views / 现有 models 业务逻辑；所有逻辑在本文件内。
"""
import logging
import json
import asyncio
import re
import threading

from django.db import close_old_connections
from asgiref.sync import sync_to_async

from .models import (
    UiScriptGeneration, Element, TestScript, ScriptStep, LocatorStrategy,
)
from apps.testcases.models import TestCase
from apps.requirement_analysis.models import AIModelService, AIModelConfig

logger = logging.getLogger('django')

# 停止信号（与现有 AI 执行一致，用内存字典控制）
STOP_SIGNALS = {}


# ======================================================================
# 进度日志工具
# ======================================================================
def _log(gen, msg):
    """把一行进度追加写回 UiScriptGeneration，并刷新 DB 连接（线程安全）。"""
    try:
        close_old_connections()
        gen.progress_log = (gen.progress_log or '') + str(msg) + "\n"
        gen.save(update_fields=['progress_log', 'updated_at'])
    except Exception as e:
        logger.warning(f"[case_script] 写日志失败: {e}")


def _save(gen):
    try:
        close_old_connections()
        gen.save()
    except Exception as e:
        logger.warning(f"[case_script] 保存失败: {e}")


# ======================================================================
# 1) 用例 → 结构化动作序列（LLM 辅助，带规则兜底）
# ======================================================================
_SYS_PROMPT_STRUCT = """你是一个测试脚本分析专家。给定一条测试用例，请将其拆解为浏览器可执行的原子操作序列。
只输出 JSON（不要任何解释、不要 markdown 围栏），格式：
[
  {"step":1,"action_type":"NAVIGATE|CLICK|INPUT|SELECT|VERIFY|WAIT|HOVER","target":"对要操作元素的自然语言描述，如'登录按钮'、'用户名输入框'","input_value":"输入类操作的文本值，无则空字符串","expected":"该步骤预期结果简述","assert_type":"textContains|textEquals|isVisible|exists"}
]
规则：
- 首个涉及页面跳转的步骤用 NAVIGATE（target 为页面或URL描述）。
- 点击用 CLICK，填表用 INPUT（input_value 为填入值），下拉选择用 SELECT，校验用 VERIFY。
- target 必须是对页面可见元素的描述，供后续智能体在系统中定位。
- 不同 INPUT 步骤的 target **必须明确区分字段**（例如"用户名输入框"与"密码输入框"不能写成同一个描述），若用例含"用户名/密码/验证码/邮箱/手机号/搜索"等字段，target 必须对应写出。
- 保持步骤顺序与用例一致。"""


def _build_case_text(tc):
    lines = [f"用例标题：{tc.title}"]
    if tc.description:
        lines.append(f"用例描述：{tc.description}")
    if tc.preconditions:
        lines.append(f"前置条件：{tc.preconditions}")
    steps = list(tc.step_details.all().order_by('step_number'))
    if steps:
        lines.append("操作步骤：")
        for s in steps:
            lines.append(f"{s.step_number}. {s.action}  （预期：{s.expected}）")
    elif tc.steps:
        lines.append(f"操作步骤：{tc.steps}")
    lines.append(f"预期结果：{tc.expected_result}")
    return "\n".join(lines)


def _extract_json_array(text):
    if not text:
        return None
    text = text.strip()
    if text.startswith('```'):
        parts = text.split('```', 2)
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith('json'):
                text = text[4:]
    try:
        return json.loads(text)
    except Exception:
        s = text.find('[')
        e = text.rfind(']')
        if s >= 0 and e > s:
            try:
                return json.loads(text[s:e + 1])
            except Exception:
                return None
    return None


def _fallback_steps(tc):
    """无 LLM / LLM 失败时，用规则把用例步骤转成 CLICK 动作序列。"""
    out = []
    steps = list(tc.step_details.all().order_by('step_number'))
    if steps:
        for s in steps:
            out.append({"step": s.step_number, "action_type": "CLICK",
                        "target": s.action, "input_value": "",
                        "expected": s.expected, "assert_type": "textContains"})
    elif tc.steps:
        for i, line in enumerate(tc.steps.splitlines()):
            line = line.strip()
            if line:
                out.append({"step": i + 1, "action_type": "CLICK",
                            "target": line, "input_value": "",
                            "expected": "", "assert_type": "textContains"})
    if not out:
        out.append({"step": 1, "action_type": "VERIFY", "target": tc.title,
                    "input_value": "", "expected": tc.expected_result,
                    "assert_type": "textContains"})
    return out


_FIELD_KEYWORDS = [
    ('验证码', '验证码'), ('确认', '确认'), ('密码', '密码'), ('用户名', '用户名'),
    ('账号', '账号'), ('邮箱', '邮箱'), ('手机号', '手机号'), ('姓名', '姓名'),
    ('搜索', '搜索'),
]


def _raw_step_text_by_number(tc):
    """返回 {step_number: 原文 action 文本}，用于把用例原文的字段词带进 target。"""
    mapping = {}
    if not hasattr(tc, 'step_details'):
        return mapping
    for s in tc.step_details.all().order_by('step_number'):
        mapping[s.step_number] = f"{s.action} {s.expected or ''}"
    return mapping


def _disambiguate_input_targets(tc, data):
    """INPUT 步骤 target 必须能区分不同字段（用户名输入框 ≠ 密码输入框）。

    LLM 常把"输入用户名/输入密码"两步塌缩成同一个 target（都写"用户名输入框"），
    导致后续 _match_element 只能命中同一个 input。这里用用例原文的字段词重建 target：
    原文含 密码 → "密码输入框"，含 用户名 → "用户名输入框"，保证不同字段不同 target、
    可被元素匹配正确分开。原文无字段词时保留 LLM target，仅对撞车者追加序号。
    """
    raw_by_no = _raw_step_text_by_number(tc)
    seen = {}
    for d in data:
        if (d.get('action_type') or '').upper() != 'INPUT':
            continue
        raw = raw_by_no.get(d.get('step'), '') or ''
        field_label = None
        for kw, label in _FIELD_KEYWORDS:
            if kw in raw:
                field_label = label
                break
        tgt = (d.get('target') or '').strip()
        if field_label:
            # 用原文字段词重建，消除 LLM 塌缩（即使 LLM 给了错 target 也纠正）
            tgt = f"{field_label}输入框"
        elif not tgt:
            tgt = f"输入框{d.get('step', '')}"
        if tgt in seen:
            seen[tgt] += 1
            tgt = f"{tgt}({seen[tgt]})"
        else:
            seen[tgt] = 1
        d['target'] = tgt
    return data


def structurize_case(tc):
    """把用例拆成结构化动作序列。优先 LLM，失败回退规则。"""
    cfg = AIModelConfig.objects.filter(role='writer', is_active=True).first()
    if not cfg:
        logger.warning("[case_script] 未配置 writer 模型，使用规则兜底")
        return _fallback_steps(tc)
    messages = [
        {"role": "system", "content": _SYS_PROMPT_STRUCT},
        {"role": "user", "content": _build_case_text(tc)},
    ]
    try:
        close_old_connections()
        resp = asyncio.run(
            AIModelService.call_openai_compatible_api(
                cfg, messages, min_tokens=1024,
                meta={"module": "ui_automation", "feature": "case_script_struct"},
            )
        )
        text = resp['choices'][0]['message']['content']
        data = _extract_json_array(text)
        if data:
            for i, d in enumerate(data):
                d.setdefault('step', i + 1)
                d.setdefault('action_type', 'CLICK')
                d.setdefault('target', '')
                d.setdefault('input_value', '')
                d.setdefault('expected', '')
                d.setdefault('assert_type', 'textContains')
            _disambiguate_input_targets(tc, data)
            return data
    except Exception as e:
        logger.warning(f"[case_script] 结构化用例失败，回退规则: {e}")
    return _fallback_steps(tc)


# ======================================================================
# 2) 拼 browser-use 任务描述
# ======================================================================
def build_agent_task(structured_steps, base_url):
    # 关键规则：浏览器智能体最容易"挑错元素"——选到 form-item wrapper 或 .ant-btn 通用类。
    # 注意：措辞从"硬性禁止"改为"优先建议"，否则在 Element Plus + Ant Design 混用的页面，
    # agent 找不到"完美区分度"的按钮会反复 retry / 提前结束，反而只填了第一个输入框就停。
    # 真实项目里 wrapper / 通用类往往就是唯一可点的控件，应允许使用，只要能唯一定位目标。
    lines = [
        f"请打开网站 {base_url}。",
        "【元素定位建议（优先遵守，提升执行稳定性）】",
        "- 输入框**优先**选原生 <input> / <textarea> 本身（优先用 placeholder / name / aria-label 定位）；"
        "若页面只有 form-item / form / wrapper 容器包裹的输入框可用，也可选用，但要确保该选择器能唯一定位到你要填的那个框。",
        "- 登录/提交等按钮**优先**选有区分度的选择器（带具体文本或专属 class，如 `.btn-login` / `#login`）；"
        "若页面只有 `.ant-btn` / `.el-button` / `button[type='submit']` 这类通用按钮，也可选用，但要确认它就是你要点那个（例如按钮文字是'登录'）。",
        "- 每一步操作后明确告知你已经完成了哪个步骤。",
        "",
        "严格按照下面列出的测试步骤，在网站中一步步操作；所有步骤完成后，明确宣布\"任务完成\"。",
        "测试步骤：",
    ]
    for s in structured_steps:
        step_no = s.get('step', '')
        tgt = s.get('target', '')
        at = s.get('action_type', 'CLICK')
        val = s.get('input_value', '')
        if at == 'INPUT':
            lines.append(f"{step_no}. 在「{tgt}」中输入：{val}")
        elif at == 'CLICK':
            lines.append(f"{step_no}. 点击「{tgt}」")
        elif at == 'NAVIGATE':
            lines.append(f"{step_no}. 导航到 / 打开「{tgt}」")
        elif at == 'SELECT':
            lines.append(f"{step_no}. 在「{tgt}」中选择：{val}")
        elif at == 'VERIFY':
            lines.append(f"{step_no}. 验证「{tgt}」（预期：{s.get('expected', '')}）")
        elif at == 'WAIT':
            lines.append(f"{step_no}. 等待（{tgt}）")
        elif at == 'HOVER':
            lines.append(f"{step_no}. 悬停到「{tgt}」")
        else:
            lines.append(f"{step_no}. {tgt}")
    return "\n".join(lines)


# ======================================================================
# 3) 从 AgentHistoryList 抽取智能体实际交互的元素
# ======================================================================
def _action_name(action):
    try:
        d = action.model_dump() if hasattr(action, 'model_dump') else {}
        if d:
            return list(d.keys())[0]
    except Exception:
        pass
    return 'interact'


_INPUT_WRAPPER_ID_RE = re.compile(r'^(form_item|input_|form_|wrapper|field_|field|wrap|group)_', re.I)
_GENERIC_BTN_CLASSES = {'ant-btn', 'el-button', 'btn', 'button', 'submit', 'primary-btn', 'default-btn', 'btn-primary', 'btn-default'}

# 中文 target → 常见 attrs 英文别名（用于跨语言匹配）
_ATTR_TRANSLATE = {
    '密码': ['password', 'pwd', 'pass'],
    '用户名': ['username', 'user', 'loginname', 'login-name', 'account'],
    '账号': ['account', 'username'],
    '邮箱': ['email', 'mail'],
    '手机号': ['phone', 'mobile', 'tel', 'cellphone'],
    '搜索': ['search', 'query', 'keyword'],
    '姓名': ['name', 'fullname', 'realname'],
    '登录': ['login', 'signin', 'sign-in'],
    '验证码': ['captcha', 'verify', 'code', 'vcode', 'auth-code'],
    '确认': ['confirm', 'retry', 'again'],
    '新': ['new'],
    '旧': ['old', 'current'],
}


def _expand_keywords(keywords):
    """扩 keywords：中文 target 词对应的常见英文 attrs 关键词一起作为匹配信号。
    
    由于中文 target 可能没有空格分词（如"密码输入框"），对每个 kw
    枚举 ≥2 字的所有连续子串，逐个查 _ATTR_TRANSLATE 拿到英文 alias。
    """
    out = list(keywords)
    for kw in keywords:
        n = len(kw)
        # 枚举所有连续子串（长度 ≥2）
        subs = set()
        for i in range(n):
            for j in range(i + 2, n + 1):
                sub = kw[i:j]
                # 仅当全是中文字符时才进 _ATTR_TRANSLATE，避免把 'username' 拆成无意义片段
                if all('\u4e00' <= ch <= '\u9fff' for ch in sub):
                    subs.add(sub)
        for sub in subs:
            for alias in _ATTR_TRANSLATE.get(sub, []):
                if alias not in out:
                    out.append(alias)
    return out


def _looks_like_wrapper_id(el_id):
    """id 形如 form_item_username / input_pwd / wrapper_xxx 这种是容器/wrapper，不是真控件。"""
    if not el_id:
        return False
    el_id = str(el_id).strip()
    if _INPUT_WRAPPER_ID_RE.match(el_id):
        return True
    # 纯前缀无意义（如 #user / #pwd）+ 无 name 提示 → 优先放弃 id
    return False


def _is_generic_btn_class(cls):
    """Ant/Element/MUI 等通用按钮类，没有区分度。"""
    if not cls:
        return False
    tokens = [t.lower() for t in str(cls).split() if t]
    # 命中通用类 且 没有定语/状态修饰（不足以区分多个按钮）
    bare = [t for t in tokens if t in _GENERIC_BTN_CLASSES]
    if not bare:
        return False
    # 若还有第二个专属 token（如 ant-btn-lg、ant-btn-primary）也认作没区分度
    return len(tokens) <= 2


def choose_locator(node_name, attrs, xpath, text):
    """按 node_name 选最稳定且可直接交互的定位器。
    
    规则：
    - 输入类（input/textarea/select）：name > placeholder > id(非wrapper) > text > xpath；舍弃 form_item_* 等容器 id。
    - 按钮/链接（button/a）：text > id > name > type > CSS类(非通用) > xpath；舍弃 .ant-btn/.el-button 等通用类。
    - 其他（div/span/label/form）：只用 text > xpath，且仅在文本非空时返回，否则返回最保守的 xpath。
    """
    attrs = attrs or {}
    node = str(node_name or '').strip().lower()

    el_id = attrs.get('id')
    el_id_clean = str(el_id).strip() if el_id and ' ' not in str(el_id).strip() else ''
    name = attrs.get('name')
    placeholder = attrs.get('placeholder')
    cls = attrs.get('class')
    btn_type = attrs.get('type')
    txt = (text or '').strip()

    # === 输入类 ===
    if node in ('input', 'textarea', 'select'):
        if name:
            return {'strategy': 'css', 'value': f"[name='{name}']"}
        if placeholder:
            return {'strategy': 'css', 'value': f"[placeholder='{placeholder}']"}
        # 真 input 的 id 通常形如 username/password 直接单词；wrapper id 如 form_item_*
        if el_id_clean and not _looks_like_wrapper_id(el_id_clean):
            return {'strategy': 'css', 'value': f"#{el_id_clean}"}
        if txt:
            return {'strategy': 'text', 'value': txt}
        if xpath:
            return {'strategy': 'xpath', 'value': xpath}
        return {'strategy': 'xpath', 'value': xpath or '//input'}

    # === 按钮/链接 ===
    if node in ('button', 'a'):
        if txt:
            return {'strategy': 'text', 'value': txt}
        if el_id_clean:
            return {'strategy': 'css', 'value': f"#{el_id_clean}"}
        if name:
            return {'strategy': 'css', 'value': f"[name='{name}']"}
        if btn_type:
            return {'strategy': 'css', 'value': f"button[type='{btn_type}']"}
        # 通用按钮类没区分度，跳过 → 落到 xpath
        if cls and not _is_generic_btn_class(cls):
            first_cls = str(cls).split()[0]
            if first_cls:
                return {'strategy': 'css', 'value': f".{first_cls}"}
        if xpath:
            return {'strategy': 'xpath', 'value': xpath}
        return {'strategy': 'xpath', 'value': xpath or '//button'}

    # === 其他节点（div/span/label/form）默认不可直接交互，降级用 text ===
    if txt:
        return {'strategy': 'text', 'value': txt}
    if xpath:
        return {'strategy': 'xpath', 'value': xpath}
    return {'strategy': 'xpath', 'value': xpath or '//*'}


def extract_elements(history):
    """遍历 AgentHistoryList，抽取每一步 interacted_element，去重返回元素列表。"""
    seen = {}
    elements = []
    hist = getattr(history, 'history', None)
    if not hist:
        return elements
    for step in hist:
        mo = getattr(step, 'model_output', None)
        if not mo:
            continue
        actions = mo.action if isinstance(mo.action, list) else [mo.action]
        state = getattr(step, 'state', None)
        inter = getattr(state, 'interacted_element', None) if state else None
        for k, action in enumerate(actions):
            el = None
            if inter and k < len(inter):
                el = inter[k]
            if not el:
                continue
            node_name = getattr(el, 'node_name', '') or ''
            xpath = getattr(el, 'x_path', '') or ''
            attrs = getattr(el, 'attributes', {}) or {}
            text = getattr(el, 'ax_name', '') or ''
            loc = choose_locator(node_name, attrs, xpath, text)
            key = (loc['strategy'], loc['value'])
            if key in seen:
                seen[key]['actions'].add(_action_name(action))
                continue
            rec = {
                'node_name': node_name,
                'xpath': xpath,
                'attributes': attrs,
                'text': text,
                'action': _action_name(action),
                'actions': {_action_name(action)},
                'locator': loc,
            }
            seen[key] = rec
            elements.append(rec)
    return elements


def _match_element(pool, target, action_type, used_keys):
    """智能匹配抓取到的元素（按动作类型 + 文本子串多关键词 + 顺序回退）。

    pool 中元素按浏览器真实执行顺序排列（已去重）；used_keys 是
    本任务其他 step 已绑定的 (strategy, value) 集合，避免一个元素被
    多个 step 抢注而 Step A 用错元素（Step B 仍能复用同一元素，允许）。

    返回值：命中的元素 dict；找不到返回 None（此时 Element 字段留空）。
    对 NAVIGATE/WAIT/VERIFY 等不需要元素的 step 直接返回 None。
    """
    at = (action_type or '').upper()
    want_actions = {
        'INPUT': {'input_text', 'type_text', 'type', 'fill', 'input'},
        'CLICK': {'click', 'left_click'},
        'HOVER': {'hover'},
        'SELECT': {'select_option', 'click'},
    }.get(at, None)
    if want_actions is None:
        # NAVIGATE / WAIT / VERIFY 等不需要 UI 元素
        return None

    # node_name 限制：INPUT/SELECT 必须是原生控件；CLICK 优先 button/a；HOVER 任意可悬停
    want_nodes = {
        'INPUT':   {'input', 'textarea'},
        'SELECT':  {'select', 'input'},
        'HOVER':   None,  # 不限
    }.get(at) if at != 'CLICK' else {'button', 'a'}

    t = (target or '').strip()
    # 拆多个关键词（去"的"等虚词），至少 2 字
    keywords = [k for k in t.replace('的', ' ').split() if len(k) >= 2] if t else []
    input_like_kw = {'输入', '填写', '键入', '账号', '密码', '用户名', '搜索', '邮箱', '手机号', 'input'}
    # CLICK 步骤若 target 含"输入/搜索框"等词，应让 click 也能命中到 input（罕见但存在）
    if at == 'CLICK' and any(k in input_like_kw for k in keywords):
        want_nodes = {'button', 'a', 'input', 'textarea', 'select'}

    candidates = [el for el in pool if (el['locator']['strategy'] + ':' + el['locator'].get('value', '')) not in used_keys]
    if want_nodes is not None:
        node_filtered = [el for el in candidates if (el.get('node_name') or '').lower() in want_nodes]
        if node_filtered:
            candidates = node_filtered

    def _attr_text(el):
        """把元素所有可标识字符串拼起来，便于模糊匹配。"""
        attrs = el.get('attributes') or {}
        parts = [
            str(el.get('text', '')),
            str(el.get('node_name', '')),
            str(attrs.get('name', '')),
            str(attrs.get('placeholder', '')),
            str(attrs.get('id', '')),
            str(attrs.get('aria-label', '')),
            str(el.get('locator', {}).get('value', '')),
        ]
        return ' '.join(p for p in parts if p).lower()

    def _text_match(el):
        if not keywords:
            return True
        hay = _attr_text(el)
        all_kws = _expand_keywords(keywords)
        # OR 命中：扩展后的 keywords（含中英 alias）只要有 1 个出现在 hay 中即算匹配
        # 对中文 '密码' vs 英文 'password' 的鸿沟特别重要：靠 alias 命中
        return any(kw.lower() in hay for kw in all_kws)

    def _type_ok(el):
        return bool(el.get('actions') & want_actions)

    # 一级：类型 OK + 文本 multi-keyword 命中
    for el in candidates:
        if _type_ok(el) and _text_match(el):
            return el
    # 二级：仅类型匹配（按出现顺序取未用的同类型第一个）
    for el in candidates:
        if _type_ok(el):
            return el
    # 兜底：放弃绑定，宁可让用户手动补，也不把另一个 input 错绑到这一 step
    #   （避免 username/password 两个 input 被同一元素占两次的踩坑）
    if not candidates:
        return None
    # 仅在只有一个候选时才允许兜底（如整页只抓到一个元素）
    if len(candidates) == 1:
        return candidates[0]
    return None


# ======================================================================
# 4) 落库元素 + 生成 Playwright 脚本
# ======================================================================
_ELEMENT_TYPE_MAP = {
    'button': 'BUTTON', 'input': 'INPUT', 'a': 'LINK', 'select': 'DROPDOWN',
    'textarea': 'INPUT', 'img': 'IMAGE', 'form': 'FORM', 'table': 'TABLE',
}


def _map_element_type(node_name, strategy):
    return _ELEMENT_TYPE_MAP.get(str(node_name).lower(), 'CONTAINER')


def _esc(s):
    return str(s).replace('"', '\\"').replace('\n', ' ')


def _code_line(s, el):
    at = s.get('action_type', 'CLICK')
    target = s.get('target', '')
    val = s.get('input_value', '')
    loc = el['locator']['value'] if el else target
    if at == 'INPUT':
        return f'        page.fill("{_esc(loc)}", "{_esc(val)}")'
    if at == 'CLICK':
        return f'        page.click("{_esc(loc)}")'
    if at == 'SELECT':
        return f'        page.select_option("{_esc(loc)}", "{_esc(val)}")'
    if at == 'HOVER':
        return f'        page.hover("{_esc(loc)}")'
    if at == 'VERIFY':
        exp = s.get('expected', '')
        atype = s.get('assert_type', 'textContains')
        if atype == 'isVisible':
            return f'        assert page.is_visible("{_esc(loc)}"), "验证可见失败: {_esc(target)}"'
        if atype == 'exists':
            return f'        assert page.locator("{_esc(loc)}").count() > 0, "验证存在失败: {_esc(target)}"'
        return f'        assert "{_esc(exp)}" in page.inner_text("{_esc(loc)}"), "验证文本失败: {_esc(target)}"'
    if at == 'NAVIGATE':
        return f'        page.goto("{_esc(target)}")'
    if at == 'WAIT':
        return '        page.wait_for_timeout(1000)'
    return f'        # {at}: {_esc(target)}'


class _EngineStep:
    """适配 PlaywrightTestEngine.execute_step 所需的步骤对象字段。"""
    pass


_ACTION_TO_ENGINE = {
    'CLICK': 'click', 'INPUT': 'fill', 'VERIFY': 'assert', 'WAIT': 'wait',
    'HOVER': 'hover', 'SCROLL': 'scroll', 'NAVIGATE': 'navigate',
    'SELECT': 'select_option', 'SCREENSHOT': 'screenshot',
}


def _to_engine_step(ss):
    p = ss.action_params or {}
    st = _EngineStep()
    st.action_type = _ACTION_TO_ENGINE.get(ss.action_type, ss.action_type.lower())
    st.input_value = p.get('value') or ''
    st.assert_type = p.get('assert_type') or 'textContains'
    st.assert_value = p.get('expected') or ''
    st.wait_time = 1000
    st.description = ss.description or ''
    return st


def _to_element_data(el):
    if not el:
        return {}
    return {
        'locator_strategy': el.locator_strategy.name,
        'locator_value': el.locator_value,
        'name': el.name,
        'force_action': el.force_action,
        'wait_timeout': el.wait_timeout,
    }


def _get_strategy(name):
    obj, _ = LocatorStrategy.objects.get_or_create(name=name)
    return obj


def save_elements_and_testcase(gen, structured_steps, captured, base_url):
    """落库 Element / UiTestCase / TestCaseStep，并把生成的 Playwright 代码单独存到 gen.playwright_code。

    设计原则（陛下 v5+v6 指示）：
    - 生成的"脚本"本质是**用例**，以 ui_test_cases.TestCase + ui_test_case_steps.TestCaseStep 存储
    - 套件通过 TestSuiteTestCase 关联，执行走 TestExecutor.run_with_playwright（基于 UiTestCase）
    - 不再独立建 TestScript/ScriptStep（避免两套并行数据让陛下困惑）
    - Playwright 代码单独存到 UiScriptGeneration.playwright_code，不混入 test_case.description，
      确保用例列表卡片展示干净；代码仅在「生成结果页」以可折叠卡显示。
    - 元素匹配按"动作类型 + 文本多关键词 + 顺序回退"智能绑定（之前弱匹配经常失败导致步骤全空）。
    - 同一定位器被多个 step 关联时复用 Element 行（避免重复创建）。
    """
    from .models import TestCase as UiTestCase, TestCaseStep as UiTestCaseStep

    ui_project = gen.ui_project
    # 兜底 created_by（未登录场景）
    owner = gen.created_by
    if owner is None:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        owner = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if owner is None:
            owner, _ = User.objects.get_or_create(username='case_script_system', defaults={'is_active': True})

    test_case = UiTestCase.objects.create(
        project=ui_project,
        name=(gen.source_testcase_title or f"UI用例-{gen.id}")[:200],
        description=(
            f"由业务用例 #{gen.source_testcase_id} 自动生成（生成任务 #{gen.id}） · "
            f"被测地址：{base_url} · "
            f"智能体共抓取 {len(captured)} 个去重元素、{len(structured_steps)} 个结构化步骤"
        ),
        status='draft',
        priority='medium',
        created_by=owner,
    )

    script_lines = [
        "from playwright.sync_api import sync_playwright",
        "",
        "",
        f"def test_case_{gen.id}(base_url=\"{base_url}\"):",
        "    with sync_playwright() as p:",
        "        browser = p.chromium.launch(headless=True)",
        "        page = browser.new_page()",
        "        page.goto(base_url)",
    ]

    # 1) 先把智能体抓到的全部去重元素落库为 Element，确保"元素管理"页始终有数据，
    #    不再"只有被步骤命中的元素才保存"。按 (strategy,value) 复用项目已有 Element，避免重复。
    available = list(captured)  # 复制一份作"未用池"，供步骤匹配顺序回退
    used_keys = set()
    element_obj_by_key = {}  # loc_key -> Element（含本次抓取的全部元素）
    element_ids = []

    strat_cache = {}
    def _get_strat(name):
        if name not in strat_cache:
            strat_cache[name] = LocatorStrategy.objects.get_or_create(name=name)[0]
        return strat_cache[name]

    existing_map = {
        ((e.locator_strategy.name if e.locator_strategy else None), e.locator_value): e
        for e in Element.objects.filter(project=ui_project).select_related('locator_strategy')
    }
    for el in captured:
        loc_key = el['locator']['strategy'] + ':' + el['locator'].get('value', '')
        if loc_key in element_obj_by_key:
            continue
        strat = _get_strat(el['locator']['strategy'])
        existing = existing_map.get((strat.name, el['locator'].get('value', '')))
        if existing is None:
            existing = Element.objects.create(
                project=ui_project,
                name=(el['node_name'] or el['locator'].get('value', ''))[:120],
                description=f"自动抓取@{el['node_name']}",
                element_type=_map_element_type(el['node_name'], el['locator']['strategy']),
                locator_strategy=strat,
                locator_value=el['locator']['value'],
                backup_locators=[{'strategy': 'xpath', 'value': el['xpath']}] if el['xpath'] else None,
                page='',
                validation_status='PENDING',
                created_by=owner,
            )
            existing_map[(strat.name, el['locator'].get('value', ''))] = existing
        element_obj_by_key[loc_key] = existing
        element_ids.append(existing.id)

    order = 0

    for s in structured_steps:
        order += 1
        at = (s.get('action_type') or 'CLICK').upper()
        el = _match_element(available, s.get('target', ''), at, used_keys)

        element_obj = None
        if el:
            loc_key = el['locator']['strategy'] + ':' + el['locator'].get('value', '')
            element_obj = element_obj_by_key.get(loc_key)
            used_keys.add(loc_key)
            # 从未用池移除，避免后面同级顺序回退抢走
            try:
                available.remove(el)
            except ValueError:
                pass

        step_action = _map_step_action(at)
        step_assert = (s.get('assert_type') or 'textContains')
        if step_assert not in {'textContains', 'textEquals', 'isVisible', 'exists', 'hasAttribute'}:
            step_assert = 'textContains'
        UiTestCaseStep.objects.create(
            test_case=test_case,
            step_number=order,
            action_type=step_action,
            element=element_obj,
            input_value=str(s.get('input_value', ''))[:1000],
            assert_type=step_assert if step_action == 'assert' else '',
            assert_value=str(s.get('expected', ''))[:1000] if step_action == 'assert' else '',
            wait_time=1000,
            description=str(s.get('target', ''))[:1000],
        )
        script_lines.append(_code_line(s, el))
    script_lines.append("        browser.close()")
    test_case.save()  # description 不再追加代码

    gen.generated_test_case = test_case
    gen.generated_script = None
    gen.elements_captured = len(captured)
    gen.steps_total = len(structured_steps)
    gen.playwright_code = "\n".join(script_lines)
    gen.save()
    return test_case, element_ids


def _map_step_action(at):
    """structured action_type → UiTestCaseStep.action_type choices"""
    return {
        'CLICK': 'click',
        'INPUT': 'fill',
        'FILL': 'fill',
        'NAVIGATE': 'wait',
        'WAIT': 'wait',
        'VERIFY': 'assert',
        'ASSERT': 'assert',
        'HOVER': 'hover',
        'SELECT': 'click',
        'SCROLL': 'scroll',
        'SCREENSHOT': 'screenshot',
        'SWITCH_TAB': 'switchTab',
    }.get(at, 'click')


# ======================================================================
# 5) 回放自验证（复用现有 PlaywrightTestEngine）
# ======================================================================
@sync_to_async
def _verify_load_steps(test_case):
    """异步上下文外预取步骤（含 element / locator 关联），避免 async 内访问同步 ORM。"""
    return list(
        test_case.steps.select_related('element', 'element__locator_strategy').order_by('step_number')
    )


@sync_to_async
def _verify_save_element(el, ok, log):
    """异步上下文外用 sync_to_async 落库元素验证结果。"""
    if ok:
        el.validation_status = 'VALID'
    else:
        el.validation_status = 'INVALID'
        el.validation_message = str(log)[:500]
    el.save(update_fields=['validation_status', 'validation_message'])


async def _verify_async(gen, test_case, base_url):
    """回放验证：遍历 UiTestCaseStep，跑 PlaywrightTestEngine。

    注意：所有同步 ORM 访问必须在 async 上下文之外（或经 sync_to_async 包装），
    否则 Django 会抛 "You cannot call this from an async context"。
    这里把步骤预取、逐元素 save、进度日志都改成 sync_to_async / 异步上下文外执行。
    """
    from .playwright_engine import PlaywrightTestEngine
    engine = PlaywrightTestEngine(browser_type='chromium', headless=True)
    await engine.start()
    passed = 0
    verifiable = 0
    log_lines = []
    try:
        await engine.navigate(base_url)
        steps = await _verify_load_steps(test_case)
        for step in steps:
            el = step.element
            if not el:
                # 无元素关联的步骤（如纯 assert/wait）跳过验证计数
                continue
            verifiable += 1
            eng_step = _EngineStep()
            eng_step.action_type = step.action_type
            eng_step.input_value = step.input_value or ''
            eng_step.assert_type = step.assert_type or 'textContains'
            eng_step.assert_value = step.assert_value or ''
            eng_step.wait_time = step.wait_time or 1000
            eng_step.description = step.description or ''
            element_data = _to_element_data(el)
            try:
                ok, log, _shot = await engine.execute_step(eng_step, element_data)
            except Exception as e:
                ok, log = False, str(e)
            if ok:
                passed += 1
            await _verify_save_element(el, ok, log)
            log_lines.append(
                f"  步骤{step.step_number} [{step.action_type}] {step.description}: "
                f"{'✅通过' if ok else '❌失败 ' + str(log)[:120]}"
            )
    finally:
        await engine.stop()
    if log_lines:
        # 进度日志也是同步 ORM 写，需在 async 上下文外执行
        await sync_to_async(_log)(gen, "\n".join(log_lines))
    return passed, verifiable


# ======================================================================
# 6) 驱动智能体 + 主流程
# ======================================================================
def run_agent(task, gen):
    from .ai_agent import run_full_process_sync

    def step_cb(payload):
        if isinstance(payload, dict) and payload.get('type') == 'log':
            _log(gen, payload.get('content', ''))

    should_stop = lambda: STOP_SIGNALS.get(gen.id, False)
    try:
        return run_full_process_sync(
            task, step_callback=step_cb, should_stop=should_stop,
            headless=True, case_name=str(gen.id),
        )
    finally:
        STOP_SIGNALS.pop(gen.id, None)


def create_suite_for_generation(gen, test_case):
    """生成完成后自动建一个 UI 套件，把生成的用例纳入（增量、可整体删除）。

    用 TestSuiteTestCase 关联（不是 TestSuiteScript），便于在套件管理中走"添加用例"模式查看/执行。
    """
    from .models import TestSuite, TestSuiteTestCase
    suite_name = f"UI脚本套件-{gen.source_testcase_title or gen.id}"
    suite = TestSuite.objects.create(
        project=gen.ui_project,
        name=suite_name[:200],
        description=f"由业务用例 #{gen.source_testcase_id} 自动生成 UI 用例所建（生成任务 #{gen.id}）",
    )
    TestSuiteTestCase.objects.get_or_create(
        test_suite=suite, test_case=test_case, defaults={'order': 0}
    )
    gen.ui_suite = suite
    gen.save(update_fields=['ui_suite'])
    return suite


def run_suite_execution(gen, suite):
    """建套件后自动执行（复用 TestExecutor，基于 ScriptStep 真实回放），结果回写 gen。

    增量、可整体删除；不改动现有 views / ai_base。
    """
    from .test_executor import TestExecutor

    # 自动执行时优先用生成任务记录的被测地址（gen.base_url，来自业务用例/浏览器抓取，是真实目标）。
    # 项目 base_url 可能是占位值（如 http://localhost）或为空，拿它去导航必然失败。
    # 这里临时覆盖项目 base_url 供本次执行使用，执行后恢复原值，避免污染项目配置。
    project = suite.project
    original_base_url = (project.base_url or '').strip()
    gen_url = (gen.base_url or '').strip()
    use_base_url = gen_url or original_base_url
    try:
        if use_base_url != original_base_url:
            project.base_url = use_base_url
            project.save(update_fields=['base_url'])

        executor = TestExecutor(
            test_suite=suite,
            engine='playwright',
            browser='chrome',
            headless=True,
            executed_by=gen.created_by,
        )
        executor.run()
    finally:
        # 还原项目 base_url（不污染用户项目配置）
        if use_base_url != original_base_url:
            try:
                project.refresh_from_db()
                if (project.base_url or '').strip() == use_base_url:
                    project.base_url = original_base_url
                    project.save(update_fields=['base_url'])
            except Exception:
                pass

    suite.refresh_from_db()
    execution = executor.execution
    if execution:
        try:
            execution.refresh_from_db()
            gen.suite_execution = execution
            gen.suite_exec_status = (execution.status or '').lower()
            summary = (execution.result_data or {}).get('summary') or {}
            try:
                gen.suite_exec_pass_rate = float(summary.get('pass_rate', 0) or 0)
            except (TypeError, ValueError):
                gen.suite_exec_pass_rate = 0
        except Exception as ee:
            logger.warning(f"[case_script] 读取执行结果失败: {ee}")
    gen.suite_exec_status = gen.suite_exec_status or (suite.execution_status or '')
    _save(gen)
    return execution


def _run_generation(gen_id):
    """生成主流程（按 retry_limit 失败自动重试）。

    临时异常（浏览器/网络/LLM 超时）重试有效；结构性失败（用例无法定位/解析失败）
    多跑几次无害。重试前清理上次失败留下的中间产物，避免堆积重复脚本/套件。
    自动重试次数由 gen.retry_limit 控制（可配置，默认 1）。
    """
    close_old_connections()
    gen = UiScriptGeneration.objects.get(id=gen_id)
    limit = gen.retry_limit or 0
    max_attempts = 1 + limit
    for attempt in range(1, max_attempts + 1):
        close_old_connections()
        gen.refresh_from_db()
        if STOP_SIGNALS.get(gen_id):
            _log(gen, "⏹ 收到停止信号，终止生成")
            return
        if attempt > 1:
            gen.retry_count = (gen.retry_count or 0) + 1
            _save(gen)
            _log(gen, f"🔁 第 {attempt} 次尝试（失败自动重试 {gen.retry_count}/{limit}）")
        ok = _run_generation_once(gen)
        if ok or STOP_SIGNALS.get(gen_id):
            return
        if attempt < max_attempts:
            _log(gen, "🔁 本次失败，清理中间产物并自动重试...")
            _cleanup_previous(gen)
            gen.refresh_from_db()


def _run_generation_once(gen):
    """单次生成（返回 True=成功完成，False=失败需重试）。"""
    gen.status = 'running'
    gen.error_message = ''  # 新一轮尝试，清除上次的错误信息，避免误导
    _save(gen)
    test_case = None
    try:
        tc = TestCase.objects.get(id=gen.source_testcase_id)
        gen.source_testcase_title = tc.title
        _save(gen)

        # 1) 结构化
        _log(gen, "【1/4】分析用例步骤（LLM 拆解）...")
        steps = structurize_case(tc)
        _log(gen, f"      得到 {len(steps)} 个结构化步骤")

        # 2) 智能体抓元素
        _log(gen, "【2/4】智能体按用例在真实系统中抓取元素...")
        task = build_agent_task(steps, gen.base_url)
        history = run_agent(task, gen)
        captured = extract_elements(history)
        _log(gen, f"      智能体共交互 {len(captured)} 个去重元素")

        # 3) 落库 + 生成 UI 用例
        _log(gen, "【3/4】根据抓取到的元素生成 UI 用例并落库...")
        test_case, _element_ids = save_elements_and_testcase(gen, steps, captured, gen.base_url)
        _log(gen, f"      已生成 UI 用例 #{test_case.id}（{gen.steps_total} 步）")

        # 4) 回放自验证
        _log(gen, "【4/4】回放验证元素可用性...")
        try:
            passed, verifiable = asyncio.run(_verify_async(gen, test_case, gen.base_url))
            gen.steps_passed = passed
            _log(gen, f"      验证结果：通过 {passed}/{verifiable}（共 {gen.steps_total} 步）")
        except Exception as ve:
            logger.warning(f"[case_script] 回放验证异常: {ve}")
            _log(gen, f"      ⚠️ 回放验证异常（可能浏览器环境未就绪）：{ve}")
            gen.steps_passed = 0

        if not gen.generated_test_case:
            gen.status = 'failed'
        elif gen.steps_passed == 0 and gen.steps_total > 0:
            gen.status = 'partial'
        else:
            gen.status = 'passed'

        # 5) 自动建 UI 套件：把生成的用例纳入，便于在「套件管理」一键执行
        if gen.generated_test_case and test_case:
            try:
                suite = create_suite_for_generation(gen, test_case)
                _log(gen, f"      已自动创建套件 #{suite.id}（{suite.name}）")
                # 6) 建套件后立刻自动执行并回写结果（TestExecutor 默认走 UiTestCase 路径）
                _log(gen, "【5/6】自动执行套件（Playwright 真实回放）并回写结果...")
                execution = run_suite_execution(gen, suite)
                if execution:
                    _log(gen, f"      套件执行完成：状态={execution.status}，通过率={gen.suite_exec_pass_rate}%")
                else:
                    _log(gen, "      ⚠️ 套件执行未产生执行记录（可能浏览器环境未就绪）")
            except Exception as se:
                logger.warning(f"[case_script] 自动建/执行套件失败: {se}")
                _log(gen, f"      ⚠️ 自动建/执行套件失败：{se}")

        _log(gen, f"✅ 完成，状态：{gen.status}")
        return gen.status != 'failed' and gen.generated_test_case is not None
    except Exception as e:
        logger.exception("[case_script] 生成失败")
        gen.status = 'failed'
        gen.error_message = str(e)[:2000]
        _log(gen, f"❌ 失败：{e}")
        return False
    finally:
        _save(gen)
        close_old_connections()


def _cleanup_previous(gen):
    """重试前清理上次失败留下的中间产物（UI 用例 / 套件 / 元素），避免重复堆积。

    设计：
    - 删 TestCase（级联删 TestCaseStep）
    - 删 TestSuite 及其 TestSuiteTestCase 关联
    - Element 保留（跨用例共享；validation_status 会被下次运行覆盖）
    - 兼容旧 generated_script 字段：若存在则一并删除 TestScript
    """
    try:
        if gen.generated_test_case_id:
            from .models import TestCase as UiTestCase, TestSuiteTestCase
            # 先解除套件↔用例关联
            TestSuiteTestCase.objects.filter(test_case_id=gen.generated_test_case_id).delete()
            UiTestCase.objects.filter(id=gen.generated_test_case_id).delete()
            gen.generated_test_case = None
        if gen.generated_script_id:
            # 兼容：旧版产物若仍残留，删 TestScript（级联删 ScriptStep）
            TestScript.objects.filter(id=gen.generated_script_id).delete()
            gen.generated_script = None
        if gen.ui_suite_id:
            gen.ui_suite.delete()
            gen.ui_suite = None
        gen.steps_total = 0
        gen.steps_passed = 0
        gen.elements_captured = 0
        gen.suite_execution = None
        gen.suite_exec_status = ''
        gen.suite_exec_pass_rate = 0
        _save(gen)
    except Exception as ce:
        logger.warning(f"[case_script] 清理上次产物失败: {ce}")


def start_generation(gen_id):
    """在线程中启动生成任务（与现有 AI 执行一致，避免阻塞 web worker）。"""
    t = threading.Thread(target=_run_generation, args=(gen_id,), daemon=True)
    t.start()


def stop_generation(gen_id):
    STOP_SIGNALS[gen_id] = True


def retry_generation(gen_id):
    """手动重试：重置失败任务并单独跑一次（不触发进一步的自动重试）。

    用于列表/详情页「重试」按钮。无论 retry_limit 是多少，手动重试只跑一轮，
    失败即保持 failed，交给用户决定是否再次手动触发。
    """
    close_old_connections()
    gen = UiScriptGeneration.objects.get(id=gen_id)
    if STOP_SIGNALS.get(gen_id):
        return
    gen.retry_count = (gen.retry_count or 0) + 1
    _save(gen)
    _log(gen, f"🔁 手动重试（累计第 {gen.retry_count} 次）")
    _cleanup_previous(gen)
    gen.refresh_from_db()
    gen.error_message = ''
    _save(gen)
    _run_generation_once(gen)
