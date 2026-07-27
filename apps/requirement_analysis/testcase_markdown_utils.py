"""测试用例 Markdown 表格解析与重建（任务详情采纳/弃用）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def parse_markdown_table_cases(content: str) -> List[Dict[str, str]]:
    """从 Markdown 表格解析测试用例列表。"""
    if not (content or "").strip():
        return []

    lines = [ln for ln in (content or "").splitlines() if ln.strip()]
    table_rows: List[List[str]] = []
    for line in lines:
        trimmed = line.strip()
        if "|" not in trimmed or "----" in trimmed:
            continue
        cells = [c.strip() for c in trimmed.split("|") if c.strip()]
        if len(cells) > 1:
            table_rows.append(cells)

    if len(table_rows) < 2:
        return []

    headers = table_rows[0]
    cases: List[Dict[str, str]] = []
    for row in table_rows[1:]:
        item: Dict[str, str] = {}
        for idx, header in enumerate(headers):
            value = row[idx] if idx < len(row) else ""
            h = header.lower()
            if any(k in header for k in ("编号", "ID", "用例ID")):
                item["caseId"] = value
            elif any(k in header for k in ("场景", "标题", "测试目标")):
                item["scenario"] = value
            elif "前置" in header:
                item["precondition"] = value
            elif any(k in header for k in ("步骤", "操作步骤")):
                item["steps"] = value
            elif any(k in header for k in ("预期", "结果")):
                item["expected"] = value
            elif "优先级" in header:
                item["priority"] = value
            else:
                item.setdefault("_extra", "")
                item["_extra"] = value
        if item.get("scenario") or item.get("caseId"):
            cases.append(item)
    return cases


def rebuild_markdown_table_cases(cases: List[Dict[str, str]]) -> str:
    """将用例列表重建为 Markdown 表格。"""
    if not cases:
        return ""
    headers = ["用例编号", "测试场景", "前置条件", "操作步骤", "预期结果", "优先级"]
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    lines = ["| " + " | ".join(headers) + " |", sep]
    for idx, case in enumerate(cases, start=1):
        case_id = case.get("caseId") or f"TC{idx:03d}"
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_cell(case_id),
                    _escape_cell(case.get("scenario") or ""),
                    _escape_cell(case.get("precondition") or ""),
                    _escape_cell(case.get("steps") or ""),
                    _escape_cell(case.get("expected") or ""),
                    _escape_cell(case.get("priority") or "中"),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _escape_cell(value: str) -> str:
    return (value or "").replace("\n", "<br>").replace("|", "\\|")


def remove_cases_by_indices(content: str, indices: List[int]) -> tuple[str, int, List[Dict[str, str]]]:
    """按索引删除用例，返回 (新正文, 删除数量, 剩余用例)。"""
    cases = parse_markdown_table_cases(content)
    if not cases:
        return content, 0, cases

    remove_set = set()
    for i in indices:
        try:
            remove_set.add(int(i))
        except (TypeError, ValueError):
            continue
    remaining = [c for i, c in enumerate(cases) if i not in remove_set]
    removed = len(cases) - len(remaining)
    if not remaining:
        return "", removed, []
    return rebuild_markdown_table_cases(remaining), removed, remaining
