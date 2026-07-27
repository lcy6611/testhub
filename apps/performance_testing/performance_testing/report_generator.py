# -*- coding: utf-8 -*-
"""
自定义 HTML 报告生成器。

基于 JTL 解析结果生成独立 HTML 文件，解决 JMeter 原生报告在 iframe 中
资源路径/JS 执行不稳定的问题。
支持大模型报告分析（调用 AIModelConfig 配置的 OpenAI 兼容 API）。
"""

from __future__ import annotations

import html
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .result_parser import parse_jtl

logger = logging.getLogger(__name__)


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


def _build_timeline_series(summary: Dict[str, Any], metrics: List[Dict[str, Any]], thread_count: int, ramp_up: int, duration: int) -> Dict[str, List[Any]]:
    """从 summary 或 metrics 的 timeline 构建图表序列。"""
    total_timeline = (summary or {}).get("timeline") or (metrics[0]["timeline"] if metrics else [])
    times = [f"{p['t']}s" for p in total_timeline]
    avg_rt = [p.get("avg", 0) for p in total_timeline]
    throughput = [round((p.get("count", 0) or 0) / 10, 2) for p in total_timeline]
    error_rate = [
        round((p.get("error_count", 0) or 0) / max(p.get("count", 1) or 1, 1) * 100, 2)
        for p in total_timeline
    ]

    # 根据 ramp-up 计算预期活跃线程数
    active_threads = []
    for p in total_timeline:
        t = p.get("t", 0)
        if t < 0:
            active_threads.append(0)
        elif ramp_up <= 0:
            active_threads.append(thread_count)
        elif t >= duration:
            active_threads.append(0)
        elif t >= ramp_up:
            active_threads.append(thread_count)
        else:
            active_threads.append(max(1, int(round(thread_count * t / ramp_up))))

    return {
        "times": times,
        "avg_rt": avg_rt,
        "throughput": throughput,
        "error_rate": error_rate,
        "active_threads": active_threads,
    }


