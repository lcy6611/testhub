"""MCP (Model Context Protocol) 轻量端点 —— 让外部 AI Agent 查询 TestHub 知识图谱。

实现 Streamable HTTP 风格的 JSON-RPC：外部 MCP client（Claude Desktop / Cursor /
CodeBuddy 等）可 POST JSON-RPC 请求到 /api/kg/mcp/，调用以下工具：
    - query_subgraph(entity, depth, max_nodes): 以实体为根取子图
    - get_neighbors(entity, direction):         取实体的邻居
    - list_projects():                          列出测试项目
无需向量数据库，直接复用现有图谱查询能力。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from .models import kg_enabled
from .query import get_entity_neighbors, get_subgraph

logger = logging.getLogger(__name__)


def _tools() -> list:
    return [
        {
            "name": "query_subgraph",
            "description": "以某个实体（entity_key）为根，取其 N 跳子图（节点与关系）。用于快速了解一个项目/需求/用例的关联网络。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "实体键，如 project:1 / tc:12 / kb_func:3"},
                    "depth": {"type": "integer", "default": 2, "description": "遍历深度"},
                    "max_nodes": {"type": "integer", "default": 100, "description": "最大节点数"},
                },
                "required": ["entity"],
            },
        },
        {
            "name": "get_neighbors",
            "description": "获取实体的直接邻居（出边/入边/双向）。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "实体键"},
                    "direction": {"type": "string", "enum": ["out", "in", "both"], "default": "both"},
                },
                "required": ["entity"],
            },
        },
        {
            "name": "list_projects",
            "description": "列出 TestHub 中的测试项目（id + 名称），用于确定 project_id。",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def _call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    arguments = arguments or {}
    if name == "query_subgraph":
        entity = (arguments.get("entity") or "").strip()
        if not entity:
            return {"isError": True, "content": [{"type": "text", "text": "缺少 entity 参数"}]}
        depth = int(arguments.get("depth", 2) or 2)
        max_nodes = int(arguments.get("max_nodes", 100) or 100)
        data = get_subgraph(entity, depth=depth, max_nodes=max_nodes)
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
    if name == "get_neighbors":
        entity = (arguments.get("entity") or "").strip()
        if not entity:
            return {"isError": True, "content": [{"type": "text", "text": "缺少 entity 参数"}]}
        direction = (arguments.get("direction") or "both").strip()
        data = get_entity_neighbors(entity, direction=direction)
        return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False)}]}
    if name == "list_projects":
        try:
            from apps.projects.models import Project

            rows = Project.objects.values("id", "name")[:200]
            text = json.dumps([{"id": r["id"], "name": r["name"]} for r in rows], ensure_ascii=False)
        except Exception as exc:
            return {"isError": True, "content": [{"type": "text", "text": f"查询项目失败: {exc}"}]}
        return {"content": [{"type": "text", "text": text}]}
    return {"isError": True, "content": [{"type": "text", "text": f"未知工具: {name}"}]}


def handle_mcp_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """处理 JSON-RPC 请求，返回 JSON-RPC 响应（不含 id/jsonrpc，由 view 补全）。"""
    if not isinstance(payload, dict):
        return {"error": {"code": -32600, "message": "Invalid Request"}}
    if not kg_enabled():
        return {"error": {"code": -32000, "message": "知识图谱已禁用"}}

    method = payload.get("method")
    params = payload.get("params") or {}
    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "testhub-knowledge-graph", "version": "1.0.0"},
        }
    if method == "notifications/initialized":
        return {}
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": _tools()}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        return _call_tool(name, arguments)
    return {"error": {"code": -32601, "message": f"Method not found: {method}"}}
