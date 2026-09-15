"""监控中心调度任务：被 Django-Q2 周期调用，真正执行探测。

由 apps/monitor/apps.py 在 ready() 中幂等注册的 Schedule
(name='monitor-sweep', schedule_type='I', minutes=1) 每 1 分钟触发一次本函数。
"""
import logging
from datetime import timedelta

from django.utils import timezone

from .models import MonitorTarget
from .utils.scheduler_heartbeat import set_scheduler_beat

logger = logging.getLogger(__name__)


def run_monitor_sweep():
    """遍历所有启用目标，对到点的目标执行一次探测。

    - 先写入调度器心跳（Redis 不可用则静默降级），供看板判断在线状态。
    - 每个目标按 should_run_now() 判断是否需要探测；run_check() 内部会
      更新 next_check_at / status / 连续失败计数，并触发告警分发。
    - 单个目标探测异常被隔离（try/except），不影响其余目标。
    返回本次实际触发探测的目标数量。
    """
    try:
        set_scheduler_beat()
    except Exception:
        pass

    ran = 0
    for target in MonitorTarget.objects.filter(enabled=True):
        try:
            if target.should_run_now():
                target.run_check()
                ran += 1
        except Exception as exc:  # 单个目标异常不阻断整轮扫描
            logger.exception('[monitor] 目标 %s 探测异常: %s', target.name, exc)

    logger.info('[monitor] sweep 完成, 本次触发探测 %s 个', ran)
    return ran
