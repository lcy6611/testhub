# Generated migration for adding GenerationConfig and stream fields

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('requirement_analysis', '0002_initial'),
    ]

    operations = [
        # 创建 GenerationConfig 模型
        migrations.CreateModel(
            name='GenerationConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='默认生成配置', max_length=100, verbose_name='配置名称')),
                ('default_output_mode', models.CharField(choices=[('stream', '实时流式输出'), ('complete', '完整输出')], default='stream', help_text='测试用例生成的默认输出方式', max_length=10, verbose_name='默认输出模式')),
                ('enable_auto_review', models.BooleanField(default=True, help_text='生成完成后自动进行AI评审，并根据评审意见改进测试用例', verbose_name='启用AI评审和改进')),
                ('review_timeout', models.IntegerField(default=120, help_text='AI评审和改进的最大等待时间（总时长）', verbose_name='评审和改进超时时间（秒）')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '生成行为配置',
                'verbose_name_plural': '生成行为配置',
                'db_table': 'generation_config',
            },
        ),
        # 为 TestCaseGenerationTask 添加新字段
        migrations.AddField(
            model_name='testcasegenerationtask',
            name='output_mode',
            field=models.CharField(choices=[('stream', '实时流式输出'), ('complete', '完整输出')], default='stream', max_length=10, verbose_name='输出模式'),
        ),
        migrations.AddField(
            model_name='testcasegenerationtask',
            name='stream_buffer',
            field=models.TextField(blank=True, verbose_name='流式输出缓冲区'),
        ),
        migrations.AddField(
            model_name='testcasegenerationtask',
            name='stream_position',
            field=models.IntegerField(default=0, verbose_name='流式输出位置'),
        ),
        migrations.AddField(
            model_name='testcasegenerationtask',
            name='last_stream_update',
            field=models.DateTimeField(blank=True, null=True, verbose_name='最后流式更新时间'),
        ),
    ]
