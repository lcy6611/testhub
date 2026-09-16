# -*- coding: utf-8 -*-
"""压测引擎自检：打印三个引擎的可用性与版本。

使用方式：
    python manage.py check_perf_engines
    python manage.py check_perf_engines --strict   # 有不可用引擎时以退出码 1 结束
    python manage.py check_perf_engines --json     # 机器可读输出
"""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "自检压测引擎（BUILTIN / LOCUST / JMETER）的可用性与版本"

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="存在不可用引擎时以退出码 1 结束")
        parser.add_argument("--json", action="store_true", help="以 JSON 输出（便于脚本消费）")

    def handle(self, *args, **options):
        from apps.performance_testing import engines

        status = engines.engine_status(force=True)

        if options["json"]:
            self.stdout.write(json.dumps({"engines": status}, ensure_ascii=False, indent=2))
        else:
            self.stdout.write("压测引擎自检：\n")
            for item in status:
                flag = "可用" if item["available"] else "不可用"
                mark = "✓" if item["available"] else "✗"
                default = "（默认）" if item.get("default") else ""
                self.stdout.write(
                    f"  {mark} {item['name']:<8}{default:<6} {flag:<4} version={item['version']}"
                )
                self.stdout.write(f"      {item['description']}")
            unavailable = [i["name"] for i in status if not i["available"]]
            self.stdout.write("")
            if unavailable:
                self.stdout.write(self.style.WARNING(
                    f"不可用引擎：{', '.join(unavailable)}（不影响其他引擎使用）"
                ))
            else:
                self.stdout.write(self.style.SUCCESS("全部引擎可用"))

        if options["strict"] and any(not i["available"] for i in status):
            raise SystemExit(1)
