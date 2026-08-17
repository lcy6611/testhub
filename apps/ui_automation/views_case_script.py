"""用例 → UI 自动化脚本 生成 API（增量功能，独立视图集，可整体删除）。

端点（前缀 /ui-automation/case-script-generations/）：
  GET    /                       列表
  GET    /{id}/                 详情（含 progress_log / status / 统计）
  POST   /                       触发生成（source_testcase_ids 或 source_testcase_id, ui_project_id 可选, base_url）
                                  多用例时为每个用例各起一条任务，独立线程并行执行。
  POST   /{id}/stop/            停止生成
  GET    /{id}/elements/        本次生成抓取到的元素及验证状态
"""
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import UiScriptGeneration, ScriptStep
from .case_script_service import start_generation, stop_generation, retry_generation


def _ensure_tmp_ui_project(testcase, base_url):
    """当调用方未指定 ui_project_id 时，按 testcase.project 自动建（或复用）一个临时 UiProject。
    复用规则：同业务项目下名为"__tmp__base_url__"的临时项目若已存在则复用，避免每条用例建一个。
    返回 UiProject 实例。
    """
    from .models import UiProject
    biz_proj = getattr(testcase, 'project', None)
    if biz_proj is not None:
        # 尝试复用：业务项目下存在同名临时项目（按 base_url）则复用
        existing = UiProject.objects.filter(project=biz_proj, base_url=base_url).order_by('-id').first()
        if existing is not None:
            return existing
    name = f'__tmp__base_url__{biz_proj.id if biz_proj else "free"}'
    return UiProject.objects.create(
        name=name[:200],
        base_url=base_url,
        description=f'由用例→UI脚本自动创建的临时 UI 项目（用例 #{testcase.id}）',
        project=biz_proj,
    )


class UiScriptGenerationSerializer(serializers.ModelSerializer):
    suite_detail = serializers.SerializerMethodField()
    suite_execution_detail = serializers.SerializerMethodField()
    ui_project_detail = serializers.SerializerMethodField()
    generated_test_case_detail = serializers.SerializerMethodField()

    class Meta:
        model = UiScriptGeneration
        fields = [
            'id', 'source_testcase_id', 'source_testcase_title', 'ui_project',
            'ui_project_detail',
            'base_url', 'status', 'generated_script', 'ai_execution_record',
            'generated_test_case', 'generated_test_case_detail',
            'ui_suite', 'suite_detail',
            'suite_execution', 'suite_exec_status', 'suite_exec_pass_rate', 'suite_execution_detail',
            'elements_captured', 'steps_total',
            'steps_passed', 'progress_log', 'error_message',
            'playwright_code',
            'retry_limit', 'retry_count', 'created_at', 'updated_at',
        ]
        read_only_fields = (
            'status', 'progress_log', 'error_message', 'elements_captured',
            'steps_total', 'steps_passed', 'generated_script', 'generated_test_case',
            'ai_execution_record',
            'ui_suite', 'suite_execution', 'suite_exec_status', 'suite_exec_pass_rate',
            'playwright_code', 'retry_count', 'created_at', 'updated_at',
        )

    def get_suite_detail(self, obj):
        if obj.ui_suite:
            return {'id': obj.ui_suite.id, 'name': obj.ui_suite.name}
        return None

    def get_generated_test_case_detail(self, obj):
        if not obj.generated_test_case_id:
            return None
        try:
            tc = obj.generated_test_case
            return {
                'id': tc.id,
                'name': tc.name,
                'status': tc.status,
                'project_id': tc.project_id,
            }
        except Exception:
            return None

    def get_ui_project_detail(self, obj):
        if not getattr(obj, 'ui_project_id', None):
            return None
        try:
            p = obj.ui_project
            return {'id': p.id, 'name': p.name}
        except Exception:
            return None

    def get_suite_execution_detail(self, obj):
        if not obj.suite_execution_id:
            return None
        ex = obj.suite_execution
        summary = (ex.result_data or {}).get('summary') or {}
        return {
            'id': ex.id,
            'status': ex.status,
            'passed': ex.passed_cases,
            'failed': ex.failed_cases,
            'pass_rate': summary.get('pass_rate', obj.suite_exec_pass_rate),
            'duration': float(ex.duration) if ex.duration else None,
        }


