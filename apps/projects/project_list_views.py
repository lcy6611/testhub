from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import models
from .models import Project

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_projects_list(request):
    """获取项目列表（取消用户隔离）"""
    projects = Project.objects.all().values('id', 'name', 'status').order_by('name')
    
    return Response({
        'results': list(projects)
    })