import logging
import os

from asgiref.sync import async_to_sync
from django.http import FileResponse, HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import OpsEnvironment, Text2SQLRecord, LogQuerySession, FileTransferTask
from .serializers import (
    OpsEnvironmentSerializer,
    Text2SQLRecordSerializer,
    LogQuerySessionSerializer,
    FileTransferTaskSerializer,
)

logger = logging.getLogger(__name__)


class OpsEnvironmentViewSet(viewsets.ModelViewSet):
    """运维环境配置"""
    queryset = OpsEnvironment.objects.all()
    serializer_class = OpsEnvironmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get('project')
        if project_id:
            qs = qs.filter(project_id=project_id)
        return qs

    @action(detail=True, methods=['post'], url_path='connect')
    def connect(self, request, pk=None):
        """测试环境连接并同步状态"""
        env = self.get_object()
        # 本地访问方式：校验挂载目录是否真实存在
        if env.access_method == 'local':
            root = os.path.normpath(env.current_dir or '/host_logs')
            ok = os.path.isdir(root)
            env.status = 'ready' if ok else 'error'
            env.last_sync = __import__('django.utils.timezone', fromlist=['now']).now()
            env.save(update_fields=['status', 'last_sync'])
            return Response({
                'detail': '连接成功（本地）' if ok else f'目录不存在: {root}',
                'status': env.status,
                'last_sync': env.last_sync,
            })
        # TODO: SSH 方式用 paramiko 实际连接
        env.status = 'ready'
        env.last_sync = __import__('django.utils.timezone', fromlist=['now']).now()
        env.save(update_fields=['status', 'last_sync'])
        return Response({
            'detail': '连接成功（演示模式）',
            'status': env.status,
            'last_sync': env.last_sync,
        })

    @action(detail=True, methods=['get'], url_path='databases')
    def databases(self, request, pk=None):
        """获取环境下的数据库列表"""
        env = self.get_object()
        # TODO: 真实场景从数据库元数据读取
        dbs = [db.strip() for db in (env.database_scope or '').split(',') if db.strip()]
        if not dbs:
            dbs = [env.db_name or 'testhub']
        return Response({'databases': dbs})


