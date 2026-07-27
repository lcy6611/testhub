from django.db import migrations, models
import django.db.models.deletion


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


def _add_column_if_missing(cursor, table, column, ddl):
    if not _column_exists(cursor, table, column):
        cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN {ddl}")


def _rename_column_if_needed(cursor, table, old_name, new_name, ddl):
    if _column_exists(cursor, table, old_name) and not _column_exists(cursor, table, new_name):
        cursor.execute(f"ALTER TABLE `{table}` CHANGE `{old_name}` `{new_name}` {ddl}")


def apply_kb_fields(apps, schema_editor):
    table = "testcase_generation_task"
    with schema_editor.connection.cursor() as cursor:
        _rename_column_if_needed(
            cursor,
            table,
            "dataset_id",
            "dify_dataset_id",
            "varchar(64) NOT NULL DEFAULT ''",
        )
        _add_column_if_missing(
            cursor,
            table,
            "dify_config_id",
            "`dify_config_id` bigint NULL",
        )
        _add_column_if_missing(
            cursor,
            table,
            "dify_dataset_id",
            "`dify_dataset_id` varchar(64) NOT NULL DEFAULT ''",
        )
        _add_column_if_missing(
            cursor,
            table,
            "dify_dataset_name",
            "`dify_dataset_name` varchar(200) NOT NULL DEFAULT ''",
        )
        _add_column_if_missing(
            cursor,
            table,
            "kb_context",
            "`kb_context` longtext NOT NULL",
        )
        _add_column_if_missing(
            cursor,
            table,
            "kb_top_k",
            "`kb_top_k` smallint UNSIGNED NOT NULL DEFAULT 5",
        )


def reverse_kb_fields(apps, schema_editor):
    # 开发环境回滚时不强制删列，避免误删已有数据
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0004_difyconfig_dataset_api_key"),
        ("requirement_analysis", "0006_add_source_document_to_generation_task"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(apply_kb_fields, reverse_kb_fields),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="testcasegenerationtask",
                    name="dify_config",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="generation_tasks",
                        to="assistant.difyconfig",
                        verbose_name="Dify 配置",
                    ),
                ),
                migrations.AddField(
                    model_name="testcasegenerationtask",
                    name="dify_dataset_id",
                    field=models.CharField(blank=True, default="", max_length=64, verbose_name="Dify 知识库 ID"),
                ),
                migrations.AddField(
                    model_name="testcasegenerationtask",
                    name="dify_dataset_name",
                    field=models.CharField(blank=True, default="", max_length=200, verbose_name="Dify 知识库名称"),
                ),
                migrations.AddField(
                    model_name="testcasegenerationtask",
                    name="kb_context",
                    field=models.TextField(blank=True, default="", verbose_name="知识库检索上下文"),
                ),
                migrations.AddField(
                    model_name="testcasegenerationtask",
                    name="kb_top_k",
                    field=models.PositiveSmallIntegerField(default=5, verbose_name="知识库检索条数"),
                ),
            ],
        ),
    ]
