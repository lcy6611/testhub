"""性能基线比对：本次执行 vs 基线，判断是否劣化。

指标方向与容忍度沿用开源版语义：
- 响应时间类「越小越好」：涨幅 > ``rt_degrade_pct`` 视为劣化
- 吞吐量类「越大越好」：跌幅 > ``tps_degrade_pct`` 视为劣化

字段名对齐本模块 ``PerformanceSummary``（avg_response_time / p95 / p99 / throughput）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

DEFAULT_TOLERANCE = {"rt_degrade_pct": 20, "tps_degrade_pct": 15}

#: (字段名, 展示名) —— 越小越好
LOWER_BETTER = (
    ("avg_response_time", "平均响应时间"),
    ("p95", "P95 响应时间"),
    ("p99", "P99 响应时间"),
)

#: (字段名, 展示名) —— 越大越好
HIGHER_BETTER = (
    ("throughput", "TPS"),
)

#: 基线快照 / 本次执行 参与比对的字段
METRIC_FIELDS = tuple(k for k, _ in LOWER_BETTER) + tuple(k for k, _ in HIGHER_BETTER)


def summary_to_metrics(summary) -> Dict[str, float]:
    """把 ``PerformanceSummary`` 实例（或 dict）转成基线指标快照。"""
    if summary is None:
        return {}
    getter = summary.get if isinstance(summary, dict) else (lambda k, d=None: getattr(summary, k, d))
    return {key: float(getter(key, 0) or 0) for key in METRIC_FIELDS}


def merge_tolerance(tolerance: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """容忍度与默认值合并，非法值回退默认。"""
    merged = dict(DEFAULT_TOLERANCE)
    for key in DEFAULT_TOLERANCE:
        raw = (tolerance or {}).get(key)
        if raw in (None, ""):
            continue
        try:
            merged[key] = float(raw)
        except (TypeError, ValueError):
            continue
    return merged


def compare(baseline_metrics: Optional[Dict[str, Any]],
            current_metrics: Optional[Dict[str, Any]],
            tolerance: Optional[Dict[str, Any]]) -> Tuple[bool, List[Dict[str, Any]]]:
    """逐指标比对，返回 ``(degraded, items)``。

    ``items`` 每项：``{metric, label, baseline, current, change_pct, direction, tolerance_pct, degraded}``
    """
    tol = merge_tolerance(tolerance)
    base = baseline_metrics or {}
    cur = current_metrics or {}
    items: List[Dict[str, Any]] = []

    def _num(value):
        return float(value) if isinstance(value, (int, float)) else None

    for key, label in LOWER_BETTER:
        b, c = _num(base.get(key)), _num(cur.get(key))
        if not b or c is None:
            continue
        change = round((c - b) / b * 100, 2)
        items.append({
            "metric": key, "label": label, "baseline": b, "current": c,
            "change_pct": change, "direction": "lower_better",
            "tolerance_pct": tol["rt_degrade_pct"],
            "degraded": change > tol["rt_degrade_pct"],
        })

    for key, label in HIGHER_BETTER:
        b, c = _num(base.get(key)), _num(cur.get(key))
        if not b or c is None:
            continue
        change = round((c - b) / b * 100, 2)
        items.append({
            "metric": key, "label": label, "baseline": b, "current": c,
            "change_pct": change, "direction": "higher_better",
            "tolerance_pct": tol["tps_degrade_pct"],
            "degraded": change < -tol["tps_degrade_pct"],
        })

    return any(i["degraded"] for i in items), items
