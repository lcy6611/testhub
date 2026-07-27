# -*- coding: utf-8 -*-
"""
项目级批量执行 HTML 报告生成器。

汇总批次内所有脚本的执行结果，生成独立 HTML 文件。
"""

from __future__ import annotations

import html
import json
import os
from typing import Any, Dict, List

from .result_parser import parse_jtl


def _fmt_num(n, digits: int = 2) -> str:
    if n is None:
        return "-"
    try:
        num = float(n)
    except (ValueError, TypeError):
        return "-"
    if digits == 0:
        return str(int(round(num)))
    return f"{num:.{digits}f}"


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _script_rows(executions: List[Any], summaries: Dict[int, Dict[str, Any]]) -> List[str]:
    rows = []
    for e in executions:
        s = summaries.get(e.id) or {}
        rows.append(
            f"""<tr>
                <td>{html.escape(e.execution_id)}</td>
                <td>{html.escape(e.script.name if e.script else "-")}</td>
                <td>{html.escape(e.get_status_display())}</td>
                <td>{_fmt_num(s.get('total_samples', 0), 0)}</td>
                <td>{_fmt_num(s.get('error_count', 0), 0)}</td>
                <td>{_fmt_num(s.get('error_rate', 0.0), 2)}%</td>
                <td>{_fmt_num(s.get('avg_response_time', 0.0), 2)}</td>
                <td>{_fmt_num(s.get('p95', 0.0), 2)}</td>
                <td>{_fmt_num(s.get('throughput', 0.0), 2)}</td>
            </tr>"""
        )
    return rows


