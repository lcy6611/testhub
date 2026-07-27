from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("requirement_analysis", "0012_testcasegenerationtask_image_data_urls"),
    ]

    operations = [
        migrations.AddField(
            model_name="testcasegenerationtask",
            name="image_attachments",
            field=models.JSONField(blank=True, default=list, verbose_name="带角色的图片附件"),
        ),
    ]
