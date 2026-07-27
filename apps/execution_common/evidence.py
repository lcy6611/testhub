# -*- coding: utf-8 -*-
"""证据采集助手。

证据层只负责「把一次采集结果存成 ExecutionEvidence 记录」。真正的采集动作
（如 Playwright 截图、requests 抓取请求响应、Appium 录屏）由调用方完成，
本模块提供统一的落库入口与常用便捷封装，保证三端证据结构一致、可关联回溯。
"""
import logging

from .models import ExecutionEvidence, ChainType

logger = logging.getLogger('django')


def record_evidence(*, chain, execution_id, evidence_type, payload=None, step_key='', record_fn=None):
    """写入一条证据记录。

    :param chain: ChainType 值。
    :param execution_id: 执行标识。
    :param evidence_type: ExecutionEvidence.EVIDENCE_TYPE_CHOICES 之一。
    :param payload: 任意可 JSON 序列化的证据内容。
    :param step_key: 步骤标识。
    :param record_fn: 可选落库钩子（默认 rec.save()）。
    :return: ExecutionEvidence 实例
    """
    ev = ExecutionEvidence(
        chain=chain,
        execution_id=str(execution_id),
        step_key=step_key or '',
        evidence_type=evidence_type,
        payload=payload or {},
    )
    if record_fn is not None:
        record_fn(ev)
    else:
        ev.save()
    return ev


def capture_screenshot(*, chain, execution_id, path, step_key='', extra=None, record_fn=None):
    """记录一张截图证据（截图文件由调用方先行生成，这里只存路径与元信息）。"""
    payload = {'path': path}
    if extra:
        payload.update(extra)
    return record_evidence(
        chain=chain, execution_id=execution_id,
        evidence_type='SCREENSHOT', payload=payload, step_key=step_key, record_fn=record_fn,
    )


def capture_request_response(*, chain, execution_id, request=None, response=None, step_key='', record_fn=None):
    """记录一次请求/响应证据（来自 requests 等 HTTP 客户端）。

    仅保留对诊断有价值的子集（URL / 方法 / 状态码 / 头部摘要 / 正文片段），避免大体积入库。
    """
    payload = {}
    if request is not None:
        payload['request'] = {
            'method': getattr(request, 'method', None),
            'url': getattr(request, 'url', None),
        }
        hdrs = getattr(request, 'headers', None)
        if hdrs:
            payload['request']['headers'] = {k: (v if k.lower() not in ('authorization', 'cookie') else '***')
                                             for k, v in (dict(hdrs).items() if hasattr(hdrs, 'items') else [])}
    if response is not None:
        payload['response'] = {
            'status_code': getattr(response, 'status_code', None),
            'reason': getattr(response, 'reason', None),
        }
        hdrs = getattr(response, 'headers', None)
        if hdrs:
            payload['response']['headers'] = {k: v for k, v in (dict(hdrs).items() if hasattr(hdrs, 'items') else [])}
        try:
            body = response.text if hasattr(response, 'text') else None
        except Exception:
            body = None
        if body:
            payload['response']['body_snippet'] = body[:2000]
    return record_evidence(
        chain=chain, execution_id=execution_id,
        evidence_type='REQUEST_RESPONSE', payload=payload, step_key=step_key, record_fn=record_fn,
    )


def capture_log(*, chain, execution_id, text, step_key='', record_fn=None):
    """记录一段日志证据（截断到 8000 字符，避免超长）。"""
    return record_evidence(
        chain=chain, execution_id=execution_id,
        evidence_type='LOG', payload={'text': (text or '')[-8000:]}, step_key=step_key, record_fn=record_fn,
    )
