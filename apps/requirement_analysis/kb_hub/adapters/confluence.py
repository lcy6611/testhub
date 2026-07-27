# -*- coding: utf-8 -*-
"""Confluence Cloud 适配器。

凭证约定：
- `app_secret` 存 `email:api_token`（中间用 `:` 分隔，例 `user@example.com:ATATT3x...`）
- `app_id` 存 Confluence Cloud 站点 base URL（`https://your-domain.atlassian.net/wiki`）
- `tenant_key` 可选：限定同步的 space key（留空则同步所有空间）
- `base_url` 留空，使用 `app_id` 作为站点入口
- 认证：Basic Auth（`Authorization: Basic base64(email:api_token)`）
- API：优先 `/wiki/api/v2`（推荐）；同时支持 `/wiki/rest/api` 旧版（v1 路径）
- 限流：5 req/s；429 重试

同步策略：
- 列出所有空间（GET /wiki/api/v2/spaces）
- 每个空间下列出页面（GET /wiki/api/v2/spaces/{id}/pages，循环分页）
- 对每个页面拉取 body（atlas_doc_format 优先，回退 storage 格式）
- 把 confluence storage 标签转 Markdown
"""

from __future__ import annotations

import base64
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests

from .base import ExternalKbAdapter

logger = logging.getLogger(__name__)


