import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django_q.models import Schedule

logger = logging.getLogger(__name__)

# 所有调度统一走同一个入口函数
Q_FUNC = 'apps.scheduler.tasks.dispatch'

# 当前 Q 集群名称（须与 settings.Q_CLUSTER['name'] 一致，调度器按此过滤 Schedule）
Q_CLUSTER_NAME = settings.Q_CLUSTER.get('name', 'testhub')


def _schedule_spec(task):
    """把模块任务转换为 Django-Q2 Schedule 的字段字典；无效返回 None。"""
    trigger = (getattr(task, 'trigger_type', '') or '').upper()
    if trigger == 'CRON':
        if not getattr(task, 'cron_expression', ''):
            return None
        return {'schedule_type': 'C', 'cron': task.cron_expression}
    if trigger == 'INTERVAL':
        secs = int(getattr(task, 'interval_seconds', 0) or 0)
        if secs <= 0:
            return None
        # Django-Q2 间隔最小单位为分钟
        minutes = max(1, secs // 60)
        return {'schedule_type': 'I', 'minutes': minutes}
    if trigger == 'ONCE':
        dt = getattr(task, 'execute_at', None) or (timezone.now() + timedelta(minutes=1))
        return {'schedule_type': 'O', 'next_run': dt}
    return None


def ensure_schedule(module, task):
    """根据模块任务创建/更新 Django-Q2 Schedule；返回 ScheduleBinding。"""
    from apps.scheduler.models import ScheduleBinding

    spec = _schedule_spec(task)
    if not spec:
        logger.warning(f'[scheduler] 任务 {module}#{task.id} 无有效触发器，跳过注册')
        return None

    binding, _ = ScheduleBinding.objects.get_or_create(module=module, module_task_id=task.id)
    q = Schedule.objects.filter(id=binding.q_schedule_id).first() if binding.q_schedule_id else None
    if q is None:
        q = Schedule(func=Q_FUNC)

    q.func = Q_FUNC
    # Django-Q2 要求 args/kwargs 为 Python 字面量字符串，且多参数必须是「元组」字面量，
    # 否则调度器 ast.literal_eval 后会被整体包成单个参数。
    q.args = str((module, task.id))
    q.kwargs = "{}"
    q.cluster = Q_CLUSTER_NAME
    q.schedule_type = spec['schedule_type']
    q.cron = spec.get('cron', '')
    q.minutes = spec.get('minutes', 0)
    # 调度器只认 next_run < now 的 Schedule；非一次性任务设为稍早于现在，立即被接管
    if spec['schedule_type'] == 'O':
        q.next_run = spec.get('next_run')
    else:
        q.next_run = timezone.now() - timedelta(seconds=5)
    q.repeats = -1  # -1 = 无限重复
    q.save()

    binding.q_schedule_id = q.id
    binding.enabled = True
    binding.save()
    logger.info(f'[scheduler] 已注册/更新 Q Schedule #{q.id} -> {module}#{task.id} (type={q.schedule_type})')
    return binding


def disable_schedule(module, task_id):
    """停用/删除模块的 Django-Q2 Schedule。"""
    from apps.scheduler.models import ScheduleBinding

    binding = ScheduleBinding.objects.filter(module=module, module_task_id=task_id).first()
    if not binding:
        return
    if binding.q_schedule_id:
        Schedule.objects.filter(id=binding.q_schedule_id).delete()
    binding.q_schedule_id = None
    binding.enabled = False
    binding.save()
    logger.info(f'[scheduler] 已停用 Q Schedule -> {module}#{task_id}')


def sync_schedule(module, task):
    """ACTIVE 注册；其它状态（PAUSED/COMPLETED/FAILED）停用。"""
    if getattr(task, 'status', None) == 'ACTIVE':
        return ensure_schedule(module, task)
    return disable_schedule(module, task.id)
