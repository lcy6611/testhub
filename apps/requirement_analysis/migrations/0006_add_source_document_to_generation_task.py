from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("requirement_analysis", "0005_alter_aimodelconfig_role"),
    ]

    operations = [
        migrations.AddField(
            model_name="testcasegenerationtask",
            name="source_document",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="generation_tasks",
                to="requirement_analysis.requirementdocument",
                verbose_name="来源需求文档",
            ),
        ),
    ]

