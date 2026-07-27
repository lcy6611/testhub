from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import FilterSet, ModelChoiceFilter, NumberFilter, CharFilter, BooleanFilter
from rest_framework import filters
from django.db import models
from django.utils import timezone
from django.http import HttpResponse, FileResponse, Http404, HttpResponseNotFound
from django.views.static import serve
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import requests
import time
import os
import json
import logging
import uuid
import subprocess
from datetime import datetime, timedelta

from .models import (
    ApiProject, ApiCollection, ApiRequest, Environment,
    RequestHistory, TestSuite, TestExecution, TestSuiteRequest,
    ScheduledTask, TaskExecutionLog, NotificationConfig, NotificationLog,
    TaskNotificationSetting, OperationLog,
)

from .serializers import (
    ApiProjectSerializer, ApiCollectionSerializer, ApiRequestSerializer,
    EnvironmentSerializer, RequestHistorySerializer, TestSuiteSerializer,
    TestSuiteRequestSerializer, TestExecutionSerializer, UserSerializer,
    ScheduledTaskSerializer, TaskExecutionLogSerializer,
    NotificationConfigSerializer, NotificationLogSerializer, TaskNotificationSettingSerializer,
    NotificationConfigDetailSerializer, NotificationLogDetailSerializer,
    TaskNotificationSettingDetailSerializer, OperationLogSerializer
)

logger = logging.getLogger(__name__)

from .utils import execute_assertions
from .operation_logger import log_operation
from .serializers import (
    ApiProjectSerializer, ApiCollectionSerializer, ApiRequestSerializer,
    EnvironmentSerializer, RequestHistorySerializer, TestSuiteSerializer,
    TestSuiteRequestSerializer, TestExecutionSerializer, UserSerializer,
    ScheduledTaskSerializer, ScheduledTaskSerializer
)

User = get_user_model()


from rest_framework.pagination import PageNumberPagination

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000


