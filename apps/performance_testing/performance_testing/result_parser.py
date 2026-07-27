# -*- coding: utf-8 -*-
"""
JTL 结果解析：CSV JTL → summary + metrics（按请求名分组 + 10秒时间线 + Top20错误）。
"""

from __future__ import annotations

import csv
import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return round(sorted_vals[f], 2)
    return round(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f), 2)


def parse_jtl(jtl_path: str) -> Dict[str, Any]:
    """解析 JTL 文件。返回 {summary, metrics}。"""
    if not jtl_path or not os.path.exists(jtl_path):
        return {"summary": {}, "metrics": [], "error": "JTL 文件不存在"}

    try:
        with open(jtl_path, "r", encoding="utf-8", errors="ignore") as f:
            sample_line = f.readline()
            is_csv = "," in sample_line and "<?xml" not in sample_line
            f.seek(0)
            if is_csv:
                return _parse_csv_jtl(f)
            else:
                return _parse_xml_jtl(f)
    except Exception as exc:
        logger.exception("JTL 解析失败: %s", exc)
        return {"summary": {}, "metrics": [], "error": str(exc)}


def _parse_csv_jtl(f) -> Dict[str, Any]:
    reader = csv.DictReader(f)
    # 标准列
    by_label: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_rows: List[Dict[str, Any]] = []

    for row in reader:
        label = (row.get("label") or row.get("Label") or "unknown").strip()
        try:
            elapsed = float(row.get("elapsed") or 0)
            ts = int(row.get("timeStamp") or 0)
            success = (row.get("success") or "true").lower() == "true"
            code = (row.get("responseCode") or "").strip()
            bytes_recv = int(row.get("bytes") or row.get("Bytes") or 0)
            bytes_sent = int(row.get("sentBytes") or 0)
        except (ValueError, TypeError):
            continue
        rec = {
            "label": label, "elapsed": elapsed, "ts": ts, "success": success,
            "code": code, "bytes": bytes_recv, "sentBytes": bytes_sent,
        }
        by_label[label].append(rec)
        all_rows.append(rec)

    return _aggregate(by_label, all_rows)


def _parse_xml_jtl(f) -> Dict[str, Any]:
    from xml.etree import ElementTree as ET
    try:
        tree = ET.parse(f)
    except Exception:
        return {"summary": {}, "metrics": [], "error": "XML JTL 解析失败"}
    root = tree.getroot()
    by_label: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_rows: List[Dict[str, Any]] = []
    for sample in root.iter():
        if sample.tag not in ("sample", "httpSample"):
            continue
        label = (sample.get("lb") or "unknown").strip()
        try:
            elapsed = float(sample.get("t") or 0)
            ts = int(sample.get("ts") or 0)
            success = (sample.get("s") or "true").lower() == "true"
            code = (sample.get("rc") or "").strip()
            bytes_recv = int(sample.get("by") or 0)
            bytes_sent = int(sample.get("sby") or 0)
        except (ValueError, TypeError):
            continue
        rec = {
            "label": label, "elapsed": elapsed, "ts": ts, "success": success,
            "code": code, "bytes": bytes_recv, "sentBytes": bytes_sent,
        }
        by_label[label].append(rec)
        all_rows.append(rec)
    return _aggregate(by_label, all_rows)


def _aggregate(by_label: Dict[str, List[Dict[str, Any]]], all_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    metrics: List[Dict[str, Any]] = []
    for label, rows in by_label.items():
        metrics.append(_metric_for_label(label, rows))

    # summary：全量聚合
    summary = _metric_for_label("TOTAL", all_rows, is_summary=True)
    summary["total_samples"] = summary.pop("sample_count", 0)
    summary["data_received"] = summary.pop("bytes", 0)
    summary["data_sent"] = summary.pop("sent_bytes", 0)
    return {"summary": summary, "metrics": metrics}


def _metric_for_label(label: str, rows: List[Dict[str, Any]], *, is_summary: bool = False) -> Dict[str, Any]:
    if not rows:
        return {"sample_label": label}
    elapsed_list = [r["elapsed"] for r in rows]
    elapsed_sorted = sorted(elapsed_list)
    count = len(rows)
    errors = [r for r in rows if not r["success"]]
    error_count = len(errors)
    error_rate = round(error_count / count * 100, 2) if count else 0.0
    total_bytes = sum(r["bytes"] for r in rows)
    total_sent = sum(r["sentBytes"] for r in rows)

    # 吞吐量：样本数 / 总时长(秒)
    if len(rows) >= 2:
        ts_min = min(r["ts"] for r in rows)
        ts_max = max(r["ts"] + r["elapsed"] for r in rows)
        span_s = max((ts_max - ts_min) / 1000.0, 0.001)
        throughput = round(count / span_s, 2)
    else:
        throughput = 0.0

    # 10秒时间线
    timeline = _build_timeline(rows)

    # Top20 错误
    error_codes: Dict[str, int] = defaultdict(int)
    for e in errors:
        key = e["code"] or "unknown"
        error_codes[key] += 1
    top_errors = sorted(
        [{"code": k, "count": v} for k, v in error_codes.items()],
        key=lambda x: x["count"], reverse=True,
    )[:20]

    metric = {
        "sample_label": label,
        "sample_count": count,
        "error_count": error_count,
        "error_rate": error_rate,
        "avg": round(sum(elapsed_list) / count, 2),
        "min": round(elapsed_sorted[0], 2),
        "max": round(elapsed_sorted[-1], 2),
        "p90": _percentile(elapsed_sorted, 0.90),
        "p95": _percentile(elapsed_sorted, 0.95),
        "p99": _percentile(elapsed_sorted, 0.99),
        "throughput": throughput,
        "timeline": timeline,
        "top_errors": top_errors,
    }
    if is_summary:
        metric["bytes"] = total_bytes
        metric["sent_bytes"] = total_sent
    return metric


def _build_timeline(rows: List[Dict[str, Any]], bucket_s: int = 10) -> List[Dict[str, Any]]:
    if not rows:
        return []
    ts_min = min(r["ts"] for r in rows)
    buckets: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        idx = int((r["ts"] - ts_min) // 1000 // bucket_s)
        buckets[idx].append(r)
    timeline: List[Dict[str, Any]] = []
    for idx in sorted(buckets.keys()):
        bucket_rows = buckets[idx]
        elapsed = [r["elapsed"] for r in bucket_rows]
        errs = sum(1 for r in bucket_rows if not r["success"])
        elapsed_sorted = sorted(elapsed)
        timeline.append({
            "t": idx * bucket_s,
            "count": len(bucket_rows),
            "avg": round(sum(elapsed) / len(elapsed), 2) if elapsed else 0,
            "p95": _percentile(elapsed_sorted, 0.95),
            "error_count": errs,
        })
    return timeline
