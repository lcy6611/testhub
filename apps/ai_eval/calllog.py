# -*- coding: utf-8 -*-
"""
AI 调用成本/用量记录（best-effort，不阻塞主流程）。

设计要点：
- 在异步上下文里直接写 Django ORM 会触发 SynchronousOnlyOperation，因此统一用
  daemon 线程做落库，主流程（LLM 调用）零阻塞、零风险。
- 任何异常都被吞掉：ai_eval 未迁移 / 表不存在 / 连接抖动 都不影响业务 AI 调用。
- 成本仅按模型名做粗粒度估算（元），价格表可后续在后台调整；tokens 始终精确记录。
"""
import threading
import logging

logger = logging.getLogger(__name__)

# 价格表：按 model_name 子串匹配，单位 元/1K tokens (输入, 输出)
# 仅为估算口径，非计费依据。
PRICING = [
    ("deepseek", 0.001, 0.002),
    ("qwen", 0.003, 0.006),
    ("qwq", 0.003, 0.006),
    ("glm", 0.005, 0.005),
    ("gpt-4", 0.03, 0.06),
    ("gpt-3.5", 0.0015, 0.002),
    ("claude", 0.03, 0.09),
    ("gemini", 0.01, 0.03),
]
DEFAULT_PRICE = (0.002, 0.004)


def estimate_cost(model_name, input_tokens, output_tokens):
    """按模型名粗估成本（元）。"""
    mn = (model_name or "").lower()
    pin, pout = DEFAULT_PRICE
    for key, pi, po in PRICING:
        if key in mn:
            pin, pout = pi, po
            break
    return round((input_tokens or 0) / 1000.0 * pin + (output_tokens or 0) / 1000.0 * pout, 6)


def record_ai_call(*, module, feature="", provider="", model_name="", model_config_id=None,
                    prompt_version_id=None, prompt_key="", project_id=None, user_id=None,
                    input_tokens=0, output_tokens=0, total_tokens=0,
                    status="success", error="", latency_ms=None):
    """线程安全地落一条 AI 调用记录。所有异常被吞掉。"""
    def _do():
        try:
            from .models import AICallLog
            cost = estimate_cost(model_name, input_tokens, output_tokens)
            AICallLog.objects.create(
                module=module,
                feature=feature or "",
                provider=provider or "",
                model_name=model_name or "",
                model_config_id=model_config_id,
                prompt_version_id=prompt_version_id,
                prompt_key=prompt_key or "",
                project_id=project_id,
                user_id=user_id,
                input_tokens=int(input_tokens or 0),
                output_tokens=int(output_tokens or 0),
                total_tokens=int(total_tokens or 0),
                cost=cost,
                latency_ms=latency_ms,
                status=status or "success",
                error=(error or "")[:1000],
            )
        except Exception as exc:  # pragma: no cover - 防御性
            logger.debug("ai_eval record_ai_call skipped: %s", exc)

    threading.Thread(target=_do, daemon=True).start()
