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

urlpatterns = [
    path("", include(router.urls)),
]
