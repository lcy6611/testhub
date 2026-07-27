"""UI 资产跨项目克隆与引用分析（资产复用治理 #259）

核心能力：
1. 跨项目克隆：Element / TestScript(+ScriptStep) / TestCase(+TestCaseStep) /
   PageObject(+PageObjectElement) 从源项目克隆到目标项目，子表一并复制，
   外键（元素/页面对象/公共步骤）按目标项目重新匹配，避免跨项目悬空引用。
2. 命名冲突自动化解：目标项目已有同名资产时追加 ``_副本{n}``。
3. 克隆溯源：克隆产物记录 ``cloned_from``（源资产 id）+ ``cloned_at``。
4. 影响分析：``element_references`` 返回引用某元素的脚本步骤/用例步骤/页面对象。
"""
import logging
from django.utils import timezone
from django.db import transaction

from ..models import (
    Element,
    TestScript,
    ScriptStep,
    TestCase,
    TestCaseStep,
    PageObject,
    PageObjectElement,
    UiProject,
)

logger = logging.getLogger(__name__)


def _unique_name(model_cls, project, base_name, name_field="name"):
    """目标项目已有同名资产时，自动追加 ``_副本{n}`` 防止冲突。"""
    if not model_cls.objects.filter(project=project, **{name_field: base_name}).exists():
        return base_name
    n = 1
    while model_cls.objects.filter(project=project, **{name_field: f"{base_name}_副本{n}"}).exists():
        n += 1
    return f"{base_name}_副本{n}"


def _match_element(element, target_project):
    """按名称在目标项目匹配元素；找不到返回 None（避免跨项目 FK 悬空）。"""
    if element is None:
        return None
    return Element.objects.filter(project=target_project, name=element.name).first()


@transaction.atomic
def clone_element(src, target_project, user=None):
    name = _unique_name(Element, target_project, src.name)
    new = Element(
        project=target_project,
        group=None,  # 分组按项目隔离，不跨项目复制
        name=name,
        description=src.description,
        element_type=src.element_type,
        locator_strategy=src.locator_strategy,
        locator_value=src.locator_value,
        backup_locators=src.backup_locators,
        page=src.page,
        component_name=src.component_name,
        parent_element=None,
        is_unique=src.is_unique,
        wait_timeout=src.wait_timeout,
        is_visible=src.is_visible,
        is_enabled=src.is_enabled,
        force_action=src.force_action,
        created_by=user,
        cloned_from=src.id,
        cloned_at=timezone.now(),
    )
    new.save()
    return new


@transaction.atomic
def clone_test_script(src, target_project, user=None):
    name = _unique_name(TestScript, target_project, src.name)
    new = TestScript(
        project=target_project,
        name=name,
        description=src.description,
        script_type=src.script_type,
        content=src.content,
        language=src.language,
        framework=src.framework,
        cloned_from=src.id,
        cloned_at=timezone.now(),
    )
    new.save()
    for step in src.steps.all().order_by("step_order"):
        ScriptStep.objects.create(
            script=new,
            step_order=step.step_order,
            action_type=step.action_type,
            target_element=_match_element(step.target_element, target_project),
            page_object=None,
            action_params=step.action_params,
            description=step.description,
            expected_result=step.expected_result,
            wait_before=step.wait_before,
            wait_after=step.wait_after,
            retry_count=step.retry_count,
            shared_step=None,  # 公共步骤按项目隔离，跨项目克隆不保留引用
        )
    return new


@transaction.atomic
def clone_test_case(src, target_project, user=None):
    name = _unique_name(TestCase, target_project, src.name)
    new = TestCase(
        project=target_project,
        name=name,
        description=src.description,
        status=src.status,
        priority=src.priority,
        created_by=user or src.created_by,
        cloned_from=src.id,
        cloned_at=timezone.now(),
    )
    new.save()
    for step in src.steps.all().order_by("step_number"):
        TestCaseStep.objects.create(
            test_case=new,
            step_number=step.step_number,
            action_type=step.action_type,
            element=_match_element(step.element, target_project),
            input_value=step.input_value,
            wait_time=step.wait_time,
            assert_type=step.assert_type,
            assert_value=step.assert_value,
            description=step.description,
            shared_step=None,
        )
    return new


@transaction.atomic
def clone_page_object(src, target_project, user=None):
    name = _unique_name(PageObject, target_project, src.name)
    new = PageObject(
        name=name,
        class_name=src.class_name,
        url_pattern=src.url_pattern,
        project=target_project,
        description=src.description,
        template_code=src.template_code,
        created_by=user,
        cloned_from=src.id,
        cloned_at=timezone.now(),
    )
    new.save()
    for poe in src.page_object_elements.all().order_by("order"):
        PageObjectElement.objects.create(
            page_object=new,
            element=_match_element(poe.element, target_project),
            method_name=poe.method_name,
            is_property=poe.is_property,
            order=poe.order,
        )
    return new


def element_references(element):
    """影响分析：返回引用某 Element 的资产清单。"""
    return {
        "script_steps": [
            {
                "script_id": s.script_id,
                "step_order": s.step_order,
                "description": s.description,
            }
            for s in ScriptStep.objects.filter(target_element=element).select_related("script")
        ],
        "case_steps": [
            {
                "case_id": s.test_case_id,
                "step_number": s.step_number,
                "description": s.description,
            }
            for s in TestCaseStep.objects.filter(element=element).select_related("test_case")
        ],
        "page_object_elements": [
            {
                "page_object_id": p.page_object_id,
                "method_name": p.method_name,
            }
            for p in PageObjectElement.objects.filter(element=element).select_related("page_object")
        ],
    }


# 资源类型 -> 克隆函数 的派发表，供视图层按资源类型调用
CLONE_DISPATCH = {
    "element": clone_element,
    "test_script": clone_test_script,
    "test_case": clone_test_case,
    "page_object": clone_page_object,
}
