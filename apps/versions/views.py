from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import models
from .models import Version
from .serializers import VersionSerializer, VersionCreateSerializer
from apps.projects.models import Project

# 版本管理视图
class VersionListCreateView(generics.ListCreateAPIView):
    """版本列表和创建视图"""
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_baseline']  # 移除projects，手动处理
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return VersionCreateSerializer
        return VersionSerializer
    
    def get_queryset(self):
        # 取消用户隔离：所有登录用户可见全部版本
        queryset = Version.objects.all().distinct()
        
        # 手动处理项目筛选
        project_id = self.request.query_params.get('projects')
        if project_id and project_id.strip():  # 检查是否为空或空字符串
            try:
                project_id = int(project_id)
                queryset = queryset.filter(projects__id=project_id)
            except (ValueError, TypeError):
                # 如果无法转换为整数，忽略此筛选条件
                pass
        
        return queryset
    
    def perform_create(self, serializer):
        user = self.request.user
        project_ids = serializer.validated_data.get('project_ids')
        serializer.save(created_by=user)

class VersionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """版本详情视图"""
    serializer_class = VersionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Version.objects.all().distinct()

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_project_versions(request, project_id):
    """获取指定项目的版本列表"""
    versions = Version.objects.filter(projects__id=project_id).order_by('-created_at')
    serializer = VersionSerializer(versions, many=True)
    return Response(serializer.data)
