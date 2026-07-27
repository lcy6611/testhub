# Generated manually to fix: nullable project -> non-nullable with existing NULL rows

from django.db import migrations, models
import django.db.models.deletion


def fill_null_project(apps, schema_editor):
    """将 AICase、AIExecutionRecord 中 project 为 NULL 的记录设为第一个 UiProject（若有）。"""
    UiProject = apps.get_model('ui_automation', 'UiProject')
    AICase = apps.get_model('ui_automation', 'AICase')
    AIExecutionRecord = apps.get_model('ui_automation', 'AIExecutionRecord')
    first_project = UiProject.objects.order_by('pk').first()
    if first_project:
        AICase.objects.filter(project__isnull=True).update(project=first_project)
        AIExecutionRecord.objects.filter(project__isnull=True).update(project=first_project)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0009_remove_aiexecutionrecord_ai_suite_and_more'),
    ]

    operations = [
        migrations.RunPython(fill_null_project, noop),
        migrations.AlterField(
            model_name='aicase',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ui_automation.uiproject', verbose_name='所属项目'),
        ),
        migrations.AlterField(
            model_name='aiexecutionrecord',
            name='project',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ui_automation.uiproject', verbose_name='所属项目'),
        ),
    ]
