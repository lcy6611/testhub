from django.db import models


class ScheduleBinding(models.Model):
    """模块定时任务 -> Django-Q2 Schedule 绑定关系（调度真相源在 Django-Q2，这里只做映射与展示）"""

    MODULE_CHOICES = [
        ('api_testing', '接口测试'),
        ('ui_automation', 'UI自动化'),
        ('app_automation', 'APP自动化'),
        ('performance_testing', '性能测试'),
    ]

    module = models.CharField(max_length=30, choices=MODULE_CHOICES, verbose_name='所属模块')
    module_task_id = models.BigIntegerField(verbose_name='模块任务ID')
    q_schedule_id = models.BigIntegerField(null=True, blank=True, verbose_name='Django-Q2 Schedule ID')
    enabled = models.BooleanField(default=False, verbose_name='是否已启用调度')
    last_sync_at = models.DateTimeField(auto_now=True, verbose_name='最后同步时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'scheduler_schedule_binding'
        unique_together = ('module', 'module_task_id')
        verbose_name = '调度绑定'
        verbose_name_plural = '调度绑定'

    def __str__(self):
        return f'{self.module}#{self.module_task_id} -> Q#{self.q_schedule_id}'
