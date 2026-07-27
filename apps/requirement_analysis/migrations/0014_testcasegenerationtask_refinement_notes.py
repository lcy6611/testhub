from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("requirement_analysis", "0013_testcasegenerationtask_image_attachments"),
    ]

    operations = [
        migrations.AddField(
            model_name="testcasegenerationtask",
            name="refinement_notes",
            field=models.TextField(blank=True, default="", verbose_name="迭代补充记录"),
        ),
    ]
