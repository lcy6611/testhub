from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.utils import timezone

from .models import Defect, DefectAttachment, DefectTransitionLog, DefectComment, ReleaseConclusion
from .serializers import (
    DefectSerializer, DefectAttachmentSerializer, ReleaseConclusionSerializer,
    DefectTransitionLogSerializer, DefectCommentSerializer,
)
from .services import compute_requirement_coverage, evaluate_quality_gate


class DefectViewSet(viewsets.ModelViewSet):
    """缺陷 CRUD + 按项目/状态/优先级等过滤 + 关联执行用例 + 流转/评论/统计。"""
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
        priority = self.request.query_params.get('priority')
        if priority:
            qs = qs.filter(priority=priority)
        defect_type = self.request.query_params.get('defect_type')
        if defect_type:
            qs = qs.filter(defect_type=defect_type)
        module = self.request.query_params.get('module')
        if module:
            qs = qs.filter(module=module)
        assigned_to = self.request.query_params.get('assigned_to')
        if assigned_to:
            qs = qs.filter(assigned_to_id=assigned_to)
        verifier = self.request.query_params.get('verifier')
        if verifier:
            qs = qs.filter(verifier_id=verifier)
        resolver = self.request.query_params.get('resolver')
        if resolver:
            qs = qs.filter(resolver_id=resolver)
        requirement_id = self.request.query_params.get('requirement')
        if requirement_id:
            qs = qs.filter(requirement_id=requirement_id)
        test_run_id = self.request.query_params.get('test_run')
        if test_run_id:
            qs = qs.filter(test_run_id=test_run_id)
        related_testcase = self.request.query_params.get('related_testcase')
        if related_testcase:
            qs = qs.filter(related_testcase_id=related_testcase)
        bug_code = self.request.query_params.get('bug_code')
        if bug_code:
            qs = qs.filter(bug_code=bug_code)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(bug_code__icontains=search))
        return qs

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='transition')
    def transition(self, request, pk=None):
        """状态流转：更新状态并落一条 DefectTransitionLog。"""
        defect = self.get_object()
        to_status = request.data.get('to_status')
        if not to_status:
            return Response({'detail': 'to_status 必填'}, status=400)
        valid = dict(Defect.STATUS_CHOICES)
        if to_status not in valid:
            return Response({'detail': f'非法状态：{to_status}'}, status=400)
        from_status = defect.status
        if from_status == to_status:
            return Response({'detail': '状态未变化'}, status=400)
        comment = request.data.get('comment', '')
        target_user_id = request.data.get('target_user')
        defect.status = to_status
        now = timezone.now()
        if to_status in ('resolved', 'fixed') and not defect.resolved_at:
            defect.resolved_at = now
        if to_status == 'closed' and not defect.closed_at:
            defect.closed_at = now
        if to_status in ('open', 'reopened', 'new'):
            # 重新打开则清除解决/关闭时间，便于重新统计
            if to_status == 'reopened':
                defect.resolved_at = None
                defect.closed_at = None
        defect.save()
        log = DefectTransitionLog.objects.create(
            defect=defect,
            from_status=from_status,
            to_status=to_status,
            operator=request.user,
            target_user_id=target_user_id if target_user_id else None,
            comment=comment,
        )
        return Response({
            'defect': DefectSerializer(defect, context={'request': request}).data,
            'transition': DefectTransitionLogSerializer(log).data,
        })

    @action(detail=True, methods=['get', 'post'], url_path='comments')
    def comments(self, request, pk=None):
        """列出评论 / 发表评论。"""
        defect = self.get_object()
        if request.method == 'GET':
            qs = defect.comments.all()
            return Response(DefectCommentSerializer(qs, many=True).data)
        content = (request.data.get('content') or '').strip()
        if not content:
            return Response({'detail': '评论内容不能为空'}, status=400)
        comment = DefectComment.objects.create(
            defect=defect, author=request.user, content=content
        )
        return Response(DefectCommentSerializer(comment).data, status=201)

    @action(detail=True, methods=['delete'], url_path='comments/(?P<comment_id>\\d+)')
    def delete_comment(self, request, pk=None, comment_id=None):
        """删除评论。"""
        defect = self.get_object()
        comment = get_object_or_404(DefectComment, pk=comment_id, defect=defect)
        comment.delete()
        return Response(status=204)

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

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """统计：按状态/优先级/类型/模块/人员分布 + 趋势（按天新建/关闭）。"""
        qs = Defect.objects.all()
        project_id = request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        requirement_id = request.query_params.get('requirement')
        if requirement_id:
            qs = qs.filter(requirement_id=requirement_id)

        def counter(field):
            rows = qs.values(field).annotate(count=Count('id'))
            return [{'value': r[field], 'count': r['count']} for r in rows]

        # 人员分布（处理人）
        assignee_rows = qs.filter(assigned_to__isnull=False).values(
            'assigned_to', 'assigned_to__username'
        ).annotate(count=Count('id'))
        assignee_dist = [
            {'user_id': r['assigned_to'], 'username': r['assigned_to__username'], 'count': r['count']}
            for r in assignee_rows
        ]

        # 模块分布
        module_rows = qs.filter(module__gt='').values('module').annotate(count=Count('id'))
        module_dist = [{'module': r['module'], 'count': r['count']} for r in module_rows]

        # 趋势：最近 30 天新建/关闭数
        days = int(request.query_params.get('days', 30))
        days = max(1, min(days, 180))
        end = timezone.localdate()
        start = end - timezone.timedelta(days=days - 1)
        trend = []
        for i in range(days):
            day = start + timezone.timedelta(days=i)
            next_day = day + timezone.timedelta(days=1)
            created = qs.filter(created_at__gte=day, created_at__lt=next_day).count()
            closed = qs.filter(closed_at__gte=day, closed_at__lt=next_day).count()
            resolved = qs.filter(resolved_at__gte=day, resolved_at__lt=next_day).count()
            trend.append({'date': day.isoformat(), 'created': created, 'closed': closed, 'resolved': resolved})

        return Response({
            'total': qs.count(),
            'by_status': counter('status'),
            'by_priority': counter('priority'),
            'by_type': counter('defect_type'),
            'by_assignee': assignee_dist,
            'by_module': module_dist,
            'trend': trend,
        })


class DefectCommentViewSet(viewsets.ReadOnlyModelViewSet):
    """缺陷评论查询（按 defect 过滤）。"""
    queryset = DefectComment.objects.all()
    serializer_class = DefectCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = DefectComment.objects.all()
        defect_id = self.request.query_params.get('defect')
        if defect_id:
            qs = qs.filter(defect_id=defect_id)
        return qs


class DefectTransitionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """缺陷流转历史查询（按 defect 过滤）。"""
    queryset = DefectTransitionLog.objects.all()
    serializer_class = DefectTransitionLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = DefectTransitionLog.objects.all()
        defect_id = self.request.query_params.get('defect')
        if defect_id:
            qs = qs.filter(defect_id=defect_id)
        return qs


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
