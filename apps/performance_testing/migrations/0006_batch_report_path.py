# Generated manually for batch report_path

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("performance_testing", "0005_batch_execution"),
    ]

    operations = [
        migrations.AddField(
            model_name="performancebatchexecution",
            name="report_path",
            field=models.TextField(blank=True, default="", verbose_name="项目级报告目录"),
        ),
    ]
