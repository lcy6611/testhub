# -*- coding: utf-8 -*-
"""通用步骤重试原语。

设计目标：
- 复用 tenacity 的退避/重试语义（项目已在 venv / 后端镜像中安装 tenacity）。
- 每次失败尝试都通过 ``RetryAttempt`` 落库，方便复盘「重试是否生效」「自愈前后对比」。
- 默认只在「瞬时类异常」（网络/超时/连接）上重试，断言失败、鉴权失败等确定性错误不重试。
- 既可当函数式 API（run_with_retry）使用，也可取 tenacity 装饰器（retry_decorator）。

调用方示例::

    from apps.execution_common.retry import run_with_retry
    result, attempts = run_with_retry(
        play_step, chain='UI', execution_id=str(suite_exec.id), step_key=str(step.id),
        max_attempts=3, wait_base=1.0,
        selector=element.get_all_locators(),  # 透传给 fn 的关键字参数
    )
"""
import time
import logging

from tenacity import (
    retry as tenacity_retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .models import RetryAttempt, FailureCategory

logger = logging.getLogger('django')

# 默认重试的「瞬时类」异常集合（不含断言/鉴权等确定性错误）。
DEFAULT_RETRY_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    # socket 超时等标准库异常
    TimeoutError,
)


def _coerce_category(cat):
    if cat is None:
        return FailureCategory.UNKNOWN.value
    return cat.value if hasattr(cat, 'value') else str(cat)


def _make_record(chain, execution_id, step_key, attempt_no, category, exc, record_fn):
    rec = RetryAttempt(
        chain=chain,
        execution_id=execution_id,
        step_key=step_key,
        attempt_no=attempt_no,
        trigger_category=_coerce_category(category),
        success=False,
        error_message=(str(exc)[:2000] if exc is not None else ''),
    )
    if record_fn is not None:
        record_fn(rec)
    else:
        rec.save()
    return rec


def run_with_retry(
    fn,
    *,
    chain,
    execution_id,
    step_key='',
    max_attempts=3,
    wait_base=1.0,
    retry_on=None,
    classify_fn=None,
    record_fn=None,
    **fn_kwargs,
):
    """运行 ``fn`` 并在瞬时异常上指数退避重试，每次失败落 ``RetryAttempt``。

    :param fn: 可调用对象（通常是单步执行函数）。
    :param chain: ChainType 值（'UI' / 'API' / 'APP' ...）。
    :param execution_id: 执行标识字符串。
    :param step_key: 步骤标识（可为空）。
    :param max_attempts: 最大尝试次数（含首次），>=1。
    :param wait_base: 指数退避基数（秒）。
    :param retry_on: 仅在这些异常类型上重试；为 None 时用 DEFAULT_RETRY_EXCEPTIONS。
    :param classify_fn: (exc, chain, context) -> FailureCategory 的可选覆盖。
    :param record_fn: (RetryAttempt) -> None 的可选落库钩子（默认 rec.save()）。
    :param fn_kwargs: 透传给 fn 的关键字参数（如 selector / request / device 等）。
    :return: (result, attempts list of RetryAttempt)
    :raises: 耗尽重试仍失败则抛出最后一次异常；遇到非重试类异常立即抛出。
    """
    from .diagnosis import classify_failure  # 延迟导入，避免循环依赖

    classify = classify_fn or classify_failure
    retry_types = retry_on if retry_on is not None else DEFAULT_RETRY_EXCEPTIONS
    attempts = []
    max_attempts = max(int(max_attempts), 1)

    for attempt_no in range(1, max_attempts + 1):
        try:
            return fn(**fn_kwargs), attempts
        except retry_types as exc:
            category, _hint = classify(exc, chain=chain, context={'step_key': step_key})
            attempts.append(_make_record(chain, execution_id, step_key, attempt_no, category, exc, record_fn))
            logger.info('[retry] %s/%s attempt#%d/%d failed category=%s: %s',
                        chain, execution_id, attempt_no, max_attempts, category, str(exc)[:200])
            if attempt_no < max_attempts:
                time.sleep(wait_base * (2 ** (attempt_no - 1)))
        except Exception as exc:  # 非重试类异常：记录并立即上抛
            category, _hint = classify(exc, chain=chain, context={'step_key': step_key})
            attempts.append(_make_record(chain, execution_id, step_key, attempt_no, category, exc, record_fn))
            raise

    # 重试耗尽：抛出最后一次瞬时异常
    last = attempts[-1].error_message if attempts else 'retry exhausted'
    logger.warning('[retry] %s/%s exhausted after %d attempts', chain, execution_id, max_attempts)
    raise RuntimeError(f'retry exhausted ({max_attempts} attempts): {last}')


def retry_decorator(max_attempts=3, wait_base=1.0, retry_on=None):
    """返回一个 tenacity.retry 装饰器，便于在无状态、无需落库记录的函数上直接使用。

    注意：此装饰器仅负责退避/重试，不会写 RetryAttempt；需要落库请用 run_with_retry。
    """
    retry_types = retry_on if retry_on is not None else DEFAULT_RETRY_EXCEPTIONS
    return tenacity_retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=wait_base, min=wait_base, max=wait_base * 8),
        retry=retry_if_exception_type(retry_types),
        reraise=True,
    )