class UiScriptGenerationViewSet(viewsets.ModelViewSet):
    queryset = UiScriptGeneration.objects.all().order_by('-created_at')
    serializer_class = UiScriptGenerationSerializer

    def create(self, request, *args, **kwargs):
        """支持多用例批量 + ui_project 可选自动建。

        接收参数：
          - source_testcase_ids (list[int])：批量用例主键；或 source_testcase_id (int)：单值（向后兼容）
          - ui_project_id (int|None)：目标 UI 项目；缺省时按 testcase.project 自动建临时 UiProject
          - base_url (str)：被测系统地址
        返回：多条 UiScriptGeneration 的序列化结果（list）
        """
        from apps.testcases.models import TestCase
        from .models import UiProject

        # 1) 解析用例 id 列表（兼容单值字段）
        src_ids = request.data.get('source_testcase_ids') or []
        single = request.data.get('source_testcase_id')
        if single:
            src_ids = [single] + ([s for s in src_ids if str(s) != str(single)] if isinstance(src_ids, list) else [])
        if not isinstance(src_ids, list):
            src_ids = [src_ids]
        src_ids = [int(x) for x in src_ids if x]
        if not src_ids:
            return Response({'detail': '缺少 source_testcase_ids 或 source_testcase_id'}, status=status.HTTP_400_BAD_REQUEST)

        ui_project_id = request.data.get('ui_project_id')
        base_url = request.data.get('base_url')
        if not base_url:
            return Response({'detail': '缺少 base_url'}, status=status.HTTP_400_BAD_REQUEST)

        # 可配置失败自动重试次数（默认 1）
        try:
            retry_limit = int(request.data.get('retry_limit', 1) or 1)
        except (TypeError, ValueError):
            retry_limit = 1
        if retry_limit < 0:
            retry_limit = 0

        # 2) 解析可选 UiProject
        proj = None
        if ui_project_id:
            try:
                proj = UiProject.objects.get(id=ui_project_id)
            except UiProject.DoesNotExist:
                return Response({'detail': '目标 UI 项目不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 3) 为每个用例建一条任务（缺 UiProject 时按 testcase.project 自动建临时项目）
        gens = []
        for src_id in src_ids:
            try:
                tc = TestCase.objects.get(id=src_id)
            except TestCase.DoesNotExist:
                continue  # 静默跳过不存在的 id，前端按返回数组判断
            proj_to_use = proj
            if proj_to_use is None:
                proj_to_use = _ensure_tmp_ui_project(tc, base_url)
            gen = UiScriptGeneration.objects.create(
                source_testcase_id=src_id,
                source_testcase_title=tc.title,
                ui_project=proj_to_use,
                base_url=base_url,
                retry_limit=retry_limit,
                created_by=request.user if request.user.is_authenticated else None,
                status='pending',
            )
            start_generation(gen.id)
            gens.append(gen)
        if not gens:
            return Response({'detail': '所有 source_testcase_ids 均不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(gens, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def stop(self, request, pk=None):
        stop_generation(int(pk))
        return Response({'detail': '已发送停止信号'})

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """手动重试：仅失败任务可触发，重置后单独跑一次。"""
        gen = self.get_object()
        if gen.status not in ('failed',):
            return Response({'detail': '仅失败任务可重试'}, status=status.HTTP_400_BAD_REQUEST)
        import threading
        threading.Thread(target=retry_generation, args=(gen.id,), daemon=True).start()
        return Response({'detail': '已触发重试'})

    @action(detail=False, methods=['get'])
    def by_testcase(self, request):
        """按业务用例反向查询其关联的 UI 脚本生成任务（含已建套件），实现「套件反向绑定业务用例」。"""
        tc_id = request.query_params.get('testcase_id')
        if not tc_id:
            return Response({'generations': []})
        gens = UiScriptGeneration.objects.filter(source_testcase_id=tc_id).order_by('-created_at')
        return Response({'generations': self.get_serializer(gens, many=True).data})

    @action(detail=True, methods=['get'])
    def elements(self, request, pk=None):
        gen = self.get_object()
        if not gen.generated_script:
            return Response({'elements': []})
        steps = (
            ScriptStep.objects
            .filter(script=gen.generated_script)
            .order_by('step_order')
            .select_related('target_element', 'target_element__locator_strategy')
        )
        data = []
        for s in steps:
            el = s.target_element
            data.append({
                'step_order': s.step_order,
                'action_type': s.action_type,
                'description': s.description,
                'element': {
                    'id': el.id,
                    'name': el.name,
                    'element_type': el.element_type,
                    'locator_strategy': el.locator_strategy.name if el.locator_strategy else '',
                    'locator_value': el.locator_value,
                    'validation_status': el.validation_status,
                } if el else None,
            })
        return Response({'elements': data})

    @action(detail=False, methods=['post'])
    def generate_codegen_command(self, request):
        """生成 Playwright codegen 录制命令（#329 录制回放）。

        录制在用户本机运行（需能访问被测站点），命令复制到本机执行，
        录制完成后把 .py 回传到平台 save_recorded 端点保存。
        支持 language / browser / device(视口) / save_login(保存登录态) 透传。
        """
        base_url = (request.data.get('base_url') or '').strip()
        if not base_url:
            return Response({'detail': '缺少 base_url'}, status=status.HTTP_400_BAD_REQUEST)
        from .services.recorded_script_runner import build_codegen_command
        cmd = build_codegen_command(
            base_url,
            language=request.data.get('language', 'python'),
            browser=request.data.get('browser', 'chromium'),
            device=request.data.get('device') or None,
            save_login=bool(request.data.get('save_login', False)),
        )
        return Response({
            'base_url': base_url,
            'command': cmd,
            'language': request.data.get('language', 'python'),
            'browser': request.data.get('browser', 'chromium'),
        })

    @action(detail=False, methods=['post'])
    def save_recorded(self, request):
        """保存用户回传的录制脚本（#329 录制回放）。

        录制脚本本质是 playwright codegen 生成的 .py，存入 UiScriptGeneration.playwright_code。
        可不关联源业务用例（source_testcase_id 已允许为空）。
        """
        from .models import UiProject
        from apps.testcases.models import TestCase
        base_url = (request.data.get('base_url') or '').strip()
        code = request.data.get('playwright_code') or ''
        name = (request.data.get('name') or '').strip() or '录制脚本'
        if not code.strip():
            return Response({'detail': '缺少 playwright_code'}, status=status.HTTP_400_BAD_REQUEST)
        ui_project_id = request.data.get('ui_project_id')
        proj = None
        if ui_project_id:
            try:
                proj = UiProject.objects.get(id=ui_project_id)
            except UiProject.DoesNotExist:
                return Response({'detail': '目标 UI 项目不存在'}, status=status.HTTP_404_NOT_FOUND)
        src_id = request.data.get('source_testcase_id')
        src_title = ''
        if src_id:
            try:
                tc = TestCase.objects.get(id=src_id)
                src_title = tc.title
            except TestCase.DoesNotExist:
                src_id = None
        gen = UiScriptGeneration.objects.create(
            source_testcase_id=src_id,
            source_testcase_title=src_title or name,
            ui_project=proj,
            base_url=base_url or 'http://frontend:5173/',
            status='pending',
            playwright_code=code,
            created_by=request.user if request.user.is_authenticated else None,
        )
        return Response(self.get_serializer(gen).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def run_recorded(self, request, pk=None):
        """回放执行录制脚本（#329 录制回放 / #328 定时任务执行录制脚本复用）。"""
        gen = self.get_object()
        from .services.recorded_script_runner import run_recorded_script
        headless = request.data.get('headless', None)
        if headless in (True, 'true', 'True', 1, '1'):
            headless = True
        elif headless in (False, 'false', 'False', 0, '0'):
            headless = False
        else:
            headless = None
        result = run_recorded_script(
            gen, headless=headless, browser=request.data.get('browser', 'chromium')
        )
        return Response({'id': gen.id, 'status': result.get('status'), 'result': result})
