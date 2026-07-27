# -*- coding: utf-8 -*-
"""
文档解析 + 分块。

解析策略（按 parser_type）：
  - tika:   内置纯 Python 解析（txt/md 直读；docx 用 python-docx；pdf 用 pypdf），Tika 可选增强
  - mineru: MinerU 服务 API（预留，未配置则回退内置解析）
  - textin: TextIn 服务 API（预留，未配置则回退内置解析）
"""

from __future__ import annotations

import logging
import os
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


def _read_plain(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _parse_docx(path: str) -> str:
    try:
        from docx import Document  # type: ignore
    except Exception:
        return ""
    try:
        doc = Document(path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text and p.text.strip())
    except Exception as exc:
        logger.warning("docx 解析失败: %s", exc)
        return ""


def _parse_pdf(path: str) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        return ""
    try:
        reader = PdfReader(path)
        parts: List[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text.strip())
        return "\n\n".join(parts)
    except Exception as exc:
        logger.warning("pdf 解析失败: %s", exc)
        return ""


def _parse_with_tika(path: str) -> str:
    try:
        from tika import parser as tika_parser  # type: ignore
    except Exception:
        return ""
    try:
        parsed = tika_parser.from_file(path)
        return (parsed.get("content") or "").strip()
    except Exception as exc:
        logger.warning("tika 解析失败: %s", exc)
        return ""


def parse_file(path: str, *, parser_type: str = "tika") -> str:
    """解析本地文件为 Markdown 文本。"""
    if not path or not os.path.exists(path):
        return ""
    ext = os.path.splitext(path)[1].lower()
    text = ""
    if ext in (".txt", ".md", ".markdown", ".csv", ".json", ".log"):
        text = _read_plain(path)
    elif ext == ".docx":
        text = _parse_docx(path)
    elif ext == ".pdf":
        text = _parse_pdf(path)
    elif ext in (".doc",):
        text = _parse_with_tika(path)
    else:
        text = _parse_with_tika(path) or _read_plain(path)
    return (text or "").strip()


def parse_uploaded_file(file_field, *, parser_type: str = "tika") -> str:
    """解析 Django FileField 上传文件。"""
    try:
        path = file_field.path
    except Exception:
        path = ""
    if path and os.path.exists(path):
        return parse_file(path, parser_type=parser_type)
    # 回退：直接读流
    try:
        return file_field.read().decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def parse_text(content: str) -> str:
    """文本录入直接清洗。"""
    return (content or "").strip()


def chunk_text(
    text: str,
    *,
    chunk_size: int = 500,
    overlap: int = 80,
) -> List[str]:
    """按段落 + 字符数滑动窗口分块。"""
    text = (text or "").strip()
    if not text:
        return []
    chunk_size = max(200, int(chunk_size or 500))
    overlap = max(0, int(overlap or 0))
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    buf = ""

    def _flush():
        nonlocal buf
        if not buf.strip():
            buf = ""
            return
        # 超长段落内部滑动切分
        if len(buf) <= chunk_size:
            chunks.append(buf.strip())
        else:
            start = 0
            while start < len(buf):
                piece = buf[start : start + chunk_size].strip()
                if piece:
                    chunks.append(piece)
                if start + chunk_size >= len(buf):
                    break
                start += chunk_size - overlap
        buf = ""

    for para in paragraphs:
        if len(buf) + len(para) + 2 <= chunk_size:
            buf = (buf + "\n\n" + para).strip() if buf else para
        else:
            _flush()
            buf = para
    _flush()
    return chunks
