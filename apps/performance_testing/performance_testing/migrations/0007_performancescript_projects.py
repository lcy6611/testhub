# Generated manually for performance_testing

from django.db import migrations, models


def _migrate_project_fk_to_m2m(apps, schema_editor):
    """将旧 project 外键迁移到 projects 多对多关系。"""
    PerformanceScript = apps.get_model("performance_testing", "PerformanceScript")
    for script in PerformanceScript.objects.exclude(project_id=None):
        script.projects.add(script.project_id)


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("performance_testing", "0006_batch_report_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="performancescript",
            name="projects",
            field=models.ManyToManyField(
                blank=True,
                related_name="performance_scripts",
                to="projects.project",
                verbose_name="关联项目",
            ),
        ),
        migrations.RunPython(_migrate_project_fk_to_m2m, _noop),
        migrations.RemoveField(
            model_name="performancescript",
            name="project",
        ),
    ]
