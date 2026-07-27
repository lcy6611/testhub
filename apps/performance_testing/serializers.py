# -*- coding: utf-8 -*-
"""性能测试序列化器。"""

from rest_framework import serializers

from apps.projects.models import Project

from .models import (
    PerformanceScript,
    PerformanceScriptCsvFile,
    PerformanceExecution,
    PerformanceSummary,
    PerformanceMetric,
    PerformanceScheduledTask,
    PerformanceConfig,
    PerformanceBatchExecution,
    PerformanceMonitorMetric,
)


class PerformanceScriptCsvFileSerializer(serializers.ModelSerializer):
    """脚本 CSV 附件。"""

    filename = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceScriptCsvFile
        fields = ["id", "filename", "url", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_filename(self, obj):
        import os
        return obj.original_name or os.path.basename(obj.file.name)

    def get_url(self, obj):
        request = self.context.get("request")
        if obj.file:
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class PerformanceScriptSerializer(serializers.ModelSerializer):
    """性能测试脚本。"""

    project_names = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    jmx_file_url = serializers.SerializerMethodField()
    execution_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    script_type_display = serializers.CharField(source="get_script_type_display", read_only=True)
    csv_files = PerformanceScriptCsvFileSerializer(many=True, read_only=True)

    class Meta:
        model = PerformanceScript
        fields = [
            "id",
            "name",
            "description",
            "projects",
            "project_names",
            "status",
            "status_display",
            "script_type",
            "script_type_display",
            "jmx_config",
            "jmx_content",
            "jmx_file",
            "jmx_file_url",
            "variables",
            "csv_datasets",
            "csv_files",
            "thread_count",
            "ramp_up",
            "duration",
            "realtime_enabled",
            "created_by",
            "created_by_name",
            "execution_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_by_name", "created_at", "updated_at"]

    def get_jmx_file_url(self, obj):
        if obj.jmx_file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.jmx_file.url)
            return obj.jmx_file.url
        return None

    def get_execution_count(self, obj):
        return obj.executions.count()

    def get_project_names(self, obj):
        return [p.name for p in obj.projects.all()]

    def validate(self, attrs):
        script_type = attrs.get("script_type") or (self.instance.script_type if self.instance else "ONLINE")
        if script_type == "JMX_UPLOAD":
            jmx_file = attrs.get("jmx_file") or (self.instance.jmx_file if self.instance else None)
            if not jmx_file:
                raise serializers.ValidationError({"jmx_file": "上传 JMX 创建模式必须上传 JMX 文件"})
        return attrs