def _derive_time_from_jtl(jtl_path: str) -> tuple[Optional[datetime], Optional[datetime]]:
    """从 JTL 文件的时间戳推算开始/结束时间。"""
    if not jtl_path or not os.path.exists(jtl_path):
        return None, None
    try:
        import csv
        first_ts = None
        last_ts = None
        with open(jtl_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row.get("timeStamp") or row.get("timestamp") or ""
                if ts_str:
                    try:
                        ts = int(float(ts_str))
                        if first_ts is None:
                            first_ts = ts
                        last_ts = ts
                    except (ValueError, TypeError):
                        continue
        if first_ts and last_ts:
            from datetime import datetime as dt
            return dt.fromtimestamp(first_ts / 1000), dt.fromtimestamp(last_ts / 1000)
    except Exception as exc:
        logger.warning("从 JTL 推算时间失败: %s", exc)
    return None, None


def _generate_ai_analysis(execution, summary: Dict[str, Any], metrics: List[Dict[str, Any]]) -> str:
    """调用大模型对测试结果进行分析和优化建议。

    返回 Markdown 格式的分析文本；若调用失败返回空字符串。
    """
    try:
        from apps.requirement_analysis.models import AIModelConfig
        import requests as http_requests

        # 优先使用 writer 角色，其次任意活跃配置
        config = AIModelConfig.objects.filter(is_active=True, role="writer").first()
        if not config:
            config = AIModelConfig.objects.filter(is_active=True).first()
        if not config:
            logger.info("无活跃 AI 模型配置，跳过报告分析")
            return ""

        # 构建分析提示词
        total_samples = summary.get("total_samples", 0)
        error_count = summary.get("error_count", 0)
        error_rate = summary.get("error_rate", 0.0)
        throughput = summary.get("throughput", 0.0)
        avg = summary.get("avg", 0.0)
        p95 = summary.get("p95", 0.0)
        p99 = summary.get("p99", 0.0)
        max_rt = summary.get("max", 0.0)
        min_rt = summary.get("min", 0.0)

        # 事务明细摘要
        txn_lines = []
        for m in metrics[:10]:
            txn_lines.append(
                f"- {m.get('sample_label', '-')}: 样本{m.get('sample_count', 0)}, "
                f"错误率{m.get('error_rate', 0):.2f}%, "
                f"平均{m.get('avg', 0):.0f}ms, P95={m.get('p95', 0):.0f}ms, "
                f"吞吐{m.get('throughput', 0):.2f}/s"
            )
        txn_summary = "\n".join(txn_lines) if txn_lines else "无事务明细"

        user_prompt = f"""请对以下性能测试结果进行专业分析，并给出优化建议。

## 测试概况
- 执行ID: {execution.execution_id}
- 脚本: {execution.script.name if execution.script else '-'}
- 线程数: {execution.thread_count}
- Ramp-Up: {execution.ramp_up}s
- 持续时间: {execution.duration}s

## 核心指标
- 总样本数: {total_samples}
- 错误数: {error_count}
- 错误率: {error_rate:.2f}%
- 吞吐量: {throughput:.2f} req/s
- 平均响应时间: {avg:.2f}ms
- 最小响应时间: {min_rt:.2f}ms
- 最大响应时间: {max_rt:.2f}ms
- P95: {p95:.2f}ms
- P99: {p99:.2f}ms

## 事务明细
{txn_summary}

请从以下维度分析：
1. **性能评估**：整体性能是否达标，响应时间是否在可接受范围
2. **瓶颈识别**：哪些事务存在性能瓶颈，P95/P99 是否过高
3. **错误分析**：错误率是否异常，可能的错误原因
4. **吞吐量分析**：吞吐量是否合理，是否达到预期并发能力
5. **优化建议**：具体的优化方向和改进措施

请用 Markdown 格式输出，语言简洁专业。"""

        messages = [
            {"role": "system", "content": "你是一位资深的性能测试工程师，擅长分析 JMeter 性能测试结果并给出专业建议。"},
            {"role": "user", "content": user_prompt},
        ]

        # 同步调用 OpenAI 兼容 API
        base_url = (config.base_url or "").rstrip("/")
        if not base_url.endswith("/chat/completions"):
            if base_url.endswith("/v1"):
                base_url = base_url + "/chat/completions"
            else:
                base_url = base_url.rstrip("/") + "/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.model_name,
            "messages": messages,
            "max_tokens": min(config.max_tokens or 4096, 4096),
            "temperature": config.temperature or 0.7,
            "top_p": config.top_p or 0.9,
            "stream": False,
        }

        resp = http_requests.post(base_url, headers=headers, json=payload, timeout=120)
        if resp.ok:
            data = resp.json()
            choices = data.get("choices") or []
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    return content
            logger.warning("AI 分析返回空内容")
            return ""
        else:
            logger.warning("AI 分析请求失败 %s: %s", resp.status_code, resp.text[:300])
            return ""
    except Exception as exc:
        logger.warning("AI 报告分析失败: %s", exc)
        return ""


