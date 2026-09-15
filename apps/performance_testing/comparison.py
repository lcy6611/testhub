"""多轮执行对照：指标矩阵快照 + 接口级对比 + 可选 AI 对照分析。

与 ``compare_report``（开源）的分工一致：快照供 API 与持久化报告共用，
另提供一个把快照压成文本矩阵喂给 LLM 的辅助函数。

指标字段名对齐本模块 ``PerformanceSummary``。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: 参与对照的汇总指标（顺序即表格列顺序）
METRIC_KEYS = [
    "total_samples", "throughput", "avg_response_time",
    "p90", "p95", "p99", "max_response_time", "error_rate",
]

METRIC_LABELS = {
    "total_samples": "总样本数",
    "throughput": "TPS(req/s)",
    "avg_response_time": "平均响应时间(ms)",
    "p90": "P90(ms)",
    "p95": "P95(ms)",
    "p99": "P99(ms)",
    "max_response_time": "最大响应时间(ms)",
    "error_rate": "错误率(%)",
}


def _summary_dict(execution) -> Dict[str, Any]:
    """取执行的汇总（``PerformanceSummary``）为 dict。"""
    summary = getattr(execution, "summary", None)
    if summary is None:
        return {}
    if isinstance(summary, dict):
        return summary
    return {key: getattr(summary, key, None) for key in METRIC_KEYS}


def _compute_deltas(base_summary: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """相对基准执行的变化百分比（基准值为 0/缺失时记 None）。"""
    deltas: Dict[str, Optional[float]] = {}
    for key in METRIC_KEYS:
        base_val = base_summary.get(key)
        cur_val = summary.get(key)
        if isinstance(base_val, (int, float)) and base_val and isinstance(cur_val, (int, float)):
            deltas[key] = round((cur_val - base_val) / base_val * 100, 2)
        else:
            deltas[key] = None
    return deltas


def build_snapshot(executions: List[Any], reference_execution_id: Optional[int] = None) -> Dict[str, Any]:
    """构建对照快照（JSON 可序列化）。

    :param executions: 已按用户选择顺序排好的 ``PerformanceExecution`` 列表（≥2）
    :param reference_execution_id: 基准执行的 ``pk``；缺省用第一条
    """
    from .models import PerformanceMetric

    reference = executions[0]
    if reference_execution_id:
        for e in executions:
            if e.pk == reference_execution_id:
                reference = e
                break

    base_summary = _summary_dict(reference)
    items = []
    for execution in executions:
        summary = _summary_dict(execution)
        items.append({
            "id": execution.pk,
            "execution_id": execution.execution_id,
            "script_name": execution.script.name if execution.script else "",
            "status": execution.status,
            "verdict": execution.verdict,
            "sla_result": execution.sla_result,
            "created_at": execution.created_at.isoformat() if execution.created_at else None,
            "duration": execution.duration,
            "thread_count": execution.thread_count,
            "is_reference": execution.pk == reference.pk,
            "summary": {key: summary.get(key) for key in METRIC_KEYS},
            "delta_pct": _compute_deltas(base_summary, summary),
        })

    # 接口级对比：按请求名（sample_label）对齐各执行
    step_names: List[str] = []
    for execution in executions:
        for m in PerformanceMetric.objects.filter(execution=execution):
            if m.sample_label not in step_names:
                step_names.append(m.sample_label)

    step_rows = []
    for name in step_names:
        row = {"step_name": name, "values": []}
        for execution in executions:
            metric = PerformanceMetric.objects.filter(execution=execution, sample_label=name).first()
            row["values"].append({
                "execution_id": execution.execution_id,
                "throughput": metric.throughput if metric else None,
                "avg": metric.avg if metric else None,
                "p95": metric.p95 if metric else None,
                "error_rate": metric.error_rate if metric else None,
            })
        step_rows.append(row)

    return {
        "reference_execution_id": reference.pk,
        "reference_execution_no": reference.execution_id,
        "metric_keys": METRIC_KEYS,
        "metric_labels": METRIC_LABELS,
        "executions": items,
        "step_comparison": step_rows,
    }


def trim_snapshot_for_ai(snapshot: Dict[str, Any], max_chars: int = 3000) -> str:
    """压缩快照为文本矩阵：每执行一行核心指标 + 相对基准 Δ%。"""
    def fmt(value) -> str:
        return f"{value:.2f}" if isinstance(value, (int, float)) else "-"

    lines = [
        f"基准执行: {snapshot.get('reference_execution_no')}",
        "执行 | TPS | 平均RT | P90 | P95 | P99 | 错误率% | ΔTPS% | ΔP95% | Δ错误率%",
    ]
    for item in snapshot.get("executions", []):
        s = item.get("summary") or {}
        d = item.get("delta_pct") or {}
        lines.append(" | ".join([
            str(item.get("execution_id", "")),
            fmt(s.get("throughput")), fmt(s.get("avg_response_time")),
            fmt(s.get("p90")), fmt(s.get("p95")), fmt(s.get("p99")), fmt(s.get("error_rate")),
            fmt(d.get("throughput")), fmt(d.get("p95")), fmt(d.get("error_rate")),
        ]))

    step_rows = snapshot.get("step_comparison") or []
    if step_rows:
        lines.append("")
        lines.append("接口级对比（请求名 | 各执行 TPS/平均RT/P95/错误率%）:")
        for row in step_rows[:20]:
            vals = ["{}/{}/{}/{}".format(
                fmt(v.get("throughput")), fmt(v.get("avg")), fmt(v.get("p95")), fmt(v.get("error_rate")))
                for v in row.get("values", [])]
            lines.append(f"{row.get('step_name')}: " + "; ".join(vals))

    return "\n".join(lines)[:max_chars]


def analyze(snapshot: Dict[str, Any]) -> str:
    """调 LLM 做多轮对照分析，返回 Markdown 文本；无配置或失败时返回空串。"""
    try:
        import requests as http_requests

        from apps.requirement_analysis.models import AIModelConfig

        config = (AIModelConfig.objects.filter(is_active=True, role="writer").first()
                  or AIModelConfig.objects.filter(is_active=True).first())
        if not config:
            logger.info("无活跃 AI 模型配置，跳过多轮对照 AI 分析")
            return ""

        matrix = trim_snapshot_for_ai(snapshot)
        user_prompt = f"""你是一位性能测试专家。下面是同一压测脚本多轮执行的对照矩阵，请做横向对比分析。

