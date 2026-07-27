# -*- coding: utf-8 -*-
"""
Prometheus 监控采集模块。

对接已有的 Prometheus 服务（通常由 node_exporter / mysqld_exporter 等采集端提供指标），
按性能执行的时间窗（started_at ~ completed_at）拉取被测服务器/数据库的资源指标，
并转换为 Platform 可落库的时序结构。

指标映射覆盖报告常见维度：
- 服务器/服务：CPU、内存、网络 IO、磁盘 IO、磁盘使用率（node_exporter）
- 数据库（MySQL）：连接数、活跃连接、QPS、慢查询、行锁等待、缓冲池命中率（mysqld_exporter）
  （Oracle 场景可改用 oracle_exporter，扩展 DB_METRICS 即可）
"""

from __future__ import annotations

import logging
from datetime import timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


# ==================== 指标模板 ====================

# 通用服务器/服务资源指标（node_exporter）
NODE_METRICS: Dict[str, Dict[str, str]] = {
    "cpu_usage": {
        "label": "CPU 使用率",
        "unit": "%",
        "promql": (
            "100 - (avg(rate(node_cpu_seconds_total{instance=\"$instance\",mode=\"idle\"}[1m])) * 100)"
        ),
    },
    "mem_usage": {
        "label": "内存使用率",
        "unit": "%",
        "promql": (
            "(1 - (node_memory_MemAvailable_bytes{instance=\"$instance\"} "
            "/ node_memory_MemTotal_bytes{instance=\"$instance\"})) * 100"
        ),
    },
    "net_in": {
        "label": "网络接收速率",
        "unit": "KB/s",
        "promql": (
            "sum(rate(node_network_receive_bytes_total{instance=\"$instance\",device!~\"lo\"}[1m])) / 1024"
        ),
    },
    "net_out": {
        "label": "网络发送速率",
        "unit": "KB/s",
        "promql": (
            "sum(rate(node_network_transmit_bytes_total{instance=\"$instance\",device!~\"lo\"}[1m])) / 1024"
        ),
    },
    "disk_read": {
        "label": "磁盘读速率",
        "unit": "KB/s",
        "promql": "sum(rate(node_disk_read_bytes_total{instance=\"$instance\"}[1m])) / 1024",
    },
    "disk_write": {
        "label": "磁盘写速率",
        "unit": "KB/s",
        "promql": "sum(rate(node_disk_written_bytes_total{instance=\"$instance\"}[1m])) / 1024",
    },
    "disk_usage": {
        "label": "磁盘使用率",
        "unit": "%",
        "promql": (
            "100 - (sum(node_filesystem_avail_bytes{instance=\"$instance\",mountpoint=\"/\","
            "fstype!~\"tmpfs|overlay|squashfs\"}) "
            "/ sum(node_filesystem_size_bytes{instance=\"$instance\",mountpoint=\"/\","
            "fstype!~\"tmpfs|overlay|squashfs\"})) * 100"
        ),
    },
}

