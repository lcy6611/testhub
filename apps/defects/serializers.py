from rest_framework import serializers
from .models import Defect, DefectAttachment, DefectTransitionLog, DefectComment, ReleaseConclusion


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


class DefectTransitionLogSerializer(serializers.ModelSerializer):
    """缺陷流转历史序列化器。"""
    operator_name = serializers.CharField(source='operator.username', read_only=True, default='')
    target_user_name = serializers.CharField(source='target_user.username', read_only=True, default='')
    from_status_display = serializers.CharField(source='get_from_status_display', read_only=True, default='')
    to_status_display = serializers.CharField(source='get_to_status_display', read_only=True, default='')

    class Meta:
        model = DefectTransitionLog
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class DefectCommentSerializer(serializers.ModelSerializer):
    """缺陷评论序列化器。"""
    author_name = serializers.CharField(source='author.username', read_only=True, default='')
    author_avatar = serializers.CharField(source='author.avatar', read_only=True, default='')

    class Meta:
        model = DefectComment
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'author']


class DefectSerializer(serializers.ModelSerializer):
    """缺陷序列化器（嵌套附件/评论/流转历史）。"""
    attachments = DefectAttachmentSerializer(many=True, read_only=True)
    comments = DefectCommentSerializer(many=True, read_only=True)
    transition_logs = DefectTransitionLogSerializer(many=True, read_only=True)

    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    defect_type_display = serializers.CharField(source='get_defect_type_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True, default='')

    project_name = serializers.CharField(source='project.name', read_only=True, default='')
    version_name = serializers.CharField(source='version.name', read_only=True, default='')
    reported_by_name = serializers.CharField(source='reported_by.username', read_only=True, default='')
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, default='')
    verifier_name = serializers.CharField(source='verifier.username', read_only=True, default='')
    resolver_name = serializers.CharField(source='resolver.username', read_only=True, default='')

    requirement_id = serializers.PrimaryKeyRelatedField(source='requirement', read_only=True, allow_null=True)
    requirement_title = serializers.CharField(source='requirement.title', read_only=True, default='')
    test_run_id = serializers.PrimaryKeyRelatedField(source='test_run', read_only=True, allow_null=True)
    related_testcase_id = serializers.PrimaryKeyRelatedField(source='related_testcase', read_only=True, allow_null=True)
    related_testcase_title = serializers.CharField(source='related_testcase.title', read_only=True, default='')

    class Meta:
        model = Defect
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'reported_by', 'bug_code', 'resolved_at', 'closed_at']


class ReleaseConclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReleaseConclusion
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
