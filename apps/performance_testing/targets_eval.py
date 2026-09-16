"""压测验收目标评估（perf_targets evaluation）。

与 SLA 评估（`sla.py`）的分工：
- SLA：基于 `sla_config` 阈值，判定执行过程中/结果是否「违规」（支持运行期熔断）
- 验收目标（本模块）：基于 `perf_targets`，判定执行结果是否「通过」（事后判定）

评估维度（`perf_targets` 形如
``{"max_p95_rt": 2000, "max_avg_rt": 1000, "min_tps": 100, "max_error_rate": 1.0}``）：

- ``max_p95_rt``：P95 响应时间上限（ms），任一步骤超过即 FAILED
- ``max_avg_rt``：平均响应时间上限（ms），任一步骤超过即 FAILED
- ``min_tps``：整体吞吐量下限（req/s），低于即 FAILED
- ``max_error_rate``：错误率上限（%），任一步骤超过即 FAILED
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

NOT_EVALUATED = "NOT_EVALUATED"
PASSED = "PASSED"
FAILED = "FAILED"


def evaluate_targets(perf_targets: Optional[Dict[str, Any]],
                     stats: Optional[List[Dict[str, Any]]],
                     summary: Optional[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
    """评估验收目标。

    :param perf_targets: 脚本的 perf_targets 字段
    :param stats: 逐请求指标列表（本模块对应 ``PerformanceMetric`` 序列化结果，
        字段用 ``sample_label`` / ``avg`` / ``p95`` / ``error_rate``；同时兼容
        开源版的 ``step_name`` / ``avg_response_time`` 命名）
    :param summary: 执行汇总（整体 TPS 取 ``throughput``，兼容 ``tps``）
    :return: ``(verdict, details)``
        - verdict: ``'PASSED'`` | ``'FAILED'`` | ``'NOT_EVALUATED'``
        - details: ``[{"step", "metric", "target", "actual", "unit", "result"}]``
    """
    if not perf_targets:
        return NOT_EVALUATED, []

    details: List[Dict[str, Any]] = []
    has_fail = False

    # --- 逐步骤检查 ---
    max_p95 = perf_targets.get("max_p95_rt")
    max_avg = perf_targets.get("max_avg_rt")
    max_err = perf_targets.get("max_error_rate")

    for s in (stats or []):
        step_name = s.get("sample_label") or s.get("step_name") or s.get("name") or "未知"

        if max_p95 is not None:
            actual = s.get("p95", 0) or 0
            ok = actual <= max_p95
            has_fail = has_fail or (not ok)
            details.append({
                "step": step_name, "metric": "P95响应时间",
                "target": max_p95, "actual": actual, "unit": "ms",
                "result": "PASS" if ok else "FAIL",
            })

        if max_avg is not None:
            actual = s.get("avg") if s.get("avg") is not None else (s.get("avg_response_time", 0) or 0)
            actual = actual or 0
            ok = actual <= max_avg
            has_fail = has_fail or (not ok)
            details.append({
                "step": step_name, "metric": "平均响应时间",
                "target": max_avg, "actual": actual, "unit": "ms",
                "result": "PASS" if ok else "FAIL",
            })

        if max_err is not None:
            actual = s.get("error_rate", 0) or 0
            ok = actual <= max_err
            has_fail = has_fail or (not ok)
            details.append({
                "step": step_name, "metric": "错误率",
                "target": max_err, "actual": actual, "unit": "%",
                "result": "PASS" if ok else "FAIL",
            })

    # --- 整体 TPS 检查 ---
    min_tps = perf_targets.get("min_tps")
    if min_tps is not None:
        summary = summary or {}
        actual = summary.get("throughput")
        if actual is None:
            actual = summary.get("tps", 0)
        actual = actual or 0
        ok = actual >= min_tps
        has_fail = has_fail or (not ok)
        details.append({
            "step": "(整体)", "metric": "TPS",
            "target": min_tps, "actual": actual, "unit": "req/s",
            "result": "PASS" if ok else "FAIL",
        })

    # 配置里存在键但阈值全为 None（如前端表单未填时保存的
    # {"max_p95_rt": None, ...}）时，没有任何可判定项：应与「未配置」同样视为
    # NOT_EVALUATED，否则空明细会被误判为「通过」（与 sla.evaluate 的保护对齐）。
    if not details:
        return NOT_EVALUATED, []

    return (FAILED if has_fail else PASSED), details
