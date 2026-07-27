# -*- coding: utf-8 -*-
"""性能测试后台管理。"""

from django.contrib import admin

from .models import (
    PerformanceScript,
    PerformanceExecution,
    PerformanceSummary,
    PerformanceMetric,
    PerformanceReport,
    PerformanceScheduledTask,
    PerformanceConfig,
)


@admin.register(PerformanceScript)
class PerformanceScriptAdmin(admin.ModelAdmin):
    list_display = ("name", "script_type", "status", "thread_count", "duration", "realtime_enabled", "created_by", "created_at")
    list_filter = ("script_type", "status", "realtime_enabled", "created_at")
    search_fields = ("name", "description")
    filter_horizontal = ("projects",)  # M2M 多项目
    raw_id_fields = ("created_by",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(PerformanceExecution)
class PerformanceExecutionAdmin(admin.ModelAdmin):
    list_display = ("execution_id", "script", "status", "thread_count", "duration", "started_at", "completed_at", "created_by")
    list_filter = ("status", "created_at")
    search_fields = ("execution_id", "script__name")
    raw_id_fields = ("script", "created_by")
    readonly_fields = ("execution_id", "created_at", "started_at", "completed_at", "jmx_path", "jtl_path", "report_path")


@admin.register(PerformanceSummary)
class PerformanceSummaryAdmin(admin.ModelAdmin):
    list_display = ("execution", "total_samples", "error_count", "error_rate", "p95", "throughput", "created_at")
    list_filter = ("created_at",)
    raw_id_fields = ("execution",)


@admin.register(PerformanceMetric)
class PerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ("execution", "sample_label", "sample_count", "error_rate", "p95", "throughput")
    list_filter = ("execution",)
    raw_id_fields = ("execution",)
    search_fields = ("sample_label",)


@admin.register(PerformanceReport)
class PerformanceReportAdmin(admin.ModelAdmin):
    list_display = ("name", "execution", "created_by", "created_at")
    list_filter = ("created_at",)
    search_fields = ("name",)
    raw_id_fields = ("execution", "created_by")


@admin.register(PerformanceScheduledTask)
class PerformanceScheduledTaskAdmin(admin.ModelAdmin):
    list_display = ("name", "script", "cron", "status", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "description")
    raw_id_fields = ("script", "created_by")


@admin.register(PerformanceConfig)
class PerformanceConfigAdmin(admin.ModelAdmin):
    list_display = ("jmeter_path", "realtime_report_enabled", "influxdb_url", "updated_at")
    readonly_fields = ("updated_at",)