def _markdown_to_html(md_text: str) -> str:
    """简易 Markdown → HTML 转换（支持标题、粗体、列表、段落）。"""
    if not md_text:
        return ""
    lines = md_text.strip().split("\n")
    html_parts: List[str] = []
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            html_parts.append("</ul>")
            in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            close_list()
            continue
        # 标题
        if stripped.startswith("### "):
            close_list()
            html_parts.append(f"<h4>{_md_inline(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            close_list()
            html_parts.append(f"<h3>{_md_inline(stripped[3:])}</h3>")
        elif stripped.startswith("# "):
            close_list()
            html_parts.append(f"<h3>{_md_inline(stripped[2:])}</h3>")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{_md_inline(stripped[2:])}</li>")
        else:
            close_list()
            html_parts.append(f"<p>{_md_inline(stripped)}</p>")
    close_list()
    return "\n".join(html_parts)


def _md_inline(text: str) -> str:
    """处理行内 Markdown 格式：**粗体** 和 `代码`。"""
    import re
    # 粗体
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # 行内代码
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def generate_html_report(execution, output_path: str, *, jtl_path: str = None) -> None:
    """生成基于 JTL 的自定义 HTML 报告（含大模型分析）。"""
    jtl_path = jtl_path or execution.jtl_path
    parsed = parse_jtl(jtl_path) if jtl_path and os.path.exists(jtl_path) else {"summary": {}, "metrics": []}
    summary = parsed.get("summary") or {}
    metrics = parsed.get("metrics") or []

    total_samples = summary.get("total_samples", 0)
    error_count = summary.get("error_count", 0)
    error_rate = summary.get("error_rate", 0.0)
    throughput = summary.get("throughput", 0.0)
    avg = summary.get("avg", 0.0)
    p95 = summary.get("p95", 0.0)
    p99 = summary.get("p99", 0.0)
    max_rt = summary.get("max", 0.0)
    data_received = summary.get("data_received", 0) or 0
    data_sent = summary.get("data_sent", 0) or 0

    thread_count = execution.thread_count or 10
    ramp_up = execution.ramp_up or 5
    duration = execution.duration or 60

    timeline = _build_timeline_series(summary, metrics, thread_count, ramp_up, duration)

    # 开始/结束时间：优先用 execution 字段，为空时从 JTL 推算
    start_dt = execution.started_at
    end_dt = execution.completed_at
    if not start_dt or not end_dt:
        jtl_start, jtl_end = _derive_time_from_jtl(jtl_path)
        if not start_dt and jtl_start:
            start_dt = jtl_start
        if not end_dt and jtl_end:
            end_dt = jtl_end

    start_time = start_dt.strftime("%Y-%m-%d %H:%M:%S") if start_dt else "-"
    end_time = end_dt.strftime("%Y-%m-%d %H:%M:%S") if end_dt else "-"

    # 错误统计
    top_errors = []
    if metrics:
        top_errors = metrics[0].get("top_errors") or []

    # AI 报告分析
    ai_analysis_md = _generate_ai_analysis(execution, summary, metrics)
    ai_analysis_html = _markdown_to_html(ai_analysis_md) if ai_analysis_md else ""
    ai_section = ""
    if ai_analysis_html:
        ai_section = f"""
  <div class="section">
    <h2>AI 报告分析</h2>
    <div class="ai-analysis">
      {ai_analysis_html}
    </div>
  </div>"""
    else:
        ai_section = """
  <div class="section">
    <h2>AI 报告分析</h2>
    <div class="empty">暂无分析数据（未配置 AI 模型或分析失败）</div>
  </div>"""

    # 监控数据（服务器资源 / 数据库）
    monitoring_metrics = list(execution.monitor_metrics.all()) if hasattr(execution, "monitor_metrics") else []
    monitoring_section, monitoring_script = _render_monitoring(_build_monitoring_data(monitoring_metrics))

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TestHub 性能测试报告 - {html.escape(execution.execution_id)}</title>
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
.ai-analysis {{ line-height: 1.8; }}
.ai-analysis h3 {{ font-size: 15px; color: #303133; margin: 16px 0 8px; }}
.ai-analysis h4 {{ font-size: 14px; color: #409eff; margin: 12px 0 6px; }}
.ai-analysis p {{ margin-bottom: 8px; color: #606266; }}
.ai-analysis ul {{ margin: 8px 0 12px 20px; }}
.ai-analysis li {{ margin-bottom: 4px; color: #606266; }}
.ai-analysis strong {{ color: #303133; }}
.ai-analysis code {{ background: #f5f7fa; padding: 2px 6px; border-radius: 3px; font-size: 13px; color: #e6a23c; }}
.monitor-target-title {{ font-size: 14px; font-weight: 600; color: #303133; margin: 20px 0 4px; padding-left: 8px; border-left: 3px solid #409eff; }}
@media (max-width: 768px) {{
  .charts {{ grid-template-columns: 1fr; }}
  .cards {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>TestHub 性能测试报告</h1>
    <div class="meta">
      <span>执行ID: <b>{html.escape(execution.execution_id)}</b></span>
      <span>脚本: <b>{html.escape(execution.script.name if execution.script else "-")}</b></span>
      <span>状态: <b>{html.escape(execution.get_status_display())}</b></span>
      <span>开始时间: <b>{start_time}</b></span>
      <span>结束时间: <b>{end_time}</b></span>
      <span>线程数: <b>{thread_count}</b></span>
      <span>Ramp-Up: <b>{ramp_up}s</b></span>
      <span>持续时间: <b>{duration}s</b></span>
    </div>
  </div>

  <div class="cards">
    <div class="card"><div class="label">总样本数</div><div class="value">{_fmt_num(total_samples, 0)}</div></div>
    <div class="card"><div class="label">错误数</div><div class="value danger">{_fmt_num(error_count, 0)}</div></div>
    <div class="card"><div class="label">错误率</div><div class="value {'danger' if error_rate > 0 else 'success'}">{_fmt_num(error_rate, 2)}%</div></div>
    <div class="card"><div class="label">吞吐/s</div><div class="value primary">{_fmt_num(throughput, 2)}</div></div>
    <div class="card"><div class="label">平均响应(ms)</div><div class="value">{_fmt_num(avg, 2)}</div></div>
    <div class="card"><div class="label">P95(ms)</div><div class="value">{_fmt_num(p95, 2)}</div></div>
    <div class="card"><div class="label">P99(ms)</div><div class="value">{_fmt_num(p99, 2)}</div></div>
    <div class="card"><div class="label">最大响应(ms)</div><div class="value">{_fmt_num(max_rt, 2)}</div></div>
  </div>

  <div class="section">
    <h2>趋势图表</h2>
    <div class="charts">
      <div id="chart-rt" class="chart"></div>
      <div id="chart-tps" class="chart"></div>
      <div id="chart-err" class="chart"></div>
      <div id="chart-threads" class="chart"></div>
    </div>
  </div>

  <div class="section">
    <h2>事务明细</h2>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>事务</th>
            <th>样本</th>
            <th>失败</th>
            <th>错误率(%)</th>
            <th>吞吐/s</th>
            <th>平均(ms)</th>
            <th>P95(ms)</th>
            <th>P99(ms)</th>
            <th>最大(ms)</th>
          </tr>
        </thead>
        <tbody>
          {''.join(_transaction_rows(metrics)) if metrics else '<tr><td colspan="9" class="empty">暂无数据</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>

  <div class="section">
    <h2>错误统计</h2>
    <div class="table-wrap">
      <table>
        <thead><tr><th>错误码</th><th>次数</th></tr></thead>
        <tbody>
          {''.join(f'<tr><td>{html.escape(str(e.get("code", "-")))}</td><td>{e.get("count", 0)}</td></tr>' for e in top_errors) if top_errors else '<tr><td colspan="2" class="empty">暂无错误</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>
{ai_section}
{monitoring_section}
</div>

<script>
const timeline = {_safe_json(timeline)};
const metrics = {_safe_json(metrics)};

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
  echarts.init(document.getElementById('chart-rt')).setOption(lineOption('平均响应时间(ms)', timeline.avg_rt, '#409eff'));
  echarts.init(document.getElementById('chart-tps')).setOption(lineOption('吞吐量(req/s)', timeline.throughput, '#67c23a'));
  echarts.init(document.getElementById('chart-err')).setOption(lineOption('错误率(%)', timeline.error_rate, '#f56c6c'));
  echarts.init(document.getElementById('chart-threads')).setOption(lineOption('活跃线程数', timeline.active_threads, '#e6a23c'));
}} else {{
  ['chart-rt','chart-tps','chart-err','chart-threads'].forEach(id => {{
    document.getElementById(id).innerHTML = '<div class="empty">暂无可视化数据</div>';
  }});
}}
{monitoring_script}
</script>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)


def _build_monitoring_data(metrics) -> List[Dict[str, Any]]:
    """将 PerformanceMonitorMetric 列表按目标分组，供报告/前端渲染。"""
    grouped: Dict[str, Any] = {}
    for m in metrics:
        key = m.target_name
        g = grouped.setdefault(key, {
            "target_name": m.target_name,
            "target_type": m.target_type,
            "metrics": [],
        })
        g["metrics"].append({
            "metric_key": m.metric_key,
            "metric_label": m.metric_label,
            "metric_unit": m.metric_unit,
            "timeline": m.timeline or [],
            "avg": m.avg_value,
            "max": m.max_value,
            "peak": m.peak_value,
        })
    return list(grouped.values())


def _render_monitoring(data: List[Dict[str, Any]]) -> tuple:
    """返回 (section_html, script_js)，注入 HTML 报告。"""
    if not data:
        section = """
  <div class="section">
    <h2>服务器资源与数据库监控</h2>
    <div class="empty">未采集到监控数据（未配置 Prometheus 监控目标，或执行期间无可用指标）</div>
  </div>"""
        return section, ""

    section = """
  <div class="section">
    <h2>服务器资源与数据库监控</h2>
    <div id="monitoring-container"></div>
  </div>"""

    script = """
const monitoringData = %s;
(function(){
  const container = document.getElementById('monitoring-container');
  if (!monitoringData || !monitoringData.length) {
    container.innerHTML = '<div class="empty">未采集到监控数据</div>';
    return;
  }
  const palette = ['#409eff','#67c23a','#f56c6c','#e6a23c','#9b59b6','#1abc9c','#34495e','#f39c12'];
  monitoringData.forEach(function(target, ti){
    const title = document.createElement('div');
    title.className = 'monitor-target-title';
    title.textContent = target.target_name + '（' + target.target_type + '）';
    container.appendChild(title);
    const grid = document.createElement('div');
    grid.className = 'charts';
    container.appendChild(grid);
    target.metrics.forEach(function(m, mi){
      const id = 'monitor-' + ti + '-' + mi;
      const div = document.createElement('div');
      div.className = 'chart';
      div.id = id;
      grid.appendChild(div);
      const times = m.timeline.map(function(p){ return p.t + 's'; });
      const vals = m.timeline.map(function(p){ return p.v; });
      const color = palette[ti % palette.length];
      const chart = echarts.init(document.getElementById(id));
      chart.setOption({
        title: { text: m.metric_label + ' (' + m.metric_unit + ')', left: 'center', textStyle: { fontSize: 14, fontWeight: 'normal' } },
        tooltip: { trigger: 'axis' },
        grid: { left: 55, right: 20, top: 40, bottom: 30 },
        xAxis: { type: 'category', boundaryGap: false, data: times },
        yAxis: { type: 'value', scale: true },
        series: [{ name: m.metric_label, type: 'line', smooth: true, data: vals, itemStyle: { color: color }, lineStyle: { width: 2 } }]
      });
    });
  });
})();
""" % _safe_json(data)
    return section, script


def _transaction_rows(metrics: List[Dict[str, Any]]) -> List[str]:
    rows = []
    for m in metrics:
        rows.append(
            f"""<tr>
                <td>{html.escape(m.get('sample_label', '-') or '-')}</td>
                <td>{m.get('sample_count', 0)}</td>
                <td>{m.get('error_count', 0)}</td>
                <td>{_fmt_num(m.get('error_rate', 0.0), 2)}%</td>
                <td>{_fmt_num(m.get('throughput', 0.0), 2)}</td>
                <td>{_fmt_num(m.get('avg', 0.0), 2)}</td>
                <td>{_fmt_num(m.get('p95', 0.0), 2)}</td>
                <td>{_fmt_num(m.get('p99', 0.0), 2)}</td>
                <td>{_fmt_num(m.get('max', 0.0), 2)}</td>
            </tr>"""
        )
    return rows
