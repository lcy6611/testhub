# -*- coding: utf-8 -*-
"""APP自动化项目管理视图"""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
import logging

from .test_case_views import AppPagination
from ..models import AppProject
from ..serializers import (
    AppProjectSerializer,
    AppProjectCreateSerializer,
    AppProjectUpdateSerializer,
)

logger = logging.getLogger(__name__)


class AppProjectViewSet(viewsets.ModelViewSet):
    """APP自动化项目 ViewSet"""
    queryset = AppProject.objects.all()
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'owner']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return AppProjectCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return AppProjectUpdateSerializer
        return AppProjectSerializer

    def get_queryset(self):
        # 取消用户隔离：所有登录用户可见全部项目
        return AppProject.objects.all()

    def perform_create(self, serializer):
        instance = serializer.save(owner=self.request.user)
        # 跨模块同步
        from apps.projects.project_sync import auto_sync_project_create
        auto_sync_project_create(instance, 'app_automation')

    def perform_update(self, serializer):
        instance = serializer.save()
        # 跨模块同步
        from apps.projects.project_sync import auto_sync_project_update
        auto_sync_project_update(instance, 'app_automation')

    def perform_destroy(self, instance):
        # 跨模块级联删除
        from apps.projects.project_sync import auto_sync_project_delete
        auto_sync_project_delete(instance, 'app_automation')
        instance.delete()
