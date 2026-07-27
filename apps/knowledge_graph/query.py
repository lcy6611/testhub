"""图谱查询：子图、邻域、影响分析。"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db.models import Q

from .constants import REL_PROVENANCE, REL_USED_REFERENCE
from .models import KgEdge, KgEntity, kg_enabled
from .registry import entity_key_project, get_entity


def _entity_to_dict(entity: KgEntity) -> Dict[str, Any]:
    return {
        "entity_key": entity.entity_key,
        "entity_type": entity.entity_type,
        "label": entity.label,
        "project_id": entity.project_id,
        "ref_app": entity.ref_app,
        "ref_id": entity.ref_id,
        "properties": entity.properties or {},
    }


def _edge_to_dict(edge: KgEdge) -> Dict[str, Any]:
    return {
        "src": edge.src.entity_key,
        "dst": edge.dst.entity_key,
        "relation_type": edge.relation_type,
        "source": edge.source,
        "confidence": edge.confidence,
        "confidence_level": edge.confidence_level,
        "meta": edge.meta or {},
    }


def get_subgraph(
    entity_key: str,
    *,
    depth: int = 2,
    max_nodes: int = 200,
) -> Dict[str, Any]:
    if not kg_enabled():
        return {"root": None, "nodes": [], "edges": []}

    root = get_entity(entity_key)
    if not root:
        return {"root": None, "nodes": [], "edges": [], "detail": "实体不存在"}

    depth = max(1, min(int(depth or 2), 5))
    max_nodes = max(10, min(int(max_nodes or 200), 500))

    visited: Set[int] = {root.pk}
    node_map: Dict[int, KgEntity] = {root.pk: root}
    edge_list: List[KgEdge] = []
    edge_ids: Set[int] = set()
    queue: deque[Tuple[int, int]] = deque([(root.pk, 0)])

    while queue and len(visited) < max_nodes:
        pk, d = queue.popleft()
        if d >= depth:
            continue
        qs_out = KgEdge.objects.filter(src_id=pk).select_related("src", "dst")
        qs_in = KgEdge.objects.filter(dst_id=pk).select_related("src", "dst")
        for edge in list(qs_out) + list(qs_in):
            if edge.pk not in edge_ids:
                edge_ids.add(edge.pk)
                edge_list.append(edge)
            for ent in (edge.src, edge.dst):
                if ent.pk not in visited and len(visited) < max_nodes:
                    visited.add(ent.pk)
                    node_map[ent.pk] = ent
                    queue.append((ent.pk, d + 1))

    return {
        "root": _entity_to_dict(root),
        "nodes": [_entity_to_dict(node_map[pk]) for pk in node_map],
        "edges": [_edge_to_dict(e) for e in edge_list],
    }


def get_project_graph(
    project_id: int,
    *,
    dataset_id: str = "",
    depth: int = 2,
    max_nodes: int = 300,
) -> Dict[str, Any]:
    """项目级子图：以 project_id 全集为基线 + BFS 边，保证同步的实体一定显示。
    
    Args:
        project_id: 项目ID
        dataset_id: 可选，按知识库ID过滤（为空则查全部）
    """
    empty: Dict[str, Any] = {
        "root": None,
        "nodes": [],
        "edges": [],
        "project_id": project_id,
        "dataset_id": dataset_id,
    }
    if not kg_enabled():
        empty["detail"] = "知识图谱已禁用"
        return empty

    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        empty["detail"] = "无效的项目 ID"
        return empty

    depth = max(1, min(int(depth or 2), 4))
    max_nodes = max(10, min(int(max_nodes or 300), 500))
    dataset_id = (dataset_id or "").strip()

    # ── 基线：按 project_id 拉全部实体（保证同步的需求/用例/生成任务等一定显示） ──
    base_qs = KgEntity.objects.filter(project_id=project_id)
    if dataset_id:
        base_qs = base_qs.filter(dataset_id=dataset_id)
    base_entities = list(base_qs.order_by("-updated_at")[:max_nodes])

    # 同时把 Project 根实体也纳入（即使没边连入）
    root_key = entity_key_project(project_id)
    root = get_entity(root_key)
    if root and (not dataset_id or root.dataset_id == dataset_id):
        root_in_base = any(e.pk == root.pk for e in base_entities)
        if not root_in_base and len(base_entities) < max_nodes:
            base_entities.insert(0, root)

    # Project 根作为 BFS 起点（若有边可达的额外节点）
    bfs_extra_nodes: Dict[str, KgEntity] = {}
    bfs_extra_edges: List[KgEdge] = []
    if root:
        bfs_data = get_subgraph(root_key, depth=depth, max_nodes=max_nodes)
        for n in bfs_data.get("nodes") or []:
            if n.get("entity_key") == root_key:
                continue
            bfs_extra_nodes[n["entity_key"]] = n
        for e in bfs_data.get("edges") or []:
            bfs_extra_edges.append(e)

    # 合并基线 + BFS 额外节点
    node_map: Dict[str, KgEntity] = {e.entity_key: e for e in base_entities}
    for key, n in bfs_extra_nodes.items():
        if key not in node_map and len(node_map) < max_nodes:
            # 重建实体对象（用 n 的 entity_key 查库，避免 dict 混入）
            ent = get_entity(key)
            if ent:
                node_map[key] = ent

    # 合并边：端点都在 node_map 里，或边本身属于该项目
    entity_pks = {e.pk for e in node_map.values()}
    edge_qs = KgEdge.objects.filter(
        Q(src_id__in=entity_pks) | Q(dst_id__in=entity_pks) | Q(project_id=project_id)
    )
    if dataset_id:
        edge_qs = edge_qs.filter(dataset_id=dataset_id)
    edge_qs = edge_qs.select_related("src", "dst").order_by("-created_at")[: max_nodes * 3]

    seen_edge_ids: Set[int] = set()
    edge_list: List[KgEdge] = []
    for edge in edge_qs:
        if edge.pk in seen_edge_ids:
            continue
        seen_edge_ids.add(edge.pk)
        edge_list.append(edge)
        for ent in (edge.src, edge.dst):
            if ent.entity_key not in node_map and len(node_map) < max_nodes:
                node_map[ent.entity_key] = ent

    if not node_map:
        empty["detail"] = "该项目暂无图谱数据"
        return empty

    # root：优先用 Project 根，否则用基线第一个
    display_root = root or (base_entities[0] if base_entities else None)

    return {
        "root": _entity_to_dict(display_root) if display_root else None,
        "nodes": [_entity_to_dict(node_map[key]) for key in node_map],
        "edges": [_edge_to_dict(e) for e in edge_list],
        "project_id": project_id,
        "dataset_id": dataset_id,
        "mode": "aggregated",
        "partial": len(node_map) >= max_nodes,
    }


def get_entity_neighbors(entity_key: str, *, direction: str = "both", dataset_id: str = "") -> Dict[str, Any]:
    """获取实体的邻居节点。
    
    Args:
        entity_key: 实体键
        direction: 方向（out/both/in）
        dataset_id: 可选，按知识库ID过滤边
    """
    entity = get_entity(entity_key)
    if not entity:
        return {"entity": None, "outgoing": [], "incoming": []}

    outgoing = []
    incoming = []
    
    # 构建查询集
    if direction in ("both", "out"):
        qs = KgEdge.objects.filter(src=entity).select_related("dst")
        if dataset_id:
            qs = qs.filter(dataset_id=dataset_id)
        for edge in qs.all()[:100]:
            outgoing.append({**_edge_to_dict(edge), "node": _entity_to_dict(edge.dst)})
    
    if direction in ("both", "in"):
        qs = KgEdge.objects.filter(dst=entity).select_related("src")
        if dataset_id:
            qs = qs.filter(dataset_id=dataset_id)
        for edge in qs.all()[:100]:
            incoming.append({**_edge_to_dict(edge), "node": _entity_to_dict(edge.src)})
    
    return {"entity": _entity_to_dict(entity), "outgoing": outgoing, "incoming": incoming}


def impact_test_cases_for_kb_document(dataset_id: str, document_id: str) -> List[Dict[str, Any]]:
    """某 KB 文档被哪些生成任务引用，并追溯到已采纳用例。"""
    from .registry import entity_key_kb_document

    doc_key = entity_key_kb_document(dataset_id, document_id)
    doc = get_entity(doc_key)
    if not doc:
        return []

    results: List[Dict[str, Any]] = []
    task_edges = KgEdge.objects.filter(dst=doc, relation_type=REL_USED_REFERENCE).select_related("src")
    for te in task_edges[:100]:
        task_node = te.src
        case_edges = KgEdge.objects.filter(
            dst=task_node,
            relation_type=REL_PROVENANCE,
        ).select_related("src")
        cases = [_entity_to_dict(ce.src) for ce in case_edges]
        results.append(
            {
                "generation_task": _entity_to_dict(task_node),
                "test_cases": cases,
            }
        )
    return results


def expand_kb_references_via_graph(
    *,
    dataset_id: str,
    function_ids: Optional[List[int]] = None,
    document_ids: Optional[List[str]] = None,
    max_depth: int = 2,
) -> Dict[str, Any]:
    """混合检索：沿图谱扩展功能模块与 KB 文档（最多 max_depth 跳）。"""
    from .constants import (
        ENTITY_BUSINESS_REQUIREMENT,
        ENTITY_KB_DOCUMENT,
        ENTITY_KB_FUNCTION,
        REL_DEPENDS_ON,
        REL_IMPACTS,
        REL_MAPS_TO,
        REL_REFERENCES,
        REL_RELATED,
    )
    from .registry import entity_key_kb_document, entity_key_kb_function

    def _kb_func_id_from_entity(ent: KgEntity) -> Optional[int]:
        if ent.entity_type != ENTITY_KB_FUNCTION:
            return None
        try:
            return int(ent.ref_id)
        except (TypeError, ValueError):
            return None

    def _func_dataset_matches(ent: KgEntity) -> bool:
        if not dataset_id:
            return True
        props = ent.properties or {}
        func_ds = str(props.get("dify_dataset_id") or "").strip()
        return not func_ds or func_ds == dataset_id

    initial_funcs = {int(x) for x in (function_ids or [])}
    initial_docs = {str(x).strip() for x in (document_ids or []) if str(x).strip()}
    dataset_id = (dataset_id or "").strip()

    base_result = {
        "function_ids": sorted(initial_funcs),
        "document_ids": sorted(initial_docs),
        "document_names": {},
        "graph_summary": "",
        "expanded": False,
        "meta": {
            "added_function_ids": [],
            "added_document_ids": [],
            "added_via_maps_to_function_ids": [],
        },
    }
    if not kg_enabled() or (not initial_funcs and not initial_docs):
        return base_result

    expanded_funcs: Set[int] = set(initial_funcs)
    expanded_docs: Set[str] = set(initial_docs)
    doc_names: Dict[str, str] = {}
    added_funcs: Set[int] = set()
    added_docs: Set[str] = set()
    added_maps_to_funcs: Set[int] = set()
    func_func_rels = {REL_RELATED, REL_DEPENDS_ON, REL_IMPACTS}

    frontier = list(initial_funcs)
    visited_funcs = set(initial_funcs)
    depth = 0
    max_depth = max(1, min(int(max_depth or 2), 3))

    while frontier and depth < max_depth:
        next_frontier: List[int] = []
        for fid in frontier:
            func_ent = get_entity(entity_key_kb_function(fid))
            if not func_ent:
                continue
            for edge in func_ent.outgoing_edges.select_related("dst").all():
                dst = edge.dst
                if edge.relation_type == REL_REFERENCES and dst.entity_type == ENTITY_KB_DOCUMENT:
                    doc_id = str(dst.ref_id or "").strip()
                    if not doc_id:
                        continue
                    props = dst.properties or {}
                    doc_dataset = str(props.get("dataset_id") or dataset_id).strip()
                    if dataset_id and doc_dataset and doc_dataset != dataset_id:
                        continue
                    if doc_id not in expanded_docs:
                        added_docs.add(doc_id)
                    expanded_docs.add(doc_id)
                    doc_names[doc_id] = (dst.label or doc_id)[:500]
                elif edge.relation_type in func_func_rels and dst.entity_type == ENTITY_KB_FUNCTION:
                    related_fid = _kb_func_id_from_entity(dst)
                    if related_fid is None or related_fid in visited_funcs:
                        continue
                    if not _func_dataset_matches(dst):
                        continue
                    visited_funcs.add(related_fid)
                    expanded_funcs.add(related_fid)
                    added_funcs.add(related_fid)
                    next_frontier.append(related_fid)
            # 沿 maps_to：同一业务需求映射的 sibling 功能模块及其参考文档
            for in_edge in func_ent.incoming_edges.filter(relation_type=REL_MAPS_TO).select_related("src")[:50]:
                biz_req = in_edge.src
                if biz_req.entity_type != ENTITY_BUSINESS_REQUIREMENT:
                    continue
                for out_edge in biz_req.outgoing_edges.filter(relation_type=REL_MAPS_TO).select_related("dst")[:50]:
                    dst = out_edge.dst
                    related_fid = _kb_func_id_from_entity(dst)
                    if related_fid is None or related_fid in visited_funcs:
                        continue
                    if not _func_dataset_matches(dst):
                        continue
                    visited_funcs.add(related_fid)
                    expanded_funcs.add(related_fid)
                    added_funcs.add(related_fid)
                    added_maps_to_funcs.add(related_fid)
                    next_frontier.append(related_fid)
        frontier = next_frontier
        depth += 1

    for doc_id in expanded_docs:
        if doc_id in doc_names:
            continue
        if not dataset_id:
            continue
        doc_ent = get_entity(entity_key_kb_document(dataset_id, doc_id))
        if doc_ent and doc_ent.label:
            doc_names[doc_id] = doc_ent.label

    summary_parts: List[str] = []
    if added_maps_to_funcs:
        summary_parts.append(f"需求映射扩展 {len(added_maps_to_funcs)} 个功能模块")
    other_added = added_funcs - added_maps_to_funcs
    if other_added:
        summary_parts.append(f"图谱扩展 {len(other_added)} 个关联功能模块")
    if added_docs:
        summary_parts.append(f"图谱扩展 {len(added_docs)} 份参考文档")

    return {
        "function_ids": sorted(expanded_funcs),
        "document_ids": sorted(expanded_docs),
        "document_names": doc_names,
        "graph_summary": "；".join(summary_parts),
        "expanded": bool(added_funcs or added_docs),
        "meta": {
            "added_function_ids": sorted(added_funcs),
            "added_document_ids": sorted(added_docs),
            "added_via_maps_to_function_ids": sorted(added_maps_to_funcs),
        },
    }


_REL_PROMPT_LABELS = {
    "references": "参考文档",
    "related": "相关功能",
    "depends_on": "依赖",
    "impacts": "影响",
    "used_reference": "引用参考",
    "provenance": "溯源",
    "maps_to": "映射",
    "covers": "覆盖",
    "derived_from": "来源于",
}


def build_graph_relations_prompt_summary(task, *, max_chars: int = 2048) -> str:
    """为生成 prompt 构建结构化图谱关系摘要（默认 ≤2KB）。"""
    if not kg_enabled():
        return ""

    function_ids: List[int] = []
    for raw in getattr(task, "kb_function_ids", None) or []:
        try:
            function_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    document_ids = [str(x).strip() for x in (getattr(task, "kb_document_ids", None) or []) if str(x).strip()]
    meta = getattr(task, "kb_context_meta", None) or {}
    if not isinstance(meta, dict):
        meta = {}
    expansion = meta.get("graph_expansion") or {}
    if not isinstance(expansion, dict):
        expansion = {}

    has_content = bool(
        function_ids
        or document_ids
        or expansion.get("added_function_ids")
        or expansion.get("added_document_ids")
        or meta.get("graph_summary")
        or meta.get("documents")
    )
    if not has_content:
        return ""

    from apps.requirement_analysis.kb_models import KbFunction

    from .registry import entity_key_kb_function

    func_name_map: Dict[int, str] = {}
    added_func_ids: List[int] = []
    for raw in expansion.get("added_function_ids") or []:
        try:
            added_func_ids.append(int(raw))
        except (TypeError, ValueError):
            continue
    all_func_ids = list(dict.fromkeys(function_ids + added_func_ids))
    if all_func_ids:
        for func in KbFunction.objects.filter(id__in=all_func_ids[:30]):
            func_name_map[func.id] = func.name

    lines: List[str] = [
        "【知识图谱关系摘要（结构化索引，说明功能/文档间关系；具体条文见下方知识库参考）】"
    ]

    for fid in function_ids[:12]:
        name = func_name_map.get(fid) or f"功能#{fid}"
        lines.append(f"· 已选功能模块：{name}")
        func_ent = get_entity(entity_key_kb_function(fid))
        if not func_ent:
            continue
        shown = 0
        for edge in func_ent.outgoing_edges.select_related("dst").all():
            if shown >= 6:
                break
            rel = _REL_PROMPT_LABELS.get(edge.relation_type, edge.relation_type)
            dst_label = (edge.dst.label or edge.dst.entity_key)[:120]
            lines.append(f"    - {rel} → {dst_label}")
            shown += 1

    doc_name_map: Dict[str, str] = {}
    for key, val in (meta.get("document_names") or {}).items():
        if key and val:
            doc_name_map[str(key)] = str(val)
    for doc in meta.get("documents") or []:
        if isinstance(doc, dict) and doc.get("document_id"):
            did = str(doc["document_id"])
            doc_name_map.setdefault(did, str(doc.get("document_name") or did))

    if document_ids:
        lines.append("· 已选 KB 文档：")
        for doc_id in document_ids[:10]:
            lines.append(f"    - {doc_name_map.get(doc_id) or doc_id}")

    added_funcs = expansion.get("added_function_ids") or []
    added_maps_to = expansion.get("added_via_maps_to_function_ids") or []
    added_docs = expansion.get("added_document_ids") or []
    if added_maps_to or added_funcs or added_docs:
        parts: List[str] = []
        if added_maps_to:
            fn_names = [func_name_map.get(int(i)) or f"功能#{i}" for i in added_maps_to[:6]]
            parts.append(f"需求映射功能 {len(added_maps_to)} 个：{', '.join(fn_names)}")
        rel_added = [i for i in added_funcs if int(i) not in {int(x) for x in added_maps_to}]
        if rel_added:
            fn_names = [func_name_map.get(int(i)) or f"功能#{i}" for i in rel_added[:6]]
            parts.append(f"扩展功能 {len(rel_added)} 个：{', '.join(fn_names)}")
        if added_docs:
            doc_labels = [doc_name_map.get(str(d)) or str(d) for d in added_docs[:6]]
            parts.append(f"扩展文档 {len(added_docs)} 份：{', '.join(doc_labels)}")
        lines.append("· 图谱自动扩展：" + "；".join(parts))

    if meta.get("graph_summary"):
        lines.append(f"· {meta['graph_summary']}")

    text = "\n".join(lines).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 14].rstrip() + "\n…（摘要已截断）"
    return text


def build_graph_relations_prompt_summary_for_selection(
    *,
    function_ids: Optional[List[int]] = None,
    document_ids: Optional[List[str]] = None,
    expansion_meta: Optional[Dict[str, Any]] = None,
    graph_summary: str = "",
    document_names: Optional[Dict[str, str]] = None,
    max_chars: int = 2048,
) -> str:
    """根据功能/文档选择与扩展结果构建 prompt 摘要（无需持久化 Task）。"""

    class _TaskShim:
        kb_function_ids: List[int]
        kb_document_ids: List[str]
        kb_context_meta: Dict[str, Any]

    shim = _TaskShim()
    shim.kb_function_ids = [int(x) for x in (function_ids or [])]
    shim.kb_document_ids = [str(x).strip() for x in (document_ids or []) if str(x).strip()]
    shim.kb_context_meta = {
        "graph_expansion": expansion_meta or {},
        "graph_summary": graph_summary or "",
        "document_names": document_names or {},
    }
    return build_graph_relations_prompt_summary(shim, max_chars=max_chars)