def generate_batch_report(batch, output_path: str) -> None:
    """生成基于批次内各执行 JTL 的项目级 HTML 报告。"""
    executions = list(batch.executions.order_by("id").select_related("script"))

    aggregate = {
        "total_samples": 0,
        "error_count": 0,
        "total_executions": len(executions),
        "completed": 0,
        "failed": 0,
    }
    summaries: Dict[int, Dict[str, Any]] = {}
    all_rows: List[Dict[str, Any]] = []

    for e in executions:
        if e.status == "COMPLETED":
            aggregate["completed"] += 1
        elif e.status == "FAILED":
            aggregate["failed"] += 1

        try:
            s = e.summary
            summary_data = {
                "total_samples": s.total_samples,
                "error_count": s.error_count,
                "error_rate": s.error_rate,
                "avg_response_time": s.avg_response_time,
                "p95": s.p95,
                "throughput": s.throughput,
            }
        except Exception:
            summary_data = {}
            if e.jtl_path and os.path.exists(e.jtl_path):
                parsed = parse_jtl(e.jtl_path)
                summary = parsed.get("summary") or {}
                summary_data = {
                    "total_samples": summary.get("total_samples", 0),
                    "error_count": summary.get("error_count", 0),
                    "error_rate": summary.get("error_rate", 0.0),
                    "avg_response_time": summary.get("avg", 0.0),
                    "p95": summary.get("p95", 0.0),
                    "throughput": summary.get("throughput", 0.0),
                }
                all_rows.extend(parsed.get("metrics") or [])

        summaries[e.id] = summary_data
        aggregate["total_samples"] += summary_data.get("total_samples", 0)
        aggregate["error_count"] += summary_data.get("error_count", 0)

    total = aggregate["total_samples"]
    aggregate["error_rate"] = round(aggregate["error_count"] / max(total, 1) * 100, 2)
    avg_rt = sum((s.get("avg_response_time") or 0) for s in summaries.values()) / max(len(summaries), 1)
    avg_p95 = sum((s.get("p95") or 0) for s in summaries.values()) / max(len(summaries), 1)
    avg_tps = sum((s.get("throughput") or 0) for s in summaries.values()) / max(len(summaries), 1)

    # 构建时间线：合并所有执行的时间线，按 10s bucket 汇总
    timeline_map: Dict[int, Dict[str, Any]] = {}
    for e in executions:
        if e.jtl_path and os.path.exists(e.jtl_path):
            parsed = parse_jtl(e.jtl_path)
            summary = parsed.get("summary") or {}
            for p in summary.get("timeline") or []:
                t = p.get("t", 0)
                bucket = timeline_map.setdefault(t, {"t": t, "count": 0, "avg": 0, "error_count": 0})
                bucket["count"] += p.get("count", 0) or 0
                bucket["error_count"] += p.get("error_count", 0) or 0

    # 计算加权平均响应时间
    for t, bucket in timeline_map.items():
        total_count = bucket["count"]
        # avg 不能直接加，先保留加权平均：重新计算较复杂，简化为用已汇总数据的均值
        bucket["avg"] = 0
        bucket["error_rate"] = round(bucket["error_count"] / max(total_count, 1) * 100, 2) if total_count else 0
        bucket["throughput"] = round(total_count / 10, 2) if total_count else 0

    sorted_timeline = sorted(timeline_map.values(), key=lambda x: x["t"])
    times = [f"{p['t']}s" for p in sorted_timeline]
    throughput = [p.get("throughput", 0) for p in sorted_timeline]
    error_rate = [p.get("error_rate", 0) for p in sorted_timeline]

    start_time = "-"
    end_time = "-"
    if batch.created_at:
        start_time = batch.created_at.strftime("%Y-%m-%d %H:%M:%S")
    if batch.completed_at:
        end_time = batch.completed_at.strftime("%Y-%m-%d %H:%M:%S")

    project_name = batch.project.name if batch.project else "通用项目"

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TestHub 项目级性能测试报告 - {html.escape(batch.batch_id)}</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; background: #f5f7fa; color: #303133; line-height: 1.6; }}
.container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
.header {{ background: #fff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.05); margin-bottom: 24px; }}
.header h1 {{ font-size: 22px; margin-bottom: 12px; }}
.header .meta {{ display: flex; flex-wrap: wrap; gap: 24px; color: #606266; font-size: 13px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }}
.card {{ background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.05); }}
.card .label {{ font-size: 13px; color: #909399; margin-bottom: 8px; }}
.card .value {{ font-size: 28px; font-weight: 700; color: #303133; }}
.card .value.success {{ color: #67c23a; }}
.card .value.danger {{ color: #f56c6c; }}
.card .value.primary {{ color: #409eff; }}
.section {{ background: #fff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.05); margin-bottom: 24px; }}
.section h2 {{ font-size: 16px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid #ebeef5; }}
.charts {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }}
.chart {{ height: 320px; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ebeef5; }}
th {{ background: #f5f7fa; font-weight: 600; color: #606266; }}
tr:hover {{ background: #f5f7fa; }}
.empty {{ color: #909399; text-align: center; padding: 40px; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
.badge-success {{ background: #f0f9ff; color: #409eff; }}
.badge-danger {{ background: #fef0f0; color: #f56c6c; }}
@media (max-width: 768px) {{
  .charts {{ grid-template-columns: 1fr; }}
  .cards {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>项目级性能测试报告</h1>
    <div class="meta">
      <span>批次ID: <b>{html.escape(batch.batch_id)}</b></span>
      <span>批次名称: <b>{html.escape(batch.name)}</b></span>
      <span>项目: <b>{html.escape(project_name)}</b></span>
      <span>状态: <b>{html.escape(batch.get_status_display())}</b></span>
      <span>开始时间: <b>{start_time}</b></span>
      <span>结束时间: <b>{end_time}</b></span>
      <span>脚本数: <b>{batch.total_scripts}</b></span>
      <span>成功/失败: <b>{aggregate['completed']}/{aggregate['failed']}</b></span>
    </div>
  </div>

  <div class="cards">
    <div class="card"><div class="label">总样本数</div><div class="value">{_fmt_num(aggregate['total_samples'], 0)}</div></div>
    <div class="card"><div class="label">总错误数</div><div class="value danger">{_fmt_num(aggregate['error_count'], 0)}</div></div>
    <div class="card"><div class="label">总错误率</div><div class="value {'danger' if aggregate['error_rate'] > 0 else 'success'}">{_fmt_num(aggregate['error_rate'], 2)}%</div></div>
    <div class="card"><div class="label">平均吞吐/s</div><div class="value primary">{_fmt_num(avg_tps, 2)}</div></div>
    <div class="card"><div class="label">平均响应(ms)</div><div class="value">{_fmt_num(avg_rt, 2)}</div></div>
    <div class="card"><div class="label">平均P95(ms)</div><div class="value">{_fmt_num(avg_p95, 2)}</div></div>
  </div>

  <div class="section">
    <h2>趋势图表</h2>
    <div class="charts">
      <div id="chart-tps" class="chart"></div>
      <div id="chart-err" class="chart"></div>
    </div>
  </div>

  <div class="section">
    <h2>脚本执行明细</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>执行ID</th>
            <th>脚本</th>
            <th>状态</th>
            <th>样本</th>
            <th>错误</th>
            <th>错误率(%)</th>
            <th>平均RT(ms)</th>
            <th>P95(ms)</th>
            <th>吞吐/s</th>
          </tr>
        </thead>
        <tbody>
          {''.join(_script_rows(executions, summaries)) if executions else '<tr><td colspan="9" class="empty">暂无数据</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>
</div>

<script>
const timeline = {_safe_json({"times": times, "throughput": throughput, "error_rate": error_rate})};

function lineOption(title, series, color) {{
  return {{
    title: {{ text: title, left: 'center', textStyle: {{ fontSize: 14, fontWeight: 'normal' }} }},
    tooltip: {{ trigger: 'axis' }},
    grid: {{ left: 50, right: 20, top: 40, bottom: 30 }},
    xAxis: {{ type: 'category', boundaryGap: false, data: timeline.times }},
    yAxis: {{ type: 'value', scale: true }},
    series: [{{ name: title, type: 'line', smooth: true, data: series, itemStyle: {{ color }}, lineStyle: {{ width: 2 }} }}]
  }};
}}

if (timeline.times.length > 0) {{
  echarts.init(document.getElementById('chart-tps')).setOption(lineOption('吞吐量(req/s)', timeline.throughput, '#67c23a'));
  echarts.init(document.getElementById('chart-err')).setOption(lineOption('错误率(%)', timeline.error_rate, '#f56c6c'));
}} else {{
  ['chart-tps','chart-err'].forEach(id => {{
    document.getElementById(id).innerHTML = '<div class="empty">暂无可视化数据</div>';
  }});
}}
</script>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
