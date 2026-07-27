# -*- coding: utf-8 -*-
"""APP测试用例管理视图"""
import json
import uuid
import logging

import requests
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from ..models import AppPackage, AppTestCase, AppDevice, AppTestExecution, AppElement, AppComponent, AppCustomComponent
from ..serializers import AppPackageSerializer, AppTestCaseSerializer, AppTestExecutionSerializer

logger = logging.getLogger(__name__)


class AppPagination(PageNumberPagination):
    """APP自动化模块通用分页"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class AppPackageViewSet(viewsets.ModelViewSet):
    """APP应用包名管理 ViewSet"""
    queryset = AppPackage.objects.all()
    serializer_class = AppPackageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination
    search_fields = ['name', 'package_name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AppTestCaseViewSet(viewsets.ModelViewSet):
    """APP测试用例 ViewSet"""
    queryset = AppTestCase.objects.all()
    serializer_class = AppTestCaseSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = AppPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['project', 'app_package']
    search_fields = ['name']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行测试用例"""
        test_case = self.get_object()
        device_id = request.data.get('device_id')
        package_name = request.data.get('package_name')
        
        if not device_id:
            return Response({
                'success': False,
                'message': '请选择执行设备'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # 检查设备是否可用
            device = AppDevice.objects.get(device_id=device_id)
            # 取消用户隔离：不限制“谁锁定谁执行”
            
            # 创建执行记录
            execution = AppTestExecution.objects.create(
                test_case=test_case,
                device=device,
                user=request.user,
                status='pending'
            )
            
            # 调用 Celery 任务异步执行
            from ..tasks import execute_app_test_task
            task = execute_app_test_task.delay(execution.id, package_name=package_name)
            execution.task_id = task.id
            execution.save()
            
            logger.info(f"测试已提交执行: execution_id={execution.id}, task_id={task.id}")
            
            return Response({
                'success': True,
                'message': '测试已提交执行',
                'execution': AppTestExecutionSerializer(execution).data
            })
            
        except AppDevice.DoesNotExist:
            return Response({
                'success': False,
                'message': '设备不存在'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"执行测试失败: {str(e)}")
            return Response({
                'success': False,
                'message': f'执行测试失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def ai_arrange(self, request):
        """
        AI 编排：自然语言 → 测试步骤草稿。

        入参:
          - natural_language: str  自然语言测试任务描述
          - project: int           项目 ID（用于筛选元素库）

        出参:
          - success: bool
          - steps: list[dict]      ui_flow 格式的步骤数组
          - raw: str               LLM 原始返回（调试用）
        """
        nl_text = (request.data.get('natural_language') or '').strip()
        project_id = request.data.get('project')

        if not nl_text:
            return Response(
                {'success': False, 'message': '请输入测试任务描述'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            steps, raw = _generate_steps_via_llm(nl_text, project_id)
            return Response({'success': True, 'steps': steps, 'raw': raw})
        except ValueError as e:
            return Response(
                {'success': False, 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error('AI 编排失败: %s', e, exc_info=True)
            return Response(
                {'success': False, 'message': f'AI 编排失败: {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


def _generate_steps_via_llm(nl_text: str, project_id):
    """调用 LLM 生成 APP 自动化测试步骤草稿。"""
    # 1. 加载元素库
    element_qs = AppElement.objects.filter(is_active=True)
    if project_id:
        element_qs = element_qs.filter(project_id=project_id)
    elements = list(element_qs.values('name', 'element_type', 'config')[:80])

    # 2. 加载组件
    components = list(
        AppComponent.objects.filter(enabled=True).values('type', 'name', 'category', 'default_config')
    )
    custom_components = list(
        AppCustomComponent.objects.filter(enabled=True).values('type', 'name', 'description')
    )

    if not components:
        raise ValueError('系统中没有启用的基础组件，无法生成步骤')

    # 3. 获取 writer 模型配置
    try:
        from apps.requirement_analysis.models import AIModelConfig
        cfg = AIModelConfig.objects.filter(role='writer', is_active=True).order_by('-updated_at').first()
    except Exception:
        cfg = None
    if not cfg:
        raise ValueError('未配置启用的编写模型 (writer)，请先在 AI 模型配置中启用')

    base_url = (cfg.base_url or '').rstrip('/')
    url = f'{base_url}/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {cfg.api_key}',
        'Content-Type': 'application/json',
    }

    # 4. 构建 prompt
    element_lines = []
    for el in elements:
        el_name = el.get('name', '')
        el_type = el.get('element_type', '')
        element_lines.append(f'  - {el_name} (类型: {el_type})')
    elements_block = '\n'.join(element_lines) if element_lines else '  （暂无元素库数据）'

    comp_lines = []
    for c in components:
        comp_lines.append(f'  - type="{c["type"]}", 名称="{c["name"]}", 类别="{c.get("category", "")}"')
    components_block = '\n'.join(comp_lines)

    custom_lines = []
    for cc in custom_components:
        custom_lines.append(f'  - type="{cc["type"]}", 名称="{cc["name"]}", 说明="{cc.get("description", "")}"')
    custom_block = '\n'.join(custom_lines) if custom_lines else '  （无）'

    system_prompt = (
        '你是一个 APP 自动化测试编排专家。根据用户的自然语言描述，生成 Airtest 测试步骤草稿。\n\n'
        '## 步骤数据结构\n'
        '每个步骤是一个 JSON 对象：\n'
        '{"type": "组件type", "name": "组件名称", "kind": "atomic|custom", "config": {...}}\n'
        '- type: 基础组件的 type 值（见下方组件列表）\n'
        '- kind: "atomic"=基础组件, "custom"=自定义组件\n'
        '- config: 组件参数，常见字段：element(元素名), text(输入文本), timeout(超时秒), '
        'expected(断言期望), assert_type(断言类型)\n\n'
        '## 可用基础组件\n'
        f'{components_block}\n\n'
        '## 可用自定义组件\n'
        f'{custom_block}\n\n'
        '## 元素库\n'
        'config.element 字段应填写以下元素名之一：\n'
        f'{elements_block}\n\n'
        '## 规则\n'
        '1. 只输出 JSON 数组，不要 markdown 代码块标记\n'
        '2. 每个步骤的 type 必须在上方组件列表中存在\n'
        '3. 如果步骤需要操作元素，config.element 填写元素库中的 name\n'
        '4. 合理设置 timeout（默认 20 秒）\n'
        '5. 步骤顺序应符符合用户描述的操作流程\n'
        '6. 生成 3-15 个步骤，覆盖用户描述的主要操作'
    )

    payload = {
        'model': cfg.model_name,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'测试任务描述：\n{nl_text}'},
        ],
        'max_tokens': min(cfg.max_tokens or 4096, 4096),
        'temperature': cfg.temperature or 0.3,
    }

    # 推理模型关闭 thinking
    model_name_lower = (cfg.model_name or '').lower()
    if 'qwen3' in model_name_lower or 'deepseek-r1' in model_name_lower or 'reasoning' in model_name_lower:
        payload['chat_template_kwargs'] = {'enable_thinking': False}

    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    if resp.status_code != 200:
        raise ValueError(f'LLM 接口返回 {resp.status_code}: {resp.text[:300]}')

    data = resp.json()
    choices = data.get('choices') or []
    if not choices:
        raise ValueError('LLM 返回为空')
    content = (choices[0].get('message') or {}).get('content') or ''
    content = content.strip()

    # 去掉可能的 markdown 代码块标记
    if content.startswith('```'):
        lines = content.split('\n')
        content = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

    # 尝试解析 JSON
    try:
        steps_raw = json.loads(content)
    except json.JSONDecodeError:
        # 尝试提取第一个 JSON 数组
        start = content.find('[')
        end = content.rfind(']')
        if start != -1 and end != -1:
            steps_raw = json.loads(content[start:end + 1])
        else:
            raise ValueError(f'LLM 返回的内容无法解析为 JSON: {content[:200]}')

    if not isinstance(steps_raw, list):
        raise ValueError('LLM 返回的不是 JSON 数组')

    # 补全字段
    valid_types = {c['type'] for c in components} | {c['type'] for c in custom_components}
    custom_types = {c['type'] for c in custom_components}
    steps = []
    for s in steps_raw:
        if not isinstance(s, dict):
            continue
        s_type = s.get('type', '')
        if s_type not in valid_types:
            continue
        s_kind = 'custom' if s_type in custom_types else 'atomic'
        steps.append({
            'id': f"step_{uuid.uuid4().hex[:12]}",
            'type': s_type,
            'name': s.get('name', s_type),
            'kind': s_kind,
            'config': s.get('config') or {},
        })

    if not steps:
        raise ValueError('AI 未生成有效步骤，请补充更详细的描述后重试')

    return steps, content
