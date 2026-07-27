from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("assistant", "0005_difyconfig_invoke_mode"),
        ("requirement_analysis", "0009_alter_aimodelconfig_max_tokens_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="KbChatSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_id", models.CharField(max_length=64, unique=True, verbose_name="会话标识")),
                ("title", models.CharField(blank=True, default="", max_length=500, verbose_name="标题")),
                ("dify_dataset_id", models.CharField(blank=True, default="", max_length=64, verbose_name="知识库 ID")),
                ("dify_dataset_name", models.CharField(blank=True, default="", max_length=200, verbose_name="知识库名称")),
                ("kb_document_ids", models.JSONField(blank=True, default=list, verbose_name="检索范围文档 ID")),
                ("kb_top_k", models.PositiveSmallIntegerField(default=5, verbose_name="检索条数")),
                (
                    "last_generation_task_id",
                    models.CharField(blank=True, default="", max_length=50, verbose_name="最近生成任务 ID"),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "dify_config",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="kb_chat_sessions",
                        to="assistant.difyconfig",
                        verbose_name="Dify 配置",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="kb_chat_sessions",
                        to="users.user",
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "知识库对话会话",
                "verbose_name_plural": "知识库对话会话",
                "db_table": "kb_chat_session",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.CreateModel(
            name="KbChatMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[("user", "用户"), ("assistant", "助手")],
                        max_length=20,
                        verbose_name="角色",
                    ),
                ),
                ("content", models.TextField(verbose_name="内容")),
                ("retrieval_meta", models.JSONField(blank=True, default=dict, verbose_name="检索元信息")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, verbose_name="创建时间")),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="requirement_analysis.kbchatsession",
                        verbose_name="会话",
                    ),
                ),
            ],
            options={
                "verbose_name": "知识库对话消息",
                "verbose_name_plural": "知识库对话消息",
                "db_table": "kb_chat_message",
                "ordering": ["created_at"],
            },
        ),
    ]
