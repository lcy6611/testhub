from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

from .constants import CONFIDENCE_LEVEL_CHOICES

User = get_user_model()


class KgEntity(models.Model):
    """图谱节点注册表。"""

    entity_key = models.CharField(max_length=160, unique=True, db_index=True, verbose_name="实体键")
    entity_type = models.CharField(max_length=48, db_index=True, verbose_name="实体类型")
    ref_app = models.CharField(max_length=64, blank=True, default="", verbose_name="来源 App")
    ref_id = models.CharField(max_length=128, blank=True, default="", verbose_name="来源 ID")
    dataset_id = models.CharField(max_length=128, blank=True, default="", db_index=True, verbose_name="来源知识库ID")
    project_id = models.PositiveIntegerField(null=True, blank=True, db_index=True, verbose_name="项目 ID")
    label = models.CharField(max_length=500, blank=True, default="", verbose_name="展示名")
    properties = models.JSONField(default=dict, blank=True, verbose_name="扩展属性")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "kg_entity"
        verbose_name = "图谱实体"
        verbose_name_plural = "图谱实体"
        indexes = [
            models.Index(fields=["entity_type", "project_id"]),
            models.Index(fields=["ref_app", "ref_id"]),
        ]

    def __str__(self):
        return self.entity_key


class KgEdge(models.Model):
    """图谱边。"""

    src = models.ForeignKey(
        KgEntity,
        on_delete=models.CASCADE,
        related_name="outgoing_edges",
        verbose_name="源节点",
    )
    dst = models.ForeignKey(
        KgEntity,
        on_delete=models.CASCADE,
        related_name="incoming_edges",
        verbose_name="目标节点",
    )
    relation_type = models.CharField(max_length=32, db_index=True, verbose_name="关系类型")
    dataset_id = models.CharField(max_length=128, blank=True, default="", db_index=True, verbose_name="所属知识库ID")
    project_id = models.PositiveIntegerField(null=True, blank=True, db_index=True, verbose_name="项目 ID")
    source = models.CharField(max_length=16, default="system", verbose_name="来源")
    confidence = models.FloatField(null=True, blank=True, verbose_name="置信度")
    confidence_level = models.CharField(
        max_length=16, blank=True, null=True, db_index=True,
        choices=CONFIDENCE_LEVEL_CHOICES, verbose_name="置信度等级",
    )
    meta = models.JSONField(default=dict, blank=True, verbose_name="元数据")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kg_edges_created",
        verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "kg_edge"
        verbose_name = "图谱边"
        verbose_name_plural = "图谱边"
        constraints = [
            models.UniqueConstraint(
                fields=["src", "dst", "relation_type"],
                name="uniq_kg_edge_src_dst_rel",
            )
        ]
        indexes = [
            models.Index(fields=["relation_type", "project_id"]),
        ]

    def __str__(self):
        return f"{self.src.entity_key} -[{self.relation_type}]-> {self.dst.entity_key}"


def kg_enabled() -> bool:
    return bool(getattr(settings, "KNOWLEDGE_GRAPH_ENABLED", True))
