from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import models
from .models import Project, ProjectMember, ProjectEnvironment
from .serializers import ProjectSerializer, ProjectCreateSerializer, ProjectMemberSerializer, ProjectEnvironmentSerializer
from .project_sync import auto_sync_project_create, auto_sync_project_update, auto_sync_project_delete

class ProjectListCreateView(generics.ListCreateAPIView):
    queryset = Project.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'owner']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProjectCreateSerializer
        return ProjectSerializer
    
    def get_queryset(self):
        # 取消用户隔离：所有登录用户可见全部项目
        return Project.objects.all()

    def perform_create(self, serializer):
        instance = serializer.save()
        auto_sync_project_create(instance, 'core')

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_all_projects(request):
    """获取所有项目列表，用于下拉选择等场景"""
    projects = Project.objects.all().values('id', 'name', 'description', 'status')
    return Response(list(projects))

class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_update(self, serializer):
        instance = serializer.save()
        auto_sync_project_update(instance, 'core')

    def perform_destroy(self, instance):
        auto_sync_project_delete(instance, 'core')
        instance.delete()

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def add_project_member(request, project_id):
    try:
        project = Project.objects.get(id=project_id)
        
        serializer = ProjectMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Project.DoesNotExist:
        return Response({'error': '项目不存在'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_project_members(request, project_id):
    """获取项目成员列表"""
    try:
        project = Project.objects.get(id=project_id)
        
        # 获取项目成员，包括项目所有者
        members = []
        
        # 添加项目所有者
        members.append({
            'id': project.owner.id,
            'username': project.owner.username,
            'email': project.owner.email,
            'first_name': project.owner.first_name,
            'last_name': project.owner.last_name,
            'role': 'owner'
        })
        
        # 添加项目成员
        project_members = ProjectMember.objects.filter(project=project).select_related('user')
        for member in project_members:
            members.append({
                'id': member.user.id,
                'username': member.user.username,
                'email': member.user.email,
                'first_name': member.user.first_name,
                'last_name': member.user.last_name,
                'role': member.role
            })
        
        return Response(members)
    except Project.DoesNotExist:
        return Response({'error': '项目不存在'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def remove_project_member(request, project_id, member_id):
    try:
        project = Project.objects.get(id=project_id)
        
        member = ProjectMember.objects.get(id=member_id, project=project)
        member.delete()
        return Response({'message': '成员删除成功'})
    except (Project.DoesNotExist, ProjectMember.DoesNotExist):
        return Response({'error': '项目或成员不存在'}, status=status.HTTP_404_NOT_FOUND)

class ProjectEnvironmentListCreateView(generics.ListCreateAPIView):
    serializer_class = ProjectEnvironmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        project_id = self.kwargs['project_id']
        return ProjectEnvironment.objects.filter(project_id=project_id)
    
    def perform_create(self, serializer):
        project_id = self.kwargs['project_id']
        serializer.save(project_id=project_id)