"""知识库对话业务逻辑。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Callable, Dict, List, Optional

from django.utils import timezone

from .dify_kb_service import (
    format_chat_retrieval_context,
    resolve_dify_config,
)
from .kb_hub.backend import KbBackendFactory
from .generation_task_runner import start_generation_task_background
from .kb_chat_models import KbChatMessage, KbChatSession
from .models import AIModelConfig, AIModelService, PromptConfig, TestCaseGenerationTask

KB_CHAT_SYSTEM_PROMPT = """你是 TestHub 测试知识库助手。请根据提供的知识库检索片段回答用户问题。

规则：
1. 优先依据检索片段作答，不要编造片段中不存在的内容
2. 不要在回答正文中写「引用来源」或参考文献列表，界面会单独展示引用文档
3. 若检索内容不足以回答，请明确说明缺失什么信息
4. 回答面向测试人员，简洁、专业、可执行"""


def build_chat_messages(
    session: KbChatSession,
    retrieval_context: str,
    user_message: str,
    *,
    history_limit: int = 16,
) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = [
        {
            "role": "system",
            "content": f"{KB_CHAT_SYSTEM_PROMPT}\n\n{retrieval_context}",
        }
    ]
    history = list(session.messages.order_by("-created_at")[:history_limit])
    history.reverse()
    if history and history[-1].role == "user" and (history[-1].content or "").strip() == (user_message or "").strip():
        history = history[:-1]
    for msg in history:
        if msg.role in ("user", "assistant") and (msg.content or "").strip():
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


def run_kb_chat_stream(
    *,
    session: KbChatSession,
    user_message: str,
    on_chunk: Callable[[str], None],
) -> tuple[str, Dict[str, Any]]:
    """检索知识库并流式生成回答。返回 (完整回答, retrieval_meta)。"""
    kb_id = (session.dify_dataset_id or "").strip()
    if not kb_id:
        raise ValueError("请先选择知识库")

    document_ids = [str(x).strip() for x in (session.kb_document_ids or []) if str(x).strip()]
    scope_mode = getattr(session, "kb_scope_mode", None) or ("documents" if document_ids else "full")
    if scope_mode == "full":
        document_ids = []
    top_k = max(1, min(int(session.kb_top_k or 5), 10))

    backend = KbBackendFactory.get_backend()
    records, retrieval_meta = backend.retrieve_for_chat(
        user_message,
        top_k=top_k,
        document_ids=document_ids or None,
        scope_mode=scope_mode,
        kb_id=kb_id,
    )
    retrieval_context = format_chat_retrieval_context(
        records,
        dataset_name=session.dify_dataset_name or kb_id,
    )

    writer = AIModelConfig.objects.filter(role="writer", is_active=True).order_by("-updated_at").first()
    if not writer:
        raise ValueError("未配置启用的编写模型，请先在 AI 模型配置中启用 writer 角色")

    messages = build_chat_messages(session, retrieval_context, user_message)

    async def _run() -> str:
        return await AIModelService.call_openai_compatible_api_stream(
            writer,
            messages,
            on_chunk,
            min_tokens=1024,
        )

    answer = asyncio.run(_run())
    return answer, retrieval_meta


def build_requirement_from_session(
    session: KbChatSession,
    *,
    message_ids: Optional[List[int]] = None,
) -> str:
    lines = [
        f"【来源】知识库对话 — {session.dify_dataset_name or session.dify_dataset_id}",
        "",
    ]
    qs = session.messages.order_by("created_at")
    if message_ids:
        id_set = {int(x) for x in message_ids if str(x).strip().isdigit()}
        qs = qs.filter(id__in=id_set)
    for msg in qs:
        if msg.role not in ("user", "assistant") or not (msg.content or "").strip():
            continue
        role_label = "用户" if msg.role == "user" else "助手"
        lines.append(f"{role_label}：{msg.content}")
    lines.extend(
        [
            "",
            "请根据以上知识库对话内容，生成完整、结构化、可执行的测试用例。",
            "须覆盖对话中讨论的功能点、业务规则与边界条件。",
        ]
    )
    return "\n".join(lines)


def create_testcase_generation_from_session(
    session: KbChatSession,
    *,
    user,
    project_id: Optional[int] = None,
    message_ids: Optional[List[int]] = None,
) -> TestCaseGenerationTask:
    if message_ids:
        user_count = session.messages.filter(role="user", id__in=message_ids).count()
    else:
        user_count = session.messages.filter(role="user").count()
    if user_count == 0:
        raise ValueError("请至少勾选一条用户消息，无法生成用例")

    requirement_text = build_requirement_from_session(session, message_ids=message_ids)
    title = (session.title or "知识库对话生成用例").strip()[:200]
    if title in ("", "新对话"):
        first_user = (
            session.messages.filter(role="user")
            .order_by("created_at")
            .values_list("content", flat=True)
            .first()
        )
        if first_user:
            first_user = str(first_user).strip()
            title = first_user[:30] + ("..." if len(first_user) > 30 else "")
    config = session.dify_config or resolve_dify_config(None)

    writer_model = AIModelConfig.objects.filter(role="writer", is_active=True).order_by("-updated_at").first()
    reviewer_model = AIModelConfig.objects.filter(role="reviewer", is_active=True).order_by("-updated_at").first()
    writer_prompt = PromptConfig.objects.filter(prompt_type="writer", is_active=True).order_by("-updated_at").first()
    reviewer_prompt = PromptConfig.objects.filter(prompt_type="reviewer", is_active=True).order_by("-updated_at").first()
    if not (writer_model and writer_prompt):
        raise ValueError("未配置启用的编写模型/提示词")

    kb_context = ""
    kb_context_meta: Dict[str, Any] = {}
    document_ids = [str(x).strip() for x in (session.kb_document_ids or []) if str(x).strip()]
    scope_mode = getattr(session, "kb_scope_mode", None) or ("documents" if document_ids else "full")
    if scope_mode == "full":
        document_ids = []
    top_k = max(1, min(int(session.kb_top_k or 5), 10))
    dataset_id = (session.dify_dataset_id or "").strip()
    has_kb_refs = bool(document_ids)

    if dataset_id and has_kb_refs:
        try:
            backend = KbBackendFactory.get_backend()
            kb_context, kb_context_meta = backend.build_generation_context(
                title=title,
                requirement_text=requirement_text,
                kb_name=session.dify_dataset_name or "",
                document_ids=document_ids,
                reference_mode="documents",
                top_k=top_k,
                kb_id=dataset_id,
            )
        except Exception:
            kb_context = ""
            kb_context_meta = {}

    task = TestCaseGenerationTask.objects.create(
        task_id=f"TASK_{uuid.uuid4().hex[:8].upper()}",
        title=title,
        requirement_text=requirement_text,
        output_mode="stream",
        project_id=project_id or None,
        dify_config=config,
        dify_dataset_id=dataset_id,
        dify_dataset_name=session.dify_dataset_name or "",
        kb_context=kb_context or "",
        kb_context_meta=kb_context_meta or {},
        kb_top_k=top_k if has_kb_refs else 5,
        kb_reference_mode="documents" if has_kb_refs else "hybrid",
        kb_document_ids=document_ids if has_kb_refs else [],
        kb_function_ids=[],
        writer_model_config=writer_model,
        reviewer_model_config=reviewer_model,
        writer_prompt_config=writer_prompt,
        reviewer_prompt_config=reviewer_prompt,
        created_by=user,
        status="pending",
        progress=0,
    )

    session.last_generation_task_id = task.task_id
    session.updated_at = timezone.now()
    session.save(update_fields=["last_generation_task_id", "updated_at"])

    start_generation_task_background(task.pk)
    return task
