"""层次5：图聚类 —— 用 Louvain/Leiden 社区发现给图谱分社区。

对齐 Graphify 的 Leiden 社区发现思路：按边密度把图谱划分为强连通的社区，
community_id 写回实体 properties，前端据此配色，自动识别核心模块 / 孤岛需求。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import networkx as nx

from .models import KgEdge, KgEntity, kg_enabled

logger = logging.getLogger(__name__)


def build_networkx_graph(project_id: Optional[int] = None) -> nx.Graph:
    """从 kg_entity / kg_edge 构建 NetworkX 图。"""
    G = nx.Graph()
    ent_qs = KgEntity.objects.all()
    if project_id is not None:
        ent_qs = ent_qs.filter(project_id=project_id)
    ent_map: Dict[int, str] = {}
    for ent in ent_qs.iterator():
        G.add_node(ent.entity_key, entity_type=ent.entity_type, label=ent.label or ent.entity_key)
        ent_map[ent.pk] = ent.entity_key
    edge_qs = KgEdge.objects.all()
    if project_id is not None:
        edge_qs = edge_qs.filter(project_id=project_id)
    for edge in edge_qs.iterator():
        s = ent_map.get(edge.src_id)
        d = ent_map.get(edge.dst_id)
        if s and d:
            G.add_edge(s, d, relation_type=edge.relation_type)
    return G


def cluster_graph(project_id: Optional[int] = None, resolution: float = 1.0) -> Dict[str, Any]:
    """对图谱做社区发现，community_id 写回实体 properties。返回统计。"""
    if not kg_enabled():
        return {"detail": "知识图谱已禁用"}
    G = build_networkx_graph(project_id)
    if G.number_of_nodes() == 0:
        return {"detail": "暂无图谱数据", "communities": []}
    try:
        communities = nx.community.louvain_communities(G, resolution=resolution)
        algorithm = "louvain"
    except Exception as exc:
        logger.warning("Louvain 失败，退回 greedy_modularity: %s", exc)
        communities = list(nx.community.greedy_modularity_communities(G))
        algorithm = "greedy_modularity"

    result_communities: List[Dict[str, Any]] = []
    for idx, comm in enumerate(communities):
        members = list(comm)
        type_dist: Dict[str, int] = {}
        labels_sample: List[str] = []
        for key in members[:50]:
            data = G.nodes[key]
            et = data.get("entity_type", "")
            type_dist[et] = type_dist.get(et, 0) + 1
            if len(labels_sample) < 10:
                labels_sample.append(data.get("label", key))
        result_communities.append(
            {
                "community_id": idx,
                "size": len(members),
                "type_distribution": type_dist,
                "sample_labels": labels_sample,
            }
        )

    # community_id 写回实体 properties
    for idx, comm in enumerate(communities):
        members = list(comm)
        ents = list(KgEntity.objects.filter(entity_key__in=members))
        for ent in ents:
            props = ent.properties or {}
            props["community_id"] = idx
            ent.properties = props
        if ents:
            KgEntity.objects.bulk_update(ents, ["properties"])

    return {
        "project_id": project_id,
        "algorithm": algorithm,
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "community_count": len(communities),
        "communities": result_communities,
    }
