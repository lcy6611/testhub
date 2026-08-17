from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0026_sync_old_recorded_to_testscript'),
    ]

    operations = [
        migrations.AddField(
            model_name='testscript',
            name='last_execution_video_url',
            field=models.CharField(
                blank=True,
                help_text='最近一次执行成功录制的回放视频相对/绝对 URL（由执行器写入）',
                max_length=500,
                verbose_name='最近回放视频地址',
            ),
        ),
    ]
