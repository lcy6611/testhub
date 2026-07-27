"""知识库 RAG 对话 API。"""

from __future__ import annotations

import json
import logging
import queue
import threading
import uuid

from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response

from .dify_kb_service import resolve_dify_config
from .kb_chat_models import KbChatMessage, KbChatSession
from .kb_chat_serializers import (
    KbChatGenerateTestcasesSerializer,
    KbChatMessageSerializer,
    KbChatSendMessageSerializer,
    KbChatSessionCreateSerializer,
    KbChatSessionSerializer,
    KbChatSessionUpdateSerializer,
)
from .kb_chat_service import create_testcase_generation_from_session, run_kb_chat_stream

logger = logging.getLogger(__name__)


class EventStreamRenderer(BaseRenderer):
    """允许客户端 Accept: text/event-stream，实际仍返回 StreamingHttpResponse。"""

    media_type = "text/event-stream"
    format = "event-stream"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class KbChatSessionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    lookup_field = "session_id"
    lookup_url_kwarg = "session_id"

    def get_queryset(self):
        return KbChatSession.objects.filter(user=self.request.user).select_related("dify_config")

    def get_serializer_class(self):
        if self.action in ("create",):
            return KbChatSessionCreateSerializer
        if self.action in ("update", "partial_update"):
            return KbChatSessionUpdateSerializer
        return KbChatSessionSerializer

    def perform_create(self, serializer):
        session_id = serializer.validated_data.get("session_id") or f"kbchat_{uuid.uuid4().hex[:16]}"
        serializer.save(user=self.request.user, session_id=session_id)

    def create(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data or {})
        if not data.get("session_id"):
            data["session_id"] = f"kbchat_{uuid.uuid4().hex[:16]}"
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save(user=request.user)
        return Response(KbChatSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = KbChatSessionUpdateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(KbChatSessionSerializer(instance).data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="messages")
    def messages(self, request, session_id=None):
        session = self.get_object()
        qs = session.messages.all().order_by("created_at")
        return Response(KbChatMessageSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="generate-testcases")
    def generate_testcases(self, request, session_id=None):
        session = self.get_object()
        ser = KbChatGenerateTestcasesSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        project_id = ser.validated_data.get("project")
        message_ids = ser.validated_data.get("message_ids") or None
        try:
            task = create_testcase_generation_from_session(
                session,
                user=request.user,
                project_id=project_id,
                message_ids=message_ids,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("知识库对话一键生成用例失败")
            return Response({"detail": f"创建生成任务失败: {exc}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            from apps.knowledge_graph.builder import index_generation_task

            index_generation_task(
                task,
                created_by=request.user,
                kb_chat_session_id=session.session_id,
            )
        except Exception:
            pass

        return Response(
            {
                "task_id": task.task_id,
                "detail": "测试用例生成任务已启动",
            },
            status=status.HTTP_201_CREATED,
        )


class KbChatViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(
        detail=False,
        methods=["post"],
        url_path="send_message",
        renderer_classes=[JSONRenderer, EventStreamRenderer],
    )
    def send_message(self, request):
        ser = KbChatSendMessageSerializer(data=request.data or {})
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        message = (data.get("message") or "").strip()
        session_id = (data.get("session_id") or "").strip()
        if not message:
            return Response({"detail": "message 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        if not session_id:
            return Response({"detail": "session_id 不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = KbChatSession.objects.select_related("dify_config").get(
                session_id=session_id,
                user=request.user,
            )
        except KbChatSession.DoesNotExist:
            return Response({"detail": "会话不存在"}, status=status.HTTP_404_NOT_FOUND)

        if data.get("dify_config_id"):
            config = resolve_dify_config(data["dify_config_id"])
            if config:
                session.dify_config = config
        if data.get("dify_dataset_id"):
            session.dify_dataset_id = str(data["dify_dataset_id"]).strip()
        if data.get("dify_dataset_name") is not None:
            session.dify_dataset_name = str(data.get("dify_dataset_name") or "").strip()
        if data.get("kb_scope_mode") in ("full", "documents"):
            session.kb_scope_mode = data["kb_scope_mode"]
        if session.kb_scope_mode == "full":
            session.kb_document_ids = []
        elif data.get("kb_document_ids") is not None:
            session.kb_document_ids = [
                str(x).strip() for x in data["kb_document_ids"] if str(x).strip()
            ]
        if data.get("kb_top_k"):
            session.kb_top_k = int(data["kb_top_k"])
        if not session.title:
            session.title = message[:30] + ("..." if len(message) > 30 else "")
        session.updated_at = timezone.now()
        session.save()

        user_msg = KbChatMessage.objects.create(
            session=session,
            role="user",
            content=message,
        )

        event_queue: queue.Queue = queue.Queue()

        def worker():
            from django.db import close_old_connections

            close_old_connections()
            chunks: list[str] = []
            try:
                session_ref = KbChatSession.objects.select_related("dify_config").get(pk=session.pk)

                def on_chunk(text: str):
                    chunks.append(text)
                    event_queue.put({"type": "chunk", "content": text})

                answer, retrieval_meta = run_kb_chat_stream(
                    session=session_ref,
                    user_message=message,
                    on_chunk=on_chunk,
                )
                assistant_msg = KbChatMessage.objects.create(
                    session=session,
                    role="assistant",
                    content=answer,
                    retrieval_meta=retrieval_meta or {},
                )
                session.updated_at = timezone.now()
                session.save(update_fields=["updated_at"])
                event_queue.put(
                    {
                        "type": "done",
                        "user_message": KbChatMessageSerializer(user_msg).data,
                        "assistant_message": KbChatMessageSerializer(assistant_msg).data,
                        "retrieval_meta": retrieval_meta,
                    }
                )
            except Exception as exc:
                logger.exception("知识库对话流式失败")
                event_queue.put({"type": "error", "detail": str(exc)})
            finally:
                event_queue.put(None)

        threading.Thread(target=worker, daemon=True).start()

        def event_stream():
            yield ": connected\n\n"
            while True:
                item = event_queue.get()
                if item is None:
                    break
                try:
                    payload = json.dumps(item, ensure_ascii=False, default=str)
                except Exception as exc:
                    payload = json.dumps(
                        {"type": "error", "detail": f"响应序列化失败: {exc}"},
                        ensure_ascii=False,
                    )
                yield f"data: {payload}\n\n"

        resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        resp["Cache-Control"] = "no-cache"
        resp["X-Accel-Buffering"] = "no"
        return resp