class ConfluenceAdapter(ExternalKbAdapter):
    engine_name = "confluence"

    def __init__(self, kb_source):
        super().__init__(kb_source)
        self.session = requests.Session()
        # base_url 默认指向 app_id（即 site URL）；否则用 base_url
        site_url = (kb_source.app_id or kb_source.base_url or "").rstrip("/")
        if not site_url:
            raise ValueError("Confluence 适配器需要在「App ID」字段填写 Confluence Cloud 站点 URL（如 https://your.atlassian.net/wiki）")
        self.api_base = site_url
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self.space_filter = (kb_source.tenant_key or "").strip()  # 限定 space key

    # ---------------- 工具方法 ----------------
    def _basic_auth(self) -> str:
        cred = (self.kb_source.app_secret or "").strip()
        if ":" not in cred:
            raise ValueError("Confluence 凭证格式错误：应为「邮箱:API Token」（例 user@example.com:ATATT3x...）")
        email, token = cred.split(":", 1)
        return "Basic " + base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = urljoin(self.api_base + "/", path.lstrip("/"))
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = self._basic_auth()
        for i in range(3):
            try:
                resp = self.session.request(method, url, headers=headers, timeout=30, **kwargs)
                if resp.status_code == 429:
                    wait = float(resp.headers.get("Retry-After", "1"))
                    logger.warning("Confluence 限流，等待 %ss", wait)
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
            raise RuntimeError(f"Confluence API 多次重试失败: {url} status={resp.status_code}")
        if resp.status_code >= 400:
            raise RuntimeError(f"Confluence API 错误 {resp.status_code}: {resp.text[:500]}")
        time.sleep(0.2)  # 简单节流 5 req/s
        return resp.json()

    # ---------------- 基类接口（自定义同步不走基类流程） ----------------
    def authenticate(self, token: Optional[str] = None) -> str:
        return self._basic_auth()

    def list_spaces(self, token: str) -> List[Dict[str, Any]]:
        return []

    def list_nodes(self, token: str, space_id: str) -> List[Dict[str, Any]]:
        return []

    def fetch_node_content(self, token: str, node: Dict[str, Any]) -> str:
        return ""

    # ---------------- 自定义同步流程 ----------------
    def _list_spaces(self) -> List[Dict[str, Any]]:
        """v2：列出所有空间。"""
        results: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        while True:
            params: Dict[str, Any] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            data = self._request("GET", "/api/v2/spaces", params=params)
            results.extend(data.get("results", []))
            # v2 用 _links.next 翻页；为简化也兼容 results 截断
            link = (data.get("_links") or {}).get("next")
            if link:
                # 用 cursor 参数
                m = re.search(r"cursor=([^&]+)", link)
                cursor = m.group(1) if m else None
                if not cursor:
                    break
            elif len(data.get("results", [])) < 100:
                break
            else:
                break
        return results

    def _list_pages_in_space(self, space_id: str) -> List[Dict[str, Any]]:
        """v2：列出某空间下的所有页面（不带 body）。"""
        results: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        while True:
            params: Dict[str, Any] = {"limit": 100}
            if cursor:
                params["cursor"] = cursor
            data = self._request(
                "GET", f"/api/v2/spaces/{space_id}/pages", params=params,
            )
            results.extend(data.get("results", []))
            link = (data.get("_links") or {}).get("next")
            if link:
                m = re.search(r"cursor=([^&]+)", link)
                cursor = m.group(1) if m else None
                if not cursor:
                    break
            elif len(data.get("results", [])) < 100:
                break
            else:
                break
        return results

    def _fetch_page_body(self, page_id: str) -> Tuple[str, str]:
        """拉取页面正文，返回 (title, markdown_text)。

        优先 v2 的 body-atlas-doc-format，回退到 v1 的 body.storage。
        """
        # v2 + atlas_doc_format
        try:
            data = self._request(
                "GET", f"/api/v2/pages/{page_id}",
                params={"body-format": "atlas_doc_format"},
            )
            title = data.get("title") or f"Page {page_id}"
            body = (data.get("body") or {}).get("atlas_doc_format", {}) or {}
            value = body.get("value", "") if isinstance(body, dict) else ""
            if value:
                return title, self._atlas_to_markdown(value)
        except Exception as exc:
            logger.info("v2 atlas_doc_format 失败 %s，回退 v1: %s", page_id, exc)

        # v1 回退
        try:
            data = self._request(
                "GET", f"/rest/api/content/{page_id}",
                params={"expand": "body.storage,version"},
            )
            title = data.get("title") or f"Page {page_id}"
            storage = (data.get("body") or {}).get("storage", {}) or {}
            value = storage.get("value", "") if isinstance(storage, dict) else ""
            if value:
                return title, self._storage_to_markdown(value)
            return title, ""
        except Exception as exc:
            logger.warning("Confluence 拉取页面正文失败 %s: %s", page_id, exc)
            return f"Page {page_id}", ""

    # ---------------- 格式转换 ----------------
    @staticmethod
    def _strip_tags(html: str) -> str:
        """粗略剥 HTML 标签。"""
        return re.sub(r"<[^>]+>", "", html or "").strip()

    def _storage_to_markdown(self, storage_html: str) -> str:
        """Confluence storage（XHTML）→ Markdown。

        简化策略：把常见块标签替换为 Markdown 标记，其余剥标签保留文本。
        """
        text = storage_html or ""
        # 代码块（CDATA 不存在，全部标签化）
        text = re.sub(
            r'<ac:structured-macro[^>]*ac:name="code"[^>]*>.*?<ac:plain-text-body><!\[CDATA\[(.*?)\]\]></ac:plain-text-body>.*?</ac:structured-macro>',
            lambda m: f"\n```\n{m.group(1).strip()}\n```\n",
            text, flags=re.DOTALL,
        )
        # 标题
        for i in range(6, 0, -1):
            text = re.sub(rf"<h{i}[^>]*>(.*?)</h{i}>", lambda m, lvl=i: f"\n{'#' * lvl} {self._strip_tags(m.group(1))}\n", text, flags=re.DOTALL | re.IGNORECASE)
        # 列表
        text = re.sub(r"<li[^>]*>(.*?)</li>", lambda m: f"\n- {self._strip_tags(m.group(1))}", text, flags=re.DOTALL | re.IGNORECASE)
        # 段落
        text = re.sub(r"<p[^>]*>(.*?)</p>", lambda m: f"\n{self._strip_tags(m.group(1))}\n", text, flags=re.DOTALL | re.IGNORECASE)
        # 加粗 / 斜体
        text = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", lambda m: f"**{self._strip_tags(m.group(2))}**", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", lambda m: f"*{self._strip_tags(m.group(2))}*", text, flags=re.DOTALL | re.IGNORECASE)
        # 链接
        text = re.sub(r'<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>', lambda m: f"[{self._strip_tags(m.group(2))}]({m.group(1)})", text, flags=re.DOTALL | re.IGNORECASE)
        # 其余标签去掉
        text = self._strip_tags(text)
        # 多余空行
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text

    def _atlas_to_markdown(self, atlas_json: str) -> str:
        """v2 atlas_doc_format 是 JSON 字符串，转 Markdown。

        简化：递归提取 text 属性。
        """
        import json
        try:
            data = json.loads(atlas_json)
        except Exception:
            return atlas_json or ""

        lines: List[str] = []

        def walk(node: Dict[str, Any], depth: int = 0) -> None:
            t = node.get("type")
            txt = node.get("text", "")
            if t == "heading":
                lvl = max(1, min(6, int(node.get("attrs", {}).get("level", 1))))
                lines.append(f"\n{'#' * lvl} {txt}\n")
            elif t == "paragraph":
                lines.append(f"\n{txt}\n")
            elif t == "bulletList" or t == "orderedList":
                for i, item in enumerate(node.get("content", []) or []):
                    if i > 0:
                        lines.append("")
                    lines.append(f"- {txt}" if t == "bulletList" else f"1. {txt}")
                    for child in item.get("content", []) or []:
                        walk(child, depth + 1)
            elif t == "codeBlock":
                lang = (node.get("attrs") or {}).get("language", "")
                lines.append(f"\n```{lang}\n{txt}\n```\n")
            elif t == "blockquote":
                lines.append(f"\n> {txt}\n")
            elif t == "hardBreak":
                lines.append("\n")
            elif t == "text" and txt:
                lines.append(txt)
            # 递归子节点
            for child in node.get("content", []) or []:
                walk(child, depth + 1)

        walk(data)
        return "\n".join(lines).strip()

    # ---------------- 同步入口 ----------------
    def sync_to_native(self, target_kb=None) -> Dict[str, Any]:
        source = self.kb_source
        target_kb = self._resolve_target_kb(target_kb)
        source.sync_status = "syncing"
        source.save(update_fields=["sync_status", "updated_at"])

        total = synced = failed = 0
        docs: List = []
        try:
            spaces = self._list_spaces()
            logger.info("Confluence 同步开始: 发现 %d 个空间", len(spaces))
            for space in spaces:
                sid = space.get("id")
                sname = space.get("name") or sid or "Space"
                skey = space.get("key") or ""
                # 按 tenant_key 过滤
                if self.space_filter and self.space_filter != skey:
                    continue
                try:
                    pages = self._list_pages_in_space(sid)
                except Exception as exc:
                    failed += 1
                    logger.warning("列出空间 %s 页面失败: %s", sid, exc)
                    continue
                for page in pages:
                    pid = page.get("id")
                    total += 1
                    try:
                        title, text = self._fetch_page_body(pid)
                        node = {
                            "id": pid,
                            "title": title,
                            "space_id": sid,
                        }
                        docs.append(self._make_doc(
                            target_kb, node, text, source_type="url",
                            filename=f"{title}.md",
                        ))
                        synced += 1
                    except Exception as exc:
                        failed += 1
                        logger.warning("同步 Confluence 页面失败 %s: %s", pid, exc)
            return self._finalize_sync(target_kb, docs, source, total, synced, failed)
        except Exception as exc:
            logger.exception("Confluence 同步失败 source=%s: %s", source.pk, exc)
            source.sync_status = "failed"
            source.last_sync_error = self._beautify_confluence_error(str(exc))[:1000]
            source.save(update_fields=["sync_status", "last_sync_error", "updated_at"])
            return {
                "total": total, "synced": synced, "failed": failed,
                "target_kb_id": target_kb.id if target_kb else None,
            }

    @staticmethod
    def _beautify_confluence_error(msg: str) -> str:
        """Confluence 专属错误文案美化。"""
        if "401" in msg:
            return (
                "Confluence 凭证无效（401 Unauthorized）。\n\n"
                "修复步骤：\n"
                "1. 打开 https://id.atlassian.com/manage-profile/security/api-tokens 重新生成 API Token\n"
                "2. 确认「App ID」是 Confluence Cloud 站点 URL（如 https://your.atlassian.net/wiki）\n"
                "3. 「App Secret」字段填入 `邮箱:API Token`（中间英文冒号）\n"
                "4. 保存后回到本页重新点「同步」\n\n"
                f"【原始错误】{msg}"
            )
        if "404" in msg:
            return (
                "Confluence 站点 URL 不可达（404）。请核对「App ID」字段填的是 Cloud 站点 URL（含 /wiki 后缀），不是 Confluence Server 地址。\n\n"
                f"【原始错误】{msg}"
            )
        if "403" in msg:
            return (
                "Confluence 权限不足（403）。请检查：\n"
                "1. 邮箱对应的 Atlassian 账号是否对该 Space 有「查看」权限\n"
                "2. 若站点启用了 IP 白名单，把 TestHub 服务 IP 加进去\n\n"
                f"【原始错误】{msg}"
            )
        return msg