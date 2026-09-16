# -*- coding: utf-8 -*-
"""压测数据清理：按保留天数删除历史执行记录及其产物目录。

使用方式：
    python manage.py cleanup_perf_data --dry-run          # 先看会删什么
    python manage.py cleanup_perf_data --days 30
    python manage.py cleanup_perf_data --days 7 --include-baseline-sources

安全约定（默认保守）：
- 运行中（QUEUED/RUNNING）的执行**永不删除**；
- 作为性能基线来源的执行**默认跳过**（--include-baseline-sources 可强制删除，
  但会让对应基线丢失来源追溯，删除后 baseline.execution 置空）；
- 删除执行记录前先清理 media/performance/<execution_id>/ 产物目录。
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.performance_testing.cleanup import cleanup_execution_artifacts
from apps.performance_testing.models import PerformanceBaseline, PerformanceExecution

DEFAULT_RETENTION_DAYS = 30
ACTIVE_STATUSES = ("QUEUED", "RUNNING")


class Command(BaseCommand):
    help = "按保留天数清理历史压测执行记录与产物"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None,
                            help=f"保留天数（默认取 settings.PERFORMANCE_RETENTION_DAYS，否则 {DEFAULT_RETENTION_DAYS}）")
        parser.add_argument("--dry-run", action="store_true", help="只统计不删除")
        parser.add_argument("--include-baseline-sources", action="store_true",
                            help="连基线来源执行一起删（会让基线丢失来源追溯）")

    def handle(self, *args, **options):
        from django.conf import settings

        days = options["days"]
        if days is None:
            days = int(getattr(settings, "PERFORMANCE_RETENTION_DAYS", DEFAULT_RETENTION_DAYS) or DEFAULT_RETENTION_DAYS)
        if days < 0:
            self.stderr.write(self.style.ERROR("--days 不能为负数"))
            raise SystemExit(2)

        cutoff = timezone.now() - timedelta(days=days)
        candidates = PerformanceExecution.objects.filter(
            Q(completed_at__lt=cutoff) | Q(completed_at__isnull=True, created_at__lt=cutoff)
        ).exclude(status__in=ACTIVE_STATUSES)

        baseline_source_ids = set(
            PerformanceBaseline.objects.exclude(execution__isnull=True).values_list("execution_id", flat=True)
        )
        if not options["include_baseline_sources"]:
            candidates = candidates.exclude(pk__in=baseline_source_ids)

        total = candidates.count()
        self.stdout.write(
            f"保留 {days} 天（截止 {cutoff:%Y-%m-%d %H:%M}）：命中 {total} 条待清理执行"
        )
        if baseline_source_ids and not options["include_baseline_sources"]:
            self.stdout.write(f"  已跳过 {len(baseline_source_ids)} 条基线来源执行（--include-baseline-sources 可强制删除）")

        if options["dry_run"]:
            for ex in candidates.order_by("created_at")[:20]:
                self.stdout.write(f"  [dry-run] #{ex.pk} {ex.execution_id} {ex.status} "
                                  f"{ex.completed_at or ex.created_at:%Y-%m-%d %H:%M}")
            if total > 20:
                self.stdout.write(f"  ... 其余 {total - 20} 条略")
            self.stdout.write(self.style.WARNING("dry-run 模式未删除任何数据"))
            return

        removed_artifacts = 0
        for ex in candidates.iterator():
            if cleanup_execution_artifacts(ex):
                removed_artifacts += 1
            ex.delete()

        self.stdout.write(self.style.SUCCESS(
            f"已删除 {total} 条执行记录，清理 {removed_artifacts} 个产物目录"
        ))
