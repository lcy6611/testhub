from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("requirement_analysis", "0010_kb_chat"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbchatsession",
            name="kb_scope_mode",
            field=models.CharField(
                choices=[("full", "检索全库"), ("documents", "指定文档")],
                default="full",
                max_length=20,
                verbose_name="检索范围模式",
            ),
        ),
    ]
