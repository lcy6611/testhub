# Generated manually: AI 套件、定时任务、通知日志

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ui_automation', '0005_aiexecutionrecord_performance_history'),
    ]

    operations = [
        migrations.CreateModel(
            name='AISuite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='套件名称')),
                ('description', models.TextField(blank=True, verbose_name='套件描述')),
                ('execution_status', models.CharField(
                    choices=[('not_run', '未执行'), ('passed', '通过'), ('failed', '失败'), ('running', '执行中')],
                    default='not_run', max_length=20, verbose_name='执行状态')),
                ('passed_count', models.IntegerField(default=0, verbose_name='通过数')),
                ('failed_count', models.IntegerField(default=0, verbose_name='失败数')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='创建者')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_suites', to='ui_automation.uiproject', verbose_name='所属项目')),
            ],
            options={
                'verbose_name': 'AI测试套件',
                'verbose_name_plural': 'AI测试套件',
                'db_table': 'ui_ai_suites',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AISuiteCase',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(default=0, verbose_name='执行顺序')),
                ('ai_case', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ui_automation.aicase', verbose_name='AI用例')),
                ('ai_suite', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='suite_cases', to='ui_automation.aisuite', verbose_name='AI套件')),
            ],
            options={
                'verbose_name': 'AI套件用例关联',
                'verbose_name_plural': 'AI套件用例关联',
                'db_table': 'ui_ai_suite_cases',
                'ordering': ['order'],
                'unique_together': {('ai_suite', 'ai_case')},
            },
        ),
        migrations.CreateModel(
            name='AIScheduledTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='任务名称')),
                ('task_type', models.CharField(choices=[('AI_SUITE', 'AI套件执行'), ('AI_CASE', 'AI用例执行')], max_length=20, verbose_name='任务类型')),
                ('trigger_type', models.CharField(choices=[('CRON', 'Cron表达式'), ('INTERVAL', '间隔执行'), ('ONCE', '单次执行')], default='CRON', max_length=20, verbose_name='触发类型')),
                ('cron_expression', models.CharField(blank=True, max_length=100, verbose_name='Cron表达式')),
                ('interval_seconds', models.IntegerField(blank=True, null=True, verbose_name='间隔秒数')),
                ('execute_at', models.DateTimeField(blank=True, null=True, verbose_name='单次执行时间')),
                ('execution_mode', models.CharField(default='text', max_length=20, verbose_name='执行模式')),
                ('headless', models.BooleanField(default=False, verbose_name='无头模式')),
                ('notify_on_success', models.BooleanField(default=False, verbose_name='成功时通知')),
                ('notify_on_failure', models.BooleanField(default=False, verbose_name='失败时通知')),
                ('notification_type', models.CharField(blank=True, max_length=20, verbose_name='通知类型')),
                ('notify_emails', models.JSONField(blank=True, default=list, verbose_name='通知邮箱列表')),
                ('status', models.CharField(choices=[('ACTIVE', '启用'), ('PAUSED', '暂停'), ('DISABLED', '禁用')], default='ACTIVE', max_length=20, verbose_name='任务状态')),
                ('last_run_time', models.DateTimeField(blank=True, null=True, verbose_name='最后运行时间')),
                ('next_run_time', models.DateTimeField(blank=True, null=True, verbose_name='下次运行时间')),
                ('total_runs', models.IntegerField(default=0, verbose_name='总运行次数')),
                ('successful_runs', models.IntegerField(default=0, verbose_name='成功运行次数')),
                ('failed_runs', models.IntegerField(default=0, verbose_name='失败运行次数')),
                ('last_result', models.JSONField(default=dict, verbose_name='最后执行结果')),
                ('error_message', models.TextField(blank=True, verbose_name='错误信息')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('ai_case', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='scheduled_tasks', to='ui_automation.aicase', verbose_name='AI用例')),
                ('ai_suite', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='scheduled_tasks', to='ui_automation.aisuite', verbose_name='AI套件')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='创建者')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ui_automation.uiproject', verbose_name='关联项目')),
            ],
            options={
                'verbose_name': 'AI定时任务',
                'verbose_name_plural': 'AI定时任务',
                'db_table': 'ui_ai_scheduled_tasks',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='AiNotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_name', models.CharField(max_length=200, verbose_name='任务名称')),
                ('task_type', models.CharField(blank=True, max_length=20, null=True, verbose_name='任务类型快照')),
                ('notification_type', models.CharField(
                    choices=[('task_execution', '定时任务执行'), ('suite_execution', '套件执行'), ('case_execution', '用例执行'), ('manual', '手动通知')],
                    max_length=50, verbose_name='通知类型')),
                ('sender_name', models.CharField(max_length=100, verbose_name='发件人姓名')),
                ('sender_email', models.EmailField(max_length=254, verbose_name='发件人邮箱')),
                ('recipient_info', models.JSONField(verbose_name='收件人信息')),
                ('webhook_bot_info', models.JSONField(blank=True, default=dict, null=True, verbose_name='Webhook机器人信息')),
                ('notification_content', models.TextField(verbose_name='通知内容')),
                ('status', models.CharField(
                    choices=[('pending', '待发送'), ('sending', '发送中'), ('success', '发送成功'), ('failed', '发送失败'), ('cancelled', '已取消')],
                    default='pending', max_length=20, verbose_name='发送状态')),
                ('error_message', models.TextField(blank=True, null=True, verbose_name='错误信息')),
                ('response_info', models.JSONField(blank=True, default=dict, null=True, verbose_name='响应信息')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('task', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_logs', to='ui_automation.aischeduledtask', verbose_name='关联AI任务')),
            ],
            options={
                'verbose_name': 'AI通知日志',
                'verbose_name_plural': 'AI通知日志',
                'db_table': 'ui_ai_notification_logs',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterField(
            model_name='aiexecutionrecord',
            name='status',
            field=models.CharField(
                choices=[('pending', '等待中'), ('running', '执行中'), ('passed', '成功'), ('failed', '失败'), ('stopped', '已停止')],
                default='pending', max_length=20, verbose_name='执行状态'),
        ),
    ]