class Text2SQLViewSet(viewsets.ModelViewSet):
    """Text2SQL 工作台"""
    queryset = Text2SQLRecord.objects.all()
    serializer_class = Text2SQLRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        env_id = self.request.query_params.get('environment')
        if env_id:
            qs = qs.filter(environment_id=env_id)
        return qs

    @action(detail=True, methods=['post'], url_path='generate')
    def generate(self, request, pk=None):
        """根据自然语言生成 SQL"""
        record = self.get_object()
        # 环境锁定：前端必须传当前选中的 env id，不一致说明用户已切环境但用了旧记录，必须重新点生成
        client_env_id = request.data.get('current_env_id')
        if client_env_id is not None and str(client_env_id) != str(record.environment_id):
            return Response({
                'detail': (
                    f"该 SQL 记录绑定的是环境「{record.environment.name}」，"
                    f"但你当前选择的是其他环境。请重新点击「生成 SQL」按当前环境生成。"
                )
            }, status=status.HTTP_400_BAD_REQUEST)
        if record.environment.access_method != 'db':
            return Response({
                'detail': (
                    f"环境「{record.environment.name}」的访问方式是"
                    f"「{record.environment.get_access_method_display()}」，不是数据库直连，无法生成/执行 SQL。"
                    "请到「环境管理」新建一个「数据库直连」类型的环境（host 填 host.docker.internal 或宿主 IP），"
                    "或在下拉中切换到已存在的数据库环境。"
                )
            }, status=status.HTTP_400_BAD_REQUEST)
        if not (record.environment.db_host or '').strip():
            return Response({
                'detail': (
                    f"环境「{record.environment.name}」是数据库直连类型，但未填写数据库主机（db_host）。"
                    "请到「环境管理」编辑该环境，host 填 host.docker.internal 或宿主 IP。"
                )
            }, status=status.HTTP_400_BAD_REQUEST)
        question = request.data.get('question') or record.question
        mode = request.data.get('mode') or record.mode
        record.question = question
        record.mode = mode

        # 构造 prompt，调用 AI 模型
        try:
            from apps.requirement_analysis.models import AIModelConfig, AIModelService
            config = AIModelConfig.objects.filter(role='writer', is_active=True).order_by('-updated_at').first()
            if not config:
                return Response({'detail': '未配置 writer 角色 AI 模型'}, status=status.HTTP_400_BAD_REQUEST)

            # 拉取目标库真实表结构，喂给 AI 防止瞎编表名
            from .db_executor import format_schema_for_prompt, get_schema, validate_tables

            schema = get_schema(record.environment)
            schema_text = format_schema_for_prompt(schema)

            system_prompt = (
                "你是一个 SQL 专家。请根据用户的问题、数据库信息和下面的表结构，生成一条安全、可执行的 SQL。"
                "如果是查询模式，只返回 SELECT 语句；如果是数据变更模式，可返回 INSERT/UPDATE/DELETE。"
                "只返回 SQL 代码，不要解释。"
                "\n\n"
                + (schema_text or "（未能读取到表结构，请基于已知表名生成 SQL）")
            )
            db_hint = f"数据库类型：{record.environment.db_type or 'mysql'}，数据库名：{record.environment.db_name or 'testhub'}"
            user_content = f"{db_hint}\n\n问题：{question}\n模式：{mode}"
            messages = [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content},
            ]
            response = async_to_sync(AIModelService.call_openai_compatible_api)(config, messages)
            sql = response.get('choices', [{}])[0].get('message', {}).get('content', '')
            # 简单清理 markdown 代码块
            sql = sql.strip()
            if sql.startswith('```'):
                sql = '\n'.join(sql.split('\n')[1:-1] if sql.endswith('```') else sql.split('\n')[1:])
            sql = sql.strip()

            # 生成后做一次表名校验：若表不存在，直接标失败并提示可用表
            ok, missing, available = validate_tables(record.environment, sql)
            if not ok:
                record.generated_sql = sql
                record.status = 'failed'
                record.error_message = (
                    f"生成的 SQL 使用了不存在的表：{', '.join(missing)}。"
                    f"当前数据库可用表：{', '.join(available[:30])}"
                )
            else:
                record.generated_sql = sql
                record.status = 'generated'
                record.error_message = ''
        except Exception as exc:
            logger.exception('Text2SQL 生成失败')
            record.status = 'failed'
            record.error_message = str(exc)
        record.save()
        return Response(Text2SQLRecordSerializer(record).data)

    @action(detail=True, methods=['post'], url_path='validate')
    def validate(self, request, pk=None):
        """校验 SQL（仅做语法/安全简单校验，演示模式）"""
        record = self.get_object()
        # 环境锁定（与 generate/execute 一致）
        client_env_id = request.data.get('current_env_id')
        if client_env_id is not None and str(client_env_id) != str(record.environment_id):
            return Response({
                'detail': (
                    f"该 SQL 记录绑定的是环境「{record.environment.name}」，"
                    f"与当前选择不一致，请重新生成。"
                )
            }, status=status.HTTP_400_BAD_REQUEST)
        sql = request.data.get('sql') or record.generated_sql
        record.validated_sql = sql
        # TODO: 真实场景用 sqlparse / DB explain 校验
        record.status = 'validated'
        record.save()
        return Response(Text2SQLRecordSerializer(record).data)

    @action(detail=True, methods=['post'], url_path='execute')
    def execute(self, request, pk=None):
        """执行 SQL：真实连接环境数据库。查询模式只读返回结果/写操作回滚；数据变更模式真实提交。"""
        record = self.get_object()
        # 环境锁定：防止"切了环境但还用旧 record 执行"的迷惑场景
        client_env_id = request.data.get('current_env_id')
        if client_env_id is not None and str(client_env_id) != str(record.environment_id):
            err_msg = (
                f"该 SQL 记录绑定的是环境「{record.environment.name}」，"
                f"与当前选择不一致。请重新选择正确环境后再次「生成 SQL」。"
            )
            return Response({'detail': err_msg}, status=status.HTTP_400_BAD_REQUEST)
        if record.environment.access_method != 'db':
            err_msg = (
                f"环境「{record.environment.name}」不是数据库直连类型，无法执行 SQL。"
                "请切换到「数据库直连」环境。"
            )
            record.status = 'failed'
            record.error_message = err_msg
            record.save()
            return Response({'detail': err_msg}, status=status.HTTP_400_BAD_REQUEST)
        if not (record.environment.db_host or '').strip():
            err_msg = (
                f"环境「{record.environment.name}」未配置数据库主机（db_host），无法执行 SQL。"
                "请到「环境管理」编辑该环境，host 填 host.docker.internal 或宿主 IP。"
            )
            record.status = 'failed'
            record.error_message = err_msg
            record.save()
            return Response({'detail': err_msg}, status=status.HTTP_400_BAD_REQUEST)
        sql = request.data.get('sql') or record.validated_sql or record.generated_sql
        mode = request.data.get('mode') or record.mode or 'query'
        if not sql:
            return Response({'detail': '没有可执行的 SQL'}, status=status.HTTP_400_BAD_REQUEST)

        # 执行前校验表名，避免 1146 表不存在这类低级错误直接抛给用户
        from .db_executor import validate_tables
        ok, missing, available = validate_tables(record.environment, sql)
        if not ok:
            err_msg = f"执行失败：表 {', '.join(missing)} 不存在。可用表：{', '.join(available[:30])}"
            record.status = 'failed'
            record.error_message = err_msg
            record.save()
            return Response({'detail': err_msg}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from .db_executor import run_sql
            result = run_sql(record.environment, sql, mode=mode)
            record.result = result
            record.status = 'executed'
            record.error_message = ''
        except Exception as exc:
            logger.exception('Text2SQL 执行失败')
            record.status = 'failed'
            record.error_message = str(exc)
            return Response({'detail': f'执行失败: {exc}'}, status=status.HTTP_400_BAD_REQUEST)
        record.save()
        return Response(Text2SQLRecordSerializer(record).data)


class LogQueryViewSet(viewsets.ModelViewSet):
    """日志查询"""
    queryset = LogQuerySession.objects.all()
    serializer_class = LogQuerySessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        env_id = self.request.query_params.get('environment')
        if env_id:
            qs = qs.filter(environment_id=env_id)
        return qs

    @action(detail=False, methods=['post'], url_path='list-dirs')
    def list_dirs(self, request):
        """列出日志目录（本地访问方式读取宿主机挂载日志，SSH/其他暂用演示数据）"""
        env_id = request.data.get('environment')
        parent = request.data.get('parent', '')
        env = OpsEnvironment.objects.filter(pk=env_id).first()
        if not env:
            return Response({'detail': '环境不存在'}, status=status.HTTP_400_BAD_REQUEST)

        # 本地访问方式：直接读取容器内已挂载的宿主机日志目录
        if env.access_method == 'local':
            base = os.path.normpath(parent or env.current_dir or '/host_logs')
            if not os.path.isdir(base):
                return Response({'detail': f'目录不存在: {base}'}, status=status.HTTP_400_BAD_REQUEST)
            dirs, files = [], []
            try:
                for name in sorted(os.listdir(base)):
                    full = os.path.join(base, name)
                    if os.path.isdir(full):
                        dirs.append({'name': name, 'path': full, 'type': 'dir'})
                    elif os.path.isfile(full):
                        try:
                            size = os.path.getsize(full)
                        except OSError:
                            size = 0
                        files.append({'name': name, 'path': full, 'type': 'file', 'size': size})
            except PermissionError:
                return Response({'detail': '没有目录读取权限'}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'base': base, 'dirs': dirs, 'files': files})

        # 其他访问方式（SSH 等）暂用演示数据
        base = parent or env.current_dir or '/var/log'
        dirs = [
            {'name': 'app_testing', 'path': f'{base}/app_testing', 'type': 'dir'},
            {'name': 'ui', 'path': f'{base}/ui', 'type': 'dir'},
            {'name': 'scripts', 'path': f'{base}/scripts', 'type': 'dir'},
        ]
        files = [
            {'name': 'app.log', 'path': f'{base}/app.log', 'type': 'file', 'size': 375 * 1024},
            {'name': 'django_task.log', 'path': f'{base}/django_task.log', 'type': 'file', 'size': 104 * 1024},
            {'name': 'error.log', 'path': f'{base}/error.log', 'type': 'file', 'size': 1200},
        ]
        return Response({'base': base, 'dirs': dirs, 'files': files})

    @action(detail=False, methods=['post'], url_path='read')
    def read_log(self, request):
        """读取日志内容（本地访问方式读取真实文件）"""
        env_id = request.data.get('environment')
        path = request.data.get('path', '')
        keywords = request.data.get('keywords', [])
        tail_lines = int(request.data.get('tail_lines', 200) or 200)
        env = OpsEnvironment.objects.filter(pk=env_id).first()
        if not env:
            return Response({'detail': '环境不存在'}, status=status.HTTP_400_BAD_REQUEST)

        # 本地访问方式：直接读取真实日志文件（路径白名单限制在挂载根目录内）
        if env.access_method == 'local':
            if not path:
                return Response({'detail': '请选择文件'}, status=status.HTTP_400_BAD_REQUEST)
            path = os.path.normpath(path)
            root = os.path.normpath(env.current_dir or '/host_logs')
            if not (path == root or path.startswith(root + os.sep)):
                return Response({'detail': '非法路径，超出允许范围'}, status=status.HTTP_400_BAD_REQUEST)
            if not os.path.isfile(path):
                return Response({'detail': f'文件不存在: {path}'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    all_lines = f.readlines()
            except Exception as exc:
                return Response({'detail': f'读取失败: {exc}'}, status=status.HTTP_400_BAD_REQUEST)
            if keywords:
                kw_list = [k for k in keywords if k]
                if kw_list:
                    all_lines = [ln for ln in all_lines if any(k in ln for k in kw_list)]
            selected = all_lines[-tail_lines:] if tail_lines > 0 else all_lines
            content = ''.join(selected)
            session, _ = LogQuerySession.objects.update_or_create(
                environment=env,
                current_file=path,
                defaults={
                    'log_dir': os.path.dirname(path),
                    'content': content,
                    'keywords': keywords,
                    'tail_lines': tail_lines,
                    'created_by': request.user,
                },
            )
            return Response(LogQuerySessionSerializer(session).data)

        # 其他访问方式暂用演示数据
        sample = []
        for i in range(tail_lines):
            sample.append(f'2026-04-23 20:31:{37 + i % 60:02d},274 - [apps.knowledge_base.services] INFO - 示例日志行 {i+1}')
        content = '\n'.join(sample)
        session, _ = LogQuerySession.objects.update_or_create(
            environment=env,
            current_file=path,
            defaults={
                'log_dir': os.path.dirname(path),
                'content': content,
                'keywords': keywords,
                'tail_lines': tail_lines,
                'created_by': request.user,
            },
        )
        return Response(LogQuerySessionSerializer(session).data)


class FileTransferViewSet(viewsets.ModelViewSet):
    """内网文件传输"""
    queryset = FileTransferTask.objects.all()
    serializer_class = FileTransferTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        env_id = self.request.query_params.get('environment')
        if env_id:
            qs = qs.filter(environment_id=env_id)
        return qs

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        """上传文件到远程服务器"""
        env_id = request.data.get('environment')
        remote_path = request.data.get('remote_path', '')
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'detail': '请选择文件'}, status=status.HTTP_400_BAD_REQUEST)
        env = OpsEnvironment.objects.filter(pk=env_id).first()
        if not env:
            return Response({'detail': '环境不存在'}, status=status.HTTP_400_BAD_REQUEST)
        task = FileTransferTask.objects.create(
            name=uploaded.name,
            environment=env,
            direction='upload',
            remote_path=remote_path,
            local_file=uploaded,
            size=uploaded.size,
            status='success',
            created_by=request.user,
            completed_at=__import__('django.utils.timezone', fromlist=['now']).now(),
        )
        # TODO: 真实场景通过 paramiko sftp 上传到 remote_path
        return Response(FileTransferTaskSerializer(task, context={'request': request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """下载文件到本地"""
        task = self.get_object()
        if task.local_file:
            return FileResponse(task.local_file.open('rb'), as_attachment=True, filename=os.path.basename(task.local_file.name))
        # TODO: 真实场景从远程 sftp 拉取后返回
        return Response({'detail': '暂无本地文件'}, status=status.HTTP_404_NOT_FOUND)
