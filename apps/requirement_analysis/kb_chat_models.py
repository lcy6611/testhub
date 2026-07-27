"""知识库对话会话与消息。"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class KbChatSession(models.Model):
    """知识库 RAG 对话会话。"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kb_chat_sessions",
        verbose_name="用户",
    )
    session_id = models.CharField(max_length=64, unique=True, verbose_name="会话标识")
    title = models.CharField(max_length=500, blank=True, default="", verbose_name="标题")
    dify_config = models.ForeignKey(
        "assistant.DifyConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kb_chat_sessions",
        verbose_name="Dify 配置",
    )
    dify_dataset_id = models.CharField(max_length=64, blank=True, default="", verbose_name="知识库 ID")
    dify_dataset_name = models.CharField(max_length=200, blank=True, default="", verbose_name="知识库名称")
    kb_document_ids = models.JSONField(default=list, blank=True, verbose_name="检索范围文档 ID")
    kb_scope_mode = models.CharField(
        max_length=20,
        choices=[("full", "检索全库"), ("documents", "指定文档")],
        default="full",
        verbose_name="检索范围模式",
    )
    kb_top_k = models.PositiveSmallIntegerField(default=5, verbose_name="检索条数")
    last_generation_task_id = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="最近生成任务 ID",
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "kb_chat_session"
        verbose_name = "知识库对话会话"
        verbose_name_plural = "知识库对话会话"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or self.session_id


class KbChatMessage(models.Model):
    """知识库对话消息。"""

    ROLE_CHOICES = [
        ("user", "用户"),
        ("assistant", "助手"),
    ]

    session = models.ForeignKey(
        KbChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="会话",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name="角色")
    content = models.TextField(verbose_name="内容")
    retrieval_meta = models.JSONField(default=dict, blank=True, verbose_name="检索元信息")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")

    class Meta:
        db_table = "kb_chat_message"
        verbose_name = "知识库对话消息"
        verbose_name_plural = "知识库对话消息"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_role_display()}: {(self.content or '')[:40]}"
