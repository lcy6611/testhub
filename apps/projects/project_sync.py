# -*- coding: utf-8 -*-
"""项目跨模块自动同步模块。

在任一模块（core / api_testing / ui_automation / app_automation）创建、
更新或删除项目时，自动同步到其他所有模块，确保项目在全平台可见可用。

同步策略：
- 创建：在目标模块按名称查找，已存在则仅建映射，不存在则创建项目 + 映射
- 更新：通过 ProjectMapping 找到关联项目，传播 name / description / status
- 删除：级联删除所有关联模块项目 + 核心项目 + 映射记录
"""
import threading
import logging

from apps.projects.models import Project, ProjectMapping
from apps.api_testing.models import ApiProject
from apps.ui_automation.models import UiProject
from apps.app_automation.models import AppProject

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  递归保护：防止同步操作内部触发的 model 事件再次进入同步逻辑        #
# ------------------------------------------------------------------ #
_sync_local = threading.local()


def _is_syncing():
    return getattr(_sync_local, 'syncing', False)


def _set_syncing(value):
    _sync_local.syncing = value


# ------------------------------------------------------------------ #
#  状态映射：core <-> module                                         #
# ------------------------------------------------------------------ #
STATUS_TO_MODULE = {
    'active': 'IN_PROGRESS',
    'paused': 'NOT_STARTED',
    'completed': 'COMPLETED',
    'archived': 'COMPLETED',
}

STATUS_TO_CORE = {
    'NOT_STARTED': 'paused',
    'IN_PROGRESS': 'active',
    'COMPLETED': 'completed',
}

# ------------------------------------------------------------------ #
#  模块配置                                                          #
# ------------------------------------------------------------------ #
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

ALL_MODULES = list(MODULE_CONFIGS.keys())


# ------------------------------------------------------------------ #
#  辅助函数                                                          #
# ------------------------------------------------------------------ #
def _ensure_mapping(core_project, module, external_id, external_name):
    """创建或更新 ProjectMapping 记录。"""
    obj, _ = ProjectMapping.objects.update_or_create(
        module=module,
        external_project_id=external_id,
        defaults={
            'project': core_project,
            'external_project_name': external_name,
            'auto_matched': True,
        },
    )
    return obj


def _resolve_core_project(source_instance, source_module):
    """根据来源实例和模块，找到（或创建）核心 Project。"""
    if source_module == 'core':
        return source_instance

    # 优先通过 mapping 查找
    mapping = ProjectMapping.objects.filter(
        module=source_module,
        external_project_id=source_instance.id,
    ).first()
    if mapping:
        return mapping.project

    # 按名称兜底查找
    core = Project.objects.filter(name=source_instance.name).first()
    if core:
        return core

    # 都没有 → 创建核心项目
    core_status = STATUS_TO_CORE.get(
        getattr(source_instance, 'status', 'IN_PROGRESS'), 'active'
    )
    core = Project.objects.create(
        name=source_instance.name,
        description=getattr(source_instance, 'description', '') or '',
        status=core_status,
        owner=getattr(source_instance, 'owner', None),
    )
    return core


# ------------------------------------------------------------------ #
#  对外接口                                                          #
# ------------------------------------------------------------------ #
def auto_sync_project_create(source_instance, source_module):
    """项目创建后：在所有其他模块创建对应项目 + 映射。"""
    if _is_syncing():
        return
    _set_syncing(True)
    try:
        name = source_instance.name
        description = getattr(source_instance, 'description', '') or ''
        owner = getattr(source_instance, 'owner', None)
        source_status = getattr(source_instance, 'status', 'active')

        # 1. 确定核心项目
        core_project = _resolve_core_project(source_instance, source_module)

        # 2. 在每个模块创建/关联
        for mod_name, mod_config in MODULE_CONFIGS.items():
            model = mod_config['model']

            if mod_name == source_module:
                # 来源模块：仅确保映射存在
                _ensure_mapping(core_project, mod_name, source_instance.id, source_instance.name)
                continue

            # 按名称查找是否已存在
            existing = model.objects.filter(name=name).first()
            if existing:
                _ensure_mapping(core_project, mod_name, existing.id, existing.name)
                continue

            # 创建新项目
            mod_status = STATUS_TO_MODULE.get(source_status, 'IN_PROGRESS')
            create_kwargs = {
                'name': name,
                'description': description,
                'owner': owner,
                **mod_config['defaults'],
            }
            create_kwargs['status'] = mod_status
            new_obj = model.objects.create(**create_kwargs)
            _ensure_mapping(core_project, mod_name, new_obj.id, new_obj.name)

    except Exception as e:
        logger.error('[project_sync] create error: %s', e, exc_info=True)
    finally:
        _set_syncing(False)


