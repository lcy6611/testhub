from django.db import migrations, models


def _column_exists(cursor, table, column):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        [table, column],
    )
    return cursor.fetchone()[0] > 0


def apply_dataset_api_key(apps, schema_editor):
    table = "dify_configs"
    column = "dataset_api_key"
    with schema_editor.connection.cursor() as cursor:
        if not _column_exists(cursor, table, column):
            cursor.execute(
                f"ALTER TABLE `{table}` ADD COLUMN `{column}` varchar(500) NOT NULL DEFAULT ''"
            )


def reverse_dataset_api_key(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0003_state_add_app_type"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(apply_dataset_api_key, reverse_dataset_api_key),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="difyconfig",
                    name="dataset_api_key",
                    field=models.CharField(
                        blank=True,
                        default="",
                        help_text="Dify 知识库 Dataset API Key（dataset- 开头），用于 AI 用例生成时检索知识库",
                        max_length=500,
                        verbose_name="知识库 API Key",
                    ),
                ),
            ],
        ),
    ]
