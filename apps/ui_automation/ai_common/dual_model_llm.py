import logging
from typing import Any, List

from langchain_core.messages import SystemMessage as LangChainSystemMessage


class DualModelLLM:
    """
    简单的“双模型”LLM 适配器：
    - vision_llm：只负责处理视觉输入，输出页面的文本描述
    - text_llm：负责根据任务+视觉描述做决策，输出结构化动作（pydantic / function calling）

    对外暴露与 ChatOpenAI 兼容的 `ainvoke` 接口，便于与 browser-use 集成。
    """

    def __init__(self, vision_llm: Any, text_llm: Any, logger: logging.Logger | None = None) -> None:
        self.vision_llm = vision_llm
        self.text_llm = text_llm
        self.logger = logger or logging.getLogger(__name__)

        # 尽量对齐 ChatOpenAI 的属性，方便已有日志 / TokenCost / 其他代码使用
        # ChatOpenAI 上常见的属性：provider, model, model_name, api_key, base_url
        self.provider = getattr(text_llm, "provider", None)
        self.model = getattr(text_llm, "model", None)
        # 兼容外部代码直接访问 llm.model_name
        self.model_name = getattr(text_llm, "model_name", None) or self.model

    async def ainvoke(self, messages: List[Any], output_format=None, **kwargs):
        """
        browser-use 调用链期望的入口：
        1. 尝试用视觉模型生成页面描述
        2. 将视觉描述作为额外的 system message 注入
        3. 交给文本模型执行真正的结构化决策（支持 output_format）
        """
        vision_description = None

        # 1) 调用视觉模型做页面感知（失败时不影响后续文本模型调用）
        try:
            if self.vision_llm is not None:
                # 给视觉模型一个明确的角色与输出要求
                vision_prompt = (
                    "你是网页视觉分析助手。根据下面的对话消息（其中可能包含网页截图或图像），"
                    "用简要、结构化的中文描述当前网页上与操作相关的元素，例如搜索框、按钮、链接、"
                    "搜索结果列表等。请用一小段自然语言总结。"
                )
                vision_messages = list(messages) + [LangChainSystemMessage(content=vision_prompt)]
                vision_resp = await self.vision_llm.ainvoke(vision_messages)
                vision_description = self._extract_text_from_response(vision_resp)
        except Exception as e:
            self.logger.warning(f"视觉模型调用失败，将直接使用文本模型执行浏览器步骤：{e}")
            vision_description = None

        # 2) 将视觉描述注入为额外的 system message，帮助文本模型决策
        augmented_messages = list(messages)
        if vision_description:
            augmented_messages.append(
                LangChainSystemMessage(
                    content=(
                        "下面是视觉模型对当前网页的观察，请结合它来规划下一步浏览器操作：\n"
                        f"{vision_description}"
                    )
                )
            )

        # 3) 委托文本模型执行真正的结构化决策
        # Qwen/Deepseek 等模型不支持 output_format/response_format，必须 strip 掉，否则底层报 unexpected keyword
        text_kwargs = dict(kwargs)
        text_out_fmt = output_format
        try:
            hint = (
                str(getattr(self.text_llm, "model", "") or "") + " " +
                str(getattr(self.text_llm, "model_name", "") or "")
            ).lower()
            if "qwen" in hint or "deepseek" in hint:
                text_out_fmt = None
                text_kwargs.pop("output_format", None)
                text_kwargs.pop("response_format", None)
        except Exception:
            pass
        return await self.text_llm.ainvoke(augmented_messages, output_format=text_out_fmt, **text_kwargs)

    def _extract_text_from_response(self, resp: Any) -> str:
        """
        从视觉模型响应中尽量提取可读文本，兼容多种 content / additional_kwargs 结构。
        """
        if resp is None:
            return ""

        raw = getattr(resp, "content", None)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

        # 多模态 list: [{"type": "text", "text": "..."} , ...]
        if isinstance(raw, list):
            parts: list[str] = []
            for part in raw:
                if isinstance(part, dict):
                    if part.get("type") == "text" and part.get("text"):
                        parts.append(str(part["text"]))
                    elif part.get("text"):
                        parts.append(str(part["text"]))
                    elif part.get("content"):
                        parts.append(str(part["content"]))
                elif isinstance(part, str):
                    parts.append(part)
            if parts:
                return "\n".join(parts).strip()

        extra = getattr(resp, "additional_kwargs", None) or {}
        if isinstance(extra, dict):
            for key in ("content", "text", "message"):
                v = extra.get(key)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            choices = extra.get("choices") or []
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message") or choices[0]
                c = msg.get("content")
                if isinstance(c, str) and c.strip():
                    return c.strip()

        meta = getattr(resp, "response_metadata", None) or {}
        if isinstance(meta, dict):
            c = meta.get("content")
            if isinstance(c, str) and c.strip():
                return c.strip()

        # 兜底：返回对象的字符串表示，防止完全拿不到内容
        try:
            return str(resp)[:4000]
        except Exception:
            return ""

