import django.db.models.deletion
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


def _add_column_if_missing(cursor, table, column, ddl):
    if not _column_exists(cursor, table, column):
        cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN {ddl}")


def apply_kb_reference_fields(apps, schema_editor):
    table = "testcase_generation_task"
    with schema_editor.connection.cursor() as cursor:
        _add_column_if_missing(
            cursor,
            table,
            "kb_context_meta",
            "`kb_context_meta` json NOT NULL DEFAULT (JSON_OBJECT())",
        )
        _add_column_if_missing(
            cursor,
            table,
            "kb_reference_mode",
            "`kb_reference_mode` varchar(20) NOT NULL DEFAULT 'hybrid'",
        )
        _add_column_if_missing(
            cursor,
            table,
            "kb_document_ids",
            "`kb_document_ids` json NOT NULL DEFAULT (JSON_ARRAY())",
        )
        _add_column_if_missing(
            cursor,
            table,
            "kb_function_ids",
            "`kb_function_ids` json NOT NULL DEFAULT (JSON_ARRAY())",
        )


def reverse_kb_reference_fields(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("requirement_analysis", "0007_testcasegenerationtask_dify_kb_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="KbFunction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="功能名称")),
                ("code", models.CharField(blank=True, default="", max_length=100, verbose_name="功能编码")),
                ("description", models.TextField(blank=True, default="", verbose_name="描述")),
                ("dify_dataset_id", models.CharField(max_length=64, verbose_name="Dify 知识库 ID")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "知识库功能模块",
                "verbose_name_plural": "知识库功能模块",
                "db_table": "kb_function",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="KbFunctionDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("dify_document_id", models.CharField(max_length=64, verbose_name="Dify 文档 ID")),
                ("dify_document_name", models.CharField(blank=True, default="", max_length=300, verbose_name="文档名称")),
                ("is_primary", models.BooleanField(default=False, verbose_name="主参考文档")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="排序")),
                (
                    "function",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="requirement_analysis.kbfunction",
                        verbose_name="功能模块",
                    ),
                ),
            ],
            options={
                "verbose_name": "功能参考文档",
                "verbose_name_plural": "功能参考文档",
                "db_table": "kb_function_document",
                "ordering": ["-is_primary", "sort_order", "id"],
                "unique_together": {("function", "dify_document_id")},
            },
        ),
        migrations.CreateModel(
            name="KbFunctionRelation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "relation_type",
                    models.CharField(
                        choices=[("related", "相关"), ("depends_on", "依赖"), ("impacts", "影响")],
                        default="related",
                        max_length=20,
                        verbose_name="关系类型",
                    ),
                ),
                (
                    "from_function",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outgoing_relations",
                        to="requirement_analysis.kbfunction",
                        verbose_name="源功能",
                    ),
                ),
                (
                    "to_function",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_relations",
                        to="requirement_analysis.kbfunction",
                        verbose_name="目标功能",
                    ),
                ),
            ],
            options={
                "verbose_name": "功能关联",
                "verbose_name_plural": "功能关联",
                "db_table": "kb_function_relation",
                "unique_together": {("from_function", "to_function", "relation_type")},
            },
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(apply_kb_reference_fields, reverse_kb_reference_fields),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="testcasegenerationtask",
                    name="kb_context_meta",
                    field=models.JSONField(blank=True, default=dict, verbose_name="知识库参考元信息"),
                ),
                migrations.AddField(
                    model_name="testcasegenerationtask",
                    name="kb_reference_mode",
                    field=models.CharField(
                        blank=True,
                        default="hybrid",
                        help_text="documents=指定文档, retrieval=语义检索, hybrid=混合",
                        max_length=20,
                        verbose_name="知识库参考模式",
                    ),
                ),
                migrations.AddField(
                    model_name="testcasegenerationtask",
                    name="kb_document_ids",
                    field=models.JSONField(blank=True, default=list, verbose_name="指定参考文档 ID 列表"),
                ),
                migrations.AddField(
                    model_name="testcasegenerationtask",
                    name="kb_function_ids",
                    field=models.JSONField(blank=True, default=list, verbose_name="关联功能模块 ID 列表"),
                ),
            ],
        ),
    ]
