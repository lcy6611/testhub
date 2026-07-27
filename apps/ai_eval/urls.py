# -*- coding: utf-8 -*-
"""AI 评测与反馈闭环 — 路由。"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PromptVersionViewSet, AICallLogViewSet, EvalDatasetViewSet, EvalCaseViewSet,
    EvalRunViewSet, EvalResultViewSet, AiFeedbackViewSet, StatsView,
)

router = DefaultRouter()
router.register(r"prompt-versions", PromptVersionViewSet, basename="prompt-versions")
router.register(r"call-logs", AICallLogViewSet, basename="call-logs")
router.register(r"datasets", EvalDatasetViewSet, basename="datasets")
router.register(r"cases", EvalCaseViewSet, basename="cases")
router.register(r"runs", EvalRunViewSet, basename="runs")
router.register(r"results", EvalResultViewSet, basename="results")
router.register(r"feedbacks", AiFeedbackViewSet, basename="feedbacks")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", StatsView.as_view(), name="ai-eval-stats"),
]
