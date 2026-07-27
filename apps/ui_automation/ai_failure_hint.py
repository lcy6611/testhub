# -*- coding: utf-8 -*-
"""
Agent 执行失败时，由大模型根据执行上下文分析并生成面向用户的失败提示（通用能力，无固定文案）。
"""
import logging

logger = logging.getLogger('django')

# 默认提示（LLM 不可用或超时时使用）
DEFAULT_FAILURE_HINT = "执行未完成，请查看执行日志。"


def _make_llm_for_hint(cfg):
    """与 ai_base 中 _make_llm 一致的最小实现，仅用于失败提示生成。"""
    if not cfg:
        return None
    from langchain_openai import ChatOpenAI
    api_key = cfg.api_key
    base_url = getattr(cfg, 'base_url', '') or ''
    model_name = getattr(cfg, 'model_name', '') or ''
    if not api_key:
        return None
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
    )


def _build_context(task_description, planned_tasks, logs_snippet, execution_history=None, agent_failure_text=None):
    """将执行上下文格式化为 LLM 可读的文本。"""
    parts = []
    parts.append("任务描述：")
    parts.append(task_description or "(无)")
    if agent_failure_text and agent_failure_text.strip():
        parts.append("\nAgent 返回的失败原因（可能为英文，需转化为中文提示）：")
        parts.append(agent_failure_text.strip()[:800])
    parts.append("\n计划任务及状态：")
    if planned_tasks:
        for t in planned_tasks:
            tid = t.get('id', '')
            status = t.get('status', 'pending')
            content = t.get('content', t.get('title', ''))[:80]
            parts.append(f"  - [{tid}] {status}: {content}")
    else:
        parts.append("  (无)")
    parts.append("\n执行日志（最近片段）：")
    parts.append((logs_snippet or "")[-3500:])  # 最近约 3500 字符
    if execution_history and isinstance(execution_history, dict):
        parts.append("\n执行摘要：")
        parts.append(f"  总步数: {execution_history.get('total_steps', '')}")
        parts.append(f"  执行模式: {execution_history.get('execution_mode', '')}")
    return "\n".join(parts)


def generate_failure_hint_sync(
    task_description,
    planned_tasks=None,
    logs_snippet="",
    execution_history=None,
    agent_failure_text=None,
):
    """
    根据执行上下文，调用大模型生成一句简洁的失败原因提示（通用、不固定文案，必须为中文）。
    失败或超时时返回 None，由调用方使用 DEFAULT_FAILURE_HINT。
    agent_failure_text: Agent 返回的失败原因（可能为英文），将作为上下文供模型转化为中文提示。
    """
    try:
        from apps.requirement_analysis.models import AIModelConfig
        from langchain_core.messages import SystemMessage, HumanMessage
    except ImportError as e:
        logger.warning("ai_failure_hint: import error, skip LLM hint: %s", e)
        return None

    text_config = AIModelConfig.objects.filter(role='browser_use_text', is_active=True).first()
    if not text_config:
        logger.debug("ai_failure_hint: no browser_use_text config, skip LLM hint")
        return None

    llm = _make_llm_for_hint(text_config)
    if not llm:
        return None

    context = _build_context(
        task_description, planned_tasks or [], logs_snippet, execution_history,
        agent_failure_text=agent_failure_text,
    )
    system_prompt = (
        "你是一个助手。根据用户提供的「未完成的浏览器自动化执行」信息，用1-2句中文给出面向用户的失败原因提示。"
        "要求：必须用中文输出；通用、不提及具体模型或技术名称（如视觉模型、API），不写技术堆栈。"
        "若上下文中有 Agent 返回的失败原因（可能为英文），请将其要点用中文概括进提示。只输出中文提示文案本身，不要加引号或前缀。"
    )
    user_prompt = "请根据以下执行信息给出失败原因提示：\n\n" + context

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    try:
        result = llm.invoke(messages)
    except Exception as e:
        logger.warning("ai_failure_hint: LLM invoke failed, skip hint: %s", e)
        return None

    content = None
    if hasattr(result, 'content') and result.content:
        content = result.content if isinstance(result.content, str) else str(result.content)
    if not content:
        return None
    hint = content.strip()
    if not hint:
        return None
    return hint[:500]


def get_failure_hint_for_record(execution_record, history=None, agent_failure_text=None):
    """
    根据执行记录和可选 history 生成失败提示（始终为中文）。
    返回 LLM 分析结果，若不可用则返回 DEFAULT_FAILURE_HINT。
    agent_failure_text: Agent 返回的失败原因（如英文），将作为上下文由模型转化为中文提示。
    """
    task_description = getattr(execution_record, 'task_description', '') or ''
    planned_tasks = getattr(execution_record, 'planned_tasks', None) or []
    logs_snippet = getattr(execution_record, 'logs', '') or ''
    execution_history = None
    if history and hasattr(history, 'execution_history'):
        execution_history = history.execution_history
    hint = generate_failure_hint_sync(
        task_description=task_description,
        planned_tasks=planned_tasks,
        logs_snippet=logs_snippet,
        execution_history=execution_history,
        agent_failure_text=agent_failure_text,
    )
    return hint if hint else DEFAULT_FAILURE_HINT
