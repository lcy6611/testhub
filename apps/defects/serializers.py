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
        """返回相对路径 URL，便于前端走 Vite/Nginx 代理加载（避免 5173→8000 跨域）。

        前端拿到相对路径后，浏览器会以当前页面同源发起请求，
        经 Vite proxy (Docker 下 backend:8000) 转发到后端 media 服务。
        返回绝对路径在某些部署（IP vs localhost、不同端口）下会导致 img 加载失败。
        """
        if not obj.file:
            return ''
        try:
            url = obj.file.url
        except Exception:
            return ''
        # 去掉可能的 host 前缀，只保留 /media/...
        if url.startswith('http://') or url.startswith('https://'):
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.path or url
        return url


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
