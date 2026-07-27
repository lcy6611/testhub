from rest_framework import serializers

from .models import KgEdge, KgEntity


class KgEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = KgEntity
        fields = [
            "id",
            "entity_key",
            "entity_type",
            "ref_app",
            "ref_id",
            "project_id",
            "label",
            "properties",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class KgEdgeSerializer(serializers.ModelSerializer):
    src_key = serializers.CharField(source="src.entity_key", read_only=True)
    dst_key = serializers.CharField(source="dst.entity_key", read_only=True)

    class Meta:
        model = KgEdge
        fields = [
            "id",
            "src_key",
            "dst_key",
            "relation_type",
            "project_id",
            "source",
            "confidence",
            "meta",
            "created_at",
        ]
        read_only_fields = fields