class ApiProjectViewSet(viewsets.ModelViewSet):
    queryset = ApiProject.objects.all()
    serializer_class = ApiProjectSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['project_type', 'status', 'owner']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name', 'start_date']
    ordering = ['-created_at']
    
    def get_queryset(self):
        # 取消用户隔离：所有登录用户可见全部项目（与 core / app 保持一致）
        return ApiProject.objects.all()
    
    def perform_create(self, serializer):
        """创建项目时记录日志 + 跨模块同步"""
        instance = serializer.save()
        log_operation(
            operation_type='create',
            resource_type='project',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )
        from apps.projects.project_sync import auto_sync_project_create
        auto_sync_project_create(instance, 'api_testing')
    
    def perform_update(self, serializer):
        """更新项目时记录日志 + 跨模块同步"""
        instance = serializer.save()
        log_operation(
            operation_type='edit',
            resource_type='project',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )
        from apps.projects.project_sync import auto_sync_project_update
        auto_sync_project_update(instance, 'api_testing')
    
    def perform_destroy(self, instance):
        """删除项目时记录日志 + 跨模块级联删除"""
        log_operation(
            operation_type='delete',
            resource_type='project',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )
        from apps.projects.project_sync import auto_sync_project_delete
        auto_sync_project_delete(instance, 'api_testing')
        instance.delete()
    
    @action(detail=False, methods=['post'], url_path='create-sample')
    def create_sample_project(self, request):
        """创建示例项目（宠物店）"""
        if ApiProject.objects.filter(name='宠物店API示例项目').exists():
            return Response({'message': '示例项目已存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 创建示例项目
        project = ApiProject.objects.create(
            name='宠物店API示例项目',
            description='参考Apifox宠物店示例，包含用户管理、宠物管理、订单管理等接口',
            project_type='HTTP',
            status='IN_PROGRESS',
            owner=request.user,
            start_date=datetime.now().date()
        )
        
        # 创建示例数据
        self._create_sample_data(project, request.user)
        
        serializer = self.get_serializer(project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def _create_sample_data(self, project, user):
        """创建示例数据"""
        # 用户管理集合
        user_collection = ApiCollection.objects.create(
            project=project,
            name='用户管理',
            description='用户注册、登录、信息管理相关接口',
            order=1
        )
        
        # 用户注册接口
        ApiRequest.objects.create(
            collection=user_collection,
            name='用户注册',
            description='新用户注册接口',
            method='POST',
            url='{{base_url}}/api/users/register',
            headers={'Content-Type': 'application/json'},
            body={
                'type': 'json',
                'data': {
                    'username': 'testuser',
                    'email': 'test@example.com',
                    'password': 'password123'
                }
            },
            created_by=user,
            order=1
        )
        
        # 用户登录接口
        ApiRequest.objects.create(
            collection=user_collection,
            name='用户登录',
            description='用户登录获取token',
            method='POST',
            url='{{base_url}}/api/users/login',
            headers={'Content-Type': 'application/json'},
            body={
                'type': 'json',
                'data': {
                    'username': 'testuser',
                    'password': 'password123'
                }
            },
            created_by=user,
            order=2
        )
        
        # 宠物管理集合
        pet_collection = ApiCollection.objects.create(
            project=project,
            name='宠物管理',
            description='宠物信息增删改查接口',
            order=2
        )
        
        # 获取宠物列表
        ApiRequest.objects.create(
            collection=pet_collection,
            name='获取宠物列表',
            description='分页获取宠物列表',
            method='GET',
            url='{{base_url}}/api/pets',
            headers={'Authorization': 'Bearer {{token}}'},
            params={'page': '1', 'limit': '10'},
            created_by=user,
            order=1
        )
        
        # 创建宠物
        ApiRequest.objects.create(
            collection=pet_collection,
            name='创建宠物',
            description='添加新宠物信息',
            method='POST',
            url='{{base_url}}/api/pets',
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {{token}}'
            },
            body={
                'type': 'json',
                'data': {
                    'name': '小白',
                    'category': 'dog',
                    'age': 2,
                    'price': 1000
                }
            },
            created_by=user,
            order=2
        )


class ApiCollectionViewSet(viewsets.ModelViewSet):
    queryset = ApiCollection.objects.all()
    serializer_class = ApiCollectionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['project', 'parent']
    
    def get_queryset(self):
        user = self.request.user
        return ApiCollection.objects.filter(
            project__in=ApiProject.objects.filter(
                models.Q(owner=user) | models.Q(members=user)
            )
        ).distinct()

    def perform_create(self, serializer):
        """创建集合时记录日志"""
        instance = serializer.save()
        log_operation(
            operation_type='create',
            resource_type='collection',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )

    def perform_update(self, serializer):
        """更新集合时记录日志"""
        instance = serializer.save()
        log_operation(
            operation_type='edit',
            resource_type='collection',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )

    def perform_destroy(self, instance):
        """删除集合时记录日志"""
        log_operation(
            operation_type='delete',
            resource_type='collection',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )
        instance.delete()


class ApiRequestFilter(FilterSet):
    """请求列表过滤：project 同时匹配 request.project 或 collection.project；collection__isnull 用于仅查未分类接口"""
    project = ModelChoiceFilter(
        queryset=ApiProject.objects.all(),
        method='filter_by_project'
    )
    collection = NumberFilter(field_name='collection')
    collection__isnull = BooleanFilter(field_name='collection', lookup_expr='isnull')
    method = CharFilter(field_name='method')
    request_type = CharFilter(field_name='request_type')

    def filter_by_project(self, queryset, name, value):
        if value is None:
            return queryset
        return queryset.filter(
            models.Q(project=value) | models.Q(collection__project=value) | models.Q(projects=value)
        ).distinct()

    class Meta:
        model = ApiRequest
        fields = ['collection', 'project', 'method', 'request_type']


class ApiRequestViewSet(viewsets.ModelViewSet):
    queryset = ApiRequest.objects.all()
    serializer_class = ApiRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = ApiRequestFilter
    search_fields = ['name', 'url']
    
    def get_queryset(self):
        user = self.request.user
        accessible_projects = ApiProject.objects.filter(
            models.Q(owner=user) | models.Q(members=user)
        )

        # 同时兼容两种归属方式：
        # - 新逻辑：ApiRequest.project 直接关联项目（支持 collection 为空）
        # - 旧逻辑：通过 ApiRequest.collection.project 归属项目
        # - 复用逻辑：通过 ApiRequest.projects 多对多关联项目
        # - 创建者可见：新建脚本尚未关联任何项目时，创建者本人应可看见并管理
        return ApiRequest.objects.filter(
            models.Q(project__in=accessible_projects) |
            models.Q(collection__project__in=accessible_projects) |
            models.Q(projects__in=accessible_projects) |
            models.Q(created_by=user)
        ).distinct()
    
    def perform_create(self, serializer):
        """创建接口时记录日志"""
        instance = serializer.save()
        log_operation(
            operation_type='create',
            resource_type='request',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )

    def perform_update(self, serializer):
        """更新接口时记录日志"""
        instance = serializer.save()
        log_operation(
            operation_type='edit',
            resource_type='request',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )

    def perform_destroy(self, instance):
        """删除接口时记录日志"""
        log_operation(
            operation_type='delete',
            resource_type='request',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行API请求"""
        api_request = self.get_object()
        environment_id = request.data.get('environment_id')
        
        try:
            # 解析环境变量
            variables = {}
            if environment_id:
                env = Environment.objects.get(id=environment_id)
                variables.update(env.variables)
            
            # 替换URL中的变量
            url = self._replace_variables(api_request.url or '', variables)
            
            # 准备请求头
            headers = {}
            if isinstance(api_request.headers, list):
                for header_item in api_request.headers:
                    if header_item.get('enabled', True) and header_item.get('key'):
                        key = header_item['key']
                        value = self._replace_variables(str(header_item.get('value', '')), variables)
                        headers[key] = value
            else:
                headers = api_request.headers.copy()
                for key, value in headers.items():
                    headers[key] = self._replace_variables(str(value), variables)
            
            # 准备请求参数
            params = api_request.params.copy() if api_request.params else {}
            for key, value in params.items():
                params[key] = self._replace_variables(str(value), variables)
            
            # 准备请求体
            body_data = None
            if api_request.body and api_request.method in ['POST', 'PUT', 'PATCH']:
                if api_request.body.get('type') == 'json':
                    body_data = api_request.body.get('data', {})
                    body_data = self._replace_variables_in_dict(body_data, variables)
                else:
                    body_data = self._replace_variables_in_dict(api_request.body.get('data'), variables)
            
            # 执行请求
            start_time = time.time()
            response = requests.request(
                method=api_request.method,
                url=url,
                headers=headers,
                params=params,
                json=body_data,
                timeout=30
            )
            end_time = time.time()
            
            response_time = (end_time - start_time) * 1000  # 转换为毫秒
            
            # 执行断言验证
            assertions = api_request.assertions or []
            for assertion in assertions:
                if assertion.get('type') == 'response_time':
                    assertion['actual_time'] = response_time
            assertions_results = execute_assertions(response, assertions)

            # 执行变量提取器
            extracted_vars = {}
            extractors = getattr(api_request, 'extractors', None)
            if extractors:
                from .utils import execute_extractors
                extracted_vars = execute_extractors(response, extractors)

            # 保存请求历史
            # 安全解析 JSON 响应，避免解析失败直接抛异常
            json_body = None
            try:
                content_type = response.headers.get('content-type', '')
                if isinstance(content_type, str) and content_type.startswith('application/json'):
                    json_body = response.json()
            except Exception:
                # 如果解析失败，记录日志但不中断请求流程
                logger.warning("解析响应 JSON 失败", exc_info=True)

            history = RequestHistory.objects.create(
                request=api_request,
                environment_id=environment_id,
                request_data={
                    'url': url,
                    'method': api_request.method,
                    'headers': headers,
                    'params': params,
                    'body': body_data
                },
                response_data={
                    'headers': dict(response.headers),
                    'body': response.text,
                    'json': json_body
                },
                status_code=response.status_code,
                response_time=response_time,
                executed_by=request.user
            )

            try:
                from apps.knowledge_graph.writeback import safe_writeback_api_request_execution
                safe_writeback_api_request_execution(history)
            except Exception:
                logger.warning("知识图谱回写 API 执行结果失败", exc_info=True)
            
            # 记录执行操作
            log_operation(
                operation_type='execute',
                resource_type='request',
                resource_id=api_request.id,
                resource_name=api_request.name,
                user=request.user
            )
            
            # 返回包含断言结果的数据
            history_data = RequestHistorySerializer(history).data
            history_data['assertions_results'] = assertions_results
            if extracted_vars:
                history_data['extracted_variables'] = extracted_vars
            
            return Response(history_data)
            
        except Exception as e:
            # 保存错误历史
            history = RequestHistory.objects.create(
                request=api_request,
                environment_id=environment_id,
                request_data={
                    'url': api_request.url,
                    'method': api_request.method,
                    'headers': api_request.headers,
                    'params': api_request.params,
                    'body': api_request.body
                },
                error_message=str(e),
                executed_by=request.user
            )

            try:
                from apps.knowledge_graph.writeback import safe_writeback_api_request_execution
                safe_writeback_api_request_execution(history)
            except Exception:
                logger.warning("知识图谱回写 API 执行结果失败", exc_info=True)
            
            return Response(RequestHistorySerializer(history).data, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='projects')
    def manage_projects(self, request, pk=None):
        """管理脚本关联的项目（多对多，支持脚本复用）。

        入参:
          - project_ids: 项目 ID 列表
          - mode: 'set'（默认，整体替换）| 'add'（追加）| 'remove'（移除）
        返回更新后的关联项目名列表。
        """
        api_request = self.get_object()
        project_ids = request.data.get('project_ids', [])
        mode = request.data.get('mode', 'set')

        if not isinstance(project_ids, list):
            return Response({'detail': 'project_ids 必须为列表'}, status=status.HTTP_400_BAD_REQUEST)

        projects = ApiProject.objects.filter(id__in=project_ids)
        if mode == 'add':
            api_request.projects.add(*projects)
        elif mode == 'remove':
            api_request.projects.remove(*projects)
        else:  # set
            api_request.projects.set(projects)

        return Response({
            'id': api_request.id,
            'project_ids': list(api_request.projects.values_list('id', flat=True)),
            'project_names': list(api_request.projects.values_list('name', flat=True)),
        })

    @action(detail=False, methods=['post'])
    def import_saz(self, request):
        """
        批量导入 Fiddler SAZ 文件，解析为接口请求。

        入参:
          - file: SAZ 文件（multipart upload）
          - project: 项目 ID（可选）
          - collection: 集合 ID（可选）
        """
        from .utils import parse_saz_file

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'detail': '请上传 SAZ 文件'}, status=status.HTTP_400_BAD_REQUEST)

        project_id = request.data.get('project')
        collection_id = request.data.get('collection')

        try:
            parsed_requests = parse_saz_file(uploaded)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'detail': f'解析 SAZ 文件失败: {e}'}, status=status.HTTP_400_BAD_REQUEST)

        if not parsed_requests:
            return Response({'detail': 'SAZ 文件中未找到有效请求'}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        for idx, pr in enumerate(parsed_requests):
            try:
                obj = ApiRequest.objects.create(
                    name=pr['name'][:200],
                    method=pr['method'],
                    url=pr['url'][:2000],
                    headers=pr.get('headers', []),
                    params=pr.get('params', []),
                    body=pr.get('body'),
                    project_id=project_id or None,
                    collection_id=collection_id or None,
                )
                created.append({'id': obj.id, 'name': obj.name, 'method': obj.method, 'url': obj.url})
            except Exception as e:
                logger.warning("导入 SAZ 条目 %d 失败: %s", idx, e)

        log_operation(
            operation_type='import',
            resource_type='request',
            resource_id=0,
            resource_name=f'SAZ 导入 ({len(created)} 条)',
            user=request.user,
        )

        return Response({
            'success': True,
            'imported': len(created),
            'requests': created,
        })

    def _replace_variables(self, text, variables):
        """替换文本中的变量"""
        if not isinstance(text, str):
            return text
        
        result = text
        for key, value in (variables or {}).items():
            if isinstance(value, dict):
                replacement = str(value.get('currentValue', '') or value.get('initialValue', ''))
            else:
                replacement = str(value) if value is not None else ''
            result = result.replace(f'{{{{{key}}}}}', replacement)
        return result
    
    def _replace_variables_in_dict(self, data, variables):
        """递归替换字典中的变量"""
        if isinstance(data, dict):
            return {k: self._replace_variables_in_dict(v, variables) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._replace_variables_in_dict(item, variables) for item in data]
        elif isinstance(data, str):
            return self._replace_variables(data, variables)
        else:
            return data


class EnvironmentViewSet(viewsets.ModelViewSet):
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['scope', 'project', 'is_active']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        return Environment.objects.filter(
            models.Q(scope='GLOBAL') | 
            models.Q(
                scope='LOCAL',
                project__in=ApiProject.objects.filter(
                    models.Q(owner=user) | models.Q(members=user)
                )
            )
        ).distinct().order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活环境"""
        environment = self.get_object()
        
        # 如果是局部环境，取消同项目下其他环境的激活状态
        if environment.scope == 'LOCAL' and environment.project:
            Environment.objects.filter(
                project=environment.project,
                scope='LOCAL'
            ).update(is_active=False)
        # 如果是全局环境，取消其他全局环境的激活状态
        elif environment.scope == 'GLOBAL':
            Environment.objects.filter(scope='GLOBAL').update(is_active=False)
        
        environment.is_active = True
        environment.save()

        return Response({'message': '环境已激活'})

    def destroy(self, request, *args, **kwargs):
        """删除前检查是否被引用（测试套件 / 定时任务 / 请求历史）。"""
        instance = self.get_object()
        refs = []
        suites = TestSuite.objects.filter(environment=instance)
        if suites.exists():
            refs.append(f'测试套件 ({suites.count()} 个)')
        tasks = ScheduledTask.objects.filter(environment=instance)
        if tasks.exists():
            refs.append(f'定时任务 ({tasks.count()} 个)')
        histories = RequestHistory.objects.filter(environment=instance)
        if histories.count() > 0:
            refs.append(f'请求历史 ({histories.count()} 条)')
        if refs:
            return Response(
                {'detail': f'该环境已被引用，无法删除：{", ".join(refs)}。请先解除引用后再删除。'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        """创建环境时记录日志"""
        instance = serializer.save()
        log_operation(
            operation_type='create',
            resource_type='environment',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )

    def perform_update(self, serializer):
        """更新环境时记录日志"""
        instance = serializer.save()
        log_operation(
            operation_type='edit',
            resource_type='environment',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )

    def perform_destroy(self, instance):
        """删除环境时记录日志"""
        log_operation(
            operation_type='delete',
            resource_type='environment',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )
        instance.delete()


class RequestHistoryViewSet(viewsets.ModelViewSet):
    queryset = RequestHistory.objects.all()
    serializer_class = RequestHistorySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    # 支持按请求类型 / 状态码 / 环境以及是否为“无环境”进行筛选
    filterset_fields = {
        'request__request_type': ['exact'],
        'status_code': ['exact'],
        'environment': ['exact', 'isnull'],
    }
    ordering = ['-executed_at']
    pagination_class = StandardPagination
    
    def get_queryset(self):
        user = self.request.user
        user_projects = ApiProject.objects.filter(
            models.Q(owner=user) | models.Q(members=user)
        )
        # 包含：有关联集合且集合属于用户项目的请求 + 未分类(collection 为空)但请求归属用户项目的请求
        return RequestHistory.objects.filter(
            models.Q(request__collection__project__in=user_projects) |
            models.Q(request__collection__isnull=True, request__project__in=user_projects)
        ).select_related(
            'request', 'environment', 'executed_by',
            'request__created_by', 'environment__created_by', 'environment__project'
        ).distinct()

    @action(detail=False, methods=['post'], url_path='batch-delete')
    def batch_delete(self, request):
        """批量删除请求历史"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': '未提供要删除的记录ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 确保只能删除有权限的记录
        # 先获取有权限的ID列表，避免在distinct()后调用delete()
        queryset = self.get_queryset()
        valid_ids = list(queryset.filter(id__in=ids).values_list('id', flat=True))
        
        # 使用有权限的ID列表进行删除
        deleted_count, _ = RequestHistory.objects.filter(id__in=valid_ids).delete()
        
        return Response({'message': f'成功删除 {deleted_count} 条记录'})


class TestSuiteViewSet(viewsets.ModelViewSet):
    queryset = TestSuite.objects.all()
    serializer_class = TestSuiteSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['project']
    
    def get_queryset(self):
        user = self.request.user
        return TestSuite.objects.filter(
            project__in=ApiProject.objects.filter(
                models.Q(owner=user) | models.Q(members=user)
            )
        ).distinct()

    @action(detail=True, methods=['post'])
    def execute(self, request, pk=None):
        """执行测试套件"""
        test_suite = self.get_object()
        
        try:
            # 创建执行记录
            execution = TestExecution.objects.create(
                test_suite=test_suite,
                status='RUNNING',
                start_time=timezone.now(),
                executed_by=request.user
            )
            
            # 获取套件中的请求
            suite_requests = TestSuiteRequest.objects.filter(
                test_suite=test_suite,
                enabled=True
            ).order_by('order')
            
            execution.total_requests = suite_requests.count()
            execution.save()
            
            results = []
            passed_count = 0
            failed_count = 0
            
            # 执行每个请求
            for suite_request in suite_requests:
                api_request = suite_request.request
                
                try:
                    # 解析环境变量
                    variables = {}
                    if test_suite.environment:
                        variables.update(test_suite.environment.variables)
                    
                    # 替换URL中的变量
                    url = self._replace_variables(api_request.url, variables)
                    
                    # 准备请求头
                    headers = {}
                    # 支持新的数组格式和旧的对象格式
                    if isinstance(api_request.headers, list):
                        # 新的数组格式 [{"key": "Authorization", "value": "Bearer {{token}}", "enabled": true, "description": "..."}]
                        for header_item in api_request.headers:
                            if header_item.get('enabled', True) and header_item.get('key'):
                                key = header_item['key']
                                value = self._replace_variables(str(header_item.get('value', '')), variables)
                                headers[key] = value
                    else:
                        # 旧的对象格式 {"Authorization": "Bearer {{token}}"}
                        headers = api_request.headers.copy()
                        for key, value in headers.items():
                            headers[key] = self._replace_variables(str(value), variables)
                    
                    params = api_request.params.copy()
                    for key, value in params.items():
                        params[key] = self._replace_variables(str(value), variables)
                    
                    body_data = None
                    if api_request.body and api_request.method in ['POST', 'PUT', 'PATCH']:
                        if api_request.body.get('type') == 'json':
                            body_data = api_request.body.get('data', {})
                            body_data = self._replace_variables_in_dict(body_data, variables)
                    
                    # 执行请求
                    start_time = time.time()
                    response = requests.request(
                        method=api_request.method,
                        url=url,
                        headers=headers,
                        params=params,
                        json=body_data,
                        timeout=30
                    )
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    
                    # 执行断言验证
                    assertions = api_request.assertions or []
                    # 添加响应时间到断言中
                    for assertion in assertions:
                        if assertion.get('type') == 'response_time':
                            assertion['actual_time'] = response_time
                    
                    # 使用共享的断言执行方法
                    assertions_results = execute_assertions(response, assertions)
                    
                    # 检查所有断言是否通过
                    passed = True
                    error_message = ''
                    
                    # 检查套件请求的断言
                    for assertion in suite_request.assertions:
                        # 简单的状态码断言
                        if assertion.get('type') == 'status_code':
                            expected = assertion.get('value')
                            if response.status_code != expected:
                                passed = False
                                error_message = f'状态码断言失败: 期望 {expected}, 实际 {response.status_code}'
                                break
                    
                    # 检查接口自身的断言
                    if passed and assertions_results:
                        for assertion_result in assertions_results:
                            if not assertion_result.get('passed', True):
                                passed = False
                                error_message = f"断言失败: {assertion_result.get('name', '未命名断言')} - {assertion_result.get('error', '断言不通过')}"
                                break
                    
                    if passed:
                        passed_count += 1
                    else:
                        failed_count += 1
                    
                    results.append({
                        'name': api_request.name,
                        'method': api_request.method,
                        'url': url,
                        'status_code': response.status_code,
                        'response_time': response_time,
                        'passed': passed,
                        'error': error_message,
                        'assertions_results': assertions_results
                    })
                    
                    # 保存请求历史
                    history = RequestHistory.objects.create(
                        request=api_request,
                        environment=test_suite.environment,
                        request_data={
                            'url': url,
                            'method': api_request.method,
                            'headers': headers,
                            'params': params,
                            'body': body_data
                        },
                        response_data={
                            'headers': dict(response.headers),
                            'body': response.text,
                            'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None
                        },
                        status_code=response.status_code,
                        response_time=response_time,
                        assertions_results=assertions_results,
                        executed_by=request.user
                    )
                    try:
                        from apps.knowledge_graph.writeback import safe_writeback_api_request_execution
                        safe_writeback_api_request_execution(history)
                    except Exception:
                        logger.warning("知识图谱回写 API 执行结果失败", exc_info=True)
                    
                except Exception as e:
                    failed_count += 1
                    results.append({
                        'name': api_request.name,
                        'method': api_request.method,
                        'url': api_request.url,
                        'passed': False,
                        'error': str(e)
                    })
                    history = RequestHistory.objects.create(
                        request=api_request,
                        environment=test_suite.environment,
                        request_data={
                            'url': api_request.url,
                            'method': api_request.method,
                            'headers': api_request.headers,
                            'params': api_request.params,
                            'body': api_request.body
                        },
                        error_message=str(e),
                        executed_by=request.user
                    )
                    try:
                        from apps.knowledge_graph.writeback import safe_writeback_api_request_execution
                        safe_writeback_api_request_execution(history)
                    except Exception:
                        logger.warning("知识图谱回写 API 执行结果失败", exc_info=True)
            
            # 更新执行结果
            execution.end_time = timezone.now()
            execution.passed_requests = passed_count
            execution.failed_requests = failed_count
            execution.status = 'COMPLETED' if failed_count == 0 else 'FAILED'
            execution.results = results
            execution.save()
            
            # 记录执行操作
            log_operation(
                operation_type='execute',
                resource_type='suite',
                resource_id=test_suite.id,
                resource_name=test_suite.name,
                user=request.user
            )
            
            return Response(TestExecutionSerializer(execution).data)
            
        except Exception as e:
            execution.status = 'FAILED'
            execution.end_time = timezone.now()
            execution.save()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer):
        """创建测试套件时记录日志"""
        instance = serializer.save()
        log_operation(
            operation_type='create',
            resource_type='suite',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )

    def perform_update(self, serializer):
        """更新测试套件时记录日志"""
        instance = serializer.save()
        log_operation(
            operation_type='edit',
            resource_type='suite',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )

    def perform_destroy(self, instance):
        """删除测试套件时记录日志"""
        log_operation(
            operation_type='delete',
            resource_type='suite',
            resource_id=instance.id,
            resource_name=instance.name,
            user=self.request.user
        )
        instance.delete()

    @action(detail=True, methods=['post'], url_path='add-requests')
    def add_requests(self, request, pk=None):
        """添加请求到测试套件"""
        test_suite = self.get_object()
        request_ids = request.data.get('request_ids', [])
        
        try:
            for request_id in request_ids:
                api_request = ApiRequest.objects.get(id=request_id)
                TestSuiteRequest.objects.get_or_create(
                    test_suite=test_suite,
                    request=api_request,
                    defaults={
                        'order': TestSuiteRequest.objects.filter(test_suite=test_suite).count(),
                        'enabled': True,
                        'assertions': []
                    }
                )
            
            return Response({'message': '添加成功'})
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def _replace_variables(self, text, variables):
        """替换文本中的变量"""
        if not isinstance(text, str):
            return text
        
        result = text
        for key, value in (variables or {}).items():
            if isinstance(value, dict):
                replacement = str(value.get('currentValue', '') or value.get('initialValue', ''))
            else:
                replacement = str(value) if value is not None else ''
            result = result.replace(f'{{{{{key}}}}}', replacement)
        return result
    
    def _replace_variables_in_dict(self, data, variables):
        """递归替换字典中的变量"""
        if isinstance(data, dict):
            return {k: self._replace_variables_in_dict(v, variables) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._replace_variables_in_dict(item, variables) for item in data]
        elif isinstance(data, str):
            return self._replace_variables(data, variables)
        else:
            return data


class TestSuiteRequestViewSet(viewsets.ModelViewSet):
    queryset = TestSuiteRequest.objects.all()
    serializer_class = TestSuiteRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['test_suite', 'enabled']
    
    def get_queryset(self):
        user = self.request.user
        return TestSuiteRequest.objects.filter(
            test_suite__project__in=ApiProject.objects.filter(
                models.Q(owner=user) | models.Q(members=user)
            )
        ).distinct()


class TestExecutionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TestExecution.objects.all()
    serializer_class = TestExecutionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'test_suite']
    ordering = ['-created_at']
    pagination_class = StandardPagination
    
    def get_queryset(self):
        user = self.request.user
        return TestExecution.objects.filter(
            test_suite__project__in=ApiProject.objects.filter(
                models.Q(owner=user) | models.Q(members=user)
            )
        ).distinct()
    
    @action(detail=True, methods=['post'], url_path='generate-allure-report')
    def generate_allure_report(self, request, pk=None):
        """生成Allure报告数据"""
        execution = self.get_object()
        
        report_output_dir = os.path.join(settings.MEDIA_ROOT, 'allure-reports', f'execution_{execution.id}')
        results_dir = os.path.join(settings.MEDIA_ROOT, 'allure-results', f'execution_{execution.id}')

        def _safe_ensure_dir(p: str):
            try:
                os.makedirs(p, exist_ok=True)
            except Exception:
                # 让外层处理（只有这种情况才可能真的无法提供任何报告）
                raise

        try:
            # 兼容 results 字段可能是 list 或 dict 的历史数据
            def _normalize_results(raw):
                if isinstance(raw, list):
                    return [r for r in raw if isinstance(r, dict)]
                if isinstance(raw, dict):
                    # 常见：{'results': [...], ...}
                    inner = raw.get("results")
                    if isinstance(inner, list):
                        return [r for r in inner if isinstance(r, dict)]
                    # 兜底：dict 的 values 里如果是 dict，当作列表
                    vals = list(raw.values())
                    if vals and all(isinstance(v, dict) for v in vals):
                        return vals
                return []

            results_list = _normalize_results(getattr(execution, "results", None))

            # 创建报告目录
            _safe_ensure_dir(results_dir)
            
            # 生成测试结果文件
            try:
                self._generate_test_result_files(execution, results_dir, results_list)
            except Exception:
                # 结果文件生成失败也要保证能看到 summary（最小可用）
                logger.exception("生成 allure-results 失败，将降级为 summary-only 报告")
                results_list = results_list if isinstance(results_list, list) else []
            
            # 生成Allure报告
            _safe_ensure_dir(report_output_dir)
            
            # 使用Allure命令行工具生成完整报告
            import subprocess
            import shutil
            from pathlib import Path
            
            # Allure命令行工具路径 - 使用相对路径
            base_dir = Path(__file__).resolve().parent.parent.parent
            
            # Determine executable name based on OS
            if os.name == 'nt':
                allure_executable = 'allure.bat'
            else:
                allure_executable = 'allure'
                
            allure_cmd = str(base_dir / 'allure' / 'bin' / allure_executable)

            if not os.path.exists(allure_cmd):
                logger.warning(f"Allure command not found at: {allure_cmd}, using fallback")
                # 尝试其他可能的路径
                possible_paths = [
                    base_dir / 'allure' / 'bin' / allure_executable,
                    Path('/usr/local/bin/allure'),  # 系统安装的allure
                    Path('/usr/bin/allure'),  # 系统安装的allure
                ]
                for path in possible_paths:
                    if path.exists():
                        allure_cmd = str(path)
                        break
                else:
                    allure_cmd = None
            
            # 生成 Allure 报告属于“尽力而为”，失败不应影响 summary 输出
            try:
                if allure_cmd:
                    try:
                        for attempt in range(3):  # 重试机制
                            try:
                                # 如果目录已存在，先清理
                                if os.path.exists(report_output_dir):
                                    shutil.rmtree(report_output_dir)
                                # 清理后立刻重建目录，避免后续回退复制/写文件时报目录不存在
                                _safe_ensure_dir(report_output_dir)

                                subprocess.run(
                                    [
                                        allure_cmd,
                                        "generate",
                                        results_dir,
                                        "--clean",
                                        "--output",
                                        report_output_dir,
                                    ],
                                    check=True,
                                    capture_output=True,
                                    text=True,
                                    timeout=30,
                                )
                                break
                            except subprocess.TimeoutExpired:
                                if attempt == 2:
                                    raise
                                import time as _time

                                _time.sleep(1)
                                continue
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        logger.warning(f"Allure command failed: {str(e)}, falling back to static files")

                    static_dir = os.path.join(settings.MEDIA_ROOT, "allure-static")
                    if os.path.exists(static_dir):
                        _safe_ensure_dir(report_output_dir)
                        for item in os.listdir(static_dir):
                            source = os.path.join(static_dir, item)
                            destination = os.path.join(report_output_dir, item)
                            if os.path.isdir(source):
                                shutil.copytree(source, destination, dirs_exist_ok=True)
                            else:
                                shutil.copy2(source, destination)

                # 始终确保有可用的 index.html（即使 Allure 不可用）
                if not os.path.exists(os.path.join(report_output_dir, "index.html")):
                    fallback_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title>接口测试报告（降级页）- {execution.test_suite.name}</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif; padding: 24px; }}
      .card {{ max-width: 900px; margin: 0 auto; border: 1px solid #eee; border-radius: 10px; padding: 20px; }}
      .title {{ font-size: 20px; font-weight: 700; margin-bottom: 8px; }}
      .muted {{ color: #666; }}
      .btn {{ display: inline-block; margin-top: 12px; padding: 10px 14px; background: #667eea; color: #fff; text-decoration: none; border-radius: 6px; }}
      code {{ background: #f6f6f6; padding: 2px 6px; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="card">
      <div class="title">接口测试报告（降级页）</div>
      <p class="muted">
        当前环境未成功生成 Allure 前端报告资源（通常是容器内缺少 Java 或 Allure 执行失败），因此这里展示的是可读的降级页。
      </p>
      <p>测试套件: <strong>{execution.test_suite.name}</strong></p>
      <p>状态: <strong>{execution.get_status_display()}</strong></p>
      <p>总请求数: <strong>{execution.total_requests}</strong>，通过: <strong>{execution.passed_requests}</strong>，失败: <strong>{execution.failed_requests}</strong></p>
      <p class="muted">你仍然可以查看概览页：<code>summary.html</code></p>
      <a class="btn" href="summary.html" target="_blank" rel="noopener">打开概览 summary.html</a>
    </div>
</body>
</html>
"""
                    _safe_ensure_dir(report_output_dir)
                    with open(os.path.join(report_output_dir, "index.html"), "w", encoding="utf-8") as f:
                        f.write(fallback_html)
            except Exception:
                logger.exception("Allure 报告生成/回退资源准备失败，将仅输出 summary.html")
            
            # 创建自定义的summary.html页面作为报告概览
            status_class = "status-passed" if execution.status == "COMPLETED" else "status-failed"
            index_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>测试报告概览 - {execution.test_suite.name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f5f7fa;
            color: #333;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header-content {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
            position: relative;
        }}
        .header-info {{
            flex: 1;
            text-align: center;
        }}
        .header-actions {{
            position: absolute;
            right: 2rem;
            bottom: 2rem;
        }}
        .allure-report-btn {{
            display: inline-block;
            padding: 0.8rem 1.5rem;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-radius: 6px;
            text-decoration: none;
            font-weight: bold;
            transition: all 0.3s ease;
        }}
        .allure-report-btn:hover {{
            background: rgba(255, 255, 255, 0.3);
            border-color: rgba(255, 255, 255, 0.5);
            transform: translateY(-2px);
            text-decoration: none;
        }}
        .status-row {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        .execution-time {{
            color: #666;
            font-size: 0.9rem;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}
        .summary-card {{
            background: white;
            border-radius: 10px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-top: 1rem;
        }}
        .summary-item {{
            text-align: center;
            padding: 1rem;
            border-radius: 8px;
        }}
        .summary-item.total {{
            background: #e3f2fd;
        }}
        .summary-item.passed {{
            background: #e8f5e9;
        }}
        .summary-item.failed {{
            background: #ffebee;
        }}
        .summary-number {{
            font-size: 2rem;
            font-weight: bold;
            display: block;
        }}
        .summary-label {{
            font-size: 0.9rem;
            opacity: 0.8;
        }}
        .status-badge {{
            display: inline-block;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-weight: bold;
            margin-bottom: 1rem;
        }}
        .status-passed {{
            background: #4caf50;
            color: white;
        }}
        .status-failed {{
            background: #f44336;
            color: white;
        }}
        .test-results {{
            background: white;
            border-radius: 10px;
            padding: 2rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .test-result-item {{
            padding: 1rem;
            border-left: 4px solid #eee;
            margin-bottom: 1rem;
            border-radius: 4px;
        }}
        .test-result-item.passed {{
            border-left-color: #4caf50;
            background: #f8fff8;
        }}
        .test-result-item.failed {{
            border-left-color: #f44336;
            background: #fff8f8;
        }}
        .test-header {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        .test-name {{
            font-weight: bold;
            font-size: 1.1rem;
        }}
        .test-method {{
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.9rem;
            margin-right: 0.5rem;
        }}
        .method-get {{ background: #2196f3; color: white; }}
        .method-post {{ background: #4caf50; color: white; }}
        .method-put {{ background: #ff9800; color: white; }}
        .method-delete {{ background: #f44336; color: white; }}
        .test-url {{
            color: #666;
            font-size: 0.9rem;
            margin: 0.5rem 0;
            word-break: break-all;
        }}
        .test-error {{
            color: #f44336;
            font-size: 0.9rem;
            margin-top: 0.5rem;
            padding: 0.5rem;
            background: #ffebee;
            border-radius: 4px;
        }}
        .footer {{
            text-align: center;
            margin-top: 2rem;
            padding: 1rem;
            color: #666;
            font-size: 0.9rem;
        }}
        a {{
            color: #667eea;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="header-info">
                <h1>接口测试报告</h1>
                <p>测试套件: {execution.test_suite.name}</p>
                <p>项目: {execution.test_suite.project.name}</p>
            </div>
            <div class="header-actions">
                <a href="index.html" target="_blank" class="allure-report-btn">查看完整Allure报告</a>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div class="summary-card">
            <div class="status-row">
                <div class="status-badge {status_class}">
                    状态: {execution.get_status_display()}
                </div>
                <span class="execution-time">
                    执行时间: {execution.created_at.strftime('%Y-%m-%d %H:%M:%S') if execution.created_at else 'N/A'}
                </span>
            </div>
            
            <div class="summary-grid">
                <div class="summary-item total">
                    <span class="summary-number">{execution.total_requests or 0}</span>
                    <span class="summary-label">总请求数</span>
                </div>
                <div class="summary-item passed">
                    <span class="summary-number">{execution.passed_requests or 0}</span>
                    <span class="summary-label">通过数</span>
                </div>
                <div class="summary-item failed">
                    <span class="summary-number">{execution.failed_requests or 0}</span>
                    <span class="summary-label">失败数</span>
                </div>
            </div>
        </div>
        
        <div class="test-results">
            <h2>测试结果详情</h2>
"""
            
            # 添加测试结果列表
            if results_list:
                for i, result in enumerate(results_list):
                    result_class = "passed" if result.get('passed', False) else "failed"
                    method = result.get('method') or 'GET'
                    method_class = f"method-{str(method).lower()}"
                    index_content += f"""
            <div class="test-result-item {result_class}">
                <div class="test-header">
                    <span class="test-method {method_class}">{method}</span>
                    <span class="test-name">{result.get('name', f'测试请求 {i+1}')}</span>
                </div>
                <div class="test-url">{result.get('url', '')}</div>
                <div><strong>状态:</strong> {'通过' if result.get('passed', False) else '失败'}</div>
                {f'<div class="test-error"><strong>错误:</strong> {result.get("error", "")}</div>' if result.get('error') else ""}
            </div>
"""
            
            index_content += f"""
        </div>
        <div class="footer">
            <p>报告生成时间: {execution.created_at.strftime('%Y-%m-%d %H:%M:%S') if execution.created_at else 'N/A'}</p>
        </div>
    </div>
</body>
</html>
"""
            # 保存为summary.html，避免覆盖Allure生成的index.html
            try:
                _safe_ensure_dir(report_output_dir)
                summary_file = os.path.join(report_output_dir, "summary.html")
                with open(summary_file, "w", encoding="utf-8") as f:
                    f.write(index_content)
            except Exception:
                logger.exception("写入 summary.html 失败")
                raise
            
            # 返回 Django 标准 media URL（生产 nginx 直接暴露 /media/；开发环境由前端补 /api 前缀走代理）
            return Response(
                {
                    "message": "Allure报告生成成功",
                    "report_url": f"{settings.MEDIA_URL}allure-reports/execution_{execution.id}/summary.html",
                }
            )
        except Exception as e:
            logger.exception("generate_allure_report 失败")
            # 兜底：尽量返回一个可访问的最简报告
            try:
                _safe_ensure_dir(report_output_dir)
                summary_file = os.path.join(report_output_dir, "summary.html")
                if not os.path.exists(summary_file):
                    minimal = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>测试报告</title></head>
<body><h1>测试报告</h1><p>生成报告时发生错误：{str(e)}</p></body></html>"""
                    with open(summary_file, "w", encoding="utf-8") as f:
                        f.write(minimal)
                return Response(
                    {
                        "message": "Allure报告生成成功（已降级）",
                        "report_url": f"{settings.MEDIA_URL}allure-reports/execution_{execution.id}/summary.html",
                        "warning": str(e),
                    }
                )
            except Exception:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def _generate_test_result_files(self, execution, report_dir, results_list=None):
        """生成测试结果文件"""
        results_list = results_list or []
        # 生成容器文件，定义测试套件
        container_data = {
            "uuid": str(execution.id),
            "name": execution.test_suite.name,
            "children": []
        }
        
        # 为每个测试请求添加到children列表
        if results_list:
            for i, result in enumerate(results_list):
                container_data["children"].append(f"{execution.id}-{i}")
        
        # 保存容器文件
        container_file_path = os.path.join(report_dir, f'{execution.id}-container.json')
        with open(container_file_path, 'w', encoding='utf-8') as f:
            json.dump(container_data, f, ensure_ascii=False, indent=2)
        
        # 只生成每个测试请求的结果文件，不生成测试套件的结果文件
        if results_list:
            for i, result in enumerate(results_list):
                request_result = {
                    "uuid": f"{execution.id}-{i}",
                    "name": result.get('name', f'测试请求 {i+1}'),
                    "status": "passed" if result.get('passed', False) else "failed",
                    "stage": "finished",
                    "start": int(time.time() * 1000) - 1000,  # 模拟开始时间
                    "stop": int(time.time() * 1000),  # 模拟结束时间
                    "description": f"Method: {result.get('method', 'GET')}\nURL: {result.get('url', '')}",
                    "historyId": f"{execution.test_suite.id}-{i}",
                    "fullName": f"{execution.test_suite.name} / {result.get('name', f'请求 {i+1}')}",
                    "links": [],
                    "labels": [
                        {"name": "suite", "value": execution.test_suite.name},
                        {"name": "testClass", "value": execution.test_suite.name},
                        {"name": "package", "value": "api_testing"},
                        {"name": "project", "value": execution.test_suite.project.name}
                    ],
                    "parameters": [
                        {"name": "method", "value": result.get('method', 'GET')},
                        {"name": "url", "value": result.get('url', '')}
                    ],
                    "steps": [
                        {
                            "name": "发送请求",
                            "status": "passed",
                            "stage": "finished",
                            "start": int(time.time() * 1000) - 1000,
                            "stop": int(time.time() * 1000) - 500,
                            "steps": []
                        },
                        {
                            "name": "验证响应",
                            "status": "passed" if result.get('passed', False) else "failed",
                            "stage": "finished",
                            "start": int(time.time() * 1000) - 500,
                            "stop": int(time.time() * 1000),
                            "steps": []
                        }
                    ]
                }
                
                # 添加错误信息（如果有的话）
                if result.get('error'):
                    request_result["statusDetails"] = {
                        "message": result.get('error'),
                        "trace": ""
                    }
                
                # 保存请求结果
                request_file_path = os.path.join(report_dir, f'{execution.id}-{i}-result.json')
                with open(request_file_path, 'w', encoding='utf-8') as f:
                    json.dump(request_result, f, ensure_ascii=False, indent=2)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """用户列表接口，用于项目成员选择"""
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name']


class ScheduledTaskViewSet(viewsets.ModelViewSet):
    """定时任务视图集"""
    queryset = ScheduledTask.objects.all()
    serializer_class = ScheduledTaskSerializer
    permission_classes = [IsAuthenticated]
    # 支持筛选/搜索/排序（否则前端筛选条件不会生效）
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['task_type', 'trigger_type', 'status']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'last_run_time']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """取消用户隔离：所有登录用户可见全部任务"""
        return super().get_queryset()
    
    @action(detail=True, methods=['post'])
    def run_now(self, request, pk=None):
        """立即执行定时任务"""
        import logging
        logger = logging.getLogger(__name__)
        logger.info("=== run_now 方法被调用 ===")
        
        task = self.get_object()
        logger.info(f"获取任务对象: {task.id} - {task.name}")
        
        try:
            # 创建执行日志
            execution_log = TaskExecutionLog.objects.create(
                task=task,
                status='PENDING',
                executed_by=request.user
            )
            logger.info(f"创建执行日志: {execution_log.id}")
            
            # 异步执行任务
            logger.info("调用 _execute_task_async 方法")
            self._execute_task_async(task, execution_log)
            
            logger.info("任务开始执行")
            return Response(
                {'message': '任务已开始执行', 'execution_id': execution_log.id},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {'error': f'执行任务失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活定时任务"""
        task = self.get_object()
        
        if task.status == 'ACTIVE':
            return Response(
                {'error': '任务已经是激活状态'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        task.status = 'ACTIVE'
        task.next_run_time = task.calculate_next_run()
        task.save()
        
        return Response(
            {'message': '任务已激活', 'next_run_time': task.next_run_time},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """暂停定时任务"""
        task = self.get_object()
        
        if task.status == 'PAUSED':
            return Response(
                {'error': '任务已经是暂停状态'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        task.status = 'PAUSED'
        task.next_run_time = None
        task.save()
        
        return Response(
            {'message': '任务已暂停'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['get'])
    def execution_logs(self, request, pk=None):
        """获取任务执行日志"""
        task = self.get_object()
        
        # 检查权限
        if not request.user.is_staff and task.created_by != request.user:
            return Response(
                {'error': '无权查看此任务的执行日志'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        logs = TaskExecutionLog.objects.filter(task=task).order_by('-created_at')
        page = self.paginate_queryset(logs)
        
        if page is not None:
            serializer = TaskExecutionLogSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = TaskExecutionLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    def _execute_task_async(self, task, execution_log):
        """异步执行任务"""
        import threading
        from datetime import datetime
        
        # 添加测试日志
        import logging
        logger = logging.getLogger(__name__)
        logger.info("=== _execute_task_async 方法被调用 ===")
        
        def execute():
            try:
                # 更新执行状态
                execution_log.status = 'RUNNING'
                execution_log.start_time = timezone.now()
                execution_log.save()
                
                # 执行任务
                if task.task_type == 'TEST_SUITE':
                    result = self._execute_test_suite(task)
                elif task.task_type == 'API_REQUEST':
                    result = self._execute_api_request(task)
                else:
                    raise ValueError(f"未知的任务类型: {task.task_type}")
                
                # 更新执行结果
                execution_log.status = 'COMPLETED'
                execution_log.end_time = timezone.now()
                execution_log.result = result
                execution_log.save()
                
                # 更新任务统计
                task.update_run_stats(success=True)
                task.last_result = result
                task.save()
                
                logger.info("=== 开始检查发送成功通知 ===")
                # 发送通知（如果配置了）
                # 检查任务是否有通知设置
                notification_setting = None
                if hasattr(task, 'notification_settings'):
                    try:
                        notification_setting = task.notification_settings.first()
                        logger.info(f"获取到通知设置: {notification_setting}")
                        if notification_setting:
                            logger.info(f"通知设置详情 - ID: {notification_setting.id}, 是否启用: {notification_setting.is_enabled}, 成功通知: {notification_setting.notify_on_success}")
                        else:
                            logger.info("没有找到通知设置")
                    except Exception as e:
                        logger.error(f"获取任务通知设置时出错: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    logger.info("任务没有notification_settings属性")
                
                if notification_setting and notification_setting.is_enabled:
                    logger.info("通知设置已启用，准备发送成功通知")
                    if notification_setting.notify_on_success:
                        logger.info("调用 _send_notification 方法发送成功通知")
                        self._send_notification(task, execution_log, success=True)
                    else:
                        logger.info("通知设置中未启用成功通知")
                else:
                    logger.info("通知设置未启用或不存在，跳过成功通知")
                logger.info("=== 结束检查发送成功通知 ===")
                
            except Exception as e:
                # 记录执行失败
                execution_log.status = 'FAILED'
                execution_log.end_time = timezone.now()
                execution_log.error_message = str(e)
                execution_log.save()
                
                # 更新任务统计
                task.update_run_stats(success=False)
                task.error_message = str(e)
                task.save()
                
                logger.info("=== 开始检查发送失败通知 ===")
                # 发送失败通知（如果配置了）
                # 检查任务是否有通知设置
                notification_setting = None
                if hasattr(task, 'notification_settings'):
                    try:
                        notification_setting = task.notification_settings.first()
                        logger.info(f"获取到通知设置（失败情况）: {notification_setting}")
                        if notification_setting:
                            logger.info(f"通知设置详情（失败情况） - ID: {notification_setting.id}, 是否启用: {notification_setting.is_enabled}, 失败通知: {notification_setting.notify_on_failure}")
                        else:
                            logger.info("没有找到通知设置（失败情况）")
                    except Exception as e:
                        logger.error(f"获取任务通知设置时出错（失败情况）: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    logger.info("任务没有notification_settings属性（失败情况）")
                
                if notification_setting and notification_setting.is_enabled:
                    logger.info("通知设置已启用，准备发送失败通知")
                    if notification_setting.notify_on_failure:
                        logger.info("调用 _send_notification 方法发送失败通知")
                        self._send_notification(task, execution_log, success=False)
                    else:
                        logger.info("通知设置中未启用失败通知")
                else:
                    logger.info("通知设置未启用或不存在，跳过失败通知")
                logger.info("=== 结束检查发送失败通知 ===")
        
        # 在新线程中执行
        thread = threading.Thread(target=execute)
        thread.daemon = True
        thread.start()
    
    def _execute_test_suite(self, task):
        """执行测试套件"""
        from .utils import execute_test_suite
        
        result = execute_test_suite(
            task.test_suite, 
            task.environment, 
            task.created_by
        )
        return result
    
    def _execute_api_request(self, task):
        """执行API请求"""
        from .utils import execute_api_request
        
        result = execute_api_request(
            task.api_request, 
            task.environment, 
            task.created_by
        )
        return result
    
    def _send_notification(self, task, execution_log, success=True):
        """发送通知邮件"""
        try:
            import logging
            logger = logging.getLogger(__name__)
            from django.core.mail import send_mail
            from django.conf import settings

            logger.info("=== _send_notification 方法被调用 ===")
            logger.info(f"任务ID: {task.id}, 任务名称: {task.name}, 执行状态: {success}")

            # 检查任务是否有通知设置
            notification_setting = None
            if hasattr(task, 'notification_settings'):
                try:
                    notification_setting = task.notification_settings.first()
                    logger.info(f"获取到通知设置: {notification_setting}")
                except Exception as e:
                    logger.error(f"获取任务通知设置时出错: {e}")
                    import traceback
                    traceback.print_exc()

            if not notification_setting:
                logger.warning(f"任务 {task.id} 没有通知设置")
                return

            logger.info(f"通知设置详情 - ID: {notification_setting.id}, 是否启用: {notification_setting.is_enabled}")

            if not notification_setting.is_enabled:
                logger.info(f"任务 {task.id} 的通知设置未启用")
                return

            # 检查是否应该发送通知
            execution_status = 'success' if success else 'failed'
            should_notify = notification_setting.should_notify(execution_status)
            logger.info(f"执行状态: {execution_status}, should_notify结果: {should_notify}")
            if not should_notify:
                logger.info(f"根据执行状态 {execution_status}，不应该发送通知")
                return

            logger.info("通过了通知条件检查")

            # 获取通知配置
            notification_config = notification_setting.get_notification_config()
            
            # 检查是否有通知配置或自定义配置
            has_config = notification_config is not None
            has_custom_bots = bool(notification_setting.custom_webhook_bots)
            has_custom_recipients = notification_setting.custom_recipients.exists()
            # 关键补充：如果在定时任务本身配置了 notify_emails，也视为“具备有效的通知配置”
            has_task_notify_emails = bool(getattr(task, 'notify_emails', None))
            
            if not (has_config or has_custom_bots or has_custom_recipients or has_task_notify_emails):
                logger.warning("没有找到通知配置、自定义Webhook或任务级通知邮箱，跳过通知发送")
                return

            if notification_config:
                logger.info(f"找到了通知配置: {notification_config.name}")
            else:
                logger.info("使用自定义通知设置")

            # 根据通知类型发送不同类型的通知
            logger.info(f"通知类型: {notification_setting.notification_type}")

            if notification_setting.notification_type in ['email', 'both']:
                logger.info("发送邮件通知")
                self._send_email_notification(task, execution_log, notification_setting, notification_config, success)

            if notification_setting.notification_type in ['webhook', 'both']:
                logger.info("发送Webhook通知")
                self._send_webhook_notification(task, execution_log, notification_setting, notification_config, success)

        except Exception as e:
            logger.error(f"发送通知失败: {str(e)}", exc_info=True)

    def _send_email_notification(self, task, execution_log, notification_setting, notification_config, success):
        """发送邮件通知"""
        try:
            import logging
            logger = logging.getLogger(__name__)
            from django.core.mail import send_mail
            from django.conf import settings

            logger.info("=== 开始发送邮件通知 ===")

            # 准备邮件内容
            subject = f"定时任务执行{'成功' if success else '失败'}: {task.name}"

            # 过滤掉详细的测试结果数据，只保留概要信息
            summary_info = '无详细信息'
            if execution_log.result:
                result_data = execution_log.result
                # 只保留高级概要字段,过滤掉详细的'results'数组
                summary_fields_cn = {
                    '是否成功': result_data.get('success'),
                    '执行ID': result_data.get('execution_id'),
                    '通过数': result_data.get('passed_count'),
                    '失败数': result_data.get('failed_count'),
                    '总数': result_data.get('total_count')
                }
                # 只保留有值的字段；布尔值转中文
                lines = []
                for k, v in summary_fields_cn.items():
                    if v is None:
                        continue
                    if isinstance(v, bool):
                        v = '是' if v else '否'
                    lines.append(f'{k}: {v}')
                summary_info = '\n'.join(lines) if lines else '无详细信息'

            message = f"""
            任务名称: {task.name}
            执行状态: {'成功' if success else '失败'}
            执行时间: {execution_log.created_at.strftime('%Y-%m-%d %H:%M:%S')}
            任务类型: {'测试套件执行' if task.task_type == 'TEST_SUITE' else 'API请求执行'}

            执行概要:
            {summary_info}

            错误信息:
            {execution_log.error_message if execution_log.error_message else '无错误信息'}
            """

            # 获取收件人列表
            recipients = []
            # 首先检查自定义收件人
            if notification_setting.custom_recipients.exists():
                recipients = [user.email for user in notification_setting.custom_recipients.all() if user.email]
                logger.info(f"使用自定义收件人: {recipients}")

            # 如果定时任务表单中指定了通知邮箱，也添加到收件人列表
            if hasattr(task, 'notify_emails') and task.notify_emails:
                if isinstance(task.notify_emails, list):
                    recipients.extend(task.notify_emails)
                else:
                    recipients.append(task.notify_emails)
                logger.info(f"添加任务表单中的通知邮箱: {task.notify_emails}")

            # 去重收件人
            recipients = list(set(recipients))
            logger.info(f"最终收件人列表: {recipients}")

            if not recipients:
                logger.warning("没有找到任何邮件收件人")
                return

            # 发送邮件
            from_email = settings.DEFAULT_FROM_EMAIL
            logger.info(f"准备发送邮件，发件人: {from_email}, 收件人: {recipients}")
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=recipients,
                fail_silently=False,
            )
            logger.info("邮件发送成功")

            # 记录通知日志（参照UI自动化测试的方式，添加task_type快照）
            from .models import NotificationLog
            NotificationLog.objects.create(
                task=task,
                task_name=task.name,
                notification_type='task_execution',
                sender_name='系统邮件通知',
                sender_email=from_email,
                recipient_info=[{'email': email} for email in recipients],
                notification_content=message,
                status='success',
                sent_at=timezone.now(),
                response_info={'task_type': getattr(task, 'task_type', None)}
            )

        except Exception as e:
            logger.error(f"发送邮件通知失败: {str(e)}", exc_info=True)
            # 记录通知发送失败的日志
            try:
                from .models import NotificationLog
                # 在 response_info 中写入 task_type 快照，避免后续修改任务类型污染历史数据
                NotificationLog.objects.create(
                    task=task,
                    task_name=task.name,
                    notification_type='task_execution',
                    sender_name='系统邮件通知',
                    sender_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_info=[{'email': email} for email in recipients] if 'recipients' in locals() else [],
                    notification_content=f"发送邮件通知失败: {str(e)}",
                    status='failed',
                    error_message=str(e),
                    response_info={'task_type': getattr(task, 'task_type', None)}
                )
            except:
                pass

    def _send_webhook_notification(self, task, execution_log, notification_setting, notification_config, success):
        """发送Webhook通知"""
        try:
            import logging
            import requests
            import json
            from django.utils import timezone  # 确保timezone在方法内可用
            logger = logging.getLogger(__name__)

            logger.info("=== 开始发送Webhook通知 ===")

            all_webhook_bots = []
            
            # 1. 首先获取配置中的机器
            if notification_config:
                bots = notification_config.get_webhook_bots()
                for bot in bots:
                    if bot.get('enabled', True):
                        all_webhook_bots.append(bot)
            
            # 2. 获取统一通知配置中的机器人（如果notification_config为空或没有找到机器人）
            if not all_webhook_bots:
                try:
                    from apps.core.models import UnifiedNotificationConfig
                    unified_configs = UnifiedNotificationConfig.objects.filter(
                        config_type__in=['webhook_wechat', 'webhook_feishu', 'webhook_dingtalk'],
                        is_active=True
                    )
                    logger.info(f"检查统一通知配置，找到 {unified_configs.count()} 个配置")
                    for config in unified_configs:
                        bots = config.get_webhook_bots()
                        for bot in bots:
                            # 只添加启用了"接口测试"的机器人
                            if bot.get('enabled', True) and bot.get('enable_api_testing', True):
                                all_webhook_bots.append(bot)
                                logger.info(f"添加统一配置机器人: {bot.get('name')} (接口测试已启用)")
                            elif bot.get('enabled', True):
                                logger.info(f"统一配置机器人 {bot.get('name')} 未启用接口测试，跳过")
                except ImportError as e:
                    logger.warning(f"无法导入统一通知配置: {e}")
                except Exception as e:
                    logger.error(f"获取统一通知配置时出错: {e}", exc_info=True)
            
            # 3. 获取自定义机器人配置 (覆盖同名/同类型或者是累加，这里选择累加)
            if notification_setting.custom_webhook_bots:
                logger.info(f"发现自定义Webhook机器人配置: {len(notification_setting.custom_webhook_bots)}个")
                for bot_type, bot_config in notification_setting.custom_webhook_bots.items():
                    # 构造统一的bot结构
                    bot_data = {
                        'type': bot_type,
                        'name': bot_config.get('name', f'自定义{bot_type}机器人'),
                        'webhook_url': bot_config.get('webhook_url'),
                        'enabled': bot_config.get('enabled', True)
                    }
                    if bot_type == 'dingtalk' and bot_config.get('secret'):
                        bot_data['secret'] = bot_config.get('secret')
                        
                    if bot_data.get('enabled', True) and bot_data.get('webhook_url'):
                        all_webhook_bots.append(bot_data)

            if not all_webhook_bots:
                logger.warning("没有找到任何启用的webhook机器人配置")
                # 即使没有找到机器人配置，也要创建通知日志记录，确保在通知列表中可见
                try:
                    from .models import NotificationLog
                    NotificationLog.objects.create(
                        task=task,
                        task_name=task.name,
                        notification_type='task_execution',
                        sender_name='系统Webhook通知',
                        sender_email='system@notification.com',  # 参照UI自动化测试
                        recipient_info=[],
                        webhook_bot_info={},
                        notification_content=f"未找到任何启用的webhook机器人配置",
                        status='failed',
                        error_message='没有找到任何启用的webhook机器人配置',
                        sent_at=timezone.now(),
                        response_info={'task_type': getattr(task, 'task_type', None)}
                    )
                except Exception as log_error:
                    logger.error(f"创建通知日志失败: {str(log_error)}", exc_info=True)
                return

            logger.info(f"总共找到 {len(all_webhook_bots)} 个待发送的webhook机器人")

            # 准备通知内容
            status_text = '成功' if success else '失败'
            status_color = 'green' if success else 'red'
            
            # 准备执行概要信息（参照邮件通知的格式）
            summary_info = '无详细信息'
            if execution_log.result:
                result_data = execution_log.result
                # 只保留高级概要字段,过滤掉详细的'results'数组
                summary_fields_cn = {
                    '是否成功': result_data.get('success'),
                    '执行ID': result_data.get('execution_id'),
                    '通过数': result_data.get('passed_count'),
                    '失败数': result_data.get('failed_count'),
                    '总数': result_data.get('total_count')
                }
                # 只保留有值的字段；布尔值转中文
                summary_lines = []
                for k, v in summary_fields_cn.items():
                    if v is None:
                        continue
                    if isinstance(v, bool):
                        v = '是' if v else '否'
                    summary_lines.append(f'{k}: {v}')
                if summary_lines:
                    summary_info = '\n'.join(summary_lines)
            
            # 准备错误信息
            error_info = execution_log.error_message if execution_log.error_message else '无错误信息'

            # 为不同的机器人平台准备消息格式
            for bot in all_webhook_bots:
                if not bot.get('enabled', True) or not bot.get('webhook_url'):
                    logger.info(f"跳过未启用或无URL的机器人: {bot.get('name', 'Unknown')}")
                    continue

                bot_type = bot.get('type', 'unknown')
                webhook_url = bot['webhook_url']
                logger.info(f"发送通知到 {bot_type} 机器人: {bot.get('name', 'Unknown')}")

                # 根据机器人类型构造消息格式
                if bot_type == 'wechat':  # 企业微信
                    message_data = {
                        "msgtype": "markdown",
                        "markdown": {
                            "content": f"""**定时任务执行{status_text}**

任务名称: {task.name}

执行状态: {status_text}

执行时间: {execution_log.created_at.strftime('%Y-%m-%d %H:%M:%S')}

任务类型: {'测试套件执行' if task.task_type == 'TEST_SUITE' else 'API请求执行'}

执行概要:
{summary_info}

错误信息:
{error_info}"""
                        }
                    }
                elif bot_type == 'feishu':  # 飞书
                    message_data = {
                        "msg_type": "interactive",
                        "card": {
                            "elements": [{
                                "tag": "div",
                                "text": {
                                    "content": f"**定时任务执行{status_text}**\n任务名称: {task.name}\n执行状态: {status_text}\n执行时间: {execution_log.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n任务类型: {'测试套件执行' if task.task_type == 'TEST_SUITE' else 'API请求执行'}\n\n执行概要:\n{summary_info}\n\n错误信息:\n{error_info}",
                                    "tag": "lark_md"
                                }
                            }],
                            "header": {
                                "title": {
                                    "content": f"定时任务执行{status_text}",
                                    "tag": "plain_text"
                                },
                                "template": "green" if success else "red"
                            }
                        }
                    }
                elif bot_type == 'dingtalk':  # 钉钉
                    message_data = {
                        "msgtype": "markdown",
                        "markdown": {
                            "title": f"定时任务执行{status_text}",
                            "text": f"""**定时任务执行{status_text}**

任务名称: {task.name}

执行状态: {status_text}

执行时间: {execution_log.created_at.strftime('%Y-%m-%d %H:%M:%S')}

任务类型: {'测试套件执行' if task.task_type == 'TEST_SUITE' else 'API请求执行'}

执行概要:
{summary_info}

错误信息:
{error_info}"""
                        }
                    }

                    # 钉钉机器人签名验证
                    secret = bot.get('secret')
                    if secret:
                        import time
                        import hmac
                        import hashlib
                        import base64
                        import urllib.parse

                        timestamp = str(round(time.time() * 1000))
                        string_to_sign = f'{timestamp}\n{secret}'
                        string_to_sign_enc = string_to_sign.encode('utf-8')
                        secret_enc = secret.encode('utf-8')
                        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
                        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

                        # 在URL中添加签名参数
                        if '?' in webhook_url:
                            webhook_url += f'&timestamp={timestamp}&sign={sign}'
                        else:
                            webhook_url += f'?timestamp={timestamp}&sign={sign}'

                        logger.info(f"钉钉机器人签名验证 - 时间戳: {timestamp}")
                        logger.info(f"签名字符串: {string_to_sign}")
                        logger.info(f"生成的签名: {sign}")
                        logger.info(f"最终URL: {webhook_url}")
                    else:
                        logger.info("钉钉机器人未配置签名密钥，使用无签名模式")
                else:  # 通用格式
                    message_data = {
                        "text": f"定时任务执行{status_text}\n任务名称: {task.name}\n执行状态: {status_text}\n执行时间: {execution_log.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n任务类型: {'测试套件执行' if task.task_type == 'TEST_SUITE' else 'API请求执行'}\n\n执行概要:\n{summary_info}\n\n错误信息:\n{error_info}"
                    }

                # 发送webhook请求（参照UI自动化测试的方式）
                try:
                    logger.info(f"发送请求到: {webhook_url}")
                    logger.info(f"消息数据: {json.dumps(message_data, ensure_ascii=False, indent=2)}")
                    
                    response = requests.post(
                        webhook_url,
                        json=message_data,
                        headers={'Content-Type': 'application/json'},
                        timeout=10
                    )
                    
                    logger.info(f"响应状态码: {response.status_code}")
                    logger.info(f"响应内容: {response.text}")

                    if response.status_code == 200:
                        logger.info(f"成功发送通知到 {bot.get('name', 'Unknown')}")

                        # 记录通知日志（参照UI自动化测试的方式，直接传入bot对象）
                        from .models import NotificationLog
                        NotificationLog.objects.create(
                            task=task,
                            task_name=task.name,
                            notification_type='task_execution',
                            sender_name='系统Webhook通知',
                            sender_email='system@notification.com',
                            recipient_info=[{'name': bot.get('name', 'Unknown'), 'webhook_url': webhook_url}],
                            webhook_bot_info=bot,  # 直接传入整个bot对象，参照UI自动化测试
                            notification_content=json.dumps(message_data, ensure_ascii=False),
                            status='success',
                            response_info={
                                'status_code': response.status_code,
                                'response': response.text,
                                'task_type': getattr(task, 'task_type', None),
                            },
                            sent_at=timezone.now()
                        )
                    else:
                        logger.error(f"发送通知失败，状态码: {response.status_code}, 响应: {response.text}")

                        # 记录失败日志（参照UI自动化测试的方式）
                        from .models import NotificationLog
                        NotificationLog.objects.create(
                            task=task,
                            task_name=task.name,
                            notification_type='task_execution',
                            sender_name='系统Webhook通知',
                            sender_email='system@notification.com',
                            recipient_info=[{'name': bot.get('name', 'Unknown'), 'webhook_url': webhook_url}],
                            webhook_bot_info=bot,  # 直接传入整个bot对象
                            notification_content=json.dumps(message_data, ensure_ascii=False),
                            status='failed',
                            error_message=f'HTTP {response.status_code}: {response.text}',
                            response_info={
                                'status_code': response.status_code,
                                'response': response.text,
                                'task_type': getattr(task, 'task_type', None),
                            }
                        )

                except requests.exceptions.RequestException as e:
                    logger.error(f"发送webhook请求失败: {str(e)}")

                    # 记录失败日志（参照UI自动化测试的方式）
                    from .models import NotificationLog
                    NotificationLog.objects.create(
                        task=task,
                        task_name=task.name,
                        notification_type='task_execution',
                        sender_name='系统Webhook通知',
                        sender_email='system@notification.com',
                        recipient_info=[{'name': bot.get('name', 'Unknown'), 'webhook_url': webhook_url}],
                        webhook_bot_info=bot,  # 直接传入整个bot对象
                        notification_content=json.dumps(message_data, ensure_ascii=False),
                        status='failed',
                        error_message=str(e),
                        response_info={'task_type': getattr(task, 'task_type', None)}
                    )

            logger.info("=== 结束发送Webhook通知 ===")

        except Exception as e:
            logger.error(f"发送Webhook通知失败: {str(e)}", exc_info=True)


class TaskExecutionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """任务执行日志视图集"""
    queryset = TaskExecutionLog.objects.all()
    serializer_class = TaskExecutionLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['task', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        return TaskExecutionLog.objects.filter(
            task__created_by=user
        ).select_related('task', 'executed_by')




# ================ 通知管理相关视图集 ================

class NotificationConfigViewSet(viewsets.ModelViewSet):
    """通知配置视图集"""
    queryset = NotificationConfig.objects.all()
    serializer_class = NotificationConfigSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['is_active', 'is_default', 'config_type']
    search_fields = ['name', 'sender_name', 'sender_email']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        queryset = NotificationConfig.objects.filter(
            models.Q(created_by=user) | models.Q(is_default=True)
        )
        
        # 支持按配置类型过滤
        config_type = self.request.query_params.get('config_type', None)
        if config_type:
            queryset = queryset.filter(config_type=config_type)
        
        return queryset.distinct()
    
    @action(detail=True, methods=['post'], url_path='add-bot')
    def add_webhook_bot(self, request, pk=None):
        """添加Webhook机器人配置"""
        config = self.get_object()
        bot_type = request.data.get('bot_type')
        name = request.data.get('name')
        webhook_url = request.data.get('webhook_url')
        
        if not all([bot_type, name, webhook_url]):
            return Response({'error': '请提供完整的机器人信息'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取现有配置
        webhook_bots = config.webhook_bots or {}
        webhook_bots[bot_type] = {
            'name': name,
            'webhook_url': webhook_url,
            'enabled': True
        }
        
        config.webhook_bots = webhook_bots
        config.save()
        
        serializer = NotificationConfigDetailSerializer(config)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='remove-bot')
    def remove_webhook_bot(self, request, pk=None):
        """移除Webhook机器人配置"""
        config = self.get_object()
        bot_type = request.data.get('bot_type')

        if not bot_type:
            return Response({'error': '请提供机器人类型'}, status=status.HTTP_400_BAD_REQUEST)

        webhook_bots = config.webhook_bots or {}
        if bot_type in webhook_bots:
            del webhook_bots[bot_type]
            config.webhook_bots = webhook_bots
            config.save()
            return Response({'message': f'{bot_type}机器人已移除'})

        return Response({'error': '未找到该机器人配置'}, status=status.HTTP_404_NOT_FOUND)


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """通知日志视图集"""
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'notification_type']
    search_fields = ['task_name', 'notification_content']
    ordering_fields = ['created_at', 'sent_at']
    ordering = ['-created_at']
    
    # 参照UI自动化测试，不重写get_queryset，直接返回所有记录
    # 权限控制通过permission_classes处理
    
    @action(detail=True, methods=['get'], url_path='detail')
    def get_notification_detail(self, request, pk=None):
        """获取通知详情"""
        notification = self.get_object()
        serializer = NotificationLogDetailSerializer(notification)
        return Response(serializer.data)


class TaskNotificationSettingViewSet(viewsets.ModelViewSet):
    """定时任务通知设置视图集"""
    queryset = TaskNotificationSetting.objects.all()
    serializer_class = TaskNotificationSettingSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['task', 'is_enabled']
    ordering = ['-created_at']
    
    def get_queryset(self):
        user = self.request.user
        return TaskNotificationSetting.objects.filter(
            models.Q(
                task__test_suite__project__in=ApiProject.objects.filter(
                    models.Q(owner=user) | models.Q(members=user)
                )
            ) | models.Q(
                task__api_request__collection__project__in=ApiProject.objects.filter(
                    models.Q(owner=user) | models.Q(members=user)
                )
            ) | models.Q(
                task__created_by=user
            )
        ).distinct()
    
    @action(detail=True, methods=['post'], url_path='update-settings')
    def update_notification_settings(self, request, pk=None):
        """更新通知设置"""
        setting = self.get_object()
        serializer = TaskNotificationSettingDetailSerializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)


# ================ 通知管理相关模型 ================




class OperationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """操作日志视图集"""
    queryset = OperationLog.objects.all()
    serializer_class = OperationLogSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['operation_type', 'resource_type', 'user']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """只返回当前用户相关的操作日志"""
        user = self.request.user
        # 可以根据需要调整权限逻辑，这里返回所有日志
        return OperationLog.objects.all().order_by('-created_at')


class ApiDashboardViewSet(viewsets.ViewSet):
    """API测试仪表盘视图集"""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """获取仪表盘统计数据"""
        user = request.user
        
        # 获取用户可访问的项目ID列表
        accessible_projects = ApiProject.objects.filter(
            models.Q(owner=user) | models.Q(members=user)
        ).distinct()
        project_ids = accessible_projects.values_list('id', flat=True)

        # 统计数据
        project_count = accessible_projects.count()
        
        # 接口数量 (通过项目关联)
        interface_count = ApiRequest.objects.filter(
            collection__project_id__in=project_ids
        ).count()
        
        # 测试套件数量
        suite_count = TestSuite.objects.filter(
            project_id__in=project_ids
        ).count()
        
        # 执行记录数量 (仅统计当前用户有权访问的)
        history_count = RequestHistory.objects.filter(
            request__collection__project_id__in=project_ids
        ).count()

        return Response({
            'project_count': project_count,
            'interface_count': interface_count,
            'suite_count': suite_count,
            'history_count': history_count
        })
