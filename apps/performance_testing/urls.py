# -*- coding: utf-8 -*-
"""性能测试路由。"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PerformanceScriptViewSet,
    PerformanceExecutionViewSet,
    PerformanceDashboardViewSet,
    PerformanceReportViewSet,
    PerformanceScheduledTaskViewSet,
    PerformanceConfigViewSet,
    PerformanceBatchExecutionViewSet,
    PerformanceBaselineViewSet,
    PerformanceComparisonReportViewSet,
    SharedReportView,
    SharedReportFileView,
)

router = DefaultRouter()
router.register(r"scripts", PerformanceScriptViewSet, basename="perf-script")
router.register(r"executions", PerformanceExecutionViewSet, basename="perf-execution")
router.register(r"batch-executions", PerformanceBatchExecutionViewSet, basename="perf-batch")
router.register(r"dashboard", PerformanceDashboardViewSet, basename="perf-dashboard")
router.register(r"reports", PerformanceReportViewSet, basename="perf-report")
router.register(r"scheduled-tasks", PerformanceScheduledTaskViewSet, basename="perf-scheduled-task")
router.register(r"config", PerformanceConfigViewSet, basename="perf-config")
router.register(r"baselines", PerformanceBaselineViewSet, basename="perf-baseline")
router.register(r"comparison-reports", PerformanceComparisonReportViewSet, basename="perf-comparison-report")

urlpatterns = [
    # 报告分享直链：公开只读，凭 share_token 访问（无需登录）
    path("shared/<str:token>/report/", SharedReportView.as_view(), name="perf-shared-report"),
    path("shared/<str:token>/report_file/", SharedReportFileView.as_view(), name="perf-shared-report-file"),
    path("", include(router.urls)),
]
