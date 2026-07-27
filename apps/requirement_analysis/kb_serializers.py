from rest_framework import serializers

from .kb_models import KbFunction, KbFunctionDocument, KbFunctionRelation


class KbFunctionDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KbFunctionDocument
        fields = [
            "id",
            "dify_document_id",
            "dify_document_name",
            "is_primary",
            "sort_order",
        ]


class KbFunctionRelationSerializer(serializers.ModelSerializer):
    to_function_name = serializers.CharField(source="to_function.name", read_only=True)

    class Meta:
        model = KbFunctionRelation
        fields = ["id", "to_function", "to_function_name", "relation_type"]


class KbFunctionSerializer(serializers.ModelSerializer):
    documents = KbFunctionDocumentSerializer(many=True, required=False)
    outgoing_relations = KbFunctionRelationSerializer(many=True, required=False)

    class Meta:
        model = KbFunction
        fields = [
            "id",
            "name",
            "code",
            "description",
            "dify_dataset_id",
            "is_active",
            "documents",
            "outgoing_relations",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def create(self, validated_data):
        documents_data = validated_data.pop("documents", [])
        relations_data = validated_data.pop("outgoing_relations", [])
        func = KbFunction.objects.create(**validated_data)
        self._save_documents(func, documents_data)
        self._save_relations(func, relations_data)
        return func

    def update(self, instance, validated_data):
        documents_data = validated_data.pop("documents", None)
        relations_data = validated_data.pop("outgoing_relations", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if documents_data is not None:
            instance.documents.all().delete()
            self._save_documents(instance, documents_data)
        if relations_data is not None:
            instance.outgoing_relations.all().delete()
            self._save_relations(instance, relations_data)
        return instance

    def _save_documents(self, func, documents_data):
        for idx, item in enumerate(documents_data or []):
            KbFunctionDocument.objects.create(
                function=func,
                dify_document_id=item["dify_document_id"],
                dify_document_name=item.get("dify_document_name") or "",
                is_primary=item.get("is_primary", False),
                sort_order=item.get("sort_order", idx),
            )

    def _save_relations(self, func, relations_data):
        for item in relations_data or []:
            target = item["to_function"]
            # DRF 在反序列化后,validated_data 中 to_function 存的是 KbFunction 对象,
            # 写入 *_id 字段时需要取 .id
            target_id = getattr(target, "id", target)
            KbFunctionRelation.objects.create(
                from_function=func,
                to_function_id=target_id,
                relation_type=item.get("relation_type") or "related",
            )


class KbReferencePreviewSerializer(serializers.Serializer):
    dify_config_id = serializers.IntegerField(required=False, allow_null=True)
    dify_dataset_id = serializers.CharField()
    dify_dataset_name = serializers.CharField(required=False, allow_blank=True, default="")
    title = serializers.CharField(required=False, allow_blank=True, default="")
    requirement_text = serializers.CharField(required=False, allow_blank=True, default="")
    kb_reference_mode = serializers.ChoiceField(
        choices=[("documents", "documents"), ("retrieval", "retrieval"), ("hybrid", "hybrid")],
        required=False,
        default="hybrid",
    )
    kb_document_ids = serializers.ListField(
        child=serializers.CharField(), required=False, allow_empty=True, default=list
    )
    kb_function_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True, default=list
    )
    kb_top_k = serializers.IntegerField(required=False, default=5, min_value=1, max_value=10)
    document_names = serializers.DictField(
        child=serializers.CharField(), required=False, allow_empty=True, default=dict
    )
