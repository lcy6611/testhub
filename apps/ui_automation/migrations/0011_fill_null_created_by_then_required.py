# Generated manually: nullable created_by -> non-nullable (0009 曾改为 null=True，当前模型要求必填)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def fill_null_created_by(apps, schema_editor):
    """将 AIScheduledTask 中 created_by 为 NULL 的记录设为第一个用户（若有）。"""
    User = apps.get_model(settings.AUTH_USER_MODEL)
    AIScheduledTask = apps.get_model('ui_automation', 'AIScheduledTask')
    first_user = User.objects.order_by('pk').first()
    if first_user:
        AIScheduledTask.objects.filter(created_by__isnull=True).update(created_by=first_user)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ui_automation', '0010_fill_null_project_then_required'),
    ]

    operations = [
        migrations.RunPython(fill_null_created_by, noop),
        migrations.AlterField(
            model_name='aischeduledtask',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='创建者'),
        ),
    ]
