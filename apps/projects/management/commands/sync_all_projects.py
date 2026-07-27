# -*- coding: utf-8 -*-
"""回填管理命令：为已有项目建立跨模块映射 + 补建缺失的模块项目。

使用方式：
    python manage.py sync_all_projects           # 执行回填
    python manage.py sync_all_projects --dry-run  # 仅预览不执行
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.projects.models import Project, ProjectMapping
from apps.api_testing.models import ApiProject
from apps.ui_automation.models import UiProject
from apps.app_automation.models import AppProject


MODULE_CONFIGS = {
    'api_testing': {
        'model': ApiProject,
        'defaults': {'project_type': 'HTTP', 'status': 'IN_PROGRESS'},
    },
    'ui_automation': {
        'model': UiProject,
        'defaults': {'base_url': 'http://localhost', 'status': 'IN_PROGRESS'},
    },
    'app_automation': {
        'model': AppProject,
        'defaults': {'status': 'IN_PROGRESS'},
    },
}

STATUS_TO_MODULE = {
    'active': 'IN_PROGRESS',
    'paused': 'NOT_STARTED',
    'completed': 'COMPLETED',
    'archived': 'COMPLETED',
}


class Command(BaseCommand):
    help = '为已有项目建立跨模块映射，补建缺失的模块项目'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='仅输出将要执行的操作，不实际修改数据',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        stats = {'mapping_created': 0, 'project_created': 0, 'skipped': 0}

        # 1. 以 core Project 为基准，补建缺失的模块项目
        core_projects = Project.objects.all()
        self.stdout.write(f'\n=== 处理 {core_projects.count()} 个核心项目 ===')

        for core in core_projects:
            self.stdout.write(f'\n核心项目: {core.name} (id={core.id})')

            for mod_name, mod_config in MODULE_CONFIGS.items():
                model = mod_config['model']

                # 检查映射是否已存在
                existing_mapping = ProjectMapping.objects.filter(
                    project=core, module=mod_name,
                ).first()

                if existing_mapping:
                    # 验证映射指向的项目是否存在
                    try:
                        model.objects.get(id=existing_mapping.external_project_id)
                        self.stdout.write(f'  [{mod_name}] 映射已存在 ✓')
                        continue
                    except model.DoesNotExist:
                        self.stdout.write(f'  [{mod_name}] 映射存在但项目已丢失，重建...')
                        existing_mapping.delete()

                # 按名称查找模块项目
                found = model.objects.filter(name=core.name).first()
                if found:
                    if not dry_run:
                        ProjectMapping.objects.update_or_create(
                            module=mod_name,
                            external_project_id=found.id,
                            defaults={
                                'project': core,
                                'external_project_name': found.name,
                                'auto_matched': True,
                            },
                        )
                    stats['mapping_created'] += 1
                    self.stdout.write(f'  [{mod_name}] 关联已有项目 id={found.id}')
                else:
                    # 创建新项目
                    if not dry_run:
                        mod_status = STATUS_TO_MODULE.get(core.status, 'IN_PROGRESS')
                        create_kwargs = {
                            'name': core.name,
                            'description': core.description or '',
                            'owner': core.owner,
                            **mod_config['defaults'],
                        }
                        create_kwargs['status'] = mod_status
                        new_obj = model.objects.create(**create_kwargs)
                        ProjectMapping.objects.update_or_create(
                            module=mod_name,
                            external_project_id=new_obj.id,
                            defaults={
                                'project': core,
                                'external_project_name': new_obj.name,
                                'auto_matched': True,
                            },
                        )
                    stats['project_created'] += 1
                    self.stdout.write(f'  [{mod_name}] 新建项目')

        # 2. 处理没有映射的模块项目（按名称匹配 core）
        self.stdout.write(f'\n=== 检查未映射的模块项目 ===')
        for mod_name, mod_config in MODULE_CONFIGS.items():
            model = mod_config['model']
            # 找到没有映射的模块项目
            mapped_ids = ProjectMapping.objects.filter(
                module=mod_name,
            ).values_list('external_project_id', flat=True)
            unmapped = model.objects.exclude(id__in=mapped_ids)

            for obj in unmapped:
                self.stdout.write(f'\n未映射 {mod_name} 项目: {obj.name} (id={obj.id})')
                # 按名称查找 core
                core = Project.objects.filter(name=obj.name).first()
                if core:
                    if not dry_run:
                        ProjectMapping.objects.update_or_create(
                            module=mod_name,
                            external_project_id=obj.id,
                            defaults={
                                'project': core,
                                'external_project_name': obj.name,
                                'auto_matched': True,
                            },
                        )
                    stats['mapping_created'] += 1
                    self.stdout.write(f'  关联到核心项目 id={core.id}')
                else:
                    # 创建核心项目 + 其他模块项目
                    status_map = {
                        'NOT_STARTED': 'paused',
                        'IN_PROGRESS': 'active',
                        'COMPLETED': 'completed',
                    }
                    core_status = status_map.get(obj.status, 'active')
                    if not dry_run:
                        new_core = Project.objects.create(
                            name=obj.name,
                            description=obj.description or '',
                            status=core_status,
                            owner=obj.owner,
                        )
                        ProjectMapping.objects.update_or_create(
                            module=mod_name,
                            external_project_id=obj.id,
                            defaults={
                                'project': new_core,
                                'external_project_name': obj.name,
                                'auto_matched': True,
                            },
                        )
                        # 同时在其他模块创建对应项目
                        for other_mod, other_config in MODULE_CONFIGS.items():
                            if other_mod == mod_name:
                                continue
                            other_model = other_config['model']
                            other_existing = other_model.objects.filter(name=obj.name).first()
                            if other_existing:
                                ProjectMapping.objects.update_or_create(
                                    module=other_mod,
                                    external_project_id=other_existing.id,
                                    defaults={
                                        'project': new_core,
                                        'external_project_name': other_existing.name,
                                        'auto_matched': True,
                                    },
                                )
                            else:
                                other_status = STATUS_TO_MODULE.get(core_status, 'IN_PROGRESS')
                                other_kwargs = {
                                    'name': obj.name,
                                    'description': obj.description or '',
                                    'owner': obj.owner,
                                    **other_config['defaults'],
                                }
                                other_kwargs['status'] = other_status
                                other_obj = other_model.objects.create(**other_kwargs)
                                ProjectMapping.objects.update_or_create(
                                    module=other_mod,
                                    external_project_id=other_obj.id,
                                    defaults={
                                        'project': new_core,
                                        'external_project_name': other_obj.name,
                                        'auto_matched': True,
                                    },
                                )
                                stats['project_created'] += 1
                    stats['project_created'] += 1
                    self.stdout.write(f'  新建核心项目 + 其他模块项目')

        self.stdout.write(f'\n=== 完成 ===')
        self.stdout.write(f'映射创建: {stats["mapping_created"]}')
        self.stdout.write(f'项目创建: {stats["project_created"]}')
        if dry_run:
            self.stdout.write('(dry-run 模式，未实际修改数据)')
