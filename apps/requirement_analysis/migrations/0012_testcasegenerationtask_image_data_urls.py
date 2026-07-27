from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("requirement_analysis", "0011_kbchatsession_kb_scope_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="testcasegenerationtask",
            name="image_data_urls",
            field=models.JSONField(blank=True, default=list, verbose_name="附件截图 data URLs"),
        ),
    ]
