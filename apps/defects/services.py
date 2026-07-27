"""#260 覆盖率与质量门禁核心计算（纯函数，便于单测）。

覆盖率三层模型：
  层1 linked   需求有"对应测试用例"（中央用例 requirement 关联 或 AI 生成用例已采纳）
  层2 executed 该需求下用例至少被执行过一次（TestRunCase 状态 != untested）
  层3 passed   该需求下用例至少一次执行通过（status == 'passed'）

质量门禁：综合 通过率 / 需求通过覆盖率 / 未关闭缺陷（按严重级别） 给出
  GO / CONDITIONAL_GO / NO_GO 结论 + 原因列表 + 使用的阈值。
"""
from django.db.models import Count
from apps.requirement_analysis.models import BusinessRequirement, GeneratedTestCase
from apps.testcases.models import TestCase
from apps.executions.models import TestRun, TestRunCase


def compute_requirement_coverage(project_id, version_id=None):
    """计算某项目（可选版本）的需求三层覆盖率。"""
    reqs = BusinessRequirement.objects.filter(
        analysis__document__project_id=project_id
    )
    total = reqs.count()
    if total == 0:
        return {
            'total_requirements': 0,
            'linked': 0, 'executed': 0, 'passed': 0,
            'linked_rate': 0.0, 'executed_rate': 0.0, 'passed_rate': 0.0,
            'items': [],
        }

    req_ids = set(reqs.values_list('id', flat=True))
    req_map = {r.id: r for r in reqs}

    # 层1：已关联用例
    central_linked_ids = set(
        TestCase.objects.filter(
            project_id=project_id, requirement_id__in=req_ids
        ).values_list('requirement_id', flat=True)
    )
    adopted_gen_ids = set(
        GeneratedTestCase.objects.filter(
            requirement_id__in=req_ids, status='adopted'
        ).values_list('requirement_id', flat=True)
    )
    linked_ids = central_linked_ids | adopted_gen_ids

    # 层2/3：执行与通过（基于中央用例的真实执行）
    trc = TestRunCase.objects.filter(
        testcase__project_id=project_id,
        testcase__requirement_id__in=req_ids,
    ).values_list('testcase__requirement_id', 'status')

    executed_ids = set()
    passed_ids = set()
    for rid, st in trc:
        if rid is None:
            continue
        if st and st != 'untested':
            executed_ids.add(rid)
        if st == 'passed':
            passed_ids.add(rid)

    linked = len(linked_ids)
    executed = len(executed_ids)
    passed = len(passed_ids)

    items = []
    for rid in req_ids:
        items.append({
            'requirement_id': rid,
            'requirement_name': req_map[rid].requirement_name,
            'requirement_level': req_map[rid].requirement_level,
            'linked': rid in linked_ids,
            'executed': rid in executed_ids,
            'passed': rid in passed_ids,
        })
    # 未通过的排前面，便于优先跟进
    items.sort(key=lambda x: (not x['passed'], not x['executed'], not x['linked']))

    return {
        'total_requirements': total,
        'linked': linked,
        'executed': executed,
        'passed': passed,
        'linked_rate': round(linked / total * 100, 1),
        'executed_rate': round(executed / total * 100, 1),
        'passed_rate': round(passed / total * 100, 1),
        'items': items,
    }


def default_thresholds():
    return {
        'min_pass_rate': 90.0,
        'min_coverage_rate': 80.0,
        'max_open_defects': 0,
        'allow_severity': {'S1': 0, 'S2': 0, 'S3': 5, 'S4': 10},
    }


def _aggregate_pass_rate(project_id, version_id=None, test_run_id=None):
    """汇总通过率。优先用指定 test_run；否则聚合项目（版本）下全部执行。"""
    if test_run_id:
        run = TestRun.objects.filter(id=test_run_id).first()
        if not run:
            return {'pass_rate': 0.0, 'tested': 0, 'blocked': 0}
        s = run.progress_stats
        tested = s.get('tested', 0)
        passed = s.get('passed', 0)
        return {
            'pass_rate': round(passed / tested * 100, 1) if tested else 0.0,
            'tested': tested,
            'blocked': s.get('blocked', 0),
        }

    runs = TestRun.objects.filter(project_id=project_id)
    if version_id:
        runs = runs.filter(version_id=version_id)
    total_tested = 0
    total_passed = 0
    total_blocked = 0
    for run in runs:
        s = run.progress_stats
        total_tested += s.get('tested', 0)
        total_passed += s.get('passed', 0)
        total_blocked += s.get('blocked', 0)
    return {
        'pass_rate': round(total_passed / total_tested * 100, 1) if total_tested else 0.0,
        'tested': total_tested,
        'blocked': total_blocked,
    }


def evaluate_quality_gate(project_id, version_id=None, test_run_id=None, thresholds=None):
    """评估质量门禁，返回结论 / 指标 / 原因 / 阈值。"""
    from .models import Defect

    th = thresholds or default_thresholds()
    pass_info = _aggregate_pass_rate(project_id, version_id, test_run_id)
    pass_rate = pass_info['pass_rate']
    coverage = compute_requirement_coverage(project_id, version_id)

    # 缺陷统计（按严重级别）
    open_statuses = ['open', 'in_progress', 'reopened']
    open_defects = Defect.objects.filter(
        project_id=project_id, status__in=open_statuses
    )
    open_by_sev = {s: open_defects.filter(severity=s).count() for s in ['S1', 'S2', 'S3', 'S4']}
    total_open = sum(open_by_sev.values())

    reasons = []
    conclusion = 'GO'

    if pass_rate < th['min_pass_rate']:
        conclusion = 'NO_GO'
        reasons.append(f"通过率 {pass_rate}% 低于门槛 {th['min_pass_rate']}%")

    if coverage['passed_rate'] < th['min_coverage_rate']:
        if conclusion != 'NO_GO':
            conclusion = 'CONDITIONAL_GO'
        reasons.append(
            f"需求通过覆盖率 {coverage['passed_rate']}% 低于门槛 {th['min_coverage_rate']}%"
        )

    for sev in ['S1', 'S2']:
        if open_by_sev[sev] > th['allow_severity'][sev]:
            conclusion = 'NO_GO'
            reasons.append(
                f"存在 {open_by_sev[sev]} 个未关闭的 {sev} 级缺陷（允许上限 {th['allow_severity'][sev]}）"
            )

    if th['max_open_defects'] is not None and total_open > th['max_open_defects']:
        if conclusion == 'GO':
            conclusion = 'CONDITIONAL_GO'
        reasons.append(f"未关闭缺陷总数 {total_open} 超过门槛 {th['max_open_defects']}")

    if not reasons:
        reasons.append("所有质量指标均满足发布门槛")

    metrics = {
        'pass_rate': pass_rate,
        'tested': pass_info.get('tested', 0),
        'blocked': pass_info.get('blocked', 0),
        'coverage_rate': coverage['passed_rate'],
        'linked_rate': coverage['linked_rate'],
        'executed_rate': coverage['executed_rate'],
        'total_requirements': coverage['total_requirements'],
        'open_defects': total_open,
        'open_by_severity': open_by_sev,
    }

    return {
        'conclusion': conclusion,
        'metrics': metrics,
        'reasons': reasons,
        'thresholds': th,
    }
