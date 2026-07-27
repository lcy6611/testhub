# Generated manually for adding performance metrics and execution history fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0004_testexecution_suite_run_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiexecutionrecord',
            name='performance_metrics',
            field=models.JSONField(default=dict, help_text='存储任务执行的性能数据，如各步骤耗时等', verbose_name='性能指标'),
        ),
        migrations.AddField(
            model_name='aiexecutionrecord',
            name='execution_history',
            field=models.JSONField(default=list, help_text='存储详细的执行历史，用于知识积累和复用', verbose_name='执行历史'),
        ),
        migrations.AddField(
            model_name='aiexecutionrecord',
            name='model_info',
            field=models.JSONField(default=dict, help_text='存储使用的模型配置信息', verbose_name='模型信息'),
        ),
    ]
