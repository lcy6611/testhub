from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import render
import requests
from requests.exceptions import RequestException
from .models import AssistantSession, AssistantMessage, ChatMessage, DifyConfig
from .serializers import (
    AssistantSessionSerializer, 
    AssistantSessionCreateSerializer,
    AssistantMessageSerializer,
    ChatMessageSerializer
)


class AssistantSessionViewSet(viewsets.ModelViewSet):
    """智能助手会话视图集"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AssistantSessionCreateSerializer
        return AssistantSessionSerializer
    
    def get_queryset(self):
        # 取消用户隔离：所有登录用户可见所有会话
        return AssistantSession.objects.all()
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """
        创建会话后返回完整会话对象（包含 id/session_id），
        避免前端拿不到 id 导致请求 /sessions/undefined/messages/。
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save(user=request.user)
        full = AssistantSessionSerializer(session)
        return Response(full.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_message(self, request, pk=None):
        """添加消息到会话"""
        session = self.get_object()
        serializer = AssistantMessageSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.save(session=session)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """获取会话的聊天消息"""
        session = self.get_object()
        messages = session.chat_messages.all()
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)


class ChatViewSet(viewsets.ViewSet):
    """聊天功能ViewSet"""
    permission_classes = [permissions.IsAuthenticated]
    # 记住每个 Dify 配置最近一次成功的模式，减少每次先错路由再 fallback 的开销
    _mode_cache: dict = {}

    @staticmethod
    def _normalize_dify_api_base_url(raw: str) -> str:
        """把用户配置的 base url 归一化为以 /v1 结尾的 Dify Service API base url。"""
        api_url = (raw or "").strip().rstrip("/")
        if api_url.endswith("/v1"):
            return api_url
        return f"{api_url}/v1"

    @staticmethod
    def _parse_dify_error_response(resp) -> str:
        if resp is None:
            return ""
        try:
            payload = resp.json() if resp.content else {}
            if isinstance(payload, dict):
                return (
                    payload.get("message")
                    or payload.get("detail")
                    or payload.get("code")
                    or (resp.text or "")[:500]
                )
        except Exception:
            pass
        return (getattr(resp, "text", None) or "")[:500]

    @staticmethod
    def _resolve_invoke_mode(dify_config) -> str:
        mode = (getattr(dify_config, "invoke_mode", None) or "").strip().lower()
        if mode in ("chat", "workflow"):
            return mode
        name = (getattr(dify_config, "app_type", None) or "").lower()
        if "chat" in name or "对话" in name:
            return "chat"
        if "workflow" in name or "工作流" in name:
            return "workflow"
        return "workflow"

    def _call_dify_chat(self, *, api_url, headers, message, user_id, session, file_inputs):
        payload = {
            "inputs": {},
            "query": message,
            "user": str(user_id),
            "response_mode": "blocking",
        }
        if file_inputs:
            payload["files"] = file_inputs
        if session.conversation_id:
            payload["conversation_id"] = session.conversation_id
        return requests.post(
            f"{api_url}/chat-messages",
            headers=headers,
            json=payload,
            timeout=120,
        )

    def _call_dify_workflow(self, *, api_url, headers, message, user_id, file_inputs):
        workflow_data = {
            "inputs": {
                "text": message,
                "query": message,
                "a": (message or "")[:48],
                "user_input": message,
                "input": message,
                "content": message,
                "message": message,
                "prompt": message,
                "description": message,
            },
            "response_mode": "blocking",
            "user": str(user_id),
        }
        if file_inputs:
            for k in ("files", "images", "attachments", "documents", "input_files"):
                workflow_data["inputs"][k] = file_inputs
        return requests.post(
            f"{api_url}/workflows/run",
            headers=headers,
            json=workflow_data,
            timeout=120,
        )

    @staticmethod
    def _extract_workflow_text(outputs) -> str:
        """
        workflows/run 返回的 outputs 结构较灵活，这里做尽力提取。
        常见：
        - outputs: {"text": "..."} / {"answer": "..."} / {"result": "..."}
        - outputs: {"data": {"text": "..."}} 等
        """
        try:
            if not outputs:
                return ""
            if isinstance(outputs, str):
                return outputs
            if isinstance(outputs, dict):
                for k in ("text", "answer", "result", "output"):
                    v = outputs.get(k)
                    if isinstance(v, str) and v.strip():
                        return v
                for k in ("data", "outputs", "result"):
                    v = outputs.get(k)
                    if isinstance(v, dict):
                        t = ChatViewSet._extract_workflow_text(v)
                        if t:
                            return t
            return ""
        except Exception:
            return ""

    def _handle_chat_success(self, session, user_message, response, dify_config_id):
        self._mode_cache[dify_config_id] = "chat"
        data = response.json()
        if "conversation_id" in data and not session.conversation_id:
            session.conversation_id = data["conversation_id"]
            session.save(update_fields=["conversation_id"])
        assistant_text = data.get("answer", "") or ""
        assistant_message = ChatMessage.objects.create(
            session=session,
            role="assistant",
            content=assistant_text,
            conversation_id=data.get("conversation_id"),
            message_id=data.get("message_id"),
        )
        return Response(
            {
                "user_message": ChatMessageSerializer(user_message).data,
                "assistant_message": ChatMessageSerializer(assistant_message).data,
                "conversation_id": data.get("conversation_id"),
            }
        )

    def _handle_workflow_success(self, session, user_message, resp2, dify_config_id):
        self._mode_cache[dify_config_id] = "workflow"
        data2 = resp2.json() if resp2.content else {}
        outputs = (data2.get("data") or {}).get("outputs") if isinstance(data2, dict) else None
        assistant_text = self._extract_workflow_text(outputs) or ""
        if not assistant_text:
            assistant_text = "（工作流执行成功，但未能从 outputs 中提取文本输出）"
        assistant_message = ChatMessage.objects.create(
            session=session,
            role="assistant",
            content=assistant_text,
            conversation_id=session.conversation_id,
            message_id=None,
        )
        return Response(
            {
                "user_message": ChatMessageSerializer(user_message).data,
                "assistant_message": ChatMessageSerializer(assistant_message).data,
                "conversation_id": session.conversation_id,
            }
        )
    
    @action(detail=False, methods=['post'])
    def send_message(self, request):
        """发送消息到Dify API"""
        session_id = request.data.get('session_id')
        message = request.data.get('message')
        dify_config_id = request.data.get('dify_config_id')
        
        if not session_id or not message:
            return Response(
                {'error': 'session_id和message都是必填项'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 获取会话
        try:
            session = AssistantSession.objects.get(
                session_id=session_id,
            )
        except AssistantSession.DoesNotExist:
            return Response(
                {'error': '会话不存在'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 获取Dify配置
        dify_config = None
        if dify_config_id:
            try:
                dify_config = DifyConfig.objects.get(pk=dify_config_id)
            except Exception:
                dify_config = None
        if not dify_config:
            dify_config = DifyConfig.get_active_config()
        if not dify_config:
            return Response(
                {'error': '未配置Dify API，请先在配置中心配置'},
                status=status.HTTP_400_BAD_REQUEST
            )

        dify_api_key_raw = (dify_config.api_key or '').strip()
        if not dify_api_key_raw:
            return Response(
                {
                    'error': '该 Dify 配置未填写应用 API Key（app-），无法使用 AI 评测师',
                    'detail': (
                        '知识库 API Key（dataset-）仅用于「AI 用例生成 + 知识库」；'
                        'AI 评测师对话必须在配置中心填写对应 Dify 应用的 app- API Key。'
                    ),
                    'hint': '请前往「配置中心 → AI评测师配置」，编辑所选配置并填写应用 API Key。',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # 保存用户消息
        user_message = ChatMessage.objects.create(
            session=session,
            role='user',
            content=message,
            conversation_id=session.conversation_id
        )
        
        # ---- 上传附件（可选：图片/文件）----
        # 前端会把文件以 multipart 的形式通过 key="files" 传入；这里把它们转成 Dify 的 file input objects
        uploaded_files = []
        try:
            uploaded_files = request.FILES.getlist('files') or []
        except Exception:
            uploaded_files = []

        file_inputs = []
        upload_warnings = []
        # 读取上传内容并转发到 Dify（实际上传发生在下面 uploaded_files 的真实 requests.post 循环中）

        try:
            # 调用Dify API
            dify_api_key = (dify_config.api_key or '').strip()
            # 兼容用户/配置中可能粘贴了 "Bearer xxx" 或 "Token xxx"
            prefixes = ('Bearer ', 'bearer ', 'Token ', 'token ')
            for p in prefixes:
                if dify_api_key.startswith(p):
                    dify_api_key = dify_api_key[len(p):].strip()
                    break

            headers = {
                'Authorization': f'Bearer {dify_api_key}',
                'Content-Type': 'application/json'
            }
            
            # 归一化：配置中心里常填 http://host:8081（不带 /v1），这里统一补 /v1
            api_url = self._normalize_dify_api_base_url(dify_config.api_url)
            config_id = getattr(dify_config, "id", None)
            invoke_mode = self._resolve_invoke_mode(dify_config)
            cached_mode = self._mode_cache.get(config_id)
            if cached_mode in ("chat", "workflow"):
                invoke_mode = cached_mode

            if uploaded_files:
                file_upload_url = f'{api_url}/files/upload'
                for f in uploaded_files:
                    file_bytes = f.read()
                    mime = getattr(f, "content_type", None) or ""
                    file_type = "image" if mime.startswith("image/") else "document"
                    upload_resp = requests.post(
                        file_upload_url,
                        headers={'Authorization': f'Bearer {dify_api_key}'},
                        files={'file': (f.name, file_bytes, mime) if mime else (f.name, file_bytes)},
                        data={'user': str(request.user.id)},
                        timeout=120,
                    )
                    if upload_resp.status_code not in (200, 201):
                        upload_warnings.append(f'{f.name}: {upload_resp.status_code}')
                        continue
                    try:
                        upload_id = upload_resp.json().get('id')
                    except Exception:
                        upload_id = None
                    if not upload_id:
                        upload_warnings.append(f'{f.name}: 无 upload_file_id')
                        continue
                    file_inputs.append({
                        'type': file_type,
                        'transfer_method': 'local_file',
                        'upload_file_id': upload_id,
                    })

            order = ("workflow", "chat") if invoke_mode == "workflow" else ("chat", "workflow")
            chat_resp = None
            workflow_resp = None

            for mode in order:
                if mode == "chat":
                    chat_resp = self._call_dify_chat(
                        api_url=api_url,
                        headers=headers,
                        message=message,
                        user_id=request.user.id,
                        session=session,
                        file_inputs=file_inputs,
                    )
                    if chat_resp.status_code == 200:
                        return self._handle_chat_success(session, user_message, chat_resp, config_id)
                else:
                    workflow_resp = self._call_dify_workflow(
                        api_url=api_url,
                        headers=headers,
                        message=message,
                        user_id=request.user.id,
                        file_inputs=file_inputs,
                    )
                    if workflow_resp.status_code == 200:
                        return self._handle_workflow_success(session, user_message, workflow_resp, config_id)

            chat_detail = self._parse_dify_error_response(chat_resp)
            workflow_detail = self._parse_dify_error_response(workflow_resp)
            return Response(
                {
                    'error': 'Dify API 调用失败',
                    'detail': chat_detail or workflow_detail,
                    'invoke_mode': invoke_mode,
                    'chat_status': getattr(chat_resp, "status_code", None),
                    'workflow_status': getattr(workflow_resp, "status_code", None),
                    'chat_detail': chat_detail,
                    'workflow_detail': workflow_detail,
                    'hint': (
                        '请确认：1) API URL 与 Dify 浏览器地址一致（本机建议用 localhost）；'
                        '2) 配置中心「调用模式」与 Dify 应用类型一致（工作流/对话）；'
                        '3) 使用的是该应用对应的 app- API Key。'
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
                
        except requests.exceptions.Timeout:
            return Response({
                'error': 'API请求超时'
            }, status=status.HTTP_408_REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as e:
            return Response({
                'error': f'API请求失败: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def assistant_view(request):
    """智能助手页面视图 - 用于iframe内嵌"""
    return render(request, 'assistant/assistant.html')
