from rest_framework import serializers

from .kb_chat_models import KbChatMessage, KbChatSession


class KbChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = KbChatMessage
        fields = ["id", "role", "content", "retrieval_meta", "created_at"]
        read_only_fields = fields


class KbChatSessionSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()
    dify_config_name = serializers.SerializerMethodField()

    class Meta:
        model = KbChatSession
        fields = [
            "id",
            "session_id",
            "title",
            "dify_config",
            "dify_config_name",
            "dify_dataset_id",
            "dify_dataset_name",
            "kb_document_ids",
            "kb_scope_mode",
            "kb_top_k",
            "last_generation_task_id",
            "message_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "session_id", "last_generation_task_id", "created_at", "updated_at"]

    def get_message_count(self, obj):
        return obj.messages.count()

    def get_dify_config_name(self, obj):
        if obj.dify_config_id and obj.dify_config:
            return getattr(obj.dify_config, "app_type", "") or f"配置#{obj.dify_config_id}"
        return ""


class KbChatSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KbChatSession
        fields = [
            "session_id",
            "title",
            "dify_config",
            "dify_dataset_id",
            "dify_dataset_name",
            "kb_document_ids",
            "kb_scope_mode",
            "kb_top_k",
        ]

    def validate_kb_document_ids(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("kb_document_ids 必须为数组")
        return [str(x).strip() for x in value if str(x).strip()]

    def validate_kb_top_k(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 5
        return max(1, min(value, 10))


    def validate(self, attrs):
        if attrs.get("kb_scope_mode", "full") == "full":
            attrs["kb_document_ids"] = []
        return attrs


class KbChatSessionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = KbChatSession
        fields = [
            "title",
            "dify_config",
            "dify_dataset_id",
            "dify_dataset_name",
            "kb_document_ids",
            "kb_scope_mode",
            "kb_top_k",
        ]

    def validate_kb_document_ids(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("kb_document_ids 必须为数组")
        return [str(x).strip() for x in value if str(x).strip()]

    def validate(self, attrs):
        mode = attrs.get("kb_scope_mode")
        if mode is None and self.instance is not None:
            mode = getattr(self.instance, "kb_scope_mode", "full")
        if mode == "full":
            attrs["kb_document_ids"] = []
        return attrs


class KbChatSendMessageSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=64)
    message = serializers.CharField(max_length=8000)
    dify_config_id = serializers.IntegerField(required=False, allow_null=True)
    dify_dataset_id = serializers.CharField(required=False, allow_blank=True, max_length=64)
    dify_dataset_name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    kb_document_ids = serializers.ListField(
        child=serializers.CharField(max_length=64),
        required=False,
        allow_empty=True,
    )
    kb_top_k = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)
    kb_scope_mode = serializers.ChoiceField(
        choices=["full", "documents"],
        required=False,
        default="full",
    )


class KbChatGenerateTestcasesSerializer(serializers.Serializer):
    project = serializers.IntegerField(required=False, allow_null=True)
    message_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
    )
