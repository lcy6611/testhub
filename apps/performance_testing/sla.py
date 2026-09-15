"""SLA 阈值判定（借鉴 k6 thresholds）+ 运行期熔断检测。

与验收目标（`targets_eval.py`）的分工：
- **SLA**（本模块）：基于脚本的 `sla_config` 阈值，判定执行结果是否「违规」，并支持运行期熔断中止；
- **验收目标**（targets_eval）：基于脚本的 `perf_targets`，判定执行结果是否「通过」。

SLA 配置形如::

    {
      "enabled": true,
      "abort_on_breach": false,     # 运行期是否熔断中止
      "breach_window": 10,          # 连续违规窗口（秒）
      "thresholds": {
        "avg_response_time": 800,   # 平均响应时间上限(ms)
        "p95_response_time": 2000,  # P95 上限(ms)
        "error_rate": 1.0,          # 错误率上限(%)
        "min_tps": 100              # 吞吐量下限(req/s)
      }
    }
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

NOT_EVALUATED = "NOT_EVALUATED"
PASSED = "PASSED"
FAILED = "FAILED"

#: 配置 key -> (汇总字段名, 比较方向, 展示名)
#: direction = 'max' 表示实际值「超过」阈值即失败；'min' 表示「低于」阈值即失败
SLA_METRICS = {
    # 字段名对齐本模块 PerformanceSummary
    "avg_response_time": ("avg_response_time", "max", "平均响应时间(ms)"),
    "p90_response_time": ("p90", "max", "P90响应时间(ms)"),
    "p95_response_time": ("p95", "max", "P95响应时间(ms)"),
    "p99_response_time": ("p99", "max", "P99响应时间(ms)"),
    "error_rate": ("error_rate", "max", "错误率(%)"),
    "min_tps": ("throughput", "min", "TPS"),
}


def evaluate(sla_config: Optional[Dict[str, Any]], summary: Optional[Dict[str, Any]]
             ) -> Tuple[str, List[Dict[str, Any]]]:
    """根据 SLA 配置评估汇总指标（事后判定）。

    返回 ``(result, detail)``：

    - ``result`` ∈ ``PASSED`` / ``FAILED`` / ``NOT_EVALUATED``
    - ``detail`` = ``[{metric, label, threshold, actual, direction, comparator, passed}]``
    """
    sla_config = sla_config or {}
    if not sla_config.get("enabled"):
        return NOT_EVALUATED, []

    thresholds = sla_config.get("thresholds") or {}
    detail: List[Dict[str, Any]] = []
    all_passed = True

    for key, threshold in thresholds.items():
        meta = SLA_METRICS.get(key)
        if not meta:
            continue
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            continue
        # 0 视为未设置（error_rate=0 是合法的严格要求，单独放行）
        if threshold == 0 and key != "error_rate":
            continue
        field, direction, label = meta
        actual = float((summary or {}).get(field) or 0)
        passed = actual <= threshold if direction == "max" else actual >= threshold
        if not passed:
            all_passed = False
        detail.append({
            "metric": key,
            "label": label,
            "threshold": threshold,
            "actual": round(actual, 2),
            "direction": direction,
            "comparator": "≤" if direction == "max" else "≥",
            "passed": passed,
        })

    if not detail:
        return NOT_EVALUATED, []
    return (PASSED if all_passed else FAILED), detail


class BreachDetector:
    """运行期 SLA 熔断检测：连续 N 个采样周期违规才触发，避免抖动误判。"""

    def __init__(self, sla_config: Optional[Dict[str, Any]], sample_interval: int = 1):
        self.config = sla_config or {}
        self.enabled = bool(self.config.get("enabled")) and bool(self.config.get("abort_on_breach"))
        window_seconds = self.config.get("breach_window") or 10
        self.required = max(1, int(round(window_seconds / max(sample_interval, 1))))
        self.streak = 0
        self.reason = ""

    def check(self, sample: Dict[str, Any]) -> bool:
        """传入一个采样点，返回是否应该熔断中止。"""
        if not self.enabled:
            return False

        def _fmt(value) -> str:
            # 整数展示不带多余的 .0，长小数保留 2 位，便于人读
            num = round(float(value), 2)
            return str(int(num)) if num == int(num) else f"{num:g}"

        thresholds = self.config.get("thresholds") or {}
        breached = []
        for key, threshold in thresholds.items():
            meta = SLA_METRICS.get(key)
            if not meta:
                continue
            field, direction, label = meta
            if field not in sample:
                continue
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                continue
            if threshold <= 0 and key != "error_rate":
                continue
            actual = float(sample.get(field) or 0)
            # TPS 为 0 的采样点（如加压阶段刚开始）不参与 min 类判定，避免误熔断
            if direction == "min" and actual <= 0:
                continue
            if (direction == "max" and actual > threshold) or (direction == "min" and actual < threshold):
                breached.append(f"{label} 实际 {_fmt(actual)} 超出阈值 {_fmt(threshold)}")

        if breached:
            self.streak += 1
            self.reason = "；".join(breached)
        else:
            self.streak = 0
            self.reason = ""

        return self.streak >= self.required
