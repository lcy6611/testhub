# Generated manually: AI 执行记录增加套件运行字段

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ui_automation", "0006_ai_suite_scheduled_notification"),
    ]

    operations = [
        migrations.AddField(
            model_name="aiexecutionrecord",
            name="ai_suite",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="ui_automation.aisuite",
                verbose_name="关联AI套件",
            ),
        ),
        migrations.AddField(
            model_name="aiexecutionrecord",
            name="suite_run_id",
            field=models.CharField(
                blank=True,
                max_length=64,
                null=True,
                verbose_name="套件运行ID",
            ),
        ),
    ]

