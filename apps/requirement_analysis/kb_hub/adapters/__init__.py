# -*- coding: utf-8 -*-
"""外部知识源适配器工厂。"""

from __future__ import annotations

from .base import ExternalKbAdapter
from .feishu import FeishuAdapter
from .notion import NotionAdapter
from .confluence import ConfluenceAdapter

__all__ = ["ExternalKbAdapter", "FeishuAdapter", "NotionAdapter", "ConfluenceAdapter", "get_adapter"]

# 外部类型 -> 适配器类
_ADAPTER_MAP = {
    "feishu": FeishuAdapter,
    "notion": NotionAdapter,
    "confluence": ConfluenceAdapter,
}


def get_adapter(kb_source):
    """根据 KbSource 返回对应的外部适配器实例。"""
    cls = _ADAPTER_MAP.get(kb_source.external_type)
    if cls is None:
        raise ValueError(f"暂不支持的外部知识源类型: {kb_source.external_type}")
    return cls(kb_source)
