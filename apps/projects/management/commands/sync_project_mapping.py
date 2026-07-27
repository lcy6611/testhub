"""按项目名自动匹配核心项目 ↔ 各自动化模块项目，写入 ProjectMapping 表。

匹配规则：
  1. 名称完全相同（精确匹配，大小写敏感）
  2. 核心项目名称是模块项目名称的子串，或反过来（模糊匹配）
  3. 已有手动映射（auto_matched=False）不会被覆盖
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.projects.models import Project, ProjectMapping


class Command(BaseCommand):
    help = "按项目名自动匹配核心项目与 UI/API/APP 模块项目"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="只打印匹配结果，不写入数据库",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        module_configs = [
            ("ui_automation", "apps.ui_automation.models", "UiProject"),
            ("api_testing", "apps.api_testing.models", "ApiProject"),
            ("app_automation", "apps.app_automation.models", "AppProject"),
        ]

        core_projects = list(Project.objects.all())
        if not core_projects:
            self.stdout.write(self.style.WARNING("核心项目表为空，无数据可匹配"))
            return

        total_created = 0
        total_skipped = 0

        for module, model_path, model_name in module_configs:
            try:
                import importlib
                mod = importlib.import_module(model_path)
                ExternalModel = getattr(mod, model_name)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"无法导入 {model_path}.{model_name}: {exc}"))
                continue

            external_projects = list(ExternalModel.objects.all().values("id", "name"))
            self.stdout.write(f"\n=== {module} ({model_name}: {len(external_projects)} 个) ===")

            for ext_p in external_projects:
                ext_name = ext_p["name"].strip()
                matched_core = None
                match_type = ""

                # 规则1：精确匹配
                for cp in core_projects:
                    if cp.name.strip() == ext_name:
                        matched_core = cp
                        match_type = "精确"
                        break

                # 规则2：子串模糊匹配
                if not matched_core:
                    for cp in core_projects:
                        cp_name = cp.name.strip()
                        if cp_name and ext_name and (cp_name in ext_name or ext_name in cp_name):
                            matched_core = cp
                            match_type = "模糊"
                            break

                # 规则3：核心项目只有1个时，全部关联（兜底）
                if not matched_core and len(core_projects) == 1:
                    matched_core = core_projects[0]
                    match_type = "唯一项目"

                if not matched_core:
                    self.stdout.write(
                        f"  ✗ #{ext_p['id']} {ext_name} → 无匹配"
                    )
                    total_skipped += 1
                    continue

                # 检查是否已有映射（非自动匹配的不覆盖）
                existing = ProjectMapping.objects.filter(
                    module=module, external_project_id=ext_p["id"],
                ).first()

                if existing:
                    if existing.auto_matched:
                        # 更新关联
                        if existing.project_id != matched_core.id:
                            self.stdout.write(
                                f"  ↻ #{ext_p['id']} {ext_name} → {matched_core.name} ({match_type}, 更新)"
                            )
                            if not dry_run:
                                existing.project = matched_core
                                existing.external_project_name = ext_name
                                existing.save()
                        else:
                            self.stdout.write(
                                f"  = #{ext_p['id']} {ext_name} → {matched_core.name} ({match_type}, 已存在)"
                            )
                    else:
                        self.stdout.write(
                            f"  ⚠ #{ext_p['id']} {ext_name} → {existing.project.name} (手动映射, 跳过)"
                        )
                    continue

                self.stdout.write(
                    f"  ✓ #{ext_p['id']} {ext_name} → {matched_core.name} ({match_type}, 新建)"
                )
                if not dry_run:
                    ProjectMapping.objects.create(
                        project=matched_core,
                        module=module,
                        external_project_id=ext_p["id"],
                        external_project_name=ext_name,
                        auto_matched=True,
                    )
                total_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n完成: 新建 {total_created} 条映射, 跳过 {total_skipped} 条无匹配"
                + (" (dry-run)" if dry_run else "")
            )
        )
