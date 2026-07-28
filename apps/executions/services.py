"""执行步骤服务：初始化、状态更新、用例状态联动。"""
from __future__ import annotations

from django.utils import timezone
from .models import TestRunCase, TestRunCaseStep, TestRunCaseHistory


def init_steps_for_run_case(run_case: TestRunCase) -> int:
    """从 TestCase 复制步骤生成 TestRunCaseStep，返回创建条数。

    已有步骤会跳过（按 step_number 去重）。
    """
    testcase = run_case.testcase
    case_steps = list(testcase.step_details.all().order_by('step_number'))
    if not case_steps:
        return 0
    existing = set(
        run_case.step_records.values_list('step_number', flat=True)
    )
    new_records = []
    for cs in case_steps:
        if cs.step_number in existing:
            continue
        new_records.append(TestRunCaseStep(
            run_case=run_case,
            step_number=cs.step_number,
            action=cs.action,
            expected=cs.expected,
        ))
    if new_records:
        TestRunCaseStep.objects.bulk_create(new_records)
    return len(new_records)


def recompute_run_case_status(run_case: TestRunCase, force: bool = False) -> str:
    """根据步骤状态联动 TestRunCase.status。

    联动规则（force=False 时只对 untested 用例自动重算，避免覆盖人工设置）：
        - 任意步骤 failed/blocked → failed
        - 全部步骤 passed         → passed
        - 至少一步非 untested      → in_progress
        - 全部 untested            → untested
    """
    if not force and run_case.status in ('passed', 'failed', 'blocked'):
        # 已判定的不自动覆盖；除非显式 force
        return run_case.status

    steps = list(run_case.step_records.all())
    if not steps:
        return run_case.status

    statuses = {s.status for s in steps}
    if 'failed' in statuses or 'blocked' in statuses:
        new_status = 'failed'
    elif statuses == {'passed'}:
        new_status = 'passed'
    elif statuses - {'untested'}:
        new_status = 'in_progress'
    else:
        new_status = 'untested'

    if new_status != run_case.status:
        run_case.status = new_status
        run_case.save(update_fields=['status', 'updated_at'])
    return new_status


def update_step_status(run_case: TestRunCase, step_number: int, *,
                        status_value: str, actual_result: str = '',
                        comments: str = '', user=None) -> TestRunCaseStep:
    """更新一条步骤的状态/实际结果/备注，并联动用例状态。

    写入 TestRunCaseHistory 一条（便于追溯步骤级变更）。
    """
    step, _ = TestRunCaseStep.objects.get_or_create(
        run_case=run_case, step_number=step_number,
        defaults={'action': '', 'expected': ''},
    )
    # 旧值入历史（仅当 status 改变）
    if step.status != status_value:
        TestRunCaseHistory.objects.create(
            run_case=run_case,
            status=status_value,
            actual_result=actual_result,
            comments=f"step #{step_number}: {comments}".strip(),
            executed_by=user,
            executed_at=timezone.now(),
        )
    step.status = status_value
    if actual_result != '':
        step.actual_result = actual_result
    if comments != '':
        step.comments = comments
    step.executed_by = user
    step.executed_at = timezone.now()
    step.save()

    recompute_run_case_status(run_case)
    return step
