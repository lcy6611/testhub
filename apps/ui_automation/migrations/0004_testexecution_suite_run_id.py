# Generated manually for suite run grouping

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0003_uinotificationlog_task_type_alter_aicase_project_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='testexecution',
            name='suite_run_id',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name='套件运行批次ID'),
        ),
    ]
