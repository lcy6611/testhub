from rest_framework import permissions, viewsets
from rest_framework.response import Response

from apps.scheduler.models import ScheduleBinding
from apps.scheduler.registry import list_modules


class ScheduleOverviewViewSet(viewsets.ViewSet):
    """统一展示各模块定时任务及其调度状态（只读概览）。"""

    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        modules = list_modules()
        out = []
        for m in modules:
            bindings = ScheduleBinding.objects.filter(module=m['key'])
            tasks = []
            for b in bindings:
                tasks.append({
                    'module_task_id': b.module_task_id,
                    'q_schedule_id': b.q_schedule_id,
                    'enabled': b.enabled,
                    'last_sync_at': b.last_sync_at,
                })
            out.append({
                'module': m['key'],
                'label': m['label'],
                'bindings': tasks,
                'count': len(tasks),
            })
        return Response({'modules': out})
