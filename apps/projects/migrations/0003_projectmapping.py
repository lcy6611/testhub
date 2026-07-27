from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('module', models.CharField(choices=[('ui_automation', 'UI自动化'), ('api_testing', 'API测试'), ('app_automation', 'APP自动化')], max_length=32, verbose_name='模块')),
                ('external_project_id', models.PositiveIntegerField(verbose_name='模块项目ID')),
                ('external_project_name', models.CharField(blank=True, default='', max_length=200, verbose_name='模块项目名称（冗余）')),
                ('auto_matched', models.BooleanField(default=False, verbose_name='是否自动匹配')),
                ('created_at', models.DateTimeField(default=timezone.now, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='module_mappings', to='projects.project', verbose_name='核心项目')),
            ],
            options={
                'db_table': 'project_mappings',
                'verbose_name': '项目映射',
                'verbose_name_plural': '项目映射',
                'unique_together': {('module', 'external_project_id')},
            },
        ),
        migrations.AddIndex(
            model_name='projectmapping',
            index=models.Index(fields=['project', 'module'], name='prj_module_idx'),
        ),
    ]
