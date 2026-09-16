from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_userprofile_ui_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('config', models.JSONField(default=dict, verbose_name='全局配置')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'db_table': 'platform_config',
                'verbose_name': '平台配置',
                'verbose_name_plural': '平台配置',
            },
        ),
    ]
