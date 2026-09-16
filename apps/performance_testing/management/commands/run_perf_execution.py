# -*- coding: utf-8 -*-
"""命令行触发一次压测执行（CI / 定时巡检用）。

使用方式：
    python manage.py run_perf_execution --script 7
    python manage.py run_perf_execution --script 7 --environment 3 --threads 20 --duration 120
    python manage.py run_perf_execution --script 7 --timeout 900

⚠️ 为什么默认「等待执行结束」：create_execution 起的是**守护线程**，
命令进程一退出线程就会被回收、执行永远停在 QUEUED。所以除非显式 --detach，
本命令都会阻塞到执行进入终态（--timeout 保护）。
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.performance_testing.models import (
    PerformanceEnvironment,
    PerformanceExecution,
    PerformanceScript,
)

TERMINAL = ("COMPLETED", "FAILED", "CANCELLED")


class Command(BaseCommand):
    help = "按脚本触发一次压测执行并等待结果"

    def add_arguments(self, parser):
        parser.add_argument("--script", type=int, required=True, help="性能脚本 ID")
        parser.add_argument("--environment", type=int, default=None, help="执行环境 ID（可选）")
        parser.add_argument("--threads", type=int, default=None, help="并发线程数（覆盖脚本默认）")
        parser.add_argument("--duration", type=int, default=None, help="持续时间秒（覆盖脚本默认）")
        parser.add_argument("--timeout", type=int, default=1800, help="等待终态的最长秒数（默认 1800）")
        parser.add_argument("--detach", action="store_true",
                            help="不等待（警告：命令退出会终止执行线程，执行会停在 QUEUED）")

    def handle(self, *args, **options):
        script = PerformanceScript.objects.filter(pk=options["script"]).first()
        if not script:
            self.stderr.write(self.style.ERROR(f"脚本不存在：{options['script']}"))
            raise SystemExit(2)

        environment = None
        if options["environment"]:
            environment = PerformanceEnvironment.objects.filter(pk=options["environment"]).first()
            if not environment:
                self.stderr.write(self.style.ERROR(f"环境不存在：{options['environment']}"))
                raise SystemExit(2)

        from apps.performance_testing.executor import create_execution

        self.stdout.write(
            f"触发执行：脚本《{script.name}》 引擎={script.engine} "
            f"环境={environment.name if environment else '（未指定）'} "
            f"并发={options['threads'] or script.thread_count} 时长={options['duration'] or script.duration}s"
        )
        try:
            execution = create_execution(
                script,
                created_by=None,
                thread_count=options["threads"],
                duration=options["duration"],
                environment=environment,
            )
        except ValueError as exc:
            self.stderr.write(self.style.ERROR(f"参数校验失败：{exc}"))
            raise SystemExit(2)

        self.stdout.write(f"执行 ID：#{execution.pk} {execution.execution_id}")

        if options["detach"]:
            self.stdout.write(self.style.WARNING(
                "已按 --detach 立即返回；请确保本进程保持存活，否则执行线程会被回收"
            ))
            return

        deadline = time.time() + max(30, options["timeout"])
        last_status = None
        while time.time() < deadline:
            time.sleep(2)
            execution.refresh_from_db()
            if execution.status != last_status:
                self.stdout.write(f"  状态：{execution.status}")
                last_status = execution.status
            if execution.status in TERMINAL:
                break
        else:
            self.stderr.write(self.style.ERROR("等待超时，执行可能仍在进行"))
            raise SystemExit(1)

        execution.refresh_from_db()
        verdict = execution.get_verdict_display() if execution.verdict else "-"
        sla = execution.get_sla_result_display() if execution.sla_result else "-"
        finished = f"，结束={execution.completed_at:%Y-%m-%d %H:%M:%S}" if execution.completed_at else ""
        self.stdout.write(
            f"完成：状态={execution.status} 验收判定={verdict} SLA={sla}{finished}"
        )
        if execution.error_message:
            self.stdout.write(self.style.WARNING(f"错误信息：{execution.error_message}"))

        if execution.status != "COMPLETED":
            raise SystemExit(1)
