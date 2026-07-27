# -*- coding: utf-8 -*-
"""
知识中枢（Knowledge Hub）模块。

支持双后端可切换：
  - dify:  保留原有 Dify 知识库集成
  - native: 自建知识中枢（文档解析 + Embedding + Rerank + 向量检索）

配置统一收口在 KnowledgeHubConfig（单例），运行时由 KbBackendFactory 按配置路由。
"""

from .models import (
    KnowledgeHubConfig,
    NativeKb,
    NativeKbDocument,
    NativeKbChunk,
)
from .backend import KbBackend, KbBackendFactory

__all__ = [
    "KnowledgeHubConfig",
    "NativeKb",
    "NativeKbDocument",
    "NativeKbChunk",
    "KbBackend",
    "KbBackendFactory",
]
