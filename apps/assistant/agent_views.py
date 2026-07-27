# -*- coding: utf-8 -*-
"""
Agent 数字人 API 端点。
"""
import json
import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import StreamingHttpResponse

from apps.requirement_analysis.models import AIModelConfig
from .agent_engine import run_agent
from .models import HermesConversation, HermesMessage

logger = logging.getLogger(__name__)


def _get_agent_model_config():
    """获取用于 Agent 的 AI 模型配置（优先 writer 角色）"""
    config = AIModelConfig.objects.filter(is_active=True, role="writer").first()
    if not config:
        config = AIModelConfig.objects.filter(is_active=True).first()
    return config


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def agent_chat(request):
    """
    Agent 数字人对话（SSE 流式返回）。

    POST body:
        message: 用户消息（必填）
        history: 对话历史 [{"role": "user", "content": "..."}, ...]（可选）

    返回: text/event-stream
    """
    message = (request.data.get("message") or "").strip()
    if not message:
        return Response({"detail": "请输入消息"}, status=status.HTTP_400_BAD_REQUEST)

    history = request.data.get("history") or []
    conversation_id = request.data.get("conversation_id")
    images = request.data.get("images") or []

    config = _get_agent_model_config()
    if not config:
        return Response(
            {"detail": "未配置 AI 模型，请先在「AI用例生成 → 提示词配置」中添加并启用模型配置"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # 关联 Hermes 会话（前端总是传当前会话 ID，确保消息可持久化）
    user = request.user
    conversation = None
    if conversation_id:
        conversation = HermesConversation.objects.filter(pk=conversation_id, user=user).first()

    def event_stream():
        content_parts = []
        thought_parts = []
        tool_calls = []
        try:
            for event in run_agent(config, message, history):
                etype = event.get("type")
                # 收集最终内容，用于流式结束后持久化
                if etype == "message":
                    content_parts.append(event.get("content", ""))
                elif etype == "thinking":
                    thought_parts.append(event.get("content", ""))
                elif etype == "tool_call":
                    tool_calls.append({
                        "name": event.get("name"),
                        "arguments": event.get("arguments"),
                        "result": None,
                    })
                elif etype == "tool_result":
                    if tool_calls:
                        tool_calls[-1]["result"] = event.get("result")
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:
            logger.exception("Agent 流式生成异常")
            error_event = {"type": "error", "content": f"服务器内部错误: {str(e)}"}
            yield f"data: {json.dumps(error_event, ensure_ascii=False, default=str)}\n\n"
        finally:
            # 持久化用户 + 助手消息，保证切换会话 / 刷新页面后不丢失
            try:
                if conversation is not None:
                    HermesMessage.objects.create(
                        conversation=conversation,
                        role="user",
                        content=message,
                        images=images,
                    )
                    assistant_content = "".join(content_parts)
                    # 工具结果可能含 datetime / Decimal 等非 JSON 原生类型，
                    # 保存前统一序列化清洗，避免 JSONField 写入抛 TypeError
                    safe_tool_calls = json.loads(
                        json.dumps(tool_calls, ensure_ascii=False, default=str)
                    )
                    if assistant_content or safe_tool_calls:
                        HermesMessage.objects.create(
                            conversation=conversation,
                            role="assistant",
                            content=assistant_content,
                            tool_calls=safe_tool_calls,
                            thought_text="".join(thought_parts),
                        )
                    # 用首条用户消息给会话命名
                    if not conversation.title:
                        conversation.title = message[:500]
                        conversation.save(update_fields=["title", "updated_at"])
            except Exception as save_err:
                logger.exception("保存 Hermes 会话消息失败: %s", save_err)

    response = StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