def auto_sync_project_update(source_instance, source_module):
    """项目更新后：将 name/description/status 传播到所有关联项目。"""
    if _is_syncing():
        return
    _set_syncing(True)
    try:
        name = source_instance.name
        description = getattr(source_instance, 'description', '') or ''
        source_status = getattr(source_instance, 'status', '')

        core_project = _resolve_core_project(source_instance, source_module)

        # 如果来源是模块，先更新核心项目
        if source_module != 'core':
            core_status = STATUS_TO_CORE.get(source_status, core_project.status)
            Project.objects.filter(id=core_project.id).update(
                name=name,
                description=description,
                status=core_status,
            )

        # 传播到所有关联模块项目
        mappings = ProjectMapping.objects.filter(project=core_project)
        for mapping in mappings:
            mod_name = mapping.module

            # 更新映射冗余名称
            if mapping.external_project_name != name:
                mapping.external_project_name = name
                mapping.save(update_fields=['external_project_name'])

            if mod_name == source_module:
                continue
            if mod_name not in MODULE_CONFIGS:
                continue

            model = MODULE_CONFIGS[mod_name]['model']
            try:
                obj = model.objects.get(id=mapping.external_project_id)
                # 状态转换：如果来源是 core，用 STATUS_TO_MODULE；否则用 core 的状态转
                if source_module == 'core':
                    mod_status = STATUS_TO_MODULE.get(source_status, obj.status)
                else:
                    mod_status = STATUS_TO_MODULE.get(core_project.status, obj.status)
                obj.name = name
                obj.description = description
                obj.status = mod_status
                obj.save(update_fields=['name', 'description', 'status', 'updated_at'])
            except model.DoesNotExist:
                logger.warning(
                    '[project_sync] %s project #%s not found during update',
                    mod_name, mapping.external_project_id,
                )

    except Exception as e:
        logger.error('[project_sync] update error: %s', e, exc_info=True)
    finally:
        _set_syncing(False)


def auto_sync_project_delete(source_instance, source_module):
    """项目删除时：级联删除所有关联模块项目 + 核心项目 + 映射。

    注意：此函数会删除除来源实例以外的所有关联项目。
    来源实例本身的删除由调用方（ViewSet perform_destroy）负责。
    """
    if _is_syncing():
        return
    _set_syncing(True)
    try:
        # 找到核心项目
        if source_module == 'core':
            core_project = source_instance
        else:
            mapping = ProjectMapping.objects.filter(
                module=source_module,
                external_project_id=source_instance.id,
            ).first()
            if mapping:
                core_project = mapping.project
            else:
                # 按名称兜底
                core_project = Project.objects.filter(name=source_instance.name).first()
                if not core_project:
                    return

        # 收集所有映射
        all_mappings = list(ProjectMapping.objects.filter(project=core_project))

        # 删除所有关联模块项目（跳过来源模块）
        for mapping in all_mappings:
            if mapping.module == source_module:
                continue
            if mapping.module not in MODULE_CONFIGS:
                continue
            model = MODULE_CONFIGS[mapping.module]['model']
            try:
                obj = model.objects.get(id=mapping.external_project_id)
                obj.delete()
            except model.DoesNotExist:
                pass

        # 删除所有映射记录
        ProjectMapping.objects.filter(project=core_project).delete()

        # 如果来源是模块，删除核心项目
        if source_module != 'core':
            try:
                core_project.delete()
            except Exception as e:
                logger.warning('[project_sync] Failed to delete core project: %s', e)

    except Exception as e:
        logger.error('[project_sync] delete error: %s', e, exc_info=True)
    finally:
        _set_syncing(False)
