from django.apps import AppConfig
from datetime import timedelta

from django.utils import timezone


class MonitorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.monitor'
    verbose_name = '监控中心'

    def ready(self):
        # 幂等创建 Django-Q2 周期任务：每 1 分钟扫描一次监控目标并执行到点探测。
        # 与平台统一调度中心（Q 集群 'testhub'）集成，不使用 celery。
        # 若此时 Schedule 表尚未创建（如 migrate 之前），try/except 兜底忽略，
        # 待下次进程启动（表已存在）时自动补建。
        from django_q.models import Schedule

        try:
            if not Schedule.objects.filter(name='monitor-sweep').exists():
                Schedule.objects.create(
                    name='monitor-sweep',
                    func='apps.monitor.tasks.run_monitor_sweep',
                    args='()',
                    kwargs='{}',
                    schedule_type='I',   # I = 间隔（interval）
                    minutes=1,
                    repeats=-1,          # -1 = 无限重复
                    cluster='testhub',   # 须与 settings.Q_CLUSTER['name'] 一致
                    next_run=timezone.now() - timedelta(seconds=5),  # 立即被接管
                )
        except Exception:
            pass
