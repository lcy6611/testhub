# -*- coding: utf-8 -*-
"""知识中枢 URL 路由。"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    KnowledgeHubConfigViewSet,
    NativeKbDocumentViewSet,
    NativeKbViewSet,
    KbSourceViewSet,
    DifyKbBindingViewSet,
)

router = DefaultRouter()
router.register(r"config", KnowledgeHubConfigViewSet, basename="kb-hub-config")
router.register(r"native-kbs", NativeKbViewSet, basename="kb-hub-native-kb")
router.register(r"native-docs", NativeKbDocumentViewSet, basename="kb-hub-native-doc")
router.register(r"kb-sources", KbSourceViewSet, basename="kb-hub-source")
router.register(r"dify-kb-bindings", DifyKbBindingViewSet, basename="kb-hub-dify-binding")

urlpatterns = [
    # 单例配置：/config/ 集合 URL 上同时支持 GET 读取 + PUT/PATCH 写入（无需 pk）
    path("config/", KnowledgeHubConfigViewSet.as_view({
        "get": "list",
        "put": "save_singleton",
        "patch": "save_singleton",
    })),
    path("", include(router.urls)),
]