# 数据库资源指标（mysqld_exporter，MySQL 场景）
DB_METRICS: Dict[str, Dict[str, str]] = {
    "db_connections": {
        "label": "连接数",
        "unit": "个",
        "promql": "mysql_global_status_threads_connected{instance=\"$instance\"}",
    },
    "db_active_connections": {
        "label": "活跃连接数",
        "unit": "个",
        "promql": "mysql_global_status_threads_running{instance=\"$instance\"}",
    },
    "db_qps": {
        "label": "QPS",
        "unit": "次/s",
        "promql": "rate(mysql_global_status_queries{instance=\"$instance\"}[1m])",
    },
    "db_slow_queries": {
        "label": "慢查询速率",
        "unit": "次/s",
        "promql": "rate(mysql_global_status_slow_queries{instance=\"$instance\"}[1m])",
    },
    "db_row_lock_waits": {
        "label": "行锁等待速率",
        "unit": "次/s",
        "promql": "rate(mysql_global_status_innodb_row_lock_waits{instance=\"$instance\"}[1m])",
    },
    "db_row_lock_time": {
        "label": "行锁等待时间",
        "unit": "ms/s",
        "promql": "rate(mysql_global_status_innodb_row_lock_time{instance=\"$instance\"}[1m])",
    },
    "db_buffer_hit": {
        "label": "缓冲池命中率",
        "unit": "%",
        "promql": (
            "(1 - (rate(mysql_global_status_innodb_buffer_pool_reads{instance=\"$instance\"}[1m]) "
            "/ rate(mysql_global_status_innodb_buffer_pool_read_requests{instance=\"$instance\"}[1m]))) * 100"
        ),
    },
    "db_tmp_disk_tables": {
        "label": "临时表落盘速率",
        "unit": "次/s",
        "promql": "rate(mysql_global_status_created_tmp_disk_tables{instance=\"$instance\"}[1m])",
    },
    "db_full_scans": {
        "label": "全表扫描速率",
        "unit": "次/s",
        "promql": "rate(mysql_global_status_select_full_join{instance=\"$instance\"}[1m])",
    },
}

TYPE_METRIC_MAP: Dict[str, Dict[str, Dict[str, str]]] = {
    "app_server": NODE_METRICS,
    "gateway": NODE_METRICS,
    "redis": NODE_METRICS,
    "custom": NODE_METRICS,
    "db": DB_METRICS,
    "database": DB_METRICS,
}


def _render_promql(template: str, instance: str, job: str = "") -> str:
    promql = template.replace("$instance", instance)
    if job:
        # 在第一个 {instance="..."} 后追加 job 过滤
        promql = promql.replace(
            f'instance="{instance}"', f'instance="{instance}",job="{job}"'
        )
    return promql


def query_range(
    prometheus_url: str,
    query: str,
    start_ts: float,
    stop_ts: float,
    step: int = 15,
) -> List[List[Any]]:
    """调用 Prometheus /api/v1/query_range 返回 [[ts, value], ...]。"""
    url = prometheus_url.rstrip("/") + "/api/v1/query_range"
    params = {
        "query": query,
        "start": int(start_ts),
        "end": int(stop_ts),
        "step": max(1, int(step)),
    }
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Prometheus 查询失败: {data.get('error')}")
    result = (data.get("data") or {}).get("result") or []
    values: List[List[Any]] = []
    for series in result:
        for ts, val in series.get("values") or []:
            try:
                values.append([float(ts), float(val)])
            except (ValueError, TypeError):
                continue
    return values


