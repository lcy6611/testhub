from django.apps import AppConfig


class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.scheduler'
    label = 'scheduler'
    verbose_name = '统一调度中心'

    def ready(self):
        # 注册各模块执行器
        from apps.scheduler.registry import register_builtin
        register_builtin()
        # 连接各模块定时任务 -> Django-Q2 的同步信号
        from apps.scheduler import signals
        signals.connect_all()
