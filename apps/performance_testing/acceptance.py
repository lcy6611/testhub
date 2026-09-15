"""验收判定聚合：一次产出 SLA 判定 + 验收目标判定。

执行收尾（`executor.py`）与对照报告（`compare_report`）都只要「给数据拿结论」，
因此把两个判定收敛到一个入口，避免调用方各自去拼字段。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import sla as sla_module
from . import targets_eval


def evaluate_acceptance(perf_targets: Optional[Dict[str, Any]],
                        sla_config: Optional[Dict[str, Any]],
                        summary: Optional[Dict[str, Any]],
                        stats: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """同时执行 SLA 判定与验收目标判定。

    :return: 可直接 update 到 ``PerformanceExecution`` 的字段 dict：
        ``{sla_result, sla_detail, verdict, verdict_details}``
    """
    sla_result, sla_detail = sla_module.evaluate(sla_config, summary)
    verdict, verdict_details = targets_eval.evaluate_targets(perf_targets, stats, summary)
    return {
        "sla_result": sla_result,
        "sla_detail": sla_detail,
        "verdict": verdict,
        "verdict_details": verdict_details,
    }
