"""知识图谱导出（Neo4j 等外部图数据库导入预备格式）。"""

from __future__ import annotations

import networkx as nx
from typing import Any, Dict, List, Optional, Set

from django.db.models import Q

from .models import KgEdge, KgEntity, kg_enabled
from .query import _edge_to_dict, _entity_to_dict


def _neo4j_relationship_type(relation_type: str) -> str:
    return (relation_type or "RELATED").strip().upper().replace("-", "_")


def export_kg_graph(
    *,
    project_id: Optional[int] = None,
    max_nodes: int = 5000,
    max_edges: int = 10000,
) -> Dict[str, Any]:
    """导出 nodes + relationships JSON（testhub_kg_export_v1）。"""
    empty: Dict[str, Any] = {
        "format": "testhub_kg_export_v1",
        "project_id": project_id,
        "node_count": 0,
        "relationship_count": 0,
        "nodes": [],
        "relationships": [],
        "neo4j_hint": "节点以 entity_key 为 id；关系 type 为大写 REL_*，可用 neo4j-admin import 或 APOC 批量 MERGE",
    }
    if not kg_enabled():
        empty["detail"] = "知识图谱已禁用"
        return empty

    max_nodes = max(10, min(int(max_nodes or 5000), 10000))
    max_edges = max(10, min(int(max_edges or 10000), 20000))

    qs = KgEntity.objects.all().order_by("-updated_at")
    if project_id is not None:
        try:
            project_id = int(project_id)
            qs = qs.filter(project_id=project_id)
        except (TypeError, ValueError):
            empty["detail"] = "无效的项目 ID"
            return empty
    else:
        project_id = None

    entities = list(qs[:max_nodes])
    if not entities:
        empty["detail"] = "暂无图谱数据可导出"
        return empty

    entity_pks: Set[int] = {e.pk for e in entities}
    node_map: Dict[str, KgEntity] = {e.entity_key: e for e in entities}

    edge_qs = KgEdge.objects.filter(Q(src_id__in=entity_pks) | Q(dst_id__in=entity_pks)).select_related(
        "src", "dst"
    )
    edges = list(edge_qs.order_by("-created_at")[:max_edges])

    for edge in edges:
        for ent in (edge.src, edge.dst):
            if ent.entity_key not in node_map and len(node_map) < max_nodes:
                node_map[ent.entity_key] = ent
                entity_pks.add(ent.pk)

    nodes: List[Dict[str, Any]] = []
    for ent in node_map.values():
        data = _entity_to_dict(ent)
        nodes.append(
            {
                "id": data["entity_key"],
                "labels": [data["entity_type"]],
                "properties": {
                    "entity_key": data["entity_key"],
                    "entity_type": data["entity_type"],
                    "label": data["label"],
                    "project_id": data["project_id"],
                    "ref_app": data["ref_app"],
                    "ref_id": data["ref_id"],
                    **(data.get("properties") or {}),
                },
            }
        )

    relationships: List[Dict[str, Any]] = []
    for edge in edges:
        if edge.src.entity_key not in node_map or edge.dst.entity_key not in node_map:
            continue
        rel = _edge_to_dict(edge)
        relationships.append(
            {
                "id": f"kg_edge_{edge.pk}",
                "type": _neo4j_relationship_type(edge.relation_type),
                "start": rel["src"],
                "end": rel["dst"],
                "properties": {
                    "relation_type": edge.relation_type,
                    "source": edge.source,
                    "project_id": edge.project_id,
                    "confidence": edge.confidence,
                    "meta": edge.meta or {},
                },
            }
        )

    return {
        "format": "testhub_kg_export_v1",
        "project_id": project_id,
        "node_count": len(nodes),
        "relationship_count": len(relationships),
        "partial": len(entities) >= max_nodes or len(edges) >= max_edges,
        "nodes": nodes,
        "relationships": relationships,
        "neo4j_hint": empty["neo4j_hint"],
    }


# ---------------------------------------------------------------------------
# 导出增强：Mermaid / SVG / HTML（对齐 Graphify 的多格式导出）
# ---------------------------------------------------------------------------