{matrix}

请按以下格式用 Markdown 回答：
1. **稳定性结论**：多轮结果是否稳定？波动最大的是哪个指标、幅度多少？
2. **劣化/改善识别**：相对基准执行，哪些轮次明显劣化或改善，可能原因是什么？
3. **瓶颈定位**：结合接口级对比，指出最可疑的瓶颈接口。
4. **建议**：给出可执行的下一步验证或优化措施。

要求：简洁具体，关键数字必须引用上文实际值，不要泛泛而谈。"""

        base_url = (config.base_url or "").rstrip("/")
        if not base_url.endswith("/chat/completions"):
            base_url = base_url + "/chat/completions" if base_url.endswith("/v1") else base_url + "/v1/chat/completions"

        api_key = config.resolve_api_key() if hasattr(config, "resolve_api_key") else (config.api_key or "")
        resp = http_requests.post(
            base_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": config.model_name,
                "messages": [
                    {"role": "system", "content": "你是一位资深的性能测试工程师，擅长多轮压测结果横向对比与瓶颈定位。"},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": min(config.max_tokens or 4096, 4096),
                "temperature": config.temperature or 0.7,
                "top_p": config.top_p or 0.9,
                "stream": False,
            },
            timeout=120,
        )
        if not resp.ok:
            logger.warning("多轮对照 AI 分析请求失败 %s: %s", resp.status_code, resp.text[:300])
            return ""
        choices = (resp.json() or {}).get("choices") or []
        if choices:
            return choices[0].get("message", {}).get("content", "") or ""
        return ""
    except Exception as exc:
        logger.warning("多轮对照 AI 分析失败: %s", exc)
        return ""
