# -*- coding: utf-8 -*-
"""AI 评测与反馈闭环 — 视图。"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from .models import (
    PromptVersion, AICallLog, EvalDataset, EvalCase, EvalRun, EvalResult, AiFeedback,
)
from .serializers import (
    PromptVersionSerializer, AICallLogSerializer, EvalDatasetSerializer,
    EvalCaseSerializer, EvalRunSerializer, EvalResultSerializer, AiFeedbackSerializer,
)
from .services import aggregate_stats, start_eval_thread


class PromptVersionViewSet(viewsets.ModelViewSet):
    queryset = PromptVersion.objects.all()
    serializer_class = PromptVersionSerializer

    def get_queryset(self):
        qs = PromptVersion.objects.all()
        key = self.request.query_params.get("key")
        if key:
            qs = qs.filter(key=key)
        category = self.request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)
        return qs

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        pv = self.get_object()
        pv.is_active = True
        pv.save(update_fields=["is_active"])
        return Response(PromptVersionSerializer(pv).data)


class AICallLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AICallLog.objects.all()
    serializer_class = AICallLogSerializer

    def get_queryset(self):
        qs = AICallLog.objects.all()
        module = self.request.query_params.get("module")
        if module:
            qs = qs.filter(module=module)
        project_id = self.request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        days = self.request.query_params.get("days")
        if days and days.isdigit():
            from django.utils import timezone
            import datetime
            since = timezone.now() - datetime.timedelta(days=int(days))
            qs = qs.filter(created_at__gte=since)
        return qs


class EvalDatasetViewSet(viewsets.ModelViewSet):
    queryset = EvalDataset.objects.all()
    serializer_class = EvalDatasetSerializer


class EvalCaseViewSet(viewsets.ModelViewSet):
    queryset = EvalCase.objects.all()
    serializer_class = EvalCaseSerializer

    def get_queryset(self):
        qs = EvalCase.objects.all()
        dataset_id = self.request.query_params.get("dataset_id")
        if dataset_id:
            qs = qs.filter(dataset_id=dataset_id)
        return qs


class EvalRunViewSet(viewsets.ModelViewSet):
    queryset = EvalRun.objects.all()
    serializer_class = EvalRunSerializer

    def perform_create(self, serializer):
        run = serializer.save()
        start_eval_thread(run.id)

    @action(detail=True, methods=["get"])
    def results(self, request, pk=None):
        run = self.get_object()
        qs = run.results.all()
        return Response(EvalResultSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"])
    def rerun(self, request, pk=None):
        run = self.get_object()
        if run.status == "running":
            return Response({"detail": "运行中，请勿重复触发"}, status=status.HTTP_400_BAD_REQUEST)
        run.status = "pending"
        run.error = ""
        run.summary = ""
        run.save(update_fields=["status", "error", "summary"])
        start_eval_thread(run.id)
        return Response(EvalRunSerializer(run).data)


class EvalResultViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EvalResult.objects.all()
    serializer_class = EvalResultSerializer

    def get_queryset(self):
        qs = EvalResult.objects.all()
        run_id = self.request.query_params.get("run_id")
        if run_id:
            qs = qs.filter(run_id=run_id)
        return qs


class AiFeedbackViewSet(viewsets.ModelViewSet):
    queryset = AiFeedback.objects.all()
    serializer_class = AiFeedbackSerializer

    @action(detail=True, methods=["post"])
    def convert_to_case(self, request, pk=None):
        fb = self.get_object()
        dataset_id = request.data.get("dataset_id")
        if not dataset_id:
            return Response({"detail": "请提供 dataset_id"}, status=status.HTTP_400_BAD_REQUEST)
        dataset = get_object_or_404(EvalDataset, id=dataset_id)
        name = (fb.comment or f"来自反馈#{fb.id}")[:200]
        case = EvalCase.objects.create(
            dataset=dataset,
            name=name,
            input_text=fb.comment or "",
            expected_output=fb.correction or "",
            criteria="由人工反馈转化，重点校验与修正内容一致。",
        )
        fb.converted_to_case = True
        fb.save(update_fields=["converted_to_case"])
        return Response(EvalCaseSerializer(case).data, status=status.HTTP_201_CREATED)


class StatsView(APIView):
    """效果看板聚合数据。"""
    def get(self, request):
        project_id = request.query_params.get("project_id")
        days = request.query_params.get("days", "30")
        try:
            days = int(days)
        except ValueError:
            days = 30
        pid = int(project_id) if project_id and project_id.isdigit() else None
        data = aggregate_stats(project_id=pid, days=days)
        return Response(data)
