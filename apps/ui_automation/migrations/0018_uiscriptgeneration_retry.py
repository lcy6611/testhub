from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ui_automation', '0017_uiscriptgeneration_suite_exec_pass_rate_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='uiscriptgeneration',
            name='retry_limit',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='失败自动重试次数'),
        ),
        migrations.AddField(
            model_name='uiscriptgeneration',
            name='retry_count',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='已重试次数'),
        ),
    ]
