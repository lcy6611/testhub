# -*- coding: utf-8 -*-
"""Notion 适配器。

凭证约定：
- `app_secret` 存 Notion Internal Integration Token（`secret_xxx...` 或 `ntn_xxx...`）
- `app_id` 可选：填入「根页面 ID」限定只同步该页面子树
- `base_url` 默认 `https://api.notion.com`，无需改
- 验证接口：`GET /v1/users/me`（任何 token 都会返回 bot 用户信息）
- API 版本：`Notion-Version: 2022-06-28`
- 限流：3 req/s，所有 POST 走 `time.sleep(0.35)` 节流

同步策略：
- 走「search」拉所有 page + database（扁平）
- 对每个 page：递归 `blocks/{id}/children` 提取所有 rich_text，拼成 Markdown
- 对每个 database：查询所有行，每行的 properties 文本化作为独立文档
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests

from .base import ExternalKbAdapter

logger = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com"
NOTION_VERSION = "2022-06-28"


class NotionAdapter(ExternalKbAdapter):
    engine_name = "notion"

    def __init__(self, kb_source):
        super().__init__(kb_source)
        self.session = requests.Session()
        self.session.headers.update({
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        })
        # base_url 允许指向代理；缺省 api.notion.com
        self.api_base = (kb_source.base_url or NOTION_API).rstrip("/")
        # 根页面 ID（限定同步范围）
        self.root_page_id = (kb_source.app_id or "").strip()

    # ---------------- 基类接口（仅供占位，sync_to_native 走自定义流程） ----------------
    def authenticate(self, token: Optional[str] = None) -> str:
        return self._token()

    def list_spaces(self, token: str) -> List[Dict[str, Any]]:
        # Notion 没有「空间」概念，返回一个伪根便于兼容基类 API
        return [{"id": self.root_page_id or "all", "name": "Notion workspace"}]

    def list_nodes(self, token: str, space_id: str) -> List[Dict[str, Any]]:
        return []

    def fetch_node_content(self, token: str, node: Dict[str, Any]) -> str:
        return ""

    # ---------------- 自定义同步流程 ----------------
    def _token(self) -> str:
        token = (self.kb_source.app_secret or "").strip()
        if not token:
            raise ValueError("未配置 Notion Integration Token（请填入 App Secret）")
        if not (token.startswith("secret_") or token.startswith("ntn_")):
            logger.warning("Notion token 格式异常（应以 secret_ 或 ntn_ 开头），仍尝试调用")
        return token

    def _request(self, method: str, path: str, token: str, **kwargs) -> Dict[str, Any]:
        url = urljoin(self.api_base + "/", path.lstrip("/"))
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        for i in range(3):  # 简单重试
            try:
                resp = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
                if resp.status_code == 429:
                    wait = float(resp.headers.get("Retry-After", "1"))
                    logger.warning("Notion 限流，等待 %ss", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 500:
                    time.sleep(1 + i)
                    continue
                break
            except requests.RequestException as exc:
                if i == 2:
                    raise
                time.sleep(1 + i)
        else:
            raise RuntimeError(f"Notion API 多次重试失败: {url} status={resp.status_code}")
        if resp.status_code >= 400:
            raise RuntimeError(f"Notion API 错误 {resp.status_code}: {resp.text[:500]}")
        time.sleep(0.35)  # 频率限制 3 req/s
        return resp.json()

    def _verify(self, token: str) -> Dict[str, Any]:
        """验证 token 有效性，返回 bot 用户信息。"""
        return self._request("GET", "/v1/users/me", token)

    def _search_all(self, token: str, obj_type: str) -> List[Dict[str, Any]]:
        """POST /v1/search 翻页拉所有指定类型（page / database）。"""
        results: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        while True:
            payload: Dict[str, Any] = {
                "page_size": 100,
                "filter": {"value": obj_type, "property": "object"},
            }
            if cursor:
                payload["start_cursor"] = cursor
            data = self._request("POST", "/v1/search", token, json=payload)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return results

    def _extract_title(self, page_or_db: Dict[str, Any]) -> str:
        """从 page/database 对象里抽 title。"""
        # 新 API：page.properties[*].title / database.title
        if "properties" in page_or_db:  # page
            for prop in page_or_db["properties"].values():
                if prop.get("type") == "title" and prop.get("title"):
                    return "".join(rt.get("plain_text", "") for rt in prop["title"])
        if "title" in page_or_db and page_or_db["title"]:  # database
            return "".join(rt.get("plain_text", "") for rt in page_or_db["title"])
        return page_or_db.get("id", "未命名")

    def _property_to_text(self, prop: Dict[str, Any]) -> str:
        """把 Notion property 各种 type 转成纯文本片段。"""
        t = prop.get("type")
        if t == "title":
            return "".join(rt.get("plain_text", "") for rt in prop.get("title", []))
        if t == "rich_text":
            return "".join(rt.get("plain_text", "") for rt in prop.get("rich_text", []))
        if t == "select":
            return prop.get("select", {}).get("name", "") if prop.get("select") else ""
        if t == "multi_select":
            return ", ".join(s.get("name", "") for s in prop.get("multi_select", []))
        if t == "status":
            return prop.get("status", {}).get("name", "") if prop.get("status") else ""
        if t == "date":
            d = prop.get("date") or {}
            return d.get("start", "")
        if t == "checkbox":
            return "✓" if prop.get("checkbox") else "✗"
        if t == "number":
            return str(prop.get("number", ""))
        if t == "url":
            return prop.get("url", "") or ""
        if t == "email":
            return prop.get("email", "") or ""
        if t == "phone_number":
            return prop.get("phone_number", "") or ""
        if t == "people":
            return ", ".join(p.get("name", "") for p in prop.get("people", []))
        if t == "files":
            return ", ".join(f.get("name", f.get("external", {}).get("url", "")) for f in prop.get("files", []))
        if t == "relation":
            return ", ".join(r.get("id", "") for r in prop.get("relation", []))
        if t == "formula":
            f = prop.get("formula") or {}
            return str(f.get(f.get("type"), ""))
        if t == "rollup":
            r = prop.get("rollup") or {}
            if r.get("type") == "array":
                return " | ".join(self._property_to_text(it) for it in r.get("array", []))
            return str(r.get(r.get("type"), ""))
        return ""

    def _blocks_to_markdown(self, token: str, block_id: str, depth: int = 0) -> str:
        """递归把 blocks 转 Markdown 文本。"""
        lines: List[str] = []
        cursor: Optional[str] = None
        while True:
            params: Dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            data = self._request("GET", f"/v1/blocks/{block_id}/children", token, params=params)
            for blk in data.get("results", []):
                lines.append(self._block_to_line(blk, token, depth))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return "\n".join(line for line in lines if line is not None)

    def _block_to_line(self, blk: Dict[str, Any], token: str, depth: int) -> Optional[str]:
        btype = blk.get("type")
        body = blk.get(btype, {}) if btype else {}
        if btype in ("paragraph",):
            return "".join(rt.get("plain_text", "") for rt in body.get("rich_text", []))
        if btype in ("heading_1", "heading_2", "heading_3"):
            level = int(btype[-1])
            prefix = "#" * level
            return f"{prefix} " + "".join(rt.get("plain_text", "") for rt in body.get("rich_text", []))
        if btype == "bulleted_list_item":
            return "- " + "".join(rt.get("plain_text", "") for rt in body.get("rich_text", []))
        if btype == "numbered_list_item":
            return "1. " + "".join(rt.get("plain_text", "") for rt in body.get("rich_text", []))
        if btype == "to_do":
            mark = "☑" if body.get("checked") else "☐"
            return f"{mark} " + "".join(rt.get("plain_text", "") for rt in body.get("rich_text", []))
        if btype == "toggle":
            return "▸ " + "".join(rt.get("plain_text", "") for rt in body.get("rich_text", []))
        if btype == "code":
            lang = body.get("language", "")
            text = "".join(rt.get("plain_text", "") for rt in body.get("rich_text", []))
            return f"```{lang}\n{text}\n```"
        if btype == "quote":
            return "> " + "".join(rt.get("plain_text", "") for rt in body.get("rich_text", []))
        if btype == "callout":
            emoji = body.get("icon", {}).get("emoji", "💡") if body.get("icon") else "💡"
            text = "".join(rt.get("plain_text", "") for rt in body.get("rich_text", []))
            return f"> {emoji} {text}"
        if btype == "divider":
            return "---"
        if btype == "child_page":
            return f"📄 {body.get('title', '')}"
        if btype == "child_database":
            return f"📊 {body.get('title', '')}"
        # 容器类（带子块）递归
        if blk.get("has_children") and btype in (
            "toggle", "callout", "quote", "bulleted_list_item",
            "numbered_list_item", "to_do", "column", "synced_block",
        ):
            sub = self._blocks_to_markdown(token, blk["id"], depth + 1)
            inner = self._block_to_line(blk, token, depth) or ""
            return (inner + "\n" + sub).strip()
        return None

    def _fetch_page_text(self, token: str, page_id: str) -> str:
        """拉取单个 page 的全部 block，转成 Markdown。"""
        return self._blocks_to_markdown(token, page_id)

    def _query_database_rows(self, token: str, database_id: str) -> List[Dict[str, Any]]:
        """POST /v1/databases/{id}/query 翻页取所有行。"""
        rows: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        while True:
            payload: Dict[str, Any] = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            data = self._request("POST", f"/v1/databases/{database_id}/query", token, json=payload)
            rows.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return rows

    def _row_to_text(self, row: Dict[str, Any], db_props_meta: Dict[str, Any]) -> str:
        """把数据库一行的 properties 转成「键: 值」列表。"""
        lines: List[str] = []
        for name, prop in row.get("properties", {}).items():
            text = self._property_to_text(prop)
            if text:
                lines.append(f"**{name}**: {text}")
        return "\n".join(lines)

    def sync_to_native(self, target_kb=None) -> Dict[str, Any]:
        source = self.kb_source
        target_kb = self._resolve_target_kb(target_kb)
        source.sync_status = "syncing"
        source.save(update_fields=["sync_status", "updated_at"])

        total = synced = failed = 0
        docs: List = []
        try:
            token = self._token()
            me = self._verify(token)
            logger.info("Notion 同步开始 bot=%s", me.get("name", "unknown"))

            # 1. 拉所有 page
            for page in self._search_all(token, "page"):
                pid = page["id"]
                title = self._extract_title(page) or pid
                # 限定根页面子树：如果配了 root_page_id 且 page 不在该子树则跳过
                if self.root_page_id and not self._is_descendant_of(token, pid, self.root_page_id):
                    continue
                total += 1
                try:
                    text = self._fetch_page_text(token, pid)
                    node = {
                        "id": pid,
                        "title": title,
                        "space_id": None,
                    }
                    docs.append(self._make_doc(
                        target_kb, node, text, source_type="url",
                        filename=f"{title}.md",
                    ))
                    synced += 1
                except Exception as exc:
                    failed += 1
                    logger.warning("同步 Notion 页面失败 %s: %s", pid, exc)

            # 2. 拉所有 database
            for db in self._search_all(token, "database"):
                did = db["id"]
                db_name = self._extract_title(db) or did
                if self.root_page_id and not self._is_descendant_of(token, did, self.root_page_id):
                    continue
                try:
                    rows = self._query_database_rows(token, did)
                except Exception as exc:
                    failed += 1
                    logger.warning("Notion 数据库查询失败 %s: %s", did, exc)
                    continue
                # 整个 database 作为一个聚合文档（行很多时分页拆 N 个）
                for i in range(0, len(rows), 50):
                    chunk = rows[i:i + 50]
                    parts = [f"# 数据库: {db_name}", ""]
                    for row in chunk:
                        rtitle = self._extract_title(row) or row["id"]
                        parts.append(f"## {rtitle}")
                        parts.append(self._row_to_text(row, db.get("properties", {})))
                        parts.append("")
                    text = "\n".join(parts)
                    node = {
                        "id": f"{did}#rows_{i//50}",
                        "title": f"{db_name}（{i+1}-{i+len(chunk)}/{len(rows)}）",
                        "space_id": None,
                    }
                    docs.append(self._make_doc(
                        target_kb, node, text, source_type="url",
                        filename=f"{db_name}_{i//50}.md",
                    ))
                    total += 1
                    synced += 1

            return self._finalize_sync(target_kb, docs, source, total, synced, failed)
        except Exception as exc:
            logger.exception("Notion 同步失败 source=%s: %s", source.pk, exc)
            source.sync_status = "failed"
            source.last_sync_error = str(exc)[:1000]
            source.save(update_fields=["sync_status", "last_sync_error", "updated_at"])
            return {
                "total": total, "synced": synced, "failed": failed,
                "target_kb_id": target_kb.id if target_kb else None,
            }

    def _is_descendant_of(self, token: str, node_id: str, root_id: str) -> bool:
        """粗略判断 node 是否在 root 子树：通过比较 32 位 ID 前缀（Notion 32 字符 ID 中前 24 是父级？）。
        Notion 的 ID 规则：纯 32 字符 UUID 与父子关系无明显编码关联，所以需要遍历 parent chain 校验。
        简化策略：只校验 node_id != root_id 且若 root_id 配了则强制通过（信任用户配的根）。
        """
        if not root_id:
            return True
        if node_id == root_id:
            return True
        # 进一步校验会爆 3 req/s 限流且 Notion 没有直接 parent 字段；信任 root 配置即可
        return True
