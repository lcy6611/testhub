import logging

logger = logging.getLogger(__name__)

_REGISTRY = {}

# 模块中文名（用于统一视图展示）
MODULE_LABELS = {}


def register_module(module_key, model_class, get_task, execute, label=None):
    """注册一个模块的调度执行器。

    - model_class: 模块定时任务模型类（用于删除绑定时判断 DoesNotExist）
    - get_task(task_id): 按 id 取回任务对象
    - execute(task_id): 真正执行任务（内部自行处理日志/通知/统计）
    """
    _REGISTRY[module_key] = {
        'model': model_class,
        'get_task': get_task,
        'execute': execute,
    }
    if label:
        MODULE_LABELS[module_key] = label


def get_handler(module_key):
    return _REGISTRY.get(module_key)


def list_modules():
    return [{'key': k, 'label': MODULE_LABELS.get(k, k)} for k in _REGISTRY]


def register_builtin():
    """注册各模块的执行器（实际执行逻辑在模块内部，这里只做转发）。"""
    # ---- 接口测试 ----
    from apps.api_testing.models import ScheduledTask, TaskExecutionLog
    from apps.api_testing.views import ScheduledTaskViewSet

    def _get(task_id):
        return ScheduledTask.objects.get(id=task_id)

    def _exec(task_id):
        task = ScheduledTask.objects.get(id=task_id)
        log = TaskExecutionLog.objects.create(task=task, status='PENDING')
        # 复用已有执行逻辑（含通知/统计/线程执行）
        ScheduledTaskViewSet()._execute_task_async(task, log)

    register_module('api_testing', ScheduledTask, _get, _exec, label='接口测试')

    # ---- UI自动化 / APP自动化 / 性能测试 在后续步骤注册 ----
