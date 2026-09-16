# -*- coding: utf-8 -*-
"""重算历史性能执行的验收判定（verdict / verdict_details / sla_result / sla_detail）。

适用场景：
- 修复了 ``targets_eval.evaluate_targets`` 的判定逻辑（如空壳 perf_targets 误判 PASSED），
  需要把已落库的历史执行按新逻辑重新评估，而不必重新跑压测。
- 脚本的 ``perf_targets`` / ``sla_config`` 被修改后，想让历史报告同步最新判定口径。

重算完全基于已落库的数据（``perf_summary`` + ``perf_metric`` + 脚本配置快照），
不会重新执行 JMeter，也不会改动除四个判定字段外的任何内容。

使用方式：
    python manage.py recompute_perf_verdicts                 # 重算所有「已完成且有汇总」的执行
    python manage.py recompute_perf_verdicts --dry-run       # 只打印将改动的执行，不写库
    python manage.py recompute_perf_verdicts --execution PE-20260901-0001   # 只重算指定执行ID
    python manage.py recompute_perf_verdicts --pk 59         # 只重算指定主键
    python manage.py recompute_perf_verdicts --all-status    # 包含非 COMPLETED 的执行
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError

from apps.performance_testing.acceptance import evaluate_acceptance
from apps.performance_testing.models import PerformanceExecution


def _build_summary_dict(execution: PerformanceExecution) -> Optional[Dict[str, Any]]:
    """从已落库的汇总构造 evaluate_acceptance 所需的 summary。无汇总则返回 None。"""
    summary = getattr(execution, "summary", None)
    if not summary:
        return None
    return {
        "avg_response_time": summary.avg_response_time,
        "p90": summary.p90,
        "p95": summary.p95,
        "p99": summary.p99,
        "error_rate": summary.error_rate,
        "throughput": summary.throughput,
    }


def _build_stats_list(execution: PerformanceExecution) -> List[Dict[str, Any]]:
    """从逐请求指标构造 evaluate_acceptance 所需的 stats。"""
    stats: List[Dict[str, Any]] = []
    for m in execution.metrics.all():
        stats.append({
            "sample_label": m.sample_label,
            "sample_count": m.sample_count,
            "avg": m.avg,
            "avg_response_time": m.avg,
            "p95": m.p95,
            "error_rate": m.error_rate,
            "throughput": m.throughput,
        })
    return stats


def _recompute_one(execution: PerformanceExecution) -> Optional[Dict[str, Any]]:
    """重算单条执行的判定字段；无可重算数据时返回 None。"""
    summary = _build_summary_dict(execution)
    if summary is None:
        return None
    stats = _build_stats_list(execution)
    script = execution.script
    return evaluate_acceptance(
        getattr(script, "perf_targets", None),
        getattr(script, "sla_config", None),
        summary,
        stats,
    )


class Command(BaseCommand):
    help = "按新逻辑重算历史性能执行的验收判定（不重新跑压测）"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="只打印将改动的执行，不写库")
        parser.add_argument("--execution", type=str, default=None,
                            help="只重算指定 execution_id（如 PE-20260901-0001）")
        parser.add_argument("--pk", type=int, default=None,
                            help="只重算指定主键 id")
        parser.add_argument("--all-status", action="store_true",
                            help="包含非 COMPLETED 的执行（默认仅 COMPLETED）")

    def handle(self, *args, **options):
        qs = PerformanceExecution.objects.all()
        if options["execution"]:
            qs = qs.filter(execution_id=options["execution"])
        elif options["pk"] is not None:
            qs = qs.filter(pk=options["pk"])
        elif not options["all_status"]:
            qs = qs.filter(status="COMPLETED")

        if not qs.exists():
            raise CommandError("没有匹配的执行记录")

        dry_run = options["dry_run"]
        changed = 0
        skipped = 0
        for execution in qs.select_related("script", "summary").prefetch_related("metrics"):
            fields = _recompute_one(execution)
            if fields is None:
                skipped += 1
                self.stdout.write(self.style.WARNING(
                    f"  跳过 {execution.execution_id}（无汇总数据，未跑或数据缺失）"))
                continue

            old = {
                "verdict": execution.verdict,
                "sla_result": execution.sla_result,
            }
            new = {
                "verdict": fields["verdict"],
                "sla_result": fields["sla_result"],
            }
            if old == new and execution.verdict_details == fields["verdict_details"] \
                    and execution.sla_detail == fields["sla_detail"]:
                self.stdout.write(f"  无需变更 {execution.execution_id} "
                                  f"(verdict={old['verdict']}, sla={old['sla_result']})")
                continue

            changed += 1
            self.stdout.write(self.style.SUCCESS(
                f"  {'[DRY-RUN] ' if dry_run else ''}重算 {execution.execution_id} "
                f"(#{execution.pk}): verdict {old['verdict']} -> {new['verdict']}, "
                f"sla {old['sla_result']} -> {new['sla_result']}"))
            if not dry_run:
                PerformanceExecution.objects.filter(pk=execution.pk).update(**fields)

        verb = "将重算" if dry_run else "已重算"
        self.stdout.write(self.style.SUCCESS(
            f"\n完成：{verb} {changed} 条，跳过 {skipped} 条（无汇总数据）"))
