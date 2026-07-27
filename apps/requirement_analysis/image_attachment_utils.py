"""测试用例生成 — 带角色标注的图片附件。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

IMAGE_ROLE_UI_LAYOUT = "ui_layout"
IMAGE_ROLE_OPERATION_STEP = "operation_step"

IMAGE_ROLE_LABELS = {
    IMAGE_ROLE_UI_LAYOUT: "页面样式参考",
    IMAGE_ROLE_OPERATION_STEP: "操作步骤参考",
}

UI_LAYOUT_INTRO = (
    "【页面样式参考 — 非需求正文】\n"
    "以下截图仅用于识别界面布局、字段位置、按钮与菜单名称。\n"
    "请勿将截图中的文字当作业务需求条款；需求范围以上方「需求描述/需求正文」为准。"
)

OPERATION_STEP_INTRO = (
    "【操作步骤参考 — 非需求正文】\n"
    "以下截图按顺序展示用户操作流程，请据此编写测试用例中的「操作步骤」与「预期结果」。\n"
    "截图是操作示范，不是额外的需求规则或验收条款。"
)


def normalize_image_attachments(
    image_attachments: Optional[List[Any]] = None,
    image_data_urls: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """合并结构化附件与旧版纯 URL 列表。旧版默认视为页面样式参考。"""
    result: List[Dict[str, Any]] = []

    for item in image_attachments or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url.startswith("data:image"):
            continue
        role = str(item.get("role") or IMAGE_ROLE_UI_LAYOUT).strip()
        if role not in IMAGE_ROLE_LABELS:
            role = IMAGE_ROLE_UI_LAYOUT
        entry: Dict[str, Any] = {"url": url, "role": role}
        caption = str(item.get("caption") or "").strip()
        if caption:
            entry["caption"] = caption[:200]
        if role == IMAGE_ROLE_OPERATION_STEP:
            try:
                entry["step_index"] = int(item.get("step_index") or len(result) + 1)
            except (TypeError, ValueError):
                entry["step_index"] = len(result) + 1
        result.append(entry)
        if len(result) >= 12:
            return result

    if result:
        return result

    for url in image_data_urls or []:
        if isinstance(url, str) and url.strip().startswith("data:image"):
            result.append({"url": url.strip(), "role": IMAGE_ROLE_UI_LAYOUT})
        if len(result) >= 12:
            break
    return result


def merge_image_attachments(
    existing: List[Dict[str, Any]],
    new_items: List[Dict[str, Any]],
    *,
    max_count: int = 12,
) -> List[Dict[str, Any]]:
    """合并已有与新增图片附件，同 URL 以新增元数据为准。"""
    by_url: Dict[str, Dict[str, Any]] = {}
    for item in (existing or []) + (new_items or []):
        url = str(item.get("url") or "").strip()
        if not url.startswith("data:image"):
            continue
        by_url[url] = item
    return list(by_url.values())[:max_count]


def build_multimodal_user_content(text: str, attachments: List[Dict[str, Any]]) -> Any:
    """
    构建 OpenAI 多模态 user content。
    需求正文与图片分块，并用文字明确图片角色，避免模型把截图当需求。
    """
    attachments = attachments or []
    if not attachments:
        return text

    parts: List[Dict[str, Any]] = [{"type": "text", "text": text}]

    ui_items = [a for a in attachments if a.get("role") == IMAGE_ROLE_UI_LAYOUT]
    step_items = sorted(
        [a for a in attachments if a.get("role") == IMAGE_ROLE_OPERATION_STEP],
        key=lambda x: int(x.get("step_index") or 999),
    )

    if ui_items:
        parts.append({"type": "text", "text": UI_LAYOUT_INTRO})
        for idx, att in enumerate(ui_items, start=1):
            cap = (att.get("caption") or "").strip() or f"界面参考图 {idx}"
            parts.append({"type": "text", "text": f"--- {cap} ---"})
            parts.append({"type": "image_url", "image_url": {"url": att["url"]}})

    if step_items:
        parts.append({"type": "text", "text": OPERATION_STEP_INTRO})
        for att in step_items:
            step_n = int(att.get("step_index") or 0) or step_items.index(att) + 1
            cap = (att.get("caption") or "").strip() or f"操作步骤 {step_n}"
            parts.append({"type": "text", "text": f"--- 步骤 {step_n}：{cap} ---"})
            parts.append({"type": "image_url", "image_url": {"url": att["url"]}})

    return parts if len(parts) > 1 else text
