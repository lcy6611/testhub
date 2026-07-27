from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge_graph', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='kgedge',
            name='dataset_id',
            field=models.CharField(db_index=True, default='', max_length=128, verbose_name='所属知识库ID'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='kgentity',
            name='dataset_id',
            field=models.CharField(db_index=True, default='', max_length=128, verbose_name='来源知识库ID'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='kgedge',
            name='dataset_id',
            field=models.CharField(db_index=True, default='', max_length=128, verbose_name='所属知识库ID'),
        ),
        migrations.AlterField(
            model_name='kgentity',
            name='dataset_id',
            field=models.CharField(db_index=True, default='', max_length=128, verbose_name='来源知识库ID'),
        ),
    ]
