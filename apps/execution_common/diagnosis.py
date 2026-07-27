# -*- coding: utf-8 -*-
"""失败诊断：规则优先 + 可插拔 LLM 增强。

分类策略：
1. 规则优先（零成本、可离线）：根据异常类型名 + 异常消息关键字映射到 FailureCategory。
2. LLM 增强（可选）：调用方可在拿到规则分类后，自行用 ui_automation.ai_failure_hint
   生成面向用户的中文提示；本模块保持对具体 LLM 实现的零依赖，便于三端通用。
"""
import logging

from .models import FailureCategory

logger = logging.getLogger('django')


# (匹配串(小写, 出现在异常类型名或消息中), 分类, 提示)
_RULES = [
    ('timeout', FailureCategory.TIMEOUT, '执行超时，可能是页面加载慢或后端响应慢'),
    ('timed out', FailureCategory.TIMEOUT, '执行超时，可能是页面加载慢或后端响应慢'),
    ('network', FailureCategory.NETWORK_TIMEOUT, '网络层超时，请检查网络与服务可达性'),
    ('connection', FailureCategory.CONNECTION_ERROR, '连接失败，请检查服务地址、端口与网络'),
    ('refused', FailureCategory.CONNECTION_ERROR, '连接被拒绝，目标服务可能未启动'),
    ('reset by peer', FailureCategory.CONNECTION_ERROR, '连接被对端重置'),
    ('enotfound', FailureCategory.CONNECTION_ERROR, '域名或地址无法解析'),
    ('dns', FailureCategory.CONNECTION_ERROR, 'DNS 解析失败'),
    ('401', FailureCategory.AUTH_ERROR, '鉴权失败（401），请检查 token / 账号密码'),
    ('403', FailureCategory.AUTH_ERROR, '无权限（403），请检查账号授权'),
    ('unauthorized', FailureCategory.AUTH_ERROR, '鉴权失败，请检查凭证'),
    ('forbidden', FailureCategory.AUTH_ERROR, '无权限，请检查授权'),
    ('404', FailureCategory.HTTP_4XX, '资源不存在（404）'),
    ('400', FailureCategory.HTTP_4XX, '请求参数错误（400）'),
    ('409', FailureCategory.HTTP_4XX, '资源冲突（409）'),
    ('4', FailureCategory.HTTP_4XX, '客户端错误（4xx）'),
    ('500', FailureCategory.HTTP_5XX, '服务端内部错误（500）'),
    ('502', FailureCategory.HTTP_5XX, '网关错误（502）'),
    ('503', FailureCategory.HTTP_5XX, '服务不可用（503）'),
    ('504', FailureCategory.HTTP_5XX, '网关超时（504）'),
    ('5', FailureCategory.HTTP_5XX, '服务端错误（5xx）'),
    ('assert', FailureCategory.ASSERTION_ERROR, '断言失败，实际结果与预期不符'),
    ('expect', FailureCategory.ASSERTION_ERROR, '断言失败，实际结果与预期不符'),
    ('locator', FailureCategory.LOCATOR_NOT_FOUND, '定位器未找到，元素选择器可能已变化'),
    ('selector', FailureCategory.LOCATOR_NOT_FOUND, '选择器未找到，请检查元素定位表达式'),
    ('no element', FailureCategory.ELEMENT_NOT_FOUND, '未找到目标元素'),
    ('element is not', FailureCategory.ELEMENT_NOT_INTERACTABLE, '元素不可交互（被遮挡/未可见/禁用）'),
    ('not visible', FailureCategory.ELEMENT_NOT_INTERACTABLE, '元素不可见，无法操作'),
    ('not clickable', FailureCategory.ELEMENT_NOT_INTERACTABLE, '元素不可点击（可能被遮挡）'),
    ('intercept', FailureCategory.ELEMENT_NOT_INTERACTABLE, '元素被其它元素遮挡，无法交互'),
    ('device offline', FailureCategory.DEVICE_OFFLINE, '设备离线，请检查设备连接'),
    ('device not found', FailureCategory.DEVICE_OFFLINE, '未找到设备'),
    ('adb', FailureCategory.DEVICE_OFFLINE, 'ADB 连接异常，请检查设备/模拟器'),
    ('crash', FailureCategory.APP_CRASH, '应用崩溃，请查看崩溃日志'),
    ('anr', FailureCategory.APP_CRASH, '应用无响应（ANR）'),
]


# 常见异常的「类型名」直接映射（无需扫消息）
_TYPE_MAP = {
    'TimeoutError': FailureCategory.TIMEOUT,
    'asyncio.TimeoutError': FailureCategory.TIMEOUT,
    'ConnectionError': FailureCategory.CONNECTION_ERROR,
    'ConnectionResetError': FailureCategory.CONNECTION_ERROR,
    'AssertionError': FailureCategory.ASSERTION_ERROR,
    'TimeoutException': FailureCategory.TIMEOUT,  # Selenium/Playwright 风格
    'PlaywrightTimeoutError': FailureCategory.TIMEOUT,
}


def classify_failure(exc, chain=None, context=None):
    """根据异常对象推断失败分类与提示。

    :param exc: 异常实例（任意类型）。
    :param chain: 可选链路类型，用于未来按链路微调提示。
    :param context: 可选上下文字典（透传，便于 LLM 增强）。
    :return: (FailureCategory, hint:str)
    """
    if exc is None:
        return FailureCategory.UNKNOWN, '未知错误'

    type_name = exc.__class__.__name__
    module = getattr(exc.__class__, '__module__', '') or ''
    full_type = f'{module}.{type_name}'
    message = (str(exc) or '').lower()

    # 1) 精确类型名匹配
    if type_name in _TYPE_MAP:
        cat = _TYPE_MAP[type_name]
        hint = _rule_hint(cat)
        return cat, hint
    if full_type in _TYPE_MAP:
        cat = _TYPE_MAP[full_type]
        return cat, _rule_hint(cat)

    # 2) 规则关键字扫描（异常类型名 + 消息）
    for needle, cat, hint in _RULES:
        if needle in message or needle in type_name.lower():
            return cat, hint

    # 3) 兜底
    return FailureCategory.UNKNOWN, '未知错误，请查看执行日志'


def classify_from_message(message, chain=None, context=None):
    """仅根据一段文本（如从执行日志解析出的失败描述）推断分类。

    用于没有异常对象、只有日志文本的场景（如 APP 自动化回传的字符串结论）。
    """
    if not message:
        return FailureCategory.UNKNOWN, '未知错误'
    text = message.lower()
    for needle, cat, hint in _RULES:
        if needle in text:
            return cat, hint
    return FailureCategory.UNKNOWN, '未知错误，请查看执行日志'


def _rule_hint(cat):
    for _n, c, h in _RULES:
        if c == cat:
            return h
    return '未知错误，请查看执行日志'


def build_failure_summary(category, hint, chain=None, context=None):
    """组合一条结构化失败摘要（供序列化器 / 前端展示）。"""
    return {
        'category': category.value if hasattr(category, 'value') else str(category),
        'category_label': getattr(category, 'label', str(category)),
        'hint': hint,
        'chain': chain,
    }
