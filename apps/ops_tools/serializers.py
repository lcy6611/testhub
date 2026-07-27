from rest_framework import serializers
from .models import OpsEnvironment, Text2SQLRecord, LogQuerySession, FileTransferTask


class OpsEnvironmentSerializer(serializers.ModelSerializer):
    access_method_display = serializers.CharField(source='get_access_method_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    db_type_display = serializers.CharField(source='get_db_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)

    class Meta:
        model = OpsEnvironment
        fields = [
            'id', 'name', 'category', 'access_method', 'access_method_display',
            'host', 'port', 'username', 'password', 'ssh_key',
            'db_type', 'db_type_display', 'db_name', 'db_host', 'db_port',
            'db_username', 'db_password', 'database_scope', 'current_dir',
            'status', 'status_display', 'last_sync', 'project', 'project_name',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_by_name', 'last_sync']
        extra_kwargs = {
            'password': {'write_only': True},
            'ssh_key': {'write_only': True},
            'db_password': {'write_only': True},
        }

    def create(self, validated_data):
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            validated_data['created_by'] = default_user
        return super().create(validated_data)


class Text2SQLRecordSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    mode_display = serializers.CharField(source='get_mode_display', read_only=True)
    environment_name = serializers.CharField(source='environment.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Text2SQLRecord
        fields = [
            'id', 'environment', 'environment_name', 'mode', 'mode_display',
            'question', 'generated_sql', 'validated_sql', 'result', 'status',
            'status_display', 'error_message', 'created_by', 'created_by_name', 'created_at',
        ]
        read_only_fields = ['created_by', 'created_by_name', 'generated_sql', 'result']

    def create(self, validated_data):
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            validated_data['created_by'] = default_user
        return super().create(validated_data)


class LogQuerySessionSerializer(serializers.ModelSerializer):
    environment_name = serializers.CharField(source='environment.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = LogQuerySession
        fields = [
            'id', 'environment', 'environment_name', 'log_dir', 'current_file',
            'content', 'keywords', 'tail_lines', 'is_realtime',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_by', 'created_by_name', 'content']

    def create(self, validated_data):
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            validated_data['created_by'] = default_user
        return super().create(validated_data)


class FileTransferTaskSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    direction_display = serializers.CharField(source='get_direction_display', read_only=True)
    environment_name = serializers.CharField(source='environment.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    local_file_url = serializers.SerializerMethodField()

    class Meta:
        model = FileTransferTask
        fields = [
            'id', 'name', 'environment', 'environment_name', 'direction', 'direction_display',
            'remote_path', 'local_file', 'local_file_url', 'size', 'status', 'status_display',
            'error_message', 'created_by', 'created_by_name', 'created_at', 'completed_at',
        ]
        read_only_fields = ['created_by', 'created_by_name', 'size', 'status', 'completed_at']

    def get_local_file_url(self, obj):
        request = self.context.get('request')
        if obj.local_file:
            if request:
                return request.build_absolute_uri(obj.local_file.url)
            return obj.local_file.url
        return None

    def create(self, validated_data):
        user = self.context['request'].user
        if user.is_authenticated:
            validated_data['created_by'] = user
        else:
            from apps.users.models import User
            default_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
            validated_data['created_by'] = default_user
        return super().create(validated_data)
