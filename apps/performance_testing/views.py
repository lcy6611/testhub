# -*- coding: utf-8 -*-
"""性能测试视图集。"""

import logging
import os
import re
import uuid

import requests

from django.conf import settings
from django.http import HttpResponse, FileResponse, Http404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication


class QueryJWTAuthentication(JWTAuthentication):
    """支持从 URL query 参数 ?token= 读取 JWT，便于 iframe 直接访问 HTML 报告。"""

    def authenticate(self, request):
        token = request.query_params.get("token")
        if token:
            request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        return super().authenticate(request)

from .models import (
    PerformanceScript,
    PerformanceScriptCsvFile,
    PerformanceExecution,
    PerformanceSummary,
    PerformanceMetric,
    PerformanceReport,
    PerformanceScheduledTask,
    PerformanceConfig,
    PerformanceBatchExecution,
    PerformanceBaseline,
    PerformanceComparisonReport,
)
from .serializers import (
    PerformanceScriptSerializer,
    PerformanceScriptCsvFileSerializer,
    PerformanceExecutionSerializer,
    PerformanceSummarySerializer,
    PerformanceMetricSerializer,
    PerformanceMonitorMetricSerializer,
    ExecutionCreateSerializer,
    JmxImportSerializer,
    PerformanceScheduledTaskSerializer,
    PerformanceConfigSerializer,
    PerformanceBatchExecutionSerializer,
    BatchExecutionCreateSerializer,
    PerformanceBaselineSerializer,
    PerformanceComparisonReportSerializer,
    ComparisonReportCreateSerializer,
)
from .executor import create_execution, validate_load, create_batch_execution
from .influxdb_client import query_realtime, is_enabled as realtime_enabled
from .jmx_builder import detect_dangerous_components, JMeterPlanBuilder, parse_jmx_to_config
from . import baseline as baseline_service
from . import comparison as comparison_service

logger = logging.getLogger(__name__)


