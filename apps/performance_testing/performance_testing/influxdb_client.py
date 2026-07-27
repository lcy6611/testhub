# -*- coding: utf-8 -*-
"""
InfluxDB 2.x 实时指标查询（Flux 查询）。

使用 InfluxdbBackendListenerClient（聚合模式）写入的数据。
聚合模式每 10s 发送一次，字段包括: avg / count / countError / maxAT / meanAT / pct90.0 / pct95.0 等。

若未启用实时报告或 InfluxDB 不可达，返回空结果，不影响静态报告。
InfluxDB 查询结果为空时自动回退到 JTL 文件解析。
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

QUERY_TIMEOUT = 15


def _influx_config() -> Dict[str, str]:
    """优先从 PerformanceConfig（数据库）读取，无配置时回退 settings。"""
    try:
        from .models import PerformanceConfig
        cfg = PerformanceConfig.get_singleton()
        if cfg.influxdb_url:
            return {
                "url": cfg.influxdb_url or "",
                "org": cfg.influxdb_org or "testhub",
                "bucket": cfg.influxdb_bucket or "jmeter",
                "token": cfg.influxdb_token or "",
                "measurement": cfg.influxdb_measurement or "jmeter",
                "application": cfg.influxdb_application or "testhub",
                "enabled": cfg.realtime_report_enabled,
            }
    except Exception as exc:
        logger.debug("读取 PerformanceConfig 失败，回退 settings: %s", exc)

    from django.conf import settings
    return {
        "url": getattr(settings, "PERFORMANCE_INFLUXDB_URL", ""),
        "org": getattr(settings, "PERFORMANCE_INFLUXDB_ORG", "testhub"),
        "bucket": getattr(settings, "PERFORMANCE_INFLUXDB_BUCKET", "jmeter"),
        "token": getattr(settings, "PERFORMANCE_INFLUXDB_TOKEN", ""),
        "measurement": getattr(settings, "PERFORMANCE_INFLUXDB_MEASUREMENT", "jmeter"),
        "application": getattr(settings, "PERFORMANCE_INFLUXDB_APPLICATION", "testhub"),
        "enabled": getattr(settings, "PERFORMANCE_REALTIME_REPORT_ENABLED", False),
    }


def is_enabled() -> bool:
    cfg = _influx_config()
    return bool(cfg.get("enabled")) and bool(cfg.get("url"))


def _run_flux(flux: str) -> List[Dict[str, Any]]:
    cfg = _influx_config()
    if not cfg["url"] or not cfg["token"]:
        return []
    # Fix: InfluxDB 2.x 要求 ?org= 参数，否则返回 400
    url = f"{cfg['url'].rstrip('/')}/api/v2/query?org={cfg['org']}"
    headers = {
        "Authorization": f"Token {cfg['token']}",
        "Content-Type": "application/json",
        "Accept": "application/csv",
    }
    body = {"query": flux, "type": "flux"}
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=QUERY_TIMEOUT)
        if not resp.ok:
            logger.warning("InfluxDB 查询失败 %s: %s", resp.status_code, resp.text[:200])
            return []
        return _parse_flux_csv(resp.text)
    except Exception as exc:
        logger.warning("InfluxDB 查询异常: %s", exc)
        return []


def _parse_flux_csv(text: str) -> List[Dict[str, Any]]:
    """简易解析 Flux CSV 响应。"""
    if not text:
        return []
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return []
    # 找到包含 result,_table 的表头行
    header = None
    data_start = 0
    for i, ln in enumerate(lines):
        cols = ln.split(",")
        if "result" in cols and "_value" in ln:
            header = cols
            data_start = i + 1
            break
    if not header:
        return []
    rows: List[Dict[str, Any]] = []
    for ln in lines[data_start:]:
        if ln.startswith("#") or not ln.strip():
            continue
        cols = ln.split(",")
        if len(cols) < len(header):
            continue
        row = {}
        for idx, col in enumerate(header):
            if idx < len(cols):
                row[col] = cols[idx]
        if row.get("_value") not in (None, ""):
            rows.append(row)
    return rows


def query_realtime(execution_id: str, *, window_s: int = 60) -> Dict[str, Any]:
    """查询实时指标：响应时间、吞吐量、错误率、活跃线程数。

    优先使用 InfluxDB（聚合模式数据）；查询结果为空时回退到 JTL 文件解析。
    """
    from .models import PerformanceExecution
    from .result_parser import parse_jtl

    try:
        execution = PerformanceExecution.objects.get(execution_id=execution_id)
    except Exception:
        return {"enabled": False, "points": []}

    if is_enabled():
        result = _query_influxdb_realtime(execution, window_s=window_s)
        # InfluxDB 查询结果为空时回退到 JTL
        if _has_data(result):
            return result
        logger.info("InfluxDB 查询无数据，回退 JTL 解析: %s", execution_id)

    # JTL 实时解析回退
    jtl_path = execution.jtl_path
    if not jtl_path or not os.path.exists(jtl_path):
        return {"enabled": True, "source": "jtl", "response_time_p95": [], "throughput": [], "errors": [], "active_threads": []}

    parsed = parse_jtl(jtl_path)
    summary = parsed.get("summary") or {}
    timeline = summary.get("timeline") or []

    response_time_p95 = []
    throughput = []
    errors = []
    active_threads = []
    for p in timeline:
        t = p.get("t", 0)
        time_label = _fmt_seconds(t)
        count = p.get("count", 0) or 0
        response_time_p95.append({"time": time_label, "value": p.get("p95", 0)})
        throughput.append({"time": time_label, "value": round(count / 10, 2)})
        errors.append({"time": time_label, "value": p.get("error_count", 0)})
        active_threads.append({
            "time": time_label,
            "value": _expected_active_threads(t, execution.ramp_up, execution.thread_count, execution.duration),
        })
    return {
        "enabled": True,
        "source": "jtl",
        "execution_id": execution_id,
        "window_s": window_s,
        "response_time_p95": response_time_p95,
        "throughput": throughput,
        "errors": errors,
        "active_threads": active_threads,
    }


def _has_data(result: Dict[str, Any]) -> bool:
    """检查 InfluxDB 查询结果是否有数据。"""
    for key in ("response_time_p95", "throughput", "errors", "active_threads"):
        if result.get(key):
            return True
    return False


def _expected_active_threads(elapsed_s: float, ramp_up: int, thread_count: int, duration: int) -> int:
    """根据 ramp-up 计算指定时刻的预期活跃线程数。"""
    if elapsed_s < 0:
        return 0
    if ramp_up <= 0:
        return thread_count
    if elapsed_s >= duration:
        return 0
    if elapsed_s >= ramp_up:
        return thread_count
    return max(1, int(round(thread_count * elapsed_s / ramp_up)))


def _fmt_seconds(seconds: int) -> str:
    """秒数转为 MM:SS 格式。"""
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def _query_influxdb_realtime(execution, *, window_s: int = 60) -> Dict[str, Any]:
    """InfluxDB 实时指标查询（基于 InfluxdbBackendListenerClient 聚合数据）。

    聚合模式字段:
      - avg: 平均响应时间
      - count: 请求计数（每窗口）
      - countError: 错误计数
      - maxAT: 最大活跃线程
      - pct95.0: 95 百分位响应时间
    Tags: application, transaction (transaction=="all" 为全局汇总)
    """
    cfg = _influx_config()
    m = cfg["measurement"]
    app = cfg["application"]
    bucket = cfg["bucket"]

    # 根据执行记录确定时间范围
    from django.utils import timezone

    if execution.started_at:
        start = execution.started_at.isoformat()
    else:
        start = f"-{window_s}s"

    if execution.completed_at:
        stop = execution.completed_at.isoformat()
    else:
        stop = "now()"

    # 聚合模式：过滤 application + transaction=="all"（全局汇总）
    base_filter = (
        f'filter(fn: (r) => r._measurement == "{m}" and r.application == "{app}" and r.transaction == "all")'
    )

    # 平均响应时间
    flux_rt = (
        f'from(bucket:"{bucket}") |> range(start: {start}, stop: {stop}) '
        f'|> {base_filter} '
        f'|> filter(fn: (r) => r._field == "avg") '
        f'|> aggregateWindow(every: 10s, fn: mean, createEmpty: false)'
    )
    # 吞吐量（每窗口请求计数）
    flux_throughput = (
        f'from(bucket:"{bucket}") |> range(start: {start}, stop: {stop}) '
        f'|> {base_filter} '
        f'|> filter(fn: (r) => r._field == "count") '
        f'|> aggregateWindow(every: 10s, fn: sum, createEmpty: false)'
    )
    # 错误数
    flux_errors = (
        f'from(bucket:"{bucket}") |> range(start: {start}, stop: {stop}) '
        f'|> {base_filter} '
        f'|> filter(fn: (r) => r._field == "countError") '
        f'|> aggregateWindow(every: 10s, fn: sum, createEmpty: false)'
    )
    # 活跃线程数
    flux_threads = (
        f'from(bucket:"{bucket}") |> range(start: {start}, stop: {stop}) '
        f'|> {base_filter} '
        f'|> filter(fn: (r) => r._field == "maxAT") '
        f'|> aggregateWindow(every: 10s, fn: max, createEmpty: false)'
    )

    return {
        "enabled": True,
        "source": "influxdb",
        "execution_id": execution.execution_id,
        "window_s": window_s,
        "response_time_p95": _summarize(_run_flux(flux_rt)),
        "throughput": _summarize(_run_flux(flux_throughput)),
        "errors": _summarize(_run_flux(flux_errors)),
        "active_threads": _summarize(_run_flux(flux_threads)),
    }


def _summarize(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        try:
            out.append({
                "time": r.get("_time", ""),
                "value": float(r.get("_value") or 0),
            })
        except (ValueError, TypeError):
            continue
    return out