def collect_target_metrics(
    prometheus_url: str,
    target: Dict[str, Any],
    start_ts: float,
    stop_ts: float,
    step: int = 15,
) -> List[Dict[str, Any]]:
    """采集单个监控目标的指标，返回待落库的 PerformanceMonitorMetric 数据列表。"""
    instance = (target.get("instance") or "").strip()
    job = (target.get("job") or "").strip()
    target_type = target.get("type", "app_server")
    target_name = target.get("name") or instance or target_type

    templates = TYPE_METRIC_MAP.get(target_type, NODE_METRICS)

    # 若目标显式配置了 metrics 列表，则仅采集这些；否则按类型全采
    wanted = target.get("metrics") or []
    metric_items = []
    if wanted:
        for key in wanted:
            if key in templates:
                metric_items.append((key, templates[key]))
    else:
        metric_items = list(templates.items())

    span = max(1, int(stop_ts - start_ts))
    effective_step = max(1, min(step, max(1, span // 30)))

    results: List[Dict[str, Any]] = []
    for key, meta in metric_items:
        promql = _render_promql(meta["promql"], instance, job)
        try:
            raw = query_range(prometheus_url, promql, start_ts, stop_ts, effective_step)
        except Exception as exc:
            logger.warning("目标[%s] 指标[%s] 采集失败: %s", target_name, key, exc)
            continue
        if not raw:
            continue
        # 过滤 NaN/Inf，MySQL JSON 字段无法存储
        import math
        clean = [(v[0], v[1]) for v in raw if isinstance(v[1], (int, float)) and math.isfinite(v[1])]
        if not clean:
            continue
        # 时间线：相对秒（对齐 JMeter 时间线 t 含义）
        timeline = [{"t": int(round(v[0] - start_ts)), "v": round(v[1], 3)} for v in clean]
        vals = [v[1] for v in clean]
        avg = sum(vals) / len(vals)
        results.append({
            "target_name": target_name,
            "target_type": target_type,
            "metric_key": key,
            "metric_label": meta["label"],
            "metric_unit": meta["unit"],
            "timeline": timeline,
            "min_value": round(min(vals), 3),
            "avg_value": round(avg, 3),
            "max_value": round(max(vals), 3),
            "peak_value": round(max(vals), 3),
        })
    return results


def collect_execution_monitoring(execution, *, running: bool = False) -> int:
    """按时间窗采集执行的监控指标并落库。返回新增记录数；失败返回 0。

    running=True 时允许 completed_at 为空：用 now() 作为 stop 收尾，确保执行中也能
    看到监控曲线（详情 Tab / 看板 / 报告都会自动反映最新一次采集结果）。
    """
    from .models import PerformanceConfig, PerformanceMonitorMetric

    try:
        config = PerformanceConfig.get_singleton()
    except Exception:
        return 0

    if not config.prometheus_enabled or not config.prometheus_url:
        return 0
    targets = config.monitor_targets or []
    if not targets:
        return 0

    start = execution.started_at
    stop = execution.completed_at
    if not start:
        logger.info("执行 %s 尚未开始，跳过监控采集", getattr(execution, "execution_id", "?"))
        return 0
    if not stop:
        if running:
            from django.utils import timezone as dj_tz
            stop = dj_tz.now()
        else:
            logger.info("执行 %s 缺少完成时间，跳过监控采集", getattr(execution, "execution_id", "?"))
            return 0
    if stop <= start:
        stop = start

    start_ts = start.timestamp()
    stop_ts = stop.timestamp()
    if stop_ts <= start_ts:
        stop_ts = start_ts + 1

    step = config.prometheus_step or 15

    all_metrics: List[Dict[str, Any]] = []
    for target in targets:
        try:
            all_metrics.extend(
                collect_target_metrics(config.prometheus_url, target, start_ts, stop_ts, step)
            )
        except Exception as exc:
            logger.warning("监控目标采集异常 %s: %s", target.get("name"), exc)

    if not all_metrics:
        return 0

    # 清旧 + 批量写入
    PerformanceMonitorMetric.objects.filter(execution=execution).delete()
    objs = [
        PerformanceMonitorMetric(execution=execution, **m) for m in all_metrics
    ]
    PerformanceMonitorMetric.objects.bulk_create(objs)
    logger.info(
        "执行 %s 采集监控指标 %d 条（running=%s）",
        getattr(execution, "execution_id", "?"), len(objs), running,
    )
    return len(objs)


def test_prometheus_connection(prometheus_url: str) -> Dict[str, Any]:
    """测试 Prometheus 连接。"""
    if not prometheus_url:
        return {"ok": False, "message": "Prometheus URL 不能为空"}
    try:
        url = prometheus_url.rstrip("/") + "/api/v1/query?query=up"
        resp = requests.get(url, timeout=10)
        if resp.ok:
            data = resp.json()
            if data.get("status") == "success":
                return {"ok": True, "message": "Prometheus 连接正常"}
            return {"ok": False, "message": f"查询失败: {data.get('error')}"}
        return {"ok": False, "message": f"HTTP {resp.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "message": "无法连接到 Prometheus，请检查 URL 和网络"}
    except Exception as exc:
        return {"ok": False, "message": f"检测异常: {str(exc)}"}
