from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from django.db import models
from .models import TestCase, TestCaseStep, TestCaseAttachment, TestCaseComment, CaseAnalysis
from .serializers import (
    TestCaseSerializer, TestCaseCreateSerializer, TestCaseUpdateSerializer
)
from apps.projects.models import Project


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def analyze_case(request):
    """AI 深入分析用例：补充步骤 / 风险点 / 总结。

    请求体：
    {
      "testcase_id": 12,           // 可选：基于已存用例分析
      "requirement_id": 3,         // 可选：作为上下文的关联需求
      "ai_model_id": 1,            // 可选：指定 AIModelConfig；不传则取 role=writer 的活跃配置
      "title": "...",              // 草稿时必填
      "description": "...",
      "preconditions": "...",
      "steps": [{"action":"...","expected":"..."}]   // 草稿时必填
    }
    """
    data = request.data or {}
    testcase = None
    title = (data.get('title') or '').strip()
    description = data.get('description') or ''
    preconditions = data.get('preconditions') or ''
    steps = data.get('steps') or []

    testcase_id = data.get('testcase_id')
    if testcase_id:
        try:
            testcase = TestCase.objects.get(pk=testcase_id)
        except TestCase.DoesNotExist:
            return Response({'detail': '用例不存在'}, status=400)
        title = title or testcase.title
        description = description or testcase.description
        preconditions = preconditions or testcase.preconditions
        if not steps:
            steps = [
                {'action': s.action, 'expected': s.expected}
                for s in testcase.step_details.all().order_by('step_number')
            ]

    if not title:
        return Response({'detail': 'title 必填'}, status=400)
    if not steps:
        return Response({'detail': 'steps 必填（至少一条）'}, status=400)

    # 取 AI 模型
    from apps.requirement_analysis.models import AIModelConfig
    ai_model = None
    ai_model_id = data.get('ai_model_id')
    if ai_model_id:
        try:
            ai_model = AIModelConfig.objects.get(pk=ai_model_id, is_active=True)
        except AIModelConfig.DoesNotExist:
            pass
    if not ai_model:
        ai_model = AIModelConfig.objects.filter(role='writer', is_active=True).first()
    if not ai_model:
        return Response({'detail': '未找到可用的 AI 模型（role=writer 需激活）'}, status=400)

    requirement = None
    rid = data.get('requirement_id') or (testcase.requirement_id if testcase and testcase.requirement_id else None)
    if rid:
        from apps.requirement_analysis.models import BusinessRequirement
        try:
            requirement = BusinessRequirement.objects.get(pk=rid)
        except BusinessRequirement.DoesNotExist:
            pass

    import asyncio
    from .ai_analysis import analyze_case_with_ai
    result = asyncio.run(analyze_case_with_ai(
        title=title,
        description=description,
        preconditions=preconditions,
        steps=steps,
        ai_model=ai_model,
        requirement=requirement,
    ))

    # 落库
    record = CaseAnalysis.objects.create(
        testcase=testcase,
        requirement=requirement,
        ai_model=ai_model,
        input_steps=steps,
        prompt=result.get('prompt', '')[:8000],
        suggestions=result.get('suggestions', []),
        risks=result.get('risks', []),
        summary=result.get('summary', ''),
        tokens_used=result.get('tokens_used', 0),
        elapsed_ms=result.get('elapsed_ms', 0),
        created_by=request.user,
    )
    return Response({
        'id': record.id,
        'summary': record.summary,
        'suggestions': record.suggestions,
        'risks': record.risks,
        'tokens_used': record.tokens_used,
        'elapsed_ms': record.elapsed_ms,
        'ai_model': ai_model.name,
        'error': result.get('error', False),
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def list_case_analyses(request):
    """查询某用例的 AI 分析记录列表。"""
    testcase_id = request.query_params.get('testcase_id')
    qs = CaseAnalysis.objects.all()
    if testcase_id:
        qs = qs.filter(testcase_id=testcase_id)
    data = [{
        'id': a.id,
        'summary': a.summary,
        'suggestions_count': len(a.suggestions or []),
        'risks_count': len(a.risks or []),
        'ai_model': a.ai_model.name if a.ai_model else '',
        'tokens_used': a.tokens_used,
        'elapsed_ms': a.elapsed_ms,
        'created_at': a.created_at.isoformat(),
    } for a in qs[:20]]
    return Response(data)

class TestCaseListCreateView(generics.ListCreateAPIView):
    queryset = TestCase.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['priority', 'status', 'test_type', 'project']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TestCaseCreateSerializer
        return TestCaseSerializer
    
    def get_queryset(self):
        # 取消用户隔离：所有登录用户可见全部测试用例
        return TestCase.objects.all()
    
    def get_user_accessible_projects(self, user):
        """获取用户有权限访问的项目"""
        return Project.objects.filter(
            models.Q(owner=user) | models.Q(members=user)
        ).distinct()
    
    def perform_create(self, serializer):
        user = self.request.user
        project_id = self.request.data.get('project_id')
        project = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
            except Project.DoesNotExist:
                project = None
        if project is None:
            project = Project.objects.first()
        if project is None:
            project = Project.objects.create(
                name="默认项目",
                owner=user,
                description='系统自动创建的默认项目'
            )
        
        serializer.save(author=user, project=project)

class TestCaseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TestCase.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return TestCaseUpdateSerializer
        return TestCaseSerializer
    
    def get_queryset(self):
        # 取消用户隔离：所有登录用户可见全部测试用例
        return TestCase.objects.all()
    
    def get_user_accessible_projects(self, user):
        """获取用户有权限访问的项目"""
        return Project.objects.filter(
            models.Q(owner=user) | models.Q(members=user)
        ).distinct()
    
    def perform_update(self, serializer):
        user = self.request.user
        project_id = self.request.data.get('project_id')
        
        if project_id:
            # 检查指定的项目是否存在且用户有权限
            accessible_projects = self.get_user_accessible_projects(user)
            try:
                project = accessible_projects.get(id=project_id)
                serializer.save(project=project)
            except Project.DoesNotExist:
                # 如果指定项目不存在或无权限，保持原项目不变
                serializer.save()
        else:
            # 没有指定项目，保持原项目不变
            serializer.save()
