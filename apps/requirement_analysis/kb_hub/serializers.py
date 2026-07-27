# -*- coding: utf-8 -*-
"""知识中枢序列化器。"""

from rest_framework import serializers

from .models import (
    KnowledgeHubConfig,
    NativeKb,
    NativeKbDocument,
    NativeKbChunk,
    KbSource,
    ProjectDifyKbBinding,
    DocumentProjectBinding,
)


class KnowledgeHubConfigSerializer(serializers.ModelSerializer):
    engine_display = serializers.CharField(source="get_engine_display", read_only=True)
    parser_type_display = serializers.CharField(source="get_parser_type_display", read_only=True)
    dify_config_name = serializers.CharField(source="dify_config.name", read_only=True, default="")

    class Meta:
        model = KnowledgeHubConfig
        fields = [
            "id", "engine", "engine_display",
            "dify_config", "dify_config_name",
            "parser_type", "parser_type_display", "parser_api_url", "parser_api_key",
            "embedding_api_url", "embedding_api_key", "embedding_model_name",
            "rerank_api_url", "rerank_api_key", "rerank_model_name",
            "extraction_api_url", "extraction_api_key", "extraction_model_name",
            "vision_api_url", "vision_api_key", "vision_model_name",
            "top_k", "chunk_size", "chunk_overlap", "min_score",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class NativeKbSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(read_only=True)
    chunk_count = serializers.IntegerField(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    # 全局共享：True 时对所有项目可见
    is_global = serializers.BooleanField(required=False, default=False)
    # 已绑定（共享）到哪些项目（只读展示）
    shared_projects = serializers.SerializerMethodField()
    # 显式绑定到哪些项目（写入，实现跨项目共享）
    shared_project_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True,
        help_text="显式绑定到这些项目（配合 is_global=False 实现逐项目共享）",
    )

    class Meta:
        model = NativeKb
        fields = [
            "id", "name", "description", "project", "status", "status_display",
            "is_global", "shared_projects", "shared_project_ids",
            "document_count", "chunk_count", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def get_shared_projects(self, obj):
        return list(obj.project_bindings.values_list("project_id", flat=True))

    def _sync_bindings(self, kb, project_ids):
        from .models import ProjectKbBinding
        from apps.projects.models import Project

        kb.project_bindings.all().delete()
        for pid in (project_ids or []):
            if Project.objects.filter(pk=pid).exists():
                ProjectKbBinding.objects.get_or_create(project_id=pid, kb=kb)

    def create(self, validated_data):
        shared = validated_data.pop("shared_project_ids", [])
        kb = super().create(validated_data)
        self._sync_bindings(kb, shared)
        return kb

    def update(self, instance, validated_data):
        shared = validated_data.pop("shared_project_ids", None)
        kb = super().update(instance, validated_data)
        if shared is not None:
            self._sync_bindings(kb, shared)
        return kb


class NativeKbDocumentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    kb_name = serializers.CharField(source="kb.name", read_only=True)
    # 文档级共享项目（读 + 写），与 KB 级共享并行生效
    shared_projects = serializers.SerializerMethodField()
    shared_project_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, write_only=True,
        help_text="文档级多项目绑定列表",
    )

    class Meta:
        model = NativeKbDocument
        fields = [
            "id", "kb", "kb_name", "title", "source_type", "source_type_display",
            "file", "content_text", "content_md", "status", "status_display",
            "word_count", "doc_meta", "error_message",
            "shared_projects", "shared_project_ids",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "content_md", "status", "word_count", "doc_meta",
            "error_message", "created_at", "updated_at",
        ]

    def get_shared_projects(self, obj):
        return list(obj.project_bindings.values_list("project_id", flat=True))

    def _sync_bindings(self, doc, project_ids):
        from apps.projects.models import Project

        doc.project_bindings.all().delete()
        for pid in (project_ids or []):
            if Project.objects.filter(pk=pid).exists():
                DocumentProjectBinding.objects.get_or_create(
                    project_id=pid, document=doc,
                )

    def create(self, validated_data):
        shared = validated_data.pop("shared_project_ids", [])
        doc = super().create(validated_data)
        self._sync_bindings(doc, shared)
        return doc

    def update(self, instance, validated_data):
        shared = validated_data.pop("shared_project_ids", None)
        doc = super().update(instance, validated_data)
        if shared is not None:
            self._sync_bindings(doc, shared)
        return doc


class NativeKbChunkSerializer(serializers.ModelSerializer):
    document_name = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = NativeKbChunk
        fields = [
            "id", "document", "document_name", "chunk_index", "content",
            "token_count", "enabled",
        ]


class ProjectDifyKbBindingSerializer(serializers.ModelSerializer):
    """项目-Dify 知识库绑定（读写均走本序列化器）。"""

    class Meta:
        model = ProjectDifyKbBinding
        fields = [
            "id", "project", "dify_config",
            "dataset_id", "dataset_name", "document_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class KbSourceSerializer(serializers.ModelSerializer):
    target_kb_name = serializers.CharField(source="target_kb.name", read_only=True, default="")

    class Meta:
        model = KbSource
        fields = [
            "id", "name", "external_type", "feishu_mode", "feishu_root_folder_token",
            "app_id", "app_secret", "tenant_key", "base_url",
            "sync_status", "last_sync_at", "last_sync_error", "doc_count",
            "target_kb", "target_kb_name", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "sync_status", "last_sync_at", "last_sync_error", "doc_count",
            "created_by", "created_at", "updated_at",
        ]
