from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import KnowledgeGraphStatusView, KnowledgeGraphViewSet, ProjectOverviewView

router = DefaultRouter()
router.register(r"", KnowledgeGraphViewSet, basename="knowledge-graph")

urlpatterns = [
    path("status/", KnowledgeGraphStatusView.as_view(), name="kg-status"),
    # 2026-07-24 项目概览（配置中心 /configuration/project-overview 页面用）
    path("project-overview/", ProjectOverviewView.as_view(), name="kg-project-overview"),
    path("", include(router.urls)),
]
