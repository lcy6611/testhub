from django.db import migrations, models
import django.db.models.deletion


def forward_fill_project(apps, schema_editor):
    ApiRequest = apps.get_model('api_testing', 'ApiRequest')
    # 通过 collection.project 回填 project
    for req in ApiRequest.objects.filter(project__isnull=True, collection__isnull=False).select_related('collection__project'):
        try:
            req.project_id = req.collection.project_id
            req.save(update_fields=['project'])
        except Exception:
            # 忽略单条失败，避免阻断迁移
            continue


def backward_clear_project(apps, schema_editor):
    ApiRequest = apps.get_model('api_testing', 'ApiRequest')
    ApiRequest.objects.update(project=None)


class Migration(migrations.Migration):

    dependencies = [
        ('api_testing', '0003_notificationlog_task_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='apirequest',
            name='project',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='requests', to='api_testing.ApiProject', verbose_name='所属项目'),
        ),
        migrations.RunPython(forward_fill_project, backward_clear_project),
    ]

