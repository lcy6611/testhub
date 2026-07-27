# -*- coding: utf-8 -*-
"""AI 评测与反馈闭环 — 序列化器。"""
from rest_framework import serializers

from .models import (
    PromptVersion, AICallLog, EvalDataset, EvalCase, EvalRun, EvalResult, AiFeedback,
)


class PromptVersionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PromptVersion
        fields = "__all__"
        read_only_fields = ("id", "version", "created_at", "created_by_name")

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


class AICallLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AICallLog
        fields = "__all__"


class EvalCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = EvalCase
        fields = "__all__"


class EvalDatasetSerializer(serializers.ModelSerializer):
    case_count = serializers.SerializerMethodField(read_only=True)
    created_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EvalDataset
        fields = "__all__"
        read_only_fields = ("id", "created_at", "case_count", "created_by_name")

    def get_case_count(self, obj):
        return obj.cases.count()

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


class EvalResultSerializer(serializers.ModelSerializer):
    case_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EvalResult
        fields = "__all__"

    def get_case_name(self, obj):
        return obj.case.name if obj.case else None


class EvalRunSerializer(serializers.ModelSerializer):
    dataset_name = serializers.SerializerMethodField(read_only=True)
    prompt_version_label = serializers.SerializerMethodField(read_only=True)
    model_config_name = serializers.SerializerMethodField(read_only=True)
    summary_json = serializers.SerializerMethodField(read_only=True)
    result_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EvalRun
        fields = "__all__"
        read_only_fields = (
            "id", "status", "total", "summary", "error",
            "started_at", "finished_at", "created_at",
            "dataset_name", "prompt_version_label", "model_config_name",
            "summary_json", "result_count",
        )

    def get_dataset_name(self, obj):
        return obj.dataset.name if obj.dataset else None

    def get_prompt_version_label(self, obj):
        return f"{obj.prompt_version.key} v{obj.prompt_version.version}" if obj.prompt_version else None

    def get_model_config_name(self, obj):
        return obj.model_config.name if obj.model_config else None

    def get_summary_json(self, obj):
        return obj.get_summary()

    def get_result_count(self, obj):
        return obj.results.count()


class AiFeedbackSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AiFeedback
        fields = "__all__"
        read_only_fields = ("id", "created_at", "created_by_name", "converted_to_case")

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by"] = request.user
        return super().create(validated_data)
