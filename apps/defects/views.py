from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Defect, ReleaseConclusion
from .serializers import DefectSerializer, ReleaseConclusionSerializer
from .services import compute_requirement_coverage, evaluate_quality_gate


class DefectViewSet(viewsets.ModelViewSet):
    """缺陷 CRUD + 按项目/状态过滤 + 关联执行用例。"""
    queryset = Defect.objects.all()
    serializer_class = DefectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Defect.objects.all()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        requirement_id = self.request.query_params.get('requirement')
        if requirement_id:
            qs = qs.filter(requirement_id=requirement_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)


class ReleaseConclusionViewSet(viewsets.ModelViewSet):
    """发布结论（质量门禁评估结果）查询与保存。"""
    queryset = ReleaseConclusion.objects.all()
    serializer_class = ReleaseConclusionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = ReleaseConclusion.objects.all()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(approver=self.request.user)


class RequirementCoverageView(APIView):
    """需求三层覆盖率：需求→用例→执行→通过。"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get('project')
        version_id = request.query_params.get('version')
        if not project_id:
            return Response({'detail': 'project 参数必填'}, status=400)
        data = compute_requirement_coverage(
            int(project_id), int(version_id) if version_id else None
        )
        return Response(data)


class QualityGateView(APIView):
    """质量门禁：GET 评估；POST 评估并保存发布结论。"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        project_id = request.query_params.get('project')
        version_id = request.query_params.get('version')
        test_run_id = request.query_params.get('test_run')
        if not project_id:
            return Response({'detail': 'project 参数必填'}, status=400)
        result = evaluate_quality_gate(
            int(project_id),
            int(version_id) if version_id else None,
            int(test_run_id) if test_run_id else None,
        )
        return Response(result)

    def post(self, request):
        project_id = request.data.get('project')
        if not project_id:
            return Response({'detail': 'project 参数必填'}, status=400)
        version_id = request.data.get('version')
        test_run_id = request.data.get('test_run')

        evaluation = evaluate_quality_gate(
            int(project_id),
            int(version_id) if version_id else None,
            int(test_run_id) if test_run_id else None,
        )
        conclusion = request.data.get('conclusion') or evaluation['conclusion']
        rc = ReleaseConclusion.objects.create(
            project_id=project_id,
            version_id=version_id or None,
            test_run_id=test_run_id or None,
            conclusion=conclusion,
            metrics=evaluation['metrics'],
            reasons=evaluation['reasons'],
            thresholds=evaluation['thresholds'],
            note=request.data.get('note', ''),
            approver=request.user,
        )
        return Response(
            ReleaseConclusionSerializer(rc).data, status=status.HTTP_201_CREATED
        )