class PerformanceExecutionSerializer(serializers.ModelSerializer):
    """性能测试执行记录。"""

    script_name = serializers.CharField(source="script.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    has_report = serializers.SerializerMethodField()
    has_jtl = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceExecution
        fields = [
            "id",
            "execution_id",
            "script",
            "script_name",
            "batch",
            "status",
            "status_display",
            "thread_count",
            "ramp_up",
            "duration",
            "realtime_enabled",
            "jmx_path",
            "jtl_path",
            "report_path",
            "jmeter_log",
            "error_message",
            "has_report",
            "has_jtl",
            "started_at",
            "completed_at",
            "created_by",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "execution_id",
            "status",
            "status_display",
            "jmx_path",
            "jtl_path",
            "jmeter_log",
            "report_path",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        ]

    def get_has_report(self, obj):
        import os
        return bool(obj.report_path and os.path.exists(os.path.join(obj.report_path, "index.html")))

    def get_has_jtl(self, obj):
        import os
        return bool(obj.jtl_path and os.path.exists(obj.jtl_path))


class PerformanceSummarySerializer(serializers.ModelSerializer):
    """执行汇总指标。"""

    class Meta:
        model = PerformanceSummary
        fields = "__all__"


class PerformanceMetricSerializer(serializers.ModelSerializer):
    """性能指标（按请求名分组）。"""

    class Meta:
        model = PerformanceMetric
        fields = "__all__"


class PerformanceMonitorMetricSerializer(serializers.ModelSerializer):
    """执行期间的服务器/服务资源监控指标。"""

    class Meta:
        model = PerformanceMonitorMetric
        fields = [
            "id", "execution", "target_name", "target_type",
            "metric_key", "metric_label", "metric_unit",
            "timeline", "min_value", "avg_value", "max_value", "peak_value",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ExecutionCreateSerializer(serializers.Serializer):
    """执行参数（覆盖脚本默认值）。"""

    thread_count = serializers.IntegerField(required=False, min_value=1)
    ramp_up = serializers.IntegerField(required=False, min_value=0)
    duration = serializers.IntegerField(required=False, min_value=1)
    realtime_enabled = serializers.BooleanField(required=False)


class JmxImportSerializer(serializers.Serializer):
    """导入 JMX 文件创建脚本。"""

    name = serializers.CharField(max_length=200, required=False)
    projects = serializers.ListField(child=serializers.IntegerField(), required=False)
    description = serializers.CharField(allow_blank=True, required=False)
    jmx_file = serializers.FileField(required=True)
    realtime_enabled = serializers.BooleanField(required=False, default=False)


class JmxDangerCheckSerializer(serializers.Serializer):
    """JMX 危险组件检测结果。"""

    dangerous_components = serializers.ListField(child=serializers.CharField())
    warnings = serializers.ListField(child=serializers.CharField())


class PerformanceScheduledTaskSerializer(serializers.ModelSerializer):
    """性能定时任务序列化器。"""

    script_name = serializers.CharField(source="script.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = PerformanceScheduledTask
        fields = [
            "id", "name", "script", "script_name", "cron", "status", "status_display",
            "thread_count", "ramp_up", "duration", "realtime_enabled",
            "description", "created_by", "created_by_name", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_by_name", "created_at", "updated_at"]


class PerformanceConfigSerializer(serializers.ModelSerializer):
    """性能测试全局配置。"""

    class Meta:
        model = PerformanceConfig
        fields = [
            "id", "jmeter_path", "realtime_report_enabled",
            "influxdb_url", "influxdb_org", "influxdb_bucket", "influxdb_token",
            "influxdb_measurement", "influxdb_application",
            "max_threads", "max_duration",
            "prometheus_enabled", "prometheus_url", "prometheus_step", "monitor_targets",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]


# ==================== 批量执行 ====================

class PerformanceBatchExecutionSerializer(serializers.ModelSerializer):
    """批量执行记录。"""

    project_name = serializers.CharField(source="project.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    executions = serializers.SerializerMethodField()
    has_report = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceBatchExecution
        fields = [
            "id", "batch_id", "project", "project_name", "name", "status", "status_display",
            "total_scripts", "completed_scripts", "failed_scripts",
            "thread_count", "ramp_up", "duration", "realtime_enabled", "report_path",
            "error_message", "created_by", "created_by_name",
            "created_at", "completed_at", "executions", "has_report",
        ]
        read_only_fields = [
            "id", "batch_id", "status", "status_display",
            "total_scripts", "completed_scripts", "failed_scripts",
            "error_message", "created_by", "created_by_name",
            "created_at", "completed_at", "report_path",
        ]

    def get_executions(self, obj):
        execs = obj.executions.select_related("script", "created_by").all()
        return PerformanceExecutionSerializer(execs, many=True, context=self.context).data

    def get_has_report(self, obj):
        import os
        return bool(obj.report_path and os.path.exists(os.path.join(obj.report_path, "index.html")))


class BatchExecutionCreateSerializer(serializers.Serializer):
    """创建批量执行。"""

    project = serializers.IntegerField(required=False, allow_null=True)
    script_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    name = serializers.CharField(max_length=200, required=False)
    thread_count = serializers.IntegerField(required=False, min_value=1)
    ramp_up = serializers.IntegerField(required=False, min_value=0)
    duration = serializers.IntegerField(required=False, min_value=1)
    realtime_enabled = serializers.BooleanField(required=False)
