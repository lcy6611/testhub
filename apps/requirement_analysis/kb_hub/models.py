# -*- coding: utf-8 -*-
"""知识中枢数据模型。"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class KnowledgeHubConfig(models.Model):
    """知识中枢全局配置（单例，按 is_active 取激活项）。"""

    ENGINE_CHOICES = [
        ("dify", "Dify 知识库"),
        ("native", "知识中枢（自建）"),
    ]

    PARSER_CHOICES = [
        ("tika", "Apache Tika（内置兜底）"),
        ("mineru", "MinerU（私有）"),
        ("textin", "TextIn（云端）"),
    ]

    engine = models.CharField(
        max_length=16, choices=ENGINE_CHOICES, default="dify", verbose_name="知识中枢引擎"
    )

    # Dify 后端配置
    dify_config = models.ForeignKey(
        "assistant.DifyConfig",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="kb_hub_configs", verbose_name="Dify 配置",
    )

    # 文档解析（native）
    parser_type = models.CharField(
        max_length=16, choices=PARSER_CHOICES, default="tika", verbose_name="文档解析器"
    )
    parser_api_url = models.URLField(blank=True, default="", verbose_name="解析服务地址")
    parser_api_key = models.CharField(max_length=256, blank=True, default="", verbose_name="解析服务密钥")

    # Embedding 向量模型（native）
    embedding_api_url = models.URLField(blank=True, default="", verbose_name="Embedding API 地址")
    embedding_api_key = models.CharField(max_length=256, blank=True, default="", verbose_name="Embedding API Key")
    embedding_model_name = models.CharField(max_length=128, blank=True, default="Qwen/Qwen3-Embedding-8B", verbose_name="Embedding 模型")

    # Rerank 重排模型（native）
    rerank_api_url = models.URLField(blank=True, default="", verbose_name="Rerank API 地址")
    rerank_api_key = models.CharField(max_length=256, blank=True, default="", verbose_name="Rerank API Key")
    rerank_model_name = models.CharField(max_length=128, blank=True, default="Qwen/Qwen3-Reranker-8B", verbose_name="Rerank 模型")

    # 生成/抽取模型（native）
    extraction_api_url = models.URLField(blank=True, default="", verbose_name="抽取模型 API 地址")
    extraction_api_key = models.CharField(max_length=256, blank=True, default="", verbose_name="抽取模型 API Key")
    extraction_model_name = models.CharField(max_length=128, blank=True, default="", verbose_name="抽取模型名称")

    # 视觉理解模型（native，可选）
    vision_api_url = models.URLField(blank=True, default="", verbose_name="视觉模型 API 地址")
    vision_api_key = models.CharField(max_length=256, blank=True, default="", verbose_name="视觉模型 API Key")
    vision_model_name = models.CharField(max_length=128, blank=True, default="", verbose_name="视觉模型名称")

    # 检索参数
    top_k = models.PositiveSmallIntegerField(default=5, verbose_name="检索条数 Top-K")
    chunk_size = models.PositiveIntegerField(default=500, verbose_name="分块大小（字符）")
    chunk_overlap = models.PositiveIntegerField(default=80, verbose_name="分块重叠（字符）")
    min_score = models.FloatField(default=0.30, verbose_name="最低相关度阈值")

    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "kb_hub_config"
        verbose_name = "知识中枢配置"
        verbose_name_plural = "知识中枢配置"

    def __str__(self):
        return f"知识中枢配置({self.get_engine_display()})"

    @classmethod
    def get_active(cls) -> "KnowledgeHubConfig | None":
        obj = cls.objects.filter(is_active=True).order_by("-updated_at").first()
        if obj is None:
            obj = cls.objects.order_by("-id").first()
        return obj

    @classmethod
    def get_or_create_active(cls) -> "KnowledgeHubConfig":
        obj = cls.get_active()
        if obj is None:
            obj = cls.objects.create(is_active=True)
        return obj

    def get_engine_display_name(self) -> str:
        return self.get_engine_display()


class NativeKb(models.Model):
    """自建知识库。"""

    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("published", "已发布"),
        ("archived", "已归档"),
    ]

    name = models.CharField(max_length=200, verbose_name="知识库名称")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE, null=True, blank=True,
        related_name="native_kbs", verbose_name="关联项目",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="draft", verbose_name="状态"
    )
    # 全局共享：True 表示不绑定具体项目，对所有项目可见（跨项目复用同一份知识库）
    is_global = models.BooleanField(default=False, verbose_name="全局共享")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "kb_hub_native_kb"
        verbose_name = "自建知识库"
        verbose_name_plural = "自建知识库"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name

    @classmethod
    def available_for_project(cls, project_id):
        """某项目可用的知识库集合：

        - 直接归属该项目（project_id == project_id）
        - 全局共享（is_global=True）
        - 通过 ProjectKbBinding 显式绑定到该项目
        """
        if not project_id:
            # 未指定项目：仅返回全局共享的 KB
            return cls.objects.filter(is_global=True)
        return cls.objects.filter(
            models.Q(project_id=project_id)
            | models.Q(is_global=True)
            | models.Q(project_bindings__project_id=project_id)
        ).distinct()

    def is_shared_to(self, project_id):
        """该 KB 是否通过 ProjectKbBinding 显式绑定到指定项目。"""
        if not project_id:
            return False
        return self.project_bindings.filter(project_id=project_id).exists()

    @property
    def document_count(self):
        return self.documents.count()

    @property
    def chunk_count(self):
        return NativeKbChunk.objects.filter(document__kb_id=self.pk).count()


class NativeKbDocument(models.Model):
    """自建知识库文档。"""

    SOURCE_CHOICES = [
        ("file", "文件上传"),
        ("text", "文本录入"),
        ("url", "URL 抓取"),
    ]

    STATUS_CHOICES = [
        ("pending", "待解析"),
        ("parsed", "已解析"),
        ("failed", "解析失败"),
    ]

    kb = models.ForeignKey(
        NativeKb, on_delete=models.CASCADE, related_name="documents", verbose_name="所属知识库"
    )
    title = models.CharField(max_length=300, verbose_name="文档标题")
    source_type = models.CharField(
        max_length=16, choices=SOURCE_CHOICES, default="file", verbose_name="来源类型"
    )
    file = models.FileField(upload_to="kb_hub/docs/", null=True, blank=True, verbose_name="源文件")
    content_text = models.TextField(blank=True, default="", verbose_name="原始文本")
    content_md = models.TextField(blank=True, default="", verbose_name="解析后 Markdown")
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="pending", verbose_name="解析状态"
    )
    word_count = models.PositiveIntegerField(default=0, verbose_name="字数")
    doc_meta = models.JSONField(default=dict, blank=True, verbose_name="元信息")
    error_message = models.TextField(blank=True, default="", verbose_name="错误信息")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "kb_hub_native_doc"
        verbose_name = "知识库文档"
        verbose_name_plural = "知识库文档"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kb.name} / {self.title}"

    @classmethod
    def available_for_project(cls, project_id, *, status_filter=None):
        """某项目可用的文档集合（合并 KB 级共享 + 文档级绑定）。

        规则：
        - 文档所属 KB 满足：
            * 直接归属该 project_id
            * is_global=True
            * KB 与该 project 通过 ProjectKbBinding 显式绑定
        - 或文档本身通过 DocumentProjectBinding 绑定到该项目
        文档级绑定会盖过 KB 不可见：只要文档自身绑定到 project，即视为可见。
        """
        from .models import ProjectKbBinding

        if not project_id:
            return cls.objects.none()

        kb_visible = NativeKb.objects.filter(
            models.Q(project_id=project_id)
            | models.Q(is_global=True)
            | models.Q(project_bindings__project_id=project_id)
        ).values_list("pk", flat=True).distinct()

        qs = cls.objects.filter(
            models.Q(kb_id__in=kb_visible)
            | models.Q(project_bindings__project_id=project_id)
        ).distinct()
        if status_filter:
            qs = qs.filter(status__in=([status_filter] if isinstance(status_filter, str) else status_filter))
        return qs


class NativeKbChunk(models.Model):
    """文档分块 + 向量。向量存 JSONField，检索时全量计算余弦相似度。"""

    document = models.ForeignKey(
        NativeKbDocument, on_delete=models.CASCADE, related_name="chunks", verbose_name="所属文档"
    )
    chunk_index = models.PositiveIntegerField(default=0, verbose_name="分块序号")
    content = models.TextField(verbose_name="分块内容")
    embedding = models.JSONField(default=list, blank=True, verbose_name="向量")
    token_count = models.PositiveIntegerField(default=0, verbose_name="Token 数")
    enabled = models.BooleanField(default=True, verbose_name="是否启用")

    class Meta:
        db_table = "kb_hub_native_chunk"
        verbose_name = "知识库分块"
        verbose_name_plural = "知识库分块"
        indexes = [
            models.Index(fields=["document"]),
        ]

    def __str__(self):
        return f"{self.document.title}#{self.chunk_index}"

    @property
    def kb_id(self):
        return self.document.kb_id

    @property
    def document_name(self):
        return self.document.title


class ProjectKbBinding(models.Model):
    """知识库与项目的多对多绑定（支持跨项目共享）。

    配合 NativeKb.is_global 使用：
      - is_global=True 的 KB 对所有项目可见；
      - 通过本表可把某个「项目专属」KB 额外授权给其它项目复用，
        实现「一份知识库，多个项目共享」。
    """

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="kb_bindings",
        verbose_name="项目",
    )
    kb = models.ForeignKey(
        NativeKb,
        on_delete=models.CASCADE,
        related_name="project_bindings",
        verbose_name="知识库",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="绑定时间")

    class Meta:
        db_table = "kb_hub_project_kb_binding"
        unique_together = [("project", "kb")]
        verbose_name = "知识库项目绑定"
        verbose_name_plural = "知识库项目绑定"

    def __str__(self):
        return f"{self.project_id} ↔ {self.kb_id}"


class DocumentProjectBinding(models.Model):
    """文档级多项目绑定。

    在「KB 级共享」（ProjectKbBinding / is_global）之外的细粒度共享机制：
    单个文档可被显式绑定到多个项目，与所属 KB 的可见性并行生效。
    检索某项目的可用文档时，会合并：
      - KB 的 project_bindings/is_global 带来的可见文档
      - 本表的显式绑定
    """

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="doc_bindings",
        verbose_name="项目",
    )
    document = models.ForeignKey(
        NativeKbDocument,
        on_delete=models.CASCADE,
        related_name="project_bindings",
        verbose_name="文档",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="绑定时间")

    class Meta:
        db_table = "kb_hub_document_project_binding"
        unique_together = [("project", "document")]
        verbose_name = "文档项目绑定"
        verbose_name_plural = "文档项目绑定"
        indexes = [
            models.Index(fields=["project"]),
            models.Index(fields=["document"]),
        ]

    def __str__(self):
        return f"{self.project_id} ↔ Doc#{self.document_id}"


class KbSource(models.Model):
    """外部 SaaS 知识源配置（飞书 / Confluence / Notion 等）。

    通过适配器（kb_hub.adapters）把外部知识库内容同步到本地自建知识库
    （NativeKb + NativeKbDocument），之后复用 NativeKbBackend 做检索/生成，
    实现「外部知识中枢」与本地用例生成链路无缝衔接。
    """

    FEISHU_MODE_CHOICES = [
        ("wiki", "知识库"),
        ("drive", "云盘（云文档）"),
    ]

    EXTERNAL_CHOICES = [
        ("feishu", "飞书"),
        ("confluence", "Confluence"),
        ("notion", "Notion"),
    ]
    SYNC_STATUS_CHOICES = [
        ("pending", "未同步"),
        ("syncing", "同步中"),
        ("success", "同步成功"),
        ("failed", "同步失败"),
    ]

    name = models.CharField(max_length=200, verbose_name="数据源名称")
    external_type = models.CharField(
        max_length=32, choices=EXTERNAL_CHOICES, default="feishu", verbose_name="外部类型"
    )
    # 飞书接入方式：wiki=知识库（默认，向后兼容），drive=云盘（云文档）
    feishu_mode = models.CharField(
        max_length=16, choices=FEISHU_MODE_CHOICES, default="wiki", verbose_name="飞书接入方式"
    )
    # 云盘模式可选的根目录 token（留空则使用「我的空间」根目录）
    feishu_root_folder_token = models.CharField(
        max_length=200, blank=True, default="", verbose_name="云盘根目录 Token"
    )
    # 飞书等凭证
    app_id = models.CharField(max_length=200, blank=True, default="", verbose_name="App ID")
    app_secret = models.CharField(max_length=400, blank=True, default="", verbose_name="App Secret")
    tenant_key = models.CharField(max_length=200, blank=True, default="", verbose_name="Tenant Key")
    base_url = models.URLField(blank=True, default="https://open.feishu.cn", verbose_name="API 基础地址")

    # 同步状态
    sync_status = models.CharField(
        max_length=16, choices=SYNC_STATUS_CHOICES, default="pending", verbose_name="同步状态"
    )
    last_sync_at = models.DateTimeField(null=True, blank=True, verbose_name="最近同步时间")
    last_sync_error = models.TextField(blank=True, default="", verbose_name="同步错误")
    doc_count = models.PositiveIntegerField(default=0, verbose_name="文档数")

    # 同步目标：拉取的内容写入该本地知识库；为空则同步时自动创建
    target_kb = models.ForeignKey(
        NativeKb, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="sources", verbose_name="目标知识库",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "kb_hub_kb_source"
        verbose_name = "外部知识源"
        verbose_name_plural = "外部知识源"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class ProjectDifyKbBinding(models.Model):
    """项目 ↔ Dify 知识库（数据集）绑定。

    AI 用例生成「启用知识库」时，按所选项目列出已绑定到该项目的 Dify 数据集，
    用户勾选后生成阶段用 dataset_id 做检索。与自建 NativeKb 的 project_bindings
    互为补充：Dify 引擎走本表，native 引擎走 NativeKb。
    """

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="dify_kb_bindings",
        verbose_name="项目",
    )
    # 绑定所用的 Dify 配置（可空：为空表示用当前激活的 Dify 配置）
    dify_config = models.ForeignKey(
        "assistant.DifyConfig",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="project_kb_bindings", verbose_name="Dify 配置",
    )
    dataset_id = models.CharField(max_length=128, verbose_name="Dify 数据集 ID")
    dataset_name = models.CharField(max_length=255, blank=True, default="", verbose_name="数据集名称")
    document_count = models.PositiveIntegerField(default=0, verbose_name="文档数")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="绑定时间")

    class Meta:
        db_table = "kb_hub_project_dify_kb_binding"
        unique_together = [("project", "dataset_id")]
        verbose_name = "项目-Dify知识库绑定"
        verbose_name_plural = "项目-Dify知识库绑定"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project_id} ↔ {self.dataset_name or self.dataset_id}"
