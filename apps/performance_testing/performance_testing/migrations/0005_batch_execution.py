# -*- coding: utf-8 -*-
"""批量执行模型。"""

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0003_projectmapping"),
        ("performance_testing", "0004_performanceconfig"),
    ]

    operations = [
        migrations.CreateModel(
            name="PerformanceBatchExecution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("batch_id", models.CharField(max_length=50, unique=True, verbose_name="批次ID")),
                ("name", models.CharField(max_length=200, verbose_name="批次名称")),
                ("status", models.CharField(
                    max_length=16, choices=[
                        ("QUEUED", "排队中"), ("RUNNING", "执行中"),
                        ("COMPLETED", "已完成"), ("FAILED", "失败"), ("PARTIAL", "部分完成"),
                    ], default="QUEUED", verbose_name="状态")),
                ("total_scripts", models.PositiveIntegerField(default=0, verbose_name="脚本总数")),
                ("completed_scripts", models.PositiveIntegerField(default=0, verbose_name="已完成数")),
                ("failed_scripts", models.PositiveIntegerField(default=0, verbose_name="失败数")),
                ("thread_count", models.PositiveIntegerField(default=10, verbose_name="线程数")),
                ("ramp_up", models.PositiveIntegerField(default=5, verbose_name="Ramp-Up(秒)")),
                ("duration", models.PositiveIntegerField(default=60, verbose_name="持续时间(秒)")),
                ("realtime_enabled", models.BooleanField(default=False, verbose_name="启用实时报告")),
                ("error_message", models.TextField(blank=True, default="", verbose_name="错误信息")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("completed_at", models.DateTimeField(blank=True, null=True, verbose_name="完成时间")),
                ("project", models.ForeignKey(
                    blank=True, null=True, on_delete=models.SET_NULL,
                    related_name="performance_batches",
                    to="projects.project", verbose_name="关联项目")),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=models.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="创建者")),
            ],
            options={
                "verbose_name": "性能批量执行",
                "verbose_name_plural": "性能批量执行",
                "ordering": ["-created_at"],
                "db_table": "perf_batch_execution",
            },
        ),
        migrations.AddField(
            model_name="performanceexecution",
            name="batch",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=models.CASCADE,
                related_name="executions",
                to="performance_testing.performancebatchexecution", verbose_name="所属批次"),
        ),
    ]
