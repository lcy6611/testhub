from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_graph', '0002_add_dataset_id_to_entity_and_edge'),
    ]

    operations = [
        migrations.AddField(
            model_name='kgedge',
            name='confidence_level',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=16,
                verbose_name='置信度等级',
                choices=[
                    ('EXTRACTED', '字面提取'),
                    ('INFERRED', '推断'),
                    ('AMBIGUOUS', '歧义'),
                ],
            ),
        ),
    ]
