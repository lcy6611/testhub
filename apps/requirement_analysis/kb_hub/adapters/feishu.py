# -*- coding: utf-8 -*-
"""飞书适配器。

支持两种接入方式（由 KbSource.feishu_mode 决定）：
  - wiki  （默认，向后兼容）：飞书「知识库（Wiki）」
      1. 用 app_id / app_secret 换取 tenant_access_token
      2. 列出知识空间（wiki spaces）
      3. 递归遍历空间下的 wiki 节点（docx 文档节点）
      4. 拉取每个 docx 的 raw_content 存为本地文档
  - drive （云盘 / 云文档）：飞书「云空间」
      1. 换取 tenant_access_token
      2. 取「我的空间」根目录（或配置的 feishu_root_folder_token）
      3. 递归遍历文件夹（drive/explorer/v2/folder/:token/children）
      4. 按文件类型提取内容：
         - docx  -> docx/v1/documents/:token/raw_content
         - doc   -> doc/v2/documents/:token（旧版文档）
         - sheet -> sheets/v2 读取各分表全量数据
         - bitable -> bitable/v1 读取各数据表记录
         - file  -> drive/v1/files/:token/download 二进制落盘，复用本地解析器
         - mindnote / 其它 -> 暂不支持，跳过并记录警告

注意：接口路径/字段依据飞书开放平台文档，实际接入时请以最新文档为准，
且需要真实的 app_id / app_secret / 权限（drive:drive、docx:document、
sheets:spreadsheet、bitable:app 等）。未配置真实凭证时，同步会抛出清晰的
中文错误，不会静默失败。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from .base import ExternalKbAdapter

logger = logging.getLogger(__name__)


class FeishuAdapter(ExternalKbAdapter):
    engine_name = "feishu"

    # 云盘遍历最大深度，防止极端嵌套
    DRIVE_MAX_DEPTH = 12
    # 多维表格单表最多拉取记录数（防止超大表打爆内存）
    BITABLE_MAX_RECORDS = 500

    def _url(self, path: str) -> str:
        base = (self.kb_source.base_url or "https://open.feishu.cn").rstrip("/")
        return f"{base}{path}"

    def authenticate(self, token: Optional[str] = None) -> str:
        if token:
            return token
        if not (self.kb_source.app_id and self.kb_source.app_secret):
            raise ValueError("飞书数据源未配置 app_id / app_secret")
        resp = requests.post(
            self._url("/open-apis/auth/v3/tenant_access_token/internal"),
            json={"app_id": self.kb_source.app_id, "app_secret": self.kb_source.app_secret},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"飞书鉴权失败: {data.get('msg')} (code={data.get('code')})")
        return data["tenant_access_token"]

    # ===================== wiki（知识库）模式 =====================
    def list_spaces(self, token: str) -> List[Dict[str, Any]]:
        """列出知识空间（wiki）。"""
        out: List[Dict[str, Any]] = []
        url = self._url("/open-apis/wiki/v2/spaces?page_size=50")
        while url:
            resp = requests.get(
                url, headers={"Authorization": f"Bearer {token}"}, timeout=15
            )
            data = resp.json()
            if data.get("code") != 0:
                raise ValueError(f"飞书获取知识空间失败: {data.get('msg')} (code={data.get('code')})")
            items = data.get("data", {}).get("items", [])
            for item in items:
                out.append({
                    "id": item.get("space_id") or item.get("id"),
                    "name": item.get("name") or item.get("space_id") or item.get("id"),
                })
            page_token = data.get("data", {}).get("page_token")
            has_more = data.get("data", {}).get("has_more")
            url = (
                self._url(f"/open-apis/wiki/v2/spaces?page_size=50&page_token={page_token}")
                if (has_more and page_token) else None
            )
        return out

    def list_nodes(self, token: str, space_id: str) -> List[Dict[str, Any]]:
        """递归遍历空间下的节点，仅返回 docx 文档节点。"""
        out: List[Dict[str, Any]] = []

        def walk(parent_node_token: str = ""):
            url = self._url(f"/open-apis/wiki/v2/spaces/{space_id}/nodes?page_size=50")
            if parent_node_token:
                url += f"&parent_node_token={parent_node_token}"
            resp = requests.get(
                url, headers={"Authorization": f"Bearer {token}"}, timeout=15
            )
            data = resp.json()
            if data.get("code") != 0:
                raise ValueError(f"飞书获取节点失败: {data.get('msg')} (code={data.get('code')})")
            for node in data.get("data", {}).get("items", []):
                node_token = node.get("node_token") or node.get("id")
                if node.get("obj_type") == "docx":
                    out.append({
                        "id": node_token,
                        "title": node.get("title") or node_token,
                    })
                # 递归子节点（无论类型，确保文档树完整）
                walk(node_token)

        walk()
        return out

    def fetch_node_content(self, token: str, node: Dict[str, Any]) -> str:
        """获取 docx 文档纯文本（raw_content）。"""
        node_id = node.get("id")
        if not node_id:
            raise ValueError("节点缺少 id")
        return self._get_docx_raw(token, node_id)

    # ===================== drive（云盘 / 云文档）模式 =====================
    def _drive_root_token(self, token: str) -> str:
        """取云盘起始目录 token：优先用配置的，否则取「我的空间」根目录。"""
        configured = (self.kb_source.feishu_root_folder_token or "").strip()
        if configured:
            return configured
        resp = requests.get(
            self._url("/open-apis/drive/explorer/v2/root_folder/meta"),
            headers={"Authorization": f"Bearer {token}"}, timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"飞书获取云盘根目录失败: {data.get('msg')} (code={data.get('code')})")
        tok = (data.get("data", {}) or {}).get("token") or (data.get("data", {}) or {}).get("id")
        if not tok:
            raise ValueError("飞书云盘根目录为空，请检查应用云空间权限或手动配置根目录 Token")
        return tok

    def list_drive_children(self, token: str, folder_token: str) -> List[Dict[str, Any]]:
        """返回该文件夹下的 children 列表（飞书返回的是 dict，需要 .values()）。

        每个 child 含 token / name / type / is_shortcut。
        """
        resp = requests.get(
            self._url(f"/open-apis/drive/explorer/v2/folder/{folder_token}/children"),
            headers={"Authorization": f"Bearer {token}"}, timeout=15,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"飞书获取云盘目录失败: {data.get('msg')} (code={data.get('code')})")
        children = (data.get("data", {}) or {}).get("children") or {}
        return list(children.values())

    def _get_docx_raw(self, token: str, doc_token: str) -> str:
        resp = requests.get(
            self._url(f"/open-apis/docx/v1/documents/{doc_token}/raw_content"),
            headers={"Authorization": f"Bearer {token}"}, timeout=20,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"飞书获取文档内容失败: {data.get('msg')} (code={data.get('code')})")
        return (data.get("data", {}) or {}).get("content", "") or ""

    def _get_legacy_doc(self, token: str, doc_token: str) -> str:
        resp = requests.get(
            self._url(f"/open-apis/doc/v2/documents/{doc_token}"),
            headers={"Authorization": f"Bearer {token}"}, timeout=20,
        )
        data = resp.json()
        if data.get("code") != 0:
            raise ValueError(f"飞书获取旧版文档失败: {data.get('msg')} (code={data.get('code')})")
        return (data.get("data", {}) or {}).get("document", {}).get("content", "") or ""

    def _get_sheet_text(self, token: str, sheet_token: str) -> str:
        """读取电子表格全部分表的纯文本（TSV）。"""
        meta = requests.get(
            self._url(f"/open-apis/sheets/v2/spreadsheets/{sheet_token}/metadata"),
            headers={"Authorization": f"Bearer {token}"}, timeout=20,
        ).json()
        if meta.get("code") != 0:
            raise ValueError(f"飞书获取表格元信息失败: {meta.get('msg')} (code={meta.get('code')})")
        sheets = (meta.get("data", {}) or {}).get("sheets") or []
        parts: List[str] = []
        for sh in sheets:
            sheet_id = sh.get("sheetId")
            title = sh.get("title") or sheet_id
            if not sheet_id:
                continue
            rng_url = self._url(f"/open-apis/sheets/v2/spreadsheets/{sheet_token}/values/{sheet_id}")
            r = requests.get(
                rng_url, headers={"Authorization": f"Bearer {token}"},
                params={"valueRenderOption": "ToString"}, timeout=20,
            ).json()
            if r.get("code") != 0:
                logger.warning("读取表格分表 %s 失败: %s", title, r.get("msg"))
                continue
            values = (r.get("data", {}) or {}).get("valueRanges", [{}])[0].get("values") or []
            if not values:
                continue
            lines = ["\t".join("" if c is None else str(c) for c in row) for row in values]
            parts.append(f"### 分表：{title}\n" + "\n".join(lines))
        if not parts:
            raise ValueError("电子表格无可读数据")
        return "\n\n".join(parts)

    def _get_bitable_text(self, token: str, app_token: str) -> str:
        """读取多维表格各数据表的记录（纯文本 TSV，单表最多 BITABLE_MAX_RECORDS 条）。"""
        tlist = requests.get(
            self._url(f"/open-apis/bitable/v1/apps/{app_token}/tables"),
            headers={"Authorization": f"Bearer {token}"}, timeout=20,
        ).json()
        if tlist.get("code") != 0:
            raise ValueError(f"飞书获取多维表格列表失败: {tlist.get('msg')} (code={tlist.get('code')})")
        tables = (tlist.get("data", {}) or {}).get("items") or []
        parts: List[str] = []
        for tb in tables:
            table_id = tb.get("table_id") or tb.get("id")
            tname = tb.get("name") or table_id
            if not table_id:
                continue
            records: List[Dict[str, Any]] = []
            page_token: Optional[str] = None
            while len(records) < self.BITABLE_MAX_RECORDS:
                params = {"page_size": 100}
                if page_token:
                    params["page_token"] = page_token
                r = requests.get(
                    self._url(f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"),
                    headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20,
                ).json()
                if r.get("code") != 0:
                    logger.warning("读取多维表格 %s 记录失败: %s", tname, r.get("msg"))
                    break
                items = (r.get("data", {}) or {}).get("items") or []
                if not items:
                    break
                records.extend(items)
                page_token = (r.get("data", {}) or {}).get("page_token")
                if not page_token or len(items) < 100:
                    break
            if not records:
                continue
            header = list((records[0].get("fields") or {}).keys())
            lines = ["\t".join(header)]
            for rec in records:
                fields = rec.get("fields") or {}
                cells = []
                for h in header:
                    v = fields.get(h)
                    if v is None:
                        cells.append("")
                    elif isinstance(v, (list, dict)):
                        cells.append(str(v))
                    else:
                        cells.append(str(v))
                lines.append("\t".join(cells))
            parts.append(f"### 数据表：{tname}（{len(records)} 条）\n" + "\n".join(lines))
        if not parts:
            raise ValueError("多维表格无可读记录")
        return "\n\n".join(parts)

    def _download_file(self, token: str, file_token: str) -> bytes:
        """下载云盘中的二进制文件（pdf/doc/图片等），返回原始字节。"""
        resp = requests.get(
            self._url(f"/open-apis/drive/v1/files/{file_token}/download"),
            headers={"Authorization": f"Bearer {token}"}, timeout=60, stream=True,
        )
        if resp.status_code != 200:
            raise ValueError(f"飞书下载文件失败: HTTP {resp.status_code}")
        return resp.content

    def _fetch_drive_content(self, token: str, child: Dict[str, Any]) -> Tuple[str, str, Optional[bytes]]:
        """返回 (content_text, source_type, file_bytes)。

        - file_bytes 非 None 表示这是二进制文件，需落盘后由本地解析器处理；
        - 不支持的类型（mindnote 等）或提取失败直接抛异常，由调用方计入失败。
        """
        ctype = child.get("type")
        ctoken = child.get("token")
        if ctype == "docx":
            return self._get_docx_raw(token, ctoken), "url", None
        if ctype == "doc":
            return self._get_legacy_doc(token, ctoken), "url", None
        if ctype == "sheet":
            return self._get_sheet_text(token, ctoken), "url", None
        if ctype == "bitable":
            return self._get_bitable_text(token, ctoken), "url", None
        if ctype == "file":
            return "", "file", self._download_file(token, ctoken)
        # mindnote 等暂不支持
        raise ValueError(f"不支持的云盘文件类型: {ctype}")

    def _sync_drive(self, target_kb, source) -> Dict[str, Any]:
        """云盘模式同步：递归遍历文件夹，按文件类型提取内容写入本地知识库。"""
        token = self.authenticate()
        root = self._drive_root_token(token)
        docs: List[Any] = []
        total = synced = failed = 0
        seen_tokens: set = set()

        def walk(folder_token: str, depth: int = 0):
            nonlocal total, synced, failed
            if depth > self.DRIVE_MAX_DEPTH:
                logger.warning("云盘遍历超过最大深度 %s，停止: %s", self.DRIVE_MAX_DEPTH, folder_token)
                return
            for child in self.list_drive_children(token, folder_token):
                ctype = child.get("type")
                ctoken = child.get("token")
                cname = child.get("name") or ctoken
                if not ctoken or ctoken in seen_tokens:
                    continue
                seen_tokens.add(ctoken)
                if ctype == "folder":
                    walk(ctoken, depth + 1)
                    continue
                total += 1
                try:
                    content, source_type, file_bytes = self._fetch_drive_content(token, child)
                    node = {
                        "id": ctoken, "title": cname, "name": cname, "space_id": root,
                    }
                    docs.append(self._make_doc(
                        target_kb, node, content, source_type=source_type,
                        file_bytes=file_bytes, filename=cname,
                    ))
                    synced += 1
                except Exception as exc:  # 单文件失败不影响整体
                    failed += 1
                    logger.warning("同步云盘文件失败 token=%s name=%s: %s", ctoken, cname, exc)

        walk(root)
        return self._finalize_sync(target_kb, docs, source, total, synced, failed)

    def sync_to_native(self, target_kb=None):
        """按 feishu_mode 分派：drive 走云盘遍历，wiki 走知识库遍历。"""
        mode = getattr(self.kb_source, "feishu_mode", "wiki") or "wiki"
        if mode == "drive":
            return self._sync_drive(self._resolve_target_kb(target_kb), self.kb_source)
        return super().sync_to_native(target_kb)
