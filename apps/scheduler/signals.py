import logging

from django.db.models.signals import post_delete, post_save

logger = logging.getLogger(__name__)

_CONNECTED = False

# 需要调整调度配置的字段（统计字段变化不应触发重新同步）
_SCHEDULE_FIELDS = ('status', 'trigger_type', 'cron_expression', 'interval_seconds', 'execute_at')


def _api_testing_sync(sender, instance, **kwargs):
    from apps.api_testing.models import ScheduledTask
    from apps.scheduler.adapter import sync_schedule

    if kwargs.get('created', False):
        sync_schedule('api_testing', instance)
        return

    try:
        old = ScheduledTask.objects.get(pk=instance.pk)
    except ScheduledTask.DoesNotExist:
        return

    changed = any(getattr(old, f) != getattr(instance, f) for f in _SCHEDULE_FIELDS)
    if changed:
        sync_schedule('api_testing', instance)


def _api_testing_delete(sender, instance, **kwargs):
    from apps.scheduler.adapter import disable_schedule
    disable_schedule('api_testing', instance.id)


def connect_all():
    """连接各模块定时任务的同步信号（幂等）。"""
    global _CONNECTED
    if _CONNECTED:
        return
    from apps.api_testing.models import ScheduledTask

    post_save.connect(_api_testing_sync, sender=ScheduledTask, dispatch_uid='sched_api_testing')
    post_delete.connect(_api_testing_delete, sender=ScheduledTask, dispatch_uid='sched_api_testing_del')
    _CONNECTED = True
