from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from .models import Defect, DefectAttachment, ReleaseConclusion
from .serializers import DefectSerializer, DefectAttachmentSerializer, ReleaseConclusionSerializer
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

    @action(detail=True, methods=['post'], url_path='attachments', parser_classes=[MultiPartParser, FormParser, JSONParser])
    def upload_attachment(self, request, pk=None):
        """上传缺陷附件（截图/日志）。multipart/form-data 字段名=file。"""
        defect = self.get_object()
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': '缺少 file 字段'}, status=400)
        kind = request.data.get('kind', 'screenshot')
        caption = request.data.get('caption', '')
        att = DefectAttachment.objects.create(
            defect=defect,
            file=f,
            original_name=f.name,
            size_bytes=f.size,
            mime_type=f.content_type or '',
            kind=kind if kind in dict(DefectAttachment.KIND_CHOICES) else 'screenshot',
            caption=caption,
            uploaded_by=request.user,
        )
        return Response(DefectAttachmentSerializer(att, context={'request': request}).data, status=201)

    @action(detail=True, methods=['delete'], url_path='attachments/(?P<att_id>\\d+)')
    def delete_attachment(self, request, pk=None, att_id=None):
        """删除缺陷附件。"""
        defect = self.get_object()
        att = get_object_or_404(DefectAttachment, pk=att_id, defect=defect)
        att.file.delete(save=False)
        att.delete()
        return Response(status=204)


class DefectAttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    """缺陷附件查询（按 defect_id 过滤）。"""
    queryset = DefectAttachment.objects.all()
    serializer_class = DefectAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = DefectAttachment.objects.all()
        defect_id = self.request.query_params.get('defect')
        if defect_id:
            qs = qs.filter(defect_id=defect_id)
        return qs


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