class PerformanceScriptViewSet(viewsets.ModelViewSet):
    """性能测试脚本 CRUD。"""

    queryset = PerformanceScript.objects.prefetch_related("projects").select_related("created_by").all()
    serializer_class = PerformanceScriptSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["script_type", "status", "created_by"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at", "name"]

    def get_queryset(self):
        qs = self.queryset
        project = self.request.query_params.get("project")
        if project:
            qs = qs.filter(projects__id=project)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        """删除脚本时一并清理磁盘上的 jmx 与 csv 文件。"""
        import shutil

        if instance.jmx_file:
            try:
                instance.jmx_file.delete(save=False)
            except Exception:
                logger.exception("删除脚本 jmx 文件失败 %s", instance.id)
        for cf in PerformanceScriptCsvFile.objects.filter(script=instance):
            try:
                cf.file.delete(save=False)
            except Exception:
                logger.exception("删除脚本 csv 文件失败 %s", instance.id)
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def execute(self, request, pk=None):
        """触发执行（可覆盖线程数/持续时间等参数）。"""
        script = self.get_object()
        ser = ExecutionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            execution = create_execution(
                script,
                created_by=request.user,
                thread_count=data.get("thread_count"),
                ramp_up=data.get("ramp_up"),
                duration=data.get("duration"),
                realtime_enabled=data.get("realtime_enabled"),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            PerformanceExecutionSerializer(execution, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def check_jmx(self, request, pk=None):
        """检测已上传 JMX 的危险组件。"""
        script = self.get_object()
        if script.script_type != "JMX_UPLOAD" or not script.jmx_file:
            return Response({"detail": "非 JMX 上传模式或文件未上传"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            with open(script.jmx_file.path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            return Response({"detail": f"读取 JMX 失败: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        dangerous = detect_dangerous_components(content)
        warnings = []
        if dangerous:
            warnings.append(f"检测到危险组件: {', '.join(dangerous)}，请确认脚本安全性")
        return Response({"dangerous_components": dangerous, "warnings": warnings})

    @action(detail=True, methods=["post"], url_path="parse-to-online")
    def parse_to_online(self, request, pk=None):
        """将上传的 JMX 解析为在线编排配置，并切换脚本模式为 ONLINE。"""
        script = self.get_object()
        if script.script_type != "JMX_UPLOAD" or not script.jmx_file:
            return Response({"detail": "仅支持已上传 JMX 的脚本"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            config = parse_jmx_to_config(script.jmx_file.path)
        except Exception as exc:
            logger.exception("JMX 解析失败")
            return Response({"detail": f"JMX 解析失败: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

        dangerous = detect_dangerous_components(
            open(script.jmx_file.path, "r", encoding="utf-8", errors="ignore").read()
        )
        warnings = []
        if dangerous:
            warnings.append(f"检测到危险组件: {', '.join(dangerous)}，请确认脚本安全性")

        script.script_type = "ONLINE"
        script.jmx_config = config
        script.variables = config.get("variables", [])
        script.csv_datasets = config.get("csv_datasets", [])
        if config.get("thread_groups"):
            tg = config["thread_groups"][0]
            script.thread_count = tg.get("thread_count", script.thread_count)
            script.ramp_up = tg.get("ramp_up", script.ramp_up)
            script.duration = tg.get("duration", script.duration)
        script.save()
        return Response({
            "detail": "已解析为在线编排模式",
            "warnings": warnings,
            "script": PerformanceScriptSerializer(script, context={"request": request}).data,
        })

    @action(detail=True, methods=["get"])
    def export_jmx(self, request, pk=None):
        """导出 JMX 文件内容（在线编排/纯 JMX 模式）。"""
        script = self.get_object()
        if script.script_type == "JMX_RAW":
            content = script.jmx_content or ""
        elif script.script_type == "ONLINE":
            builder = JMeterPlanBuilder()
            import tempfile
            jmx_path = builder.build(
                script.jmx_config or {},
                thread_count=script.thread_count,
                ramp_up=script.ramp_up,
                duration=script.duration,
                output_dir=tempfile.mkdtemp(prefix="perf_export_"),
            )
            with open(jmx_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        else:
            if not script.jmx_file or not os.path.exists(script.jmx_file.path):
                raise Http404("JMX 文件不存在")
            with open(script.jmx_file.path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        return HttpResponse(content, content_type="application/xml")

    @action(detail=False, methods=["post"])
    def import_jmx(self, request):
        """导入 JMX 文件创建脚本。"""
        ser = JmxImportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        project_ids = data.get("projects") or []
        projects = []
        if project_ids:
            from apps.projects.models import Project
            projects = list(Project.objects.filter(id__in=project_ids))

        script = PerformanceScript.objects.create(
            name=data.get("name") or data["jmx_file"].name,
            description=data.get("description", ""),
            script_type="JMX_UPLOAD",
            jmx_file=data["jmx_file"],
            realtime_enabled=data.get("realtime_enabled", False),
            created_by=request.user,
        )
        if projects:
            script.projects.set(projects)
        return Response(
            PerformanceScriptSerializer(script, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def load_limits(self, request):
        """返回负载上限配置。"""
        from .executor import _max_threads, _max_duration
        return Response({
            "max_threads": _max_threads(),
            "max_duration": _max_duration(),
        })

    @action(detail=True, methods=["post"], url_path="upload-csv")
    def upload_csv(self, request, pk=None):
        """上传 CSV 附件到脚本。"""
        script = self.get_object()
        files = request.FILES.getlist("files")
        if not files:
            return Response({"detail": "请选择 CSV 文件"}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        for f in files:
            csv_file = PerformanceScriptCsvFile.objects.create(
                script=script,
                file=f,
                original_name=f.name,
            )
            created.append(csv_file)
        return Response(
            PerformanceScriptCsvFileSerializer(created, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="csv-files")
    def csv_files(self, request, pk=None):
        """列出脚本的所有 CSV 附件。"""
        script = self.get_object()
        qs = script.csv_files.all()
        return Response(
            PerformanceScriptCsvFileSerializer(qs, many=True, context={"request": request}).data
        )

    @action(detail=True, methods=["post"], url_path="delete-csv")
    def delete_csv(self, request, pk=None):
        """删除脚本的 CSV 附件。"""
        script = self.get_object()
        file_id = request.data.get("file_id")
        if not file_id:
            return Response({"detail": "缺少 file_id"}, status=status.HTTP_400_BAD_REQUEST)
        csv_file = script.csv_files.filter(id=file_id).first()
        if not csv_file:
            return Response({"detail": "CSV 文件不存在"}, status=status.HTTP_404_NOT_FOUND)
        csv_file.delete()
        return Response({"detail": "已删除"})

    @action(detail=False, methods=["post"], url_path="convert-from-api")
    def convert_from_api(self, request):
        """从 API 测试用例一键生成压测脚本。"""
        from apps.api_testing.models import ApiRequest

        request_ids = request.data.get("request_ids") or []
        if not request_ids or not isinstance(request_ids, list):
            return Response({"detail": "请提供 request_ids 列表"}, status=status.HTTP_400_BAD_REQUEST)

        name = request.data.get("name") or "API压测脚本"
        thread_count = int(request.data.get("thread_count", 50))
        ramp_up = int(request.data.get("ramp_up", 10))
        duration = int(request.data.get("duration", 120))
        realtime_enabled = bool(request.data.get("realtime_enabled", False))

        api_requests = ApiRequest.objects.filter(id__in=request_ids).order_by("order", "id")
        if not api_requests.exists():
            return Response({"detail": "未找到指定 API 用例"}, status=status.HTTP_404_NOT_FOUND)

        samplers = []
        for ar in api_requests:
            samplers.append(_convert_api_request_to_sampler(ar))

        jmx_config = {
            "thread_groups": [{
                "name": "API 压测线程组",
                "thread_count": thread_count,
                "ramp_up": ramp_up,
                "duration": duration,
                "loops": -1,
                "samplers": samplers,
            }],
            "variables": [],
            "csv_datasets": [],
        }

        project_ids = []
        first_ar = api_requests.first()
        if first_ar and first_ar.project:
            from apps.projects.models import ProjectMapping
            mapping = ProjectMapping.objects.filter(
                module="api_testing", external_project_id=first_ar.project_id
            ).first()
            if mapping:
                project_ids = [mapping.project_id]

        script = PerformanceScript.objects.create(
            name=name,
            description=f"从 API 用例自动生成（{len(samplers)} 个请求）",
            script_type="ONLINE",
            jmx_config=jmx_config,
            thread_count=thread_count,
            ramp_up=ramp_up,
            duration=duration,
            realtime_enabled=realtime_enabled,
            created_by=request.user,
        )
        if project_ids:
            script.projects.set(project_ids)

        return Response(
            PerformanceScriptSerializer(script, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class PerformanceExecutionViewSet(viewsets.ModelViewSet):
    """性能执行记录（支持删除，删除时级联清理报告/汇总/指标与磁盘介质）。"""

    queryset = PerformanceExecution.objects.select_related("script", "created_by").all()
    serializer_class = PerformanceExecutionSerializer
    authentication_classes = [SessionAuthentication, QueryJWTAuthentication]
    permission_classes = [IsAuthenticated]
    filterset_fields = ["script", "status", "created_by", "batch"]
    ordering_fields = ["created_at", "started_at", "completed_at"]

    # 执行记录只能通过脚本触发创建，禁用直接的 create/update，仅保留查询与删除
    def create(self, request, *args, **kwargs):
        return Response({"detail": "执行记录不可直接创建"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        return Response({"detail": "执行记录不可直接修改"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response({"detail": "执行记录不可直接修改"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def perform_destroy(self, instance):
        """删除执行记录时清理对应的 PERF_xxx 介质目录。"""
        import shutil

        base = None
        for p in (instance.jtl_path, instance.jmx_path, instance.report_path, instance.jmeter_log):
            if p and os.path.exists(p):
                base = os.path.dirname(p) if os.path.isfile(p) else p
                break
        if (
            base
            and instance.execution_id
            and instance.execution_id in base
            and os.path.isdir(base)
        ):
            try:
                shutil.rmtree(base)
            except Exception:
                logger.exception("删除执行介质目录失败 %s", base)
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """取消执行（仅 QUEUED/RUNNING 可取消）。"""
        execution = self.get_object()
        if execution.status not in ("QUEUED", "RUNNING"):
            return Response({"detail": "当前状态不可取消"}, status=status.HTTP_400_BAD_REQUEST)
        PerformanceExecution.objects.filter(pk=execution.pk).update(
            status="CANCELLED",
            error_message="用户手动取消",
        )
        return Response({"detail": "已标记取消"})

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """执行汇总指标。"""
        execution = self.get_object()
        try:
            s = execution.summary
            return Response(PerformanceSummarySerializer(s).data)
        except PerformanceSummary.DoesNotExist:
            return Response({"detail": "汇总数据尚未生成"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get"])
    def metrics(self, request, pk=None):
        """按请求名分组的结构化指标。"""
        execution = self.get_object()
        metrics = execution.metrics.all().order_by("-sample_count")
        return Response(PerformanceMetricSerializer(metrics, many=True).data)

    @action(detail=True, methods=["get"])
    def realtime(self, request, pk=None):
        """InfluxDB 实时指标（最近 N 秒）。"""
        execution = self.get_object()
        window = int(request.query_params.get("window", 60))
        window = max(5, min(window, 3600))
        data = query_realtime(execution.execution_id, window_s=window)
        return Response(data)

    @action(detail=True, methods=["get"])
    def jtl_download(self, request, pk=None):
        """下载 JTL 结果文件。"""
        execution = self.get_object()
        if not execution.jtl_path or not os.path.exists(execution.jtl_path):
            raise Http404("JTL 文件不存在")
        return FileResponse(
            open(execution.jtl_path, "rb"),
            content_type="application/octet-stream",
            filename=f"{execution.execution_id}.jtl",
        )

    @action(detail=True, methods=["get"])
    def jmx_download(self, request, pk=None):
        """下载实际执行的 JMX 文件。"""
        execution = self.get_object()
        if not execution.jmx_path or not os.path.exists(execution.jmx_path):
            raise Http404("JMX 文件不存在")
        return FileResponse(
            open(execution.jmx_path, "rb"),
            content_type="application/octet-stream",
            filename=f"{execution.execution_id}.jmx",
        )

    @action(detail=True, methods=["post"])
    def regenerate_report(self, request, pk=None):
        """重新生成 HTML 报告（用于修复旧版报告或报告损坏）。"""
        execution = self.get_object()
        if not execution.jtl_path or not os.path.exists(execution.jtl_path):
            return Response({"detail": "JTL 文件不存在，无法重新生成报告"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            from .report_generator import generate_html_report
            # 刷新 execution 对象，确保 started_at/completed_at 等字段最新
            execution.refresh_from_db()
            report_dir = os.path.join(os.path.dirname(execution.jtl_path), "report")
            os.makedirs(report_dir, exist_ok=True)
            custom_index = os.path.join(report_dir, "index.html")
            generate_html_report(execution, custom_index, jtl_path=execution.jtl_path)
            PerformanceExecution.objects.filter(pk=execution.pk).update(report_path=report_dir)
            return Response({"ok": True, "message": "报告已重新生成"})
        except Exception as exc:
            logger.exception("重新生成报告失败 %s", execution.execution_id)
            return Response({"detail": f"重新生成报告失败: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        """HTML 报告代理（返回 index.html 内容，并改写资源路径）。支持 ?token= 认证。

        响应格式：{"html": "<完整 HTML 字符串>", "size": 字节数, "execution_id": "..."}
        前端通过 res.data.html 拿到字符串后设到 iframe.srcdoc。
        之前用 HttpResponse(text/html) + 前端 responseType:'text' 的方案在部分浏览器
        axios 实现下 srcdoc 绑定后渲染为空白，改为 JSON 包装更稳定。
        """
        execution = self.get_object()
        report_index = os.path.join(execution.report_path, "index.html") if execution.report_path else ""
        if not report_index or not os.path.exists(report_index):
            raise Http404("HTML 报告尚未生成")
        with open(report_index, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        token = request.query_params.get("token", "")
        html = _rewrite_html_report_paths(html, execution.execution_id, token=token)
        return Response({
            "html": html,
            "size": len(html),
            "execution_id": execution.execution_id,
        })

    @action(detail=True, methods=["get"])
    def report_file(self, request, pk=None):
        """HTML 报告静态资源代理（content/ 路径）。支持 HTML/CSS 相对路径改写与 ?token= 认证。"""
        execution = self.get_object()
        if not execution.report_path:
            raise Http404("报告目录不存在")
        rel_path = request.query_params.get("path", "")
        # CSS 中可能带有 cache-buster 如 ?v=4.2.0，只取实际文件路径部分
        rel_path = rel_path.split("?")[0]
        rel_path = rel_path.replace("..", "").lstrip("/\\")
        target = os.path.join(execution.report_path, rel_path)
        if not os.path.abspath(target).startswith(os.path.abspath(execution.report_path)):
            raise Http404("非法路径")
        if not os.path.exists(target) or os.path.isdir(target):
            raise Http404("文件不存在")

        ext = os.path.splitext(target)[1].lower()
        token = request.query_params.get("token", "")

        # HTML/CSS 需要改写内部相对路径
        if ext in (".html", ".htm", ".css"):
            content_type = {".html": "text/html", ".htm": "text/html", ".css": "text/css"}[ext]
            with open(target, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if ext in (".html", ".htm"):
                content = _rewrite_html_report_paths(content, execution.execution_id, rel_path, token)
            elif ext == ".css":
                content = _rewrite_css_report_paths(content, execution.execution_id, rel_path, token)
            return HttpResponse(content, content_type=content_type)

        ext_map = {
            ".js": "application/javascript",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".woff": "application/font-woff",
            ".woff2": "application/font-woff2",
            ".ttf": "font/ttf",
            ".otf": "font/otf",
            ".eot": "application/vnd.ms-fontobject",
        }
        content_type = ext_map.get(ext, "application/octet-stream")
        return FileResponse(open(target, "rb"), content_type=content_type)

    @action(detail=True, methods=["get"])
    def monitoring(self, request, pk=None):
        """执行期间的服务器/数据库监控指标（按目标分组）。"""
        execution = self.get_object()
        metrics = execution.monitor_metrics.all().order_by("target_name", "metric_key")
        serializer = PerformanceMonitorMetricSerializer(metrics, many=True)
        grouped: Dict[str, Any] = {}
        for m in serializer.data:
            key = m["target_name"]
            grouped.setdefault(key, {
                "target_name": m["target_name"],
                "target_type": m["target_type"],
                "metrics": [],
            })["metrics"].append(m)
        return Response({
            "execution_id": execution.execution_id,
            "targets": list(grouped.values()),
        })


class PerformanceDashboardViewSet(viewsets.ViewSet):
    """性能测试数据看板。"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        """返回指定执行的实时/汇总数据，用于看板展示。支持 id 或 execution_id 查询。"""
        execution_id = request.query_params.get("execution_id")
        execution_pk = request.query_params.get("id")
        execution = None
        if execution_id:
            execution = PerformanceExecution.objects.filter(execution_id=execution_id).first()
        if not execution and execution_pk:
            execution = PerformanceExecution.objects.filter(pk=execution_pk).first()
        if not execution:
            execution = PerformanceExecution.objects.filter(
                status__in=("RUNNING", "COMPLETED")
            ).order_by("-created_at").first()

        if not execution:
            return Response({"detail": "暂无执行数据"}, status=status.HTTP_404_NOT_FOUND)

        summary = {}
        try:
            s = execution.summary
            summary = PerformanceSummarySerializer(s).data
        except PerformanceSummary.DoesNotExist:
            pass

        metrics = execution.metrics.all().order_by("-sample_count")
        metrics_data = PerformanceMetricSerializer(metrics, many=True).data

        # 执行中或刚结束但尚未生成 summary/metrics 时，实时解析 JTL 兜底
        if execution.status in ("RUNNING",) or (execution.status in ("COMPLETED", "FAILED") and not summary and not metrics_data):
            try:
                from .result_parser import parse_jtl
                parsed = parse_jtl(execution.jtl_path)
                raw_summary = parsed.get("summary") or {}
                if raw_summary:
                    summary = {
                        "total_samples": raw_summary.get("total_samples", 0),
                        "error_count": raw_summary.get("error_count", 0),
                        "error_rate": raw_summary.get("error_rate", 0.0),
                        "avg_response_time": raw_summary.get("avg", 0.0),
                        "min_response_time": raw_summary.get("min", 0.0),
                        "max_response_time": raw_summary.get("max", 0.0),
                        "p90": raw_summary.get("p90", 0.0),
                        "p95": raw_summary.get("p95", 0.0),
                        "p99": raw_summary.get("p99", 0.0),
                        "throughput": raw_summary.get("throughput", 0.0),
                        "data_received": raw_summary.get("data_received", 0),
                        "data_sent": raw_summary.get("data_sent", 0),
                    }
                metrics_data = parsed.get("metrics") or metrics_data
                for m in metrics_data:
                    timeline = m.get("timeline") or []
                    for p in timeline:
                        p.setdefault("t", p.get("time", 0))
            except Exception as exc:
                logger.warning("实时解析 JTL 失败 %s: %s", execution.execution_id, exc)

        # InfluxDB 实时数据（最近 60 秒），未启用则回退到 JTL 时间线
        realtime_data = query_realtime(execution.execution_id, window_s=60)

        # 监控指标（按目标分组，与执行详情一致）
        from .serializers import PerformanceMonitorMetricSerializer
        monitor_qs = execution.monitor_metrics.all().order_by("target_name", "metric_key")
        monitor_ser = PerformanceMonitorMetricSerializer(monitor_qs, many=True).data
        monitor_grouped: Dict[str, Any] = {}
        for m in monitor_ser:
            key = m["target_name"]
            monitor_grouped.setdefault(key, {
                "target_name": m["target_name"],
                "target_type": m["target_type"],
                "metrics": [],
            })["metrics"].append(m)
        monitoring = list(monitor_grouped.values())

        return Response({
            "execution": PerformanceExecutionSerializer(execution, context={"request": request}).data,
            "summary": summary,
            "metrics": metrics_data,
            "realtime": realtime_data,
            "monitoring": monitoring,
        })


class PerformanceReportViewSet(viewsets.ReadOnlyModelViewSet):
    """性能测试报告列表。"""

    queryset = PerformanceReport.objects.select_related("execution", "created_by").all()
    serializer_class = PerformanceExecutionSerializer  # 复用执行序列化器
    permission_classes = [IsAuthenticated]
    filterset_fields = ["execution__script", "created_by"]
    ordering_fields = ["created_at"]

    def list(self, request, *args, **kwargs):
        """报告列表基于执行记录，仅展示已完成/有报告的。"""
        qs = PerformanceExecution.objects.filter(status="COMPLETED").select_related(
            "script", "created_by"
        ).order_by("-created_at")
        page = self.paginate_queryset(qs)
        ser = PerformanceExecutionSerializer(page or qs, many=True, context={"request": request})
        return self.get_paginated_response(ser.data) if page else Response(ser.data)

    def retrieve(self, request, *args, **kwargs):
        execution = PerformanceExecution.objects.filter(pk=kwargs.get("pk")).first()
        if not execution:
            raise Http404("报告不存在")
        return Response(PerformanceExecutionSerializer(execution, context={"request": request}).data)


class PerformanceScheduledTaskViewSet(viewsets.ModelViewSet):
    """性能测试定时任务。"""

    queryset = PerformanceScheduledTask.objects.select_related("script", "created_by").all()
    permission_classes = [IsAuthenticated]
    filterset_fields = ["script", "status", "created_by"]
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "updated_at"]

    def get_serializer_class(self):
        return PerformanceScheduledTaskSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()


class PerformanceConfigViewSet(viewsets.ViewSet):
    """性能测试全局配置（单例）。"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        config = PerformanceConfig.get_singleton()
        return Response(PerformanceConfigSerializer(config).data)

    def update(self, request, pk=None):
        config = PerformanceConfig.get_singleton()
        ser = PerformanceConfigSerializer(config, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def partial_update(self, request, pk=None):
        config = PerformanceConfig.get_singleton()
        ser = PerformanceConfigSerializer(config, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    @action(detail=False, methods=["post"], url_path="test-influxdb")
    def test_influxdb(self, request):
        """测试 InfluxDB 连接，支持使用传入配置或已保存配置。"""
        payload = request.data or {}
        url = payload.get("influxdb_url") or payload.get("url") or ""
        token = payload.get("influxdb_token") or payload.get("token") or ""
        org = payload.get("influxdb_org") or payload.get("org") or "testhub"
        bucket = payload.get("influxdb_bucket") or payload.get("bucket") or "jmeter"

        if not url:
            return Response({"ok": False, "message": "InfluxDB URL 不能为空"}, status=400)
        if not token:
            return Response({"ok": False, "message": "InfluxDB Token 不能为空"}, status=400)

        try:
            health_url = f"{url.rstrip('/')}/health"
            resp = requests.get(health_url, timeout=10)
            if not resp.ok:
                return Response({"ok": False, "message": f"InfluxDB 健康检查失败: HTTP {resp.status_code}"}, status=200)

            # 测试查询权限
            query_url = f"{url.rstrip('/')}/api/v2/query?org={org}"
            flux = f'from(bucket:"{bucket}") |> range(start: -1m) |> limit(n:1)'
            headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
            q_resp = requests.post(query_url, headers=headers, json={"query": flux, "type": "flux"}, timeout=10)
            if q_resp.status_code in (200, 204):
                return Response({"ok": True, "message": "InfluxDB 连接正常"})
            if q_resp.status_code == 401:
                return Response({"ok": False, "message": "Token 无效或权限不足"})
            if q_resp.status_code == 404:
                return Response({"ok": False, "message": f"Bucket 不存在: {bucket}"})
            return Response({"ok": False, "message": f"查询失败: HTTP {q_resp.status_code}"})
        except requests.exceptions.ConnectionError:
            return Response({"ok": False, "message": "无法连接到 InfluxDB，请检查 URL 和网络"}, status=200)
        except Exception as exc:
            return Response({"ok": False, "message": f"检测异常: {str(exc)}"}, status=200)

    @action(detail=False, methods=["post"], url_path="test-prometheus")
    def test_prometheus(self, request):
        """测试 Prometheus 连接。"""
        from .prometheus_client import test_prometheus_connection
        url = (request.data or {}).get("prometheus_url") or ""
        if not url:
            return Response({"ok": False, "message": "Prometheus URL 不能为空"}, status=400)
        return Response(test_prometheus_connection(url))


class PerformanceBatchExecutionViewSet(viewsets.ViewSet):
    """按项目批量执行性能测试。"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        """批次执行列表。"""
        qs = PerformanceBatchExecution.objects.select_related(
            "project", "created_by"
        ).order_by("-created_at")

        project = request.query_params.get("project")
        if project:
            qs = qs.filter(project_id=project)

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        # 分页
        page_size = int(request.query_params.get("page_size", 20))
        page = int(request.query_params.get("page", 1))
        total = qs.count()
        items = qs[(page - 1) * page_size: page * page_size]

        from rest_framework.pagination import PageNumberPagination
        data = PerformanceBatchExecutionSerializer(items, many=True, context={"request": request}).data
        return Response({"count": total, "results": data})

    def create(self, request):
        """创建批量执行。"""
        ser = BatchExecutionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        script_ids = data["script_ids"]
        scripts = PerformanceScript.objects.filter(id__in=script_ids)
        if not scripts.exists():
            return Response({"detail": "未找到指定脚本"}, status=status.HTTP_400_BAD_REQUEST)

        project = None
        if data.get("project"):
            from apps.projects.models import Project
            project = Project.objects.filter(id=data["project"]).first()

        try:
            batch = create_batch_execution(
                list(scripts),
                created_by=request.user,
                project=project,
                name=data.get("name", ""),
                thread_count=data.get("thread_count"),
                ramp_up=data.get("ramp_up"),
                duration=data.get("duration"),
                realtime_enabled=data.get("realtime_enabled"),
            )
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            PerformanceBatchExecutionSerializer(batch, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        """批次详情（含所有执行记录）。"""
        try:
            batch = PerformanceBatchExecution.objects.select_related(
                "project", "created_by"
            ).get(pk=pk)
        except PerformanceBatchExecution.DoesNotExist:
            raise Http404("批次不存在")
        return Response(
            PerformanceBatchExecutionSerializer(batch, context={"request": request}).data
        )

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """批次汇总（聚合所有执行的关键指标）。"""
        try:
            batch = PerformanceBatchExecution.objects.get(pk=pk)
        except PerformanceBatchExecution.DoesNotExist:
            raise Http404("批次不存在")

        executions = batch.executions.all()
        summaries = PerformanceSummary.objects.filter(execution__in=executions)

        total_samples = sum(s.total_samples for s in summaries)
        total_errors = sum(s.error_count for s in summaries)
        avg_rt = sum(s.avg_response_time for s in summaries) / len(summaries) if summaries else 0
        avg_throughput = sum(s.throughput for s in summaries) / len(summaries) if summaries else 0
        max_rt = max((s.max_response_time for s in summaries), default=0)
        avg_p95 = sum(s.p95 for s in summaries) / len(summaries) if summaries else 0

        return Response({
            "batch": PerformanceBatchExecutionSerializer(batch, context={"request": request}).data,
            "aggregate": {
                "total_executions": executions.count(),
                "completed": executions.filter(status="COMPLETED").count(),
                "failed": executions.filter(status="FAILED").count(),
                "total_samples": total_samples,
                "total_errors": total_errors,
                "error_rate": round(total_errors / total_samples * 100, 2) if total_samples else 0,
                "avg_response_time": round(avg_rt, 2),
                "avg_throughput": round(avg_throughput, 2),
                "max_response_time": round(max_rt, 2),
                "avg_p95": round(avg_p95, 2),
            },
            "summaries": PerformanceSummarySerializer(summaries, many=True).data,
        })

    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        """项目级批量执行 HTML 报告。返回 JSON 包装 {html, size, batch_id}，与单次执行一致。"""
        try:
            batch = PerformanceBatchExecution.objects.get(pk=pk)
        except PerformanceBatchExecution.DoesNotExist:
            raise Http404("批次不存在")
        report_index = os.path.join(batch.report_path, "index.html") if batch.report_path else ""
        if not report_index or not os.path.exists(report_index):
            raise Http404("项目级报告尚未生成")
        with open(report_index, "r", encoding="utf-8", errors="ignore") as f:
            html = f.read()
        return Response({
            "html": html,
            "size": len(html),
            "batch_id": batch.batch_id,
        })


# ==================== HTML 报告路径改写 ====================

def _is_absolute_url(url: str) -> bool:
    """判断 URL 是否为绝对路径或 data URI。"""
    if not url:
        return True
    url = url.strip()
    return (
        url.startswith("http://")
        or url.startswith("https://")
        or url.startswith("//")
        or url.startswith("data:")
        or url.startswith("#")
        or url.startswith("/api/")
        or url.startswith("/static/")
    )


def _resolve_relative_path(rel: str, current_path: str = "") -> str:
    """将相对路径解析为报告根目录下的绝对路径。"""
    rel = rel.strip()
    if rel.startswith("/"):
        rel = rel.lstrip("/")
    if current_path:
        base_dir = os.path.dirname(current_path)
        resolved = os.path.normpath(os.path.join(base_dir, rel))
    else:
        resolved = os.path.normpath(rel)
    return resolved.replace("\\", "/")


def _report_file_api_url(execution_id: str, rel_path: str, current_path: str = "", token: str = "") -> str:
    """生成 report_file API 的绝对 URL。"""
    resolved = _resolve_relative_path(rel_path, current_path)
    from urllib.parse import quote
    url = f"/api/performance-testing/executions/{execution_id}/report_file/?path={quote(resolved, safe='')}"
    if token:
        url += f"&token={quote(token, safe='')}"
    return url


def _rewrite_html_report_paths(html: str, execution_id: str, current_path: str = "", token: str = "") -> str:
    """改写 HTML 报告中的相对资源路径，使其通过 report_file API 加载。"""

    def _replace_attr(match) -> str:
        value = match.group(3)
        if _is_absolute_url(value):
            return match.group(0)
        new_value = _report_file_api_url(execution_id, value, current_path, token)
        quote_char = match.group(2)
        return f"{match.group(1)}{quote_char}{new_value}{quote_char}"

    # 1) <link href="..." ...>（含 stylesheet 和 icon）
    html = re.sub(
        r'(<link\s+[^>]*href=)(["\'])([^"\']+)\2',
        _replace_attr,
        html,
        flags=re.IGNORECASE,
    )
    # 2) <script src="..."> / <img src="..."> / <a href="..."> / <iframe src="...">
    for attr in ("src", "href"):
        html = re.sub(
            rf'(<(?:script|img|a|iframe)\s+[^>]*{attr}=)(["\'])([^"\']+)\2',
            _replace_attr,
            html,
            flags=re.IGNORECASE,
        )
    return html


def _rewrite_css_report_paths(css: str, execution_id: str, current_path: str, token: str = "") -> str:
    """改写 CSS 中的相对 url(...) 路径，使其通过 report_file API 加载。"""

    def _replace_url(match) -> str:
        quote_char = match.group(1)
        value = match.group(2)
        if _is_absolute_url(value):
            return match.group(0)
        new_value = _report_file_api_url(execution_id, value, current_path, token)
        if quote_char:
            return f"url({quote_char}{new_value}{quote_char})"
        return f"url({new_value})"

    css = re.sub(
        r'url\(\s*(["\']?)([^"\']+?)\1\s*\)',
        _replace_url,
        css,
        flags=re.IGNORECASE,
    )
    return css


# ==================== API 用例 → JMX Sampler 转换 ====================

def _convert_api_request_to_sampler(ar) -> dict:
    """将 ApiRequest 转换为 JMX 在线编排的 HTTP sampler 结构。"""
    import json
    from urllib.parse import urlparse, urlencode

    url = ar.url or ""
    params = ar.params or {}
    if params:
        if isinstance(params, list):
            param_pairs = [(p.get("key", ""), p.get("value", "")) for p in params if p.get("enabled", True)]
            if param_pairs:
                url += ("&" if "?" in url else "?") + urlencode(param_pairs)
        elif isinstance(params, dict):
            if params:
                url += ("&" if "?" in url else "?") + urlencode(params)

    headers = {}
    raw_headers = ar.headers or {}
    if isinstance(raw_headers, list):
        for h in raw_headers:
            if h.get("enabled", True):
                headers[h.get("key", "")] = h.get("value", "")
    elif isinstance(raw_headers, dict):
        headers = dict(raw_headers)

    body = ""
    raw_body = ar.body or {}
    if isinstance(raw_body, dict):
        if raw_body.get("type") == "json":
            data = raw_body.get("data", "")
            body = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
        elif raw_body.get("type") == "raw":
            body = str(raw_body.get("data", ""))
        elif raw_body.get("raw"):
            body = str(raw_body.get("raw"))
    elif isinstance(raw_body, str):
        body = raw_body

    jmx_assertions = []
    for a in (ar.assertions or []):
        atype = a.get("type", "")
        if atype == "status_code":
            jmx_assertions.append({
                "type": "response_code",
                "value": str(a.get("expected", "200")),
                "name": a.get("name", "响应码断言"),
            })
        elif atype == "json_path":
            jmx_assertions.append({
                "type": "json_path",
                "path": a.get("json_path", "$.code"),
                "value": str(a.get("expected", "")),
                "name": a.get("name", "JSON断言"),
            })

    return {
        "name": ar.name or "HTTP Request",
        "method": (ar.method or "GET").upper(),
        "url": url,
        "headers": headers,
        "body": body,
        "assertions": jmx_assertions,
    }


class PerformanceBaselineViewSet(viewsets.ModelViewSet):
    """性能基线：每个脚本一条当前基线，支持从执行设置为基线与劣化比对。"""

    queryset = PerformanceBaseline.objects.all().select_related("script", "execution", "set_by")
    serializer_class = PerformanceBaselineSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["script"]
    ordering_fields = ["created_at", "updated_at"]

    def perform_create(self, serializer):
        serializer.save(set_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(set_by=self.request.user)

    @action(detail=False, methods=["post"], url_path="set-from-execution")
    def set_from_execution(self, request):
        """把某次已完成的执行结果设为该脚本的性能基线（同脚本覆盖）。"""
        execution_id = request.data.get("execution_id")
        if not execution_id:
            return Response({"error": "缺少 execution_id"}, status=status.HTTP_400_BAD_REQUEST)
        execution = PerformanceExecution.objects.filter(pk=execution_id).select_related("script").first()
        if not execution:
            return Response({"error": "执行记录不存在"}, status=status.HTTP_404_NOT_FOUND)
        if execution.status != "COMPLETED":
            return Response({"error": "只有正常完成的执行才能作为基线"}, status=status.HTTP_400_BAD_REQUEST)

        summary = getattr(execution, "summary", None)
        metrics = baseline_service.summary_to_metrics(summary)
        if not metrics:
            return Response({"error": "该执行没有汇总数据，无法作为基线"}, status=status.HTTP_400_BAD_REQUEST)

        baseline, _created = PerformanceBaseline.objects.update_or_create(
            script=execution.script,
            defaults={
                "execution": execution,
                "metrics": metrics,
                "tolerance": request.data.get("tolerance") or PerformanceBaseline.DEFAULT_TOLERANCE,
                "note": request.data.get("note", ""),
                "set_by": request.user,
            },
        )
        return Response(PerformanceBaselineSerializer(baseline).data)

    @action(detail=False, methods=["get"])
    def compare(self, request):
        """执行 vs 基线：判断是否劣化。"""
        execution_id = request.query_params.get("execution_id")
        if not execution_id:
            return Response({"error": "缺少 execution_id"}, status=status.HTTP_400_BAD_REQUEST)
        execution = PerformanceExecution.objects.filter(pk=execution_id).select_related("script").first()
        if not execution:
            return Response({"error": "执行记录不存在"}, status=status.HTTP_404_NOT_FOUND)

        baseline = PerformanceBaseline.objects.filter(script=execution.script).first()
        if not baseline:
            return Response({"has_baseline": False, "degraded": False, "items": []})

        current = baseline_service.summary_to_metrics(getattr(execution, "summary", None))
        degraded, items = baseline_service.compare(baseline.metrics, current, baseline.tolerance)
        return Response({
            "has_baseline": True,
            "baseline_execution_id": baseline.execution.execution_id if baseline.execution else "",
            "baseline_created_at": baseline.created_at,
            "tolerance": baseline_service.merge_tolerance(baseline.tolerance),
            "degraded": degraded,
            "items": items,
        })


class PerformanceComparisonReportViewSet(viewsets.ModelViewSet):
    """多轮执行对照报告：生成（矩阵快照 + 可选 AI 分析）、列表、详情、删除。"""

    queryset = PerformanceComparisonReport.objects.select_related("script", "created_by").all()
    serializer_class = PerformanceComparisonReportSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["script"]
    ordering_fields = ["created_at"]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def create(self, request, *args, **kwargs):
        """生成对照报告。

        入参 execution_ids 至少要 2 个执行；顺序即前端展示顺序，第一个（或显式
        reference_execution_id）作为基准执行。
        """
        sz = ComparisonReportCreateSerializer(data=request.data)
        sz.is_valid(raise_exception=True)
        data = sz.validated_data

        ids = list(dict.fromkeys(data["execution_ids"]))  # 去重且保序
        executions = list(PerformanceExecution.objects.filter(pk__in=ids).select_related("script"))
        if len(executions) < 2:
            return Response({"error": "至少需要 2 个有效的执行记录才能对照"},
                            status=status.HTTP_400_BAD_REQUEST)

        order = {pk: idx for idx, pk in enumerate(ids)}
        executions.sort(key=lambda e: order.get(e.pk, len(order)))

        reference_id = data.get("reference_execution_id") or executions[0].pk
        if reference_id not in {e.pk for e in executions}:
            reference_id = executions[0].pk

        snapshot = comparison_service.build_snapshot(executions, reference_id)
        ai_text = comparison_service.analyze(snapshot) if data.get("with_ai", True) else ""

        script = executions[0].script
        title = (data.get("title") or "").strip() or f"{script.name if script else '压测'} 多轮对照（{len(executions)} 轮）"
        report = PerformanceComparisonReport.objects.create(
            script=script,
            title=title,
            execution_ids=[e.pk for e in executions],
            reference_execution_id=reference_id,
            snapshot=snapshot,
            ai_analysis=ai_text,
            created_by=request.user,
        )
        return Response(self.get_serializer(report).data, status=status.HTTP_201_CREATED)
