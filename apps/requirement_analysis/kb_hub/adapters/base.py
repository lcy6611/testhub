# -*- coding: utf-8 -*-
"""外部 SaaS 知识库适配器基类。

设计目标：把飞书 / Confluence / Notion 等外部知识中枢的内容，
通过「拉取存储」策略同步到本地自建知识库（NativeKb + NativeKbDocument），
之后复用 NativeKbBackend 做检索与用例生成，从而无缝接入现有 AI 生成链路。

实现「检索」时，适配器把请求委托给目标本地知识库的 NativeKbBackend，
因为内容已落到本地；真正与外部交互的是 sync_to_native()。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from django.utils import timezone

from ..backend import KbBackend
from ..models import KnowledgeHubConfig, NativeKb, NativeKbDocument

logger = logging.getLogger(__name__)


class ExternalKbAdapter(KbBackend):
    """外部知识库适配器基类（继承 KbBackend，兼容统一检索接口）。"""

    engine_name = "external"

    def __init__(self, kb_source):
        self.kb_source = kb_source

    # ---------------- 外部源特有：同步接口（子类必须实现） ----------------
    def authenticate(self, token: Optional[str] = None) -> str:
        raise NotImplementedError

    def list_spaces(self, token: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def list_nodes(self, token: str, space_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def fetch_node_content(self, token: str, node: Dict[str, Any]) -> str:
        raise NotImplementedError

    # ---------------- 通用同步流程（拉取存储策略） ----------------
    def _resolve_target_kb(self, target_kb: Optional[NativeKb]) -> NativeKb:
        """确定同步目标本地知识库；为空时按 source 自动创建。"""
        source = self.kb_source
        if target_kb is None:
            target_kb = source.target_kb
        if target_kb is None:
            target_kb = NativeKb.objects.create(
                name=f"{source.name}（外部同步）",
                is_global=False,
                created_by=source.created_by,
            )
            source.target_kb = target_kb
        return target_kb

    def _make_doc(self, target_kb, node, content, *, source_type="url",
                  file_bytes=None, filename=None) -> NativeKbDocument:
        """构造一条 NativeKbDocument（不直接落库）。"""
        doc = NativeKbDocument(
            kb=target_kb,
            title=node.get("title") or node.get("name") or node.get("id") or "未命名",
            source_type=source_type,
            content_text=content or "",
            status="pending",
            doc_meta={
                "source": self.kb_source.external_type,
                "source_node_id": node.get("id") or node.get("token"),
                "space_id": node.get("space_id"),
            },
        )
        if file_bytes is not None and filename:
            from django.core.files.base import ContentFile
            import os
            safe_name = os.path.basename(filename) or "feishu_file"
            doc.file.save(safe_name, ContentFile(file_bytes), save=False)
        return doc

    def _finalize_sync(self, target_kb, docs, source, total, synced, failed) -> Dict[str, Any]:
        """幂等落库 + 更新 source 同步状态。docs 为已构造好的 NativeKbDocument 列表。"""
        # 删除该外部源上次同步写入的全部文档（url/file 等），保证幂等
        NativeKbDocument.objects.filter(
            kb=target_kb, doc_meta__source=self.kb_source.external_type
        ).delete()
        NativeKbDocument.objects.bulk_create(docs)
        source.doc_count = synced
        source.sync_status = "success" if failed == 0 else "failed"
        source.last_sync_at = timezone.now()
        source.last_sync_error = "" if failed == 0 else f"{failed}/{total} 篇同步失败"
        source.save(update_fields=[
            "doc_count", "sync_status", "last_sync_at",
            "last_sync_error", "target_kb", "updated_at",
        ])
        return {
            "total": total,
            "synced": synced,
            "failed": failed,
            "target_kb_id": target_kb.id,
        }

    def sync_to_native(self, target_kb: Optional[NativeKb] = None) -> Dict[str, Any]:
        """把外部知识库全部内容拉取并写入本地 NativeKbDocument。

        默认按「知识空间 → 节点」遍历（适配飞书知识库等）。
        返回统计 {total, synced, failed, target_kb_id}。
        """
        source = self.kb_source
        target_kb = self._resolve_target_kb(target_kb)

        source.sync_status = "syncing"
        source.save(update_fields=["sync_status", "updated_at"])

        total = synced = failed = 0
        docs: List[NativeKbDocument] = []
        try:
            token = self.authenticate()
            for space in self.list_spaces(token):
                for node in self.list_nodes(token, space["id"]):
                    total += 1
                    try:
                        content = self.fetch_node_content(token, node)
                        docs.append(self._make_doc(
                            target_kb, node, content, source_type="url",
                            filename=node.get("title") or node.get("name"),
                        ))
                        synced += 1
                    except Exception as exc:  # 单节点失败不影响整体
                        failed += 1
                        logger.warning("同步节点失败 node=%s: %s", node.get("id"), exc)
            return self._finalize_sync(target_kb, docs, source, total, synced, failed)
        except Exception as exc:
            logger.exception("外部知识源同步失败 source=%s: %s", source.pk, exc)
            source.sync_status = "failed"
            source.last_sync_error = self._beautify_error(str(exc))[:1000]
            source.save(update_fields=["sync_status", "last_sync_error", "updated_at"])
            return {
                "total": total, "synced": synced, "failed": failed,
                "target_kb_id": target_kb.id,
            }

    # ---------------- 错误文案美化（带操作指引） ----------------
    @staticmethod
    def _beautify_error(msg: str) -> str:
        """把飞书/Notion 等外部源的「权限不足」「scope missing」「Access denied」类报错
        转成带操作指引的中文，让用户知道去哪配置。
        """
        import re

        # 飞书类：Access denied + scope 列表
        m = re.search(r"scopes is required:\s*\[([^\]]+)\]", msg, re.IGNORECASE)
        if m and ("access denied" in msg.lower() or "权限" in msg):
            scopes = [s.strip().strip("'\"") for s in m.group(1).split(",")]
            scope_text = "、".join(scopes)
            return (
                f"飞书应用缺少权限 scope：{scope_text}\n\n"
                f"修复步骤：\n"
                f"1. 登录 飞书开放平台（https://open.feishu.cn/app），进入「你的应用 → 权限管理」\n"
                f"2. 开通缺失的权限（{scope_text}）\n"
                f"3. 进入 飞书管理后台 → 应用审核，让企业管理员审批通过\n"
                f"4. 回到本页重新点「同步」\n\n"
                f"【原始错误】{msg}"
            )

        # 飞书鉴权失败（app_id/app_secret 错）
        if "app_id" in msg and ("invalid" in msg.lower() or "10014" in msg):
            return (
                f"飞书 App ID 或 App Secret 无效（code=10014）。\n\n"
                f"修复步骤：\n"
                f"1. 打开 飞书开放平台 → 你的应用 → 凭证与基础信息\n"
                f"2. 核对 App ID / App Secret 是否与本数据源一致（注意复制时不要带空格）\n"
                f"3. 修改后回到本页重新点「同步」\n\n"
                f"【原始错误】{msg}"
            )

        # Notion 类
        if "notion" in msg.lower() and ("unauthorized" in msg.lower() or "401" in msg):
            return (
                f"Notion Integration Token 无效或已被撤销。\n\n"
                f"修复步骤：\n"
                f"1. 打开 https://www.notion.so/profile/integrations 重新创建 Integration\n"
                f"2. 把新的 Token 粘贴到本数据源「凭证」字段\n"
                f"3. 在 Notion 目标页面右上角「···」→「连接」中重新授权给该 Integration\n\n"
                f"【原始错误】{msg}"
            )

        # 其它原样
        return msg

    # ---------------- 兼容 KbBackend 统一检索接口（委托本地） ----------------
    def _local_backend(self):
        return NativeKbBackend(KnowledgeHubConfig.get_active())

    def retrieve_for_chat(self, query, *, top_k=5, document_ids=None, scope_mode="full", kb_id=None):
        if not self.kb_source.target_kb_id:
            return [], {"engine": self.engine_name, "warning": "尚未同步，无法检索"}
        return self._local_backend().retrieve_for_chat(
            query, top_k=top_k, document_ids=document_ids, scope_mode=scope_mode,
            kb_id=str(self.kb_source.target_kb_id),
        )

    def build_generation_context(self, *, title, requirement_text, kb_name="", document_ids=None,
                                 function_ids=None, reference_mode="hybrid", top_k=5, kb_id=None):
        if not self.kb_source.target_kb_id:
            return "", {"engine": self.engine_name, "warning": "尚未同步，无法构建上下文"}
        return self._local_backend().build_generation_context(
            title=title, requirement_text=requirement_text, kb_name=kb_name,
            document_ids=document_ids, function_ids=function_ids,
            reference_mode=reference_mode, top_k=top_k,
            kb_id=str(self.kb_source.target_kb_id),
        )

    def list_knowledge_bases(self, *, keyword=""):
        if not self.kb_source.target_kb_id:
            return []
        return self._local_backend().list_knowledge_bases(keyword=keyword)

    def list_documents(self, kb_id, *, keyword=""):
        if not self.kb_source.target_kb_id:
            return []
        return self._local_backend().list_documents(str(self.kb_source.target_kb_id), keyword=keyword)
