"""知识库功能模块与文档关联（轻量知识图谱）。"""

from django.db import models


class KbFunction(models.Model):
    """业务功能模块，绑定到 Dify 知识库，可关联多份参考文档。"""

    name = models.CharField(max_length=200, verbose_name="功能名称")
    code = models.CharField(max_length=100, blank=True, default="", verbose_name="功能编码")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    dify_dataset_id = models.CharField(max_length=64, verbose_name="Dify 知识库 ID")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "kb_function"
        verbose_name = "知识库功能模块"
        verbose_name_plural = "知识库功能模块"
        ordering = ["name"]

    def __str__(self):
        return self.name


class KbFunctionDocument(models.Model):
    """功能模块 ↔ Dify 文档映射。"""

    function = models.ForeignKey(
        KbFunction,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="功能模块",
    )
    dify_document_id = models.CharField(max_length=64, verbose_name="Dify 文档 ID")
    dify_document_name = models.CharField(max_length=300, blank=True, default="", verbose_name="文档名称")
    is_primary = models.BooleanField(default=False, verbose_name="主参考文档")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="排序")

    class Meta:
        db_table = "kb_function_document"
        verbose_name = "功能参考文档"
        verbose_name_plural = "功能参考文档"
        unique_together = [("function", "dify_document_id")]
        ordering = ["-is_primary", "sort_order", "id"]

    def __str__(self):
        return f"{self.function.name} → {self.dify_document_name or self.dify_document_id}"


class KbFunctionRelation(models.Model):
    """功能模块之间的关联（用于自动扩展参考文档）。"""

    RELATION_CHOICES = [
        ("related", "相关"),
        ("depends_on", "依赖"),
        ("impacts", "影响"),
    ]

    from_function = models.ForeignKey(
        KbFunction,
        on_delete=models.CASCADE,
        related_name="outgoing_relations",
        verbose_name="源功能",
    )
    to_function = models.ForeignKey(
        KbFunction,
        on_delete=models.CASCADE,
        related_name="incoming_relations",
        verbose_name="目标功能",
    )
    relation_type = models.CharField(
        max_length=20,
        choices=RELATION_CHOICES,
        default="related",
        verbose_name="关系类型",
    )

    class Meta:
        db_table = "kb_function_relation"
        verbose_name = "功能关联"
        verbose_name_plural = "功能关联"
        unique_together = [("from_function", "to_function", "relation_type")]

    def __str__(self):
        return f"{self.from_function.name} -{self.relation_type}-> {self.to_function.name}"