_ENTITY_COLOR = {
    "Project": "#409EFF",
    "TestCase": "#67C23A",
    "KbFunction": "#E6A23C",
    "BusinessRequirement": "#F56C6C",
    "KbDocument": "#9B59B6",
    "CodeClass": "#606266",
    "CodeFunction": "#606266",
    "CodeFile": "#303133",
    "CodeModule": "#909399",
}


def export_kg_mermaid(project_id: Optional[int] = None, max_nodes: int = 500, max_edges: int = 1000) -> str:
    """导出 Mermaid graph TD 文本，供前端 mermaid.js 渲染。"""
    data = export_kg_graph(project_id=project_id, max_nodes=max_nodes, max_edges=max_edges)
    nodes = data.get("nodes", [])
    edges = data.get("relationships", [])
    id_map: Dict[str, str] = {}
    lines = ["graph TD"]
    for i, n in enumerate(nodes):
        nid = f"n{i}"
        id_map[n["id"]] = nid
        label = (n.get("properties", {}).get("label") or n["id"]).replace('"', "'")[:40]
        etype = (n.get("labels") or ["Node"])[0]
        lines.append(f'    {nid}["{label}<br/>{etype}"]')
    for e in edges:
        s = id_map.get(e["start"])
        d = id_map.get(e["end"])
        if s and d:
            rel = (e.get("type") or "REL").lower()
            lines.append(f"    {s} -->|{rel}| {d}")
    return "\n".join(lines)


def export_kg_svg(
    project_id: Optional[int] = None,
    max_nodes: int = 300,
    max_edges: int = 800,
    width: int = 1000,
    height: int = 750,
) -> str:
    """导出简单力导向 SVG（内置 NetworkX spring_layout，无需额外依赖）。"""
    data = export_kg_graph(project_id=project_id, max_nodes=max_nodes, max_edges=max_edges)
    nodes = data.get("nodes", [])
    edges = data.get("relationships", [])
    if not nodes:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100"><text x="10" y="50">暂无图谱数据</text></svg>'
    G = nx.Graph()
    id_map: Dict[str, int] = {}
    for i, n in enumerate(nodes):
        id_map[n["id"]] = i
        G.add_node(i)
    for e in edges:
        s = id_map.get(e["start"])
        d = id_map.get(e["end"])
        if s is not None and d is not None:
            G.add_edge(s, d)
    try:
        pos = nx.spring_layout(G, seed=42)
    except Exception:
        pos = nx.circular_layout(G)

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    def sx(x: float) -> float:
        return 40 + (x - minx) / (maxx - minx + 1e-6) * (width - 80)

    def sy(y: float) -> float:
        return 40 + (y - miny) / (maxy - miny + 1e-6) * (height - 80)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'font-family="sans-serif" font-size="10">'
    ]
    for e in edges:
        s = id_map.get(e["start"])
        d = id_map.get(e["end"])
        if s is None or d is None:
            continue
        x1, y1 = sx(pos[s][0]), sy(pos[s][1])
        x2, y2 = sx(pos[d][0]), sy(pos[d][1])
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#bbb" stroke-width="1"/>'
        )
    for i, n in enumerate(nodes):
        x, y = sx(pos[i][0]), sy(pos[i][1])
        label = (n.get("properties", {}).get("label") or n["id"])[:18]
        etype = (n.get("labels") or ["Node"])[0]
        color = _ENTITY_COLOR.get(etype, "#909399")
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="14" fill="{color}" opacity="0.85"/>')
        parts.append(f'<text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" fill="#fff">{label[:6]}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def export_kg_html(project_id: Optional[int] = None, max_nodes: int = 500, max_edges: int = 1000) -> str:
    """导出自包含 HTML（内嵌 Mermaid，浏览器直接打开即可可视化）。"""
    mermaid = export_kg_mermaid(project_id, max_nodes, max_edges)
    data = export_kg_graph(project_id=project_id, max_nodes=max_nodes, max_edges=max_edges)
    summary = f'节点 {data.get("node_count", 0)} / 关系 {data.get("relationship_count", 0)}'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>TestHub 知识图谱</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
<style>body{{font-family:sans-serif;padding:20px}} .mermaid{{background:#fff}}</style>
</head>
<body>
<h2>🕸️ TestHub 知识图谱</h2>
<p>{summary}</p>
<div class="mermaid">
{mermaid}
</div>
<script>mermaid.initialize({{startOnLoad:true}});</script>
</body>
</html>"""
