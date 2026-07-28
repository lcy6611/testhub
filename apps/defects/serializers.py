from rest_framework import serializers
from .models import Defect, DefectAttachment, ReleaseConclusion


class DefectAttachmentSerializer(serializers.ModelSerializer):
    """缺陷附件序列化器。"""
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = DefectAttachment
        fields = '__all__'
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by', 'size_bytes', 'mime_type', 'original_name']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if not obj.file:
            return ''
        try:
            url = obj.file.url
        except Exception:
            return ''
        return request.build_absolute_uri(url) if request else url


class DefectSerializer(serializers.ModelSerializer):
    """缺陷序列化器（嵌套附件）。"""
    attachments = DefectAttachmentSerializer(many=True, read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, default='')
    reported_by_name = serializers.CharField(source='reported_by.username', read_only=True, default='')
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, default='')

    class Meta:
        model = Defect
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'reported_by']


class ReleaseConclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseConclusion
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
