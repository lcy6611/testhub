import logging

logger = logging.getLogger(__name__)


def dispatch(module, task_id):
    """Django-Q2 调度的统一入口：根据 module 调用对应模块的执行器。

    该函数被写入 Django-Q2 Schedule.func，由 Q 集群在到点时调用。
    """
    from apps.scheduler.registry import get_handler

    handler = get_handler(module)
    if not handler:
        logger.error(f'[scheduler] 未知调度模块: {module}，任务 {task_id} 被忽略')
        return

    logger.info(f'[scheduler] 触发 {module} 模块任务 #{task_id}')
    try:
        handler['execute'](task_id)
    except Exception as exc:
        logger.exception(f'[scheduler] 执行 {module}#{task_id} 失败: {exc}')
        # 抛出异常，让 Django-Q2 触发重试机制
        raise
