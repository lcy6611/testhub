# -*- coding: utf-8 -*-
"""
视觉理解模型调用工具。

用于截图/图表/界面理解，辅助 UI 用例生成与 APP 元素识别。
从 AIModelConfig 中取 role="vision" 的活跃配置，调用 OpenAI 兼容的 vision API。
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

VISION_TIMEOUT = 60


def _get_vision_config() -> Optional[Dict[str, Any]]:
    """获取视觉理解模型配置。"""
    try:
        from .models import AIModelConfig
        cfg = AIModelConfig.objects.filter(role="vision", is_active=True).order_by("-updated_at").first()
        if not cfg:
            return None
        return {
            "base_url": cfg.base_url.rstrip("/"),
            "api_key": cfg.api_key or "",
            "model_name": cfg.model_name,
            "max_tokens": cfg.max_tokens or 4096,
            "temperature": cfg.temperature or 0.3,
        }
    except Exception as e:
        logger.warning("获取视觉模型配置失败: %s", e)
        return None


def _image_to_data_url(image_input: str) -> str:
    """将图片路径或 URL 转为 data URL。如果是 http(s) URL 直接返回。"""
    if image_input.startswith(("http://", "https://")):
        return image_input
    if image_input.startswith("data:"):
        return image_input
    # 本地文件
    import os
    if os.path.exists(image_input):
        ext = os.path.splitext(image_input)[1].lower().lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext, "png")
        with open(image_input, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/{mime};base64,{b64}"
    return image_input


def analyze_image(
    image_url: str,
    prompt: str = "请描述这张图片中的界面布局、按钮、输入框等元素。",
    *,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    """调用视觉模型分析图片。

    Args:
        image_url: 图片 URL 或本地路径或 data URI
        prompt: 提示词
        max_tokens: 最大返回 token 数

    Returns:
        {"ok": True, "content": "..."} 或 {"ok": False, "error": "..."}
    """
    cfg = _get_vision_config()
    if not cfg:
        return {"ok": False, "error": "未配置视觉理解模型，请在配置中心添加 role=vision 的 AIModelConfig"}

    data_url = _image_to_data_url(image_url)

    payload = {
        "model": cfg["model_name"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "max_tokens": max_tokens or cfg["max_tokens"],
        "temperature": cfg["temperature"],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }

    url = f"{cfg['base_url']}/chat/completions"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=VISION_TIMEOUT)
        if not resp.ok:
            return {"ok": False, "error": f"视觉模型调用失败({resp.status_code}): {resp.text[:300]}"}
        data = resp.json()
        content = ""
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message", {})
            content = msg.get("content", "")
        return {"ok": True, "content": content, "raw": data}
    except requests.Timeout:
        return {"ok": False, "error": "视觉模型调用超时"}
    except Exception as e:
        logger.exception("视觉模型调用异常")
        return {"ok": False, "error": str(e)}


def analyze_images(
    image_urls: List[str],
    prompt: str = "请依次描述以下图片中的界面元素和操作流程。",
) -> Dict[str, Any]:
    """批量分析多张图片。"""
    cfg = _get_vision_config()
    if not cfg:
        return {"ok": False, "error": "未配置视觉理解模型"}

    content_parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
    for url in image_urls:
        content_parts.append({"type": "image_url", "image_url": {"url": _image_to_data_url(url)}})

    payload = {
        "model": cfg["model_name"],
        "messages": [{"role": "user", "content": content_parts}],
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['api_key']}",
    }
    url = f"{cfg['base_url']}/chat/completions"
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=VISION_TIMEOUT)
        if not resp.ok:
            return {"ok": False, "error": f"视觉模型调用失败({resp.status_code})"}
        data = resp.json()
        content = ""
        choices = data.get("choices") or []
        if choices:
            content = choices[0].get("message", {}).get("content", "")
        return {"ok": True, "content": content}
    except Exception as e:
        return {"ok": False, "error": str(e)}
