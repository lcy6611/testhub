from django.db import models
from django.utils import timezone
from asgiref.sync import sync_to_async
from apps.users.models import User
from apps.projects.models import Project
from .kb_hub.models import (
    KnowledgeHubConfig, NativeKb, NativeKbDocument, NativeKbChunk, ProjectKbBinding,
    KbSource,
)
import json
import time
import httpx
import asyncio
from contextvars import ContextVar
from typing import Dict, Any, List, Callable, Optional
import logging

logger = logging.getLogger(__name__)


# === #261 AI 成本观测：best-effort 记录每次 LLM 调用，不阻塞主流程 ===
def _ai_log_success(meta, config, merged, t0):
    if not meta:
        return
    try:
        from apps.ai_eval.calllog import record_ai_call
        usage = (merged or {}).get("usage") or {}
        record_ai_call(
            module=meta.get("module", "requirement_analysis"),
            feature=meta.get("feature", ""),
            provider=config.get_model_type_display(),
            model_name=config.model_name,
            model_config_id=config.id,
            prompt_version_id=meta.get("prompt_version_id"),
            prompt_key=meta.get("prompt_key", ""),
            project_id=meta.get("project_id"),
            user_id=meta.get("user_id"),
            input_tokens=usage.get("prompt_tokens", 0) or 0,
            output_tokens=usage.get("completion_tokens", 0) or 0,
            total_tokens=usage.get("total_tokens", 0) or 0,
            status="success",
            latency_ms=int((time.monotonic() - t0) * 1000) if t0 else None,
        )
    except Exception:
        pass


def _ai_log_fail(meta, config, t0, msg):
    if not meta:
        return
    try:
        from apps.ai_eval.calllog import record_ai_call
        record_ai_call(
            module=meta.get("module", "requirement_analysis"),
            feature=meta.get("feature", ""),
            provider=config.get_model_type_display() if config else "",
            model_name=getattr(config, "model_name", "") or "",
            model_config_id=getattr(config, "id", None),
            prompt_version_id=meta.get("prompt_version_id"),
            prompt_key=meta.get("prompt_key", ""),
            project_id=meta.get("project_id"),
            user_id=meta.get("user_id"),
            status="failure",
            error=str(msg)[:500],
            latency_ms=int((time.monotonic() - t0) * 1000) if t0 else None,
        )
    except Exception:
        pass



class RequirementDocument(models.Model):
    """需求文档模型"""
    DOCUMENT_TYPE_CHOICES = [
        ('pdf', 'PDF文档'),
        ('docx', 'Word文档'),
        ('txt', '文本文档'),
    ]
    
    STATUS_CHOICES = [
        ('uploaded', '已上传'),
        ('analyzing', '分析中'),
        ('analyzed', '分析完成'),
        ('failed', '分析失败'),
    ]
    
    title = models.CharField(max_length=200, verbose_name='文档标题')
    file = models.FileField(upload_to='requirement_docs/%Y/%m/', verbose_name='文档文件')
    document_type = models.CharField(max_length=10, choices=DOCUMENT_TYPE_CHOICES, verbose_name='文档类型')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded', verbose_name='状态')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_documents', verbose_name='上传者')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='requirement_documents', verbose_name='关联项目', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    file_size = models.PositiveIntegerField(verbose_name='文件大小(bytes)', null=True, blank=True)
    extracted_text = models.TextField(verbose_name='提取的文本内容', blank=True)
    
    class Meta:
        db_table = 'requirement_documents'
        verbose_name = '需求文档'
        verbose_name_plural = '需求文档'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"


class RequirementAnalysis(models.Model):
    """需求分析记录"""
    document = models.OneToOneField(RequirementDocument, on_delete=models.CASCADE, related_name='analysis', verbose_name='关联文档')
    analysis_report = models.TextField(verbose_name='分析报告', blank=True)
    requirements_count = models.PositiveIntegerField(verbose_name='需求数量', default=0)
    analysis_time = models.FloatField(verbose_name='分析耗时(秒)', null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'requirement_analyses'
        verbose_name = '需求分析'
        verbose_name_plural = '需求分析'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.document.title} - 分析报告"


class BusinessRequirement(models.Model):
    """业务需求模型"""
    REQUIREMENT_TYPE_CHOICES = [
        ('functional', '功能需求'),
        ('performance', '性能需求'),
        ('security', '安全需求'),
        ('usability', '可用性需求'),
        ('interface', '接口需求'),
        ('other', '其他需求'),
    ]
    
    REQUIREMENT_LEVEL_CHOICES = [
        ('high', '高'),
        ('medium', '中'),
        ('low', '低'),
    ]
    
    analysis = models.ForeignKey(RequirementAnalysis, on_delete=models.CASCADE, related_name='requirements', verbose_name='关联分析')
    requirement_id = models.CharField(max_length=50, verbose_name='需求编号')
    requirement_name = models.CharField(max_length=200, verbose_name='需求名称')
    requirement_type = models.CharField(max_length=20, choices=REQUIREMENT_TYPE_CHOICES, verbose_name='需求类型')
    parent_requirement = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, verbose_name='父级需求')
    module = models.CharField(max_length=100, verbose_name='所属模块')
    requirement_level = models.CharField(max_length=10, choices=REQUIREMENT_LEVEL_CHOICES, verbose_name='需求级别')
    reviewer = models.CharField(max_length=50, verbose_name='评审人', default='admin')
    estimated_hours = models.PositiveIntegerField(verbose_name='预计工时', default=8)
    description = models.TextField(verbose_name='需求描述')
    acceptance_criteria = models.TextField(verbose_name='验收标准')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'business_requirements'
        verbose_name = '业务需求'
        verbose_name_plural = '业务需求'
        ordering = ['-created_at']
        unique_together = ['analysis', 'requirement_id']
    
    def __str__(self):
        return f"{self.requirement_id} - {self.requirement_name}"


class GeneratedTestCase(models.Model):
    """生成的测试用例模型"""
    PRIORITY_CHOICES = [
        ('P0', '最高优先级'),
        ('P1', '高优先级'),
        ('P2', '中优先级'),
        ('P3', '低优先级'),
    ]
    
    STATUS_CHOICES = [
        ('generated', '已生成'),
        ('reviewing', '评审中'),
        ('reviewed', '已评审'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('adopted', '已采纳'),
        ('discarded', '已弃用'),
    ]
    
    requirement = models.ForeignKey(BusinessRequirement, on_delete=models.CASCADE, related_name='test_cases', verbose_name='关联需求')
    case_id = models.CharField(max_length=50, verbose_name='用例编号')
    title = models.CharField(max_length=300, verbose_name='用例标题')
    priority = models.CharField(max_length=5, choices=PRIORITY_CHOICES, verbose_name='优先级')
    precondition = models.TextField(verbose_name='前置条件')
    test_steps = models.TextField(verbose_name='测试步骤')
    expected_result = models.TextField(verbose_name='预期结果')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='generated', verbose_name='状态')
    generated_by_ai = models.CharField(max_length=50, verbose_name='生成AI模型', default='AI-A')
    reviewed_by_ai = models.CharField(max_length=50, verbose_name='评审AI模型', null=True, blank=True)
    review_comments = models.TextField(verbose_name='评审意见', blank=True)
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'generated_test_cases'
        verbose_name = '生成的测试用例'
        verbose_name_plural = '生成的测试用例'
        ordering = ['-created_at']
        unique_together = ['requirement', 'case_id']
    
    def __str__(self):
        return f"{self.case_id} - {self.title[:50]}"


class AnalysisTask(models.Model):
    """分析任务模型"""
    TASK_TYPE_CHOICES = [
        ('requirement_analysis', '需求分析'),
        ('testcase_generation', '测试用例生成'),
        ('testcase_review', '测试用例评审'),
    ]
    
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('running', '运行中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    
    task_id = models.CharField(max_length=100, unique=True, verbose_name='任务ID')
    task_type = models.CharField(max_length=30, choices=TASK_TYPE_CHOICES, verbose_name='任务类型')
    document = models.ForeignKey(RequirementDocument, on_delete=models.CASCADE, related_name='tasks', verbose_name='关联文档')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    progress = models.PositiveIntegerField(default=0, verbose_name='进度百分比')
    result = models.JSONField(verbose_name='任务结果', null=True, blank=True)
    error_message = models.TextField(verbose_name='错误信息', blank=True)
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='开始时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    
    class Meta:
        db_table = 'analysis_tasks'
        verbose_name = '分析任务'
        verbose_name_plural = '分析任务'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.task_id} - {self.get_task_type_display()}"


class AIModelConfig(models.Model):
    """AI模型配置模型"""
    MODEL_CHOICES = [
        ('deepseek', 'DeepSeek'),
        ('qwen', '通义千问'),
        ('siliconflow', '硅基流动'),
        ('other', '其他'),
    ]
    
    ROLE_CHOICES = [
        ('writer', '测试用例编写专家'),
        ('reviewer', '测试评审专家'),
        ('browser_use_text', 'Browser Use - 文本模式'),
        ('browser_use_vision', 'Browser Use - 视觉模式'),
        ('vision', '视觉理解模型'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='配置名称')
    model_type = models.CharField(max_length=20, choices=MODEL_CHOICES, verbose_name='模型类型')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    api_key = models.CharField(max_length=200, verbose_name='API Key', blank=True, null=True)
    base_url = models.URLField(verbose_name='API Base URL')
    model_name = models.CharField(max_length=100, verbose_name='模型名称')
    max_tokens = models.IntegerField(default=8192, verbose_name='最大Token数')
    temperature = models.FloatField(default=0.7, verbose_name='温度参数')
    top_p = models.FloatField(default=0.9, verbose_name='Top P参数')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'ai_model_config'
        verbose_name = 'AI模型配置'
        verbose_name_plural = 'AI模型配置'
        unique_together = ('model_type', 'role', 'is_active')  # 每种角色只能有一个活跃配置
    
    def __str__(self):
        return f"{self.get_model_type_display()} - {self.get_role_display()}"
    
    @classmethod
    def get_active_config(cls, model_type: str, role: str):
        """获取活跃的配置"""
        return cls.objects.filter(
            model_type=model_type, 
            role=role, 
            is_active=True
        ).first()


class PromptConfig(models.Model):
    """提示词配置模型"""
    PROMPT_CHOICES = [
        ('writer', '用例编写提示词'),
        ('reviewer', '用例评审提示词'),
    ]
    
    name = models.CharField(max_length=100, verbose_name='配置名称')
    prompt_type = models.CharField(max_length=20, choices=PROMPT_CHOICES, verbose_name='提示词类型')
    content = models.TextField(verbose_name='提示词内容')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'prompt_config'
        verbose_name = '提示词配置'
        verbose_name_plural = '提示词配置'
    
    def __str__(self):
        return f"{self.get_prompt_type_display()} - {self.name}"
    
    @classmethod
    def get_active_config(cls, prompt_type: str):
        """获取活跃的提示词配置"""
        return cls.objects.filter(
            prompt_type=prompt_type, 
            is_active=True
        ).first()


class GenerationConfig(models.Model):
    """生成行为配置模型"""
    OUTPUT_MODE_CHOICES = [
        ('stream', '实时流式输出'),
        ('complete', '完整输出'),
    ]

    name = models.CharField(max_length=100, verbose_name='配置名称', default='默认生成配置')
    default_output_mode = models.CharField(
        max_length=10,
        choices=OUTPUT_MODE_CHOICES,
        default='stream',
        verbose_name='默认输出模式',
        help_text='测试用例生成的默认输出方式'
    )
    enable_auto_review = models.BooleanField(
        default=True,
        verbose_name='启用AI评审和改进',
        help_text='生成完成后自动进行AI评审，并根据评审意见改进测试用例'
    )
    review_timeout = models.IntegerField(
        default=3600,
        verbose_name='评审和改进超时时间（秒）',
        help_text='AI评审和改进的最大等待时间（总时长），0 表示不限制'
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'generation_config'
        verbose_name = '生成行为配置'
        verbose_name_plural = '生成行为配置'

    def __str__(self):
        return self.name

    @classmethod
    def get_active_config(cls):
        """获取活跃的生成配置"""
        return cls.objects.filter(is_active=True).first()


class TestCaseGenerationTask(models.Model):
    """测试用例生成任务模型"""
    STATUS_CHOICES = [
        ('pending', '等待中'),
        ('generating', '生成中'),
        ('reviewing', '评审中'),
        ('revising', '改进中'),
        ('completed', '已完成'),
        ('failed', '失败'),
        ('cancelled', '已取消'),
    ]

    OUTPUT_MODE_CHOICES = [
        ('stream', '实时流式输出'),
        ('complete', '完整输出'),
    ]

    task_id = models.CharField(max_length=50, unique=True, verbose_name='任务ID')
    title = models.CharField(max_length=200, verbose_name='任务标题')
    requirement_text = models.TextField(verbose_name='需求描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    progress = models.IntegerField(default=0, verbose_name='进度百分比')

    output_mode = models.CharField(
        max_length=10,
        choices=OUTPUT_MODE_CHOICES,
        default='stream',
        verbose_name='输出模式'
    )
    stream_buffer = models.TextField(blank=True, verbose_name='流式输出缓冲区')
    stream_position = models.IntegerField(default=0, verbose_name='流式输出位置')
    last_stream_update = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='最后流式更新时间'
    )

    project = models.ForeignKey(
        Project, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='generation_tasks',
        verbose_name='关联项目'
    )

    # 可选：来源需求文档（用于多模态图文生成）
    source_document = models.ForeignKey(
        RequirementDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generation_tasks',
        verbose_name='来源需求文档'
    )

    # Dify 知识库参考（可选）
    dify_config = models.ForeignKey(
        'assistant.DifyConfig',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generation_tasks',
        verbose_name='Dify 配置',
    )
    dify_dataset_id = models.CharField(max_length=64, blank=True, default='', verbose_name='Dify 知识库 ID')
    dify_dataset_name = models.CharField(max_length=200, blank=True, default='', verbose_name='Dify 知识库名称')
    kb_context = models.TextField(blank=True, default='', verbose_name='知识库检索上下文')
    kb_context_meta = models.JSONField(default=dict, blank=True, verbose_name='知识库参考元信息')
    kb_top_k = models.PositiveSmallIntegerField(default=5, verbose_name='知识库检索条数')
    kb_reference_mode = models.CharField(
        max_length=20,
        blank=True,
        default='hybrid',
        verbose_name='知识库参考模式',
        help_text='documents=指定文档, retrieval=语义检索, hybrid=混合',
    )
    kb_document_ids = models.JSONField(default=list, blank=True, verbose_name='指定参考文档 ID 列表')
    kb_function_ids = models.JSONField(default=list, blank=True, verbose_name='关联功能模块 ID 列表')
    image_data_urls = models.JSONField(default=list, blank=True, verbose_name='附件截图 data URLs')
    image_attachments = models.JSONField(default=list, blank=True, verbose_name='带角色的图片附件')
    refinement_notes = models.TextField(blank=True, default='', verbose_name='迭代补充记录')
    writer_model_config = models.ForeignKey(
        AIModelConfig, on_delete=models.SET_NULL, null=True, 
        related_name='writer_tasks', verbose_name='编写模型配置'
    )
    reviewer_model_config = models.ForeignKey(
        AIModelConfig, on_delete=models.SET_NULL, null=True,
        related_name='reviewer_tasks', verbose_name='评审模型配置'
    )
    writer_prompt_config = models.ForeignKey(
        PromptConfig, on_delete=models.SET_NULL, null=True,
        related_name='writer_tasks', verbose_name='编写提示词配置'
    )
    reviewer_prompt_config = models.ForeignKey(
        PromptConfig, on_delete=models.SET_NULL, null=True,
        related_name='reviewer_tasks', verbose_name='评审提示词配置'
    )

    # ── Skill 注入（快照，生成时写入，保证结果可复现）──
    skill = models.ForeignKey(
        'TestCaseSkill', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tasks', verbose_name='关联技能'
    )
    skill_system_prompt = models.TextField(blank=True, default='', verbose_name='技能系统提示词(快照)')
    skill_template_columns = models.JSONField(default=list, blank=True, verbose_name='技能模板列名(快照)')
    
    # 生成结果
    generated_test_cases = models.TextField(blank=True, verbose_name='生成的测试用例')
    review_feedback = models.TextField(blank=True, verbose_name='评审反馈')
    final_test_cases = models.TextField(blank=True, verbose_name='最终测试用例')
    
    # 元数据
    generation_log = models.TextField(blank=True, verbose_name='生成日志')
    error_message = models.TextField(blank=True, verbose_name='错误信息')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')
    is_saved_to_records = models.BooleanField(default=False, verbose_name='是否已保存到记录')
    saved_at = models.DateTimeField(null=True, blank=True, verbose_name='保存到记录时间')
    
    class Meta:
        db_table = 'testcase_generation_task'
        verbose_name = '测试用例生成任务'
        verbose_name_plural = '测试用例生成任务'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.get_status_display()}"


class AIModelService:
    """AI模型服务类"""
    # 为长文档场景适当提高自动续写次数，避免在“总结/建议”处提前截断
    MAX_AUTO_CONTINUATIONS = 8
    API_TIMEOUT_SECONDS = 600.0
    MIN_WRITER_MAX_TOKENS = 8192
    MAX_REVISE_INPUT_CHARS = 28000
    MAX_REVIEW_INPUT_CHARS = 28000
    MIN_REVIEWER_MAX_TOKENS = 4096
    MAX_ALLOWED_TOKENS = 32000
    LENGTH_FINISH_REASONS = frozenset({"length", "max_tokens"})
    CONTINUE_USER_MESSAGE = (
        "继续输出剩余测试用例及「最后总结」部分，保持相同 Markdown 表格格式，"
        "不要重复已输出内容。"
    )
    _last_call_meta: ContextVar[Dict[str, Any]] = ContextVar("requirement_analysis_ai_last_call_meta", default={})

    @staticmethod
    def _resolve_max_tokens(config, min_tokens: int = 0) -> int:
        """解析有效 max_tokens，对用例生成场景保证不低于 min_tokens。"""
        raw = getattr(config, "max_tokens", None) or 8192
        try:
            raw = int(raw)
        except (TypeError, ValueError):
            raw = 8192
        if min_tokens > 0:
            raw = max(raw, min_tokens)
        return min(max(raw, 256), AIModelService.MAX_ALLOWED_TOKENS)

    @staticmethod
    def _should_auto_continue(finish_reason: Any, usage: Dict[str, Any], max_tokens: int) -> bool:
        """判断是否因 token 上限截断，需自动续写（兼容部分网关不返回 length）。"""
        reason = (finish_reason or "").lower() if isinstance(finish_reason, str) else ""
        if reason in AIModelService.LENGTH_FINISH_REASONS:
            return True
        completion = (usage or {}).get("completion_tokens") or 0
        try:
            completion = int(completion)
        except (TypeError, ValueError):
            completion = 0
        return completion >= int(max_tokens * 0.92)

    @staticmethod
    def _effective_writer_system_prompt(task) -> str:
        """获取真正生效的编写系统提示词。

        - 若任务关联了 Skill 且 Skill 注入了系统提示词（skill_system_prompt），
          优先使用它（已包含角色定义、约束规则、模板列要求）；
        - 否则回退到关联的 writer_prompt_config.content。
        """
        skill_prompt = (getattr(task, "skill_system_prompt", "") or "").strip()
        if skill_prompt:
            return skill_prompt
        wp = getattr(task, "writer_prompt_config", None)
        if wp and getattr(wp, "content", None):
            return wp.content
        return ""

    @staticmethod
    def _build_api_payload(config, messages: List[Dict[str, str]], *, stream: bool, min_tokens: int = 0) -> Dict[str, Any]:
        max_tokens = AIModelService._resolve_max_tokens(config, min_tokens)
        payload = {
            "model": config.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": getattr(config, "temperature", 0.7),
            "top_p": getattr(config, "top_p", 0.9),
            "stream": stream,
        }
        # 流式场景显式请求 usage（兼容网关才生效，不兼容则忽略，无副作用）
        if stream:
            payload["stream_options"] = {"include_usage": True}
        return payload, max_tokens

    @staticmethod
    def _resolve_chat_completions_url(config) -> str:
        base_url = config.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        if base_url.endswith("/v1") or base_url.endswith("/api") or "/v1/" in base_url:
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    @staticmethod
    def pop_last_call_meta() -> Dict[str, Any]:
        """获取并清空最近一次模型调用的元信息（用于写 generation_log）。"""
        meta = AIModelService._last_call_meta.get() or {}
        AIModelService._last_call_meta.set({})
        return meta

    @staticmethod
    def _get_task_image_attachments(task) -> List[Dict[str, Any]]:
        from .image_attachment_utils import normalize_image_attachments

        extra_att = list(getattr(task, "image_attachments", None) or [])
        extra_urls = list(getattr(task, "image_data_urls", None) or [])
        attachments = normalize_image_attachments(extra_att, extra_urls)
        try:
            doc = getattr(task, "source_document", None)
            if doc:
                from .services import DocumentProcessor

                for url in DocumentProcessor.extract_image_data_urls(doc):
                    attachments.append({"url": url, "role": "ui_layout", "caption": "需求文档内嵌图"})
        except Exception:
            pass
        seen = set()
        merged: List[Dict[str, Any]] = []
        for att in attachments:
            url = att.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            merged.append(att)
        return merged[:12]

    @staticmethod
    def _build_user_content_with_images(text: str, attachments: List[Dict[str, Any]]) -> Any:
        from .image_attachment_utils import build_multimodal_user_content

        return build_multimodal_user_content(text, attachments)

    @staticmethod
    def _get_task_image_data_urls(task) -> List[str]:
        """兼容旧逻辑：返回全部附件 URL。"""
        return [a["url"] for a in AIModelService._get_task_image_attachments(task) if a.get("url")]
    
    @staticmethod
    async def call_openai_compatible_api(
        config: AIModelConfig,
        messages: List[Dict[str, str]],
        *,
        min_tokens: int = 0,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """调用OpenAI兼容格式的API"""
        headers = {
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json'
        }

        data, effective_max_tokens = AIModelService._build_api_payload(
            config, messages, stream=False, min_tokens=min_tokens
        )
        url = AIModelService._resolve_chat_completions_url(config)

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=AIModelService.API_TIMEOUT_SECONDS) as client:
                merged: Dict[str, Any] = {}
                merged_content_parts: List[str] = []
                last_usage: Dict[str, Any] = {}
                continuation = 0
                finish_reason: Any = None

                while True:
                    response = await client.post(url, headers=headers, json=data)

                    if response.status_code != 200:
                        error_detail = response.text
                        logger.error(f"API调用返回错误: Status={response.status_code}, Body={error_detail}")

                    response.raise_for_status()
                    j = response.json()
                    merged = j

                    try:
                        choice0 = (j.get("choices") or [{}])[0] or {}
                        msg = choice0.get("message") or {}
                        content = msg.get("content") or ""
                        finish_reason = choice0.get("finish_reason")
                        if content:
                            merged_content_parts.append(content)
                        usage = j.get("usage") or {}
                        if usage:
                            last_usage = usage
                    except Exception:
                        finish_reason = None

                    if (
                        not AIModelService._should_auto_continue(finish_reason, last_usage, effective_max_tokens)
                        or continuation >= AIModelService.MAX_AUTO_CONTINUATIONS
                    ):
                        break

                    continuation += 1
                    messages = list(data.get("messages") or [])
                    messages.append({"role": "assistant", "content": merged_content_parts[-1] if merged_content_parts else ""})
                    messages.append({"role": "user", "content": AIModelService.CONTINUE_USER_MESSAGE})
                    data["messages"] = messages

                if merged_content_parts:
                    if "choices" not in merged or not merged["choices"]:
                        merged["choices"] = [{"message": {"role": "assistant", "content": ""}, "finish_reason": "stop"}]
                    merged["choices"][0].setdefault("message", {})
                    merged["choices"][0]["message"]["content"] = "".join(merged_content_parts)
                if last_usage:
                    merged["usage"] = last_usage
                _ai_log_success(meta, config, merged, t0)  # #261 成本观测
                AIModelService._last_call_meta.set(
                    {
                        "mode": "blocking",
                        "auto_continuations": continuation,
                        "finish_reason": finish_reason,
                        "max_tokens": effective_max_tokens,
                        "model": config.model_name,
                    }
                )
                return merged
        except httpx.HTTPStatusError as e:
            provider_name = config.get_model_type_display()
            error_msg = f"{provider_name} API返回错误 {e.response.status_code}: {e.response.text}"
            logger.error(error_msg)
            _ai_log_fail(meta, config, t0, error_msg)  # #261 成本观测
            raise Exception(error_msg)
        except httpx.TimeoutException as e:
            provider_name = config.get_model_type_display()
            logger.error(f"{provider_name} API请求超时: {repr(e)}")
            _ai_log_fail(meta, config, t0, f"{provider_name} API请求超时")  # #261 成本观测
            raise Exception(f"{provider_name} API请求超时，请稍后再试或检查网络连接")
        except Exception as e:
            provider_name = config.get_model_type_display()
            # Use repr(e) to capture the full exception type and message, especially if str(e) is empty
            logger.error(f"{provider_name} API调用失败: {repr(e)}")
            _ai_log_fail(meta, config, t0, f"{provider_name} API调用失败: {str(e) or repr(e)}")  # #261 成本观测
            raise Exception(f"{provider_name} API调用失败: {str(e) or repr(e)}")
    
    @staticmethod
    async def call_openai_compatible_api_stream(
        config,
        messages: List[Dict[str, str]],
        on_chunk: Callable[[str], None],
        *,
        min_tokens: int = 0,
    ) -> str:
        """流式调用 OpenAI 兼容 API，每收到一段内容就调用 on_chunk(text)，返回完整内容。"""
        headers = {
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json'
        }
        data, effective_max_tokens = AIModelService._build_api_payload(
            config, messages, stream=True, min_tokens=min_tokens
        )
        url = AIModelService._resolve_chat_completions_url(config)
        full_content: List[str] = []
        continuation = 0
        last_finish_reason: str = ""
        last_usage: Dict[str, Any] = {}  # #261 累计流式 usage

        async def _stream_once(payload: Dict[str, Any]) -> str:
            nonlocal continuation
            local_parts: List[str] = []
            finish_reason: str = ""
            stream_usage: Dict[str, Any] = {}

            async with httpx.AsyncClient(timeout=AIModelService.API_TIMEOUT_SECONDS) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        s = line[6:].strip()
                        if s == "[DONE]":
                            break
                        try:
                            j = json.loads(s)
                        except json.JSONDecodeError:
                            continue

                        usage = j.get("usage") or {}
                        if usage:
                            stream_usage = usage
                            last_usage.update(usage)  # #261 累计

                        choices = (j.get("choices") or [{}])
                        c0 = choices[0] or {}
                        if c0.get("finish_reason"):
                            finish_reason = c0.get("finish_reason") or finish_reason
                        delta = (c0.get("delta") or {}) if isinstance(c0, dict) else {}
                        part = (delta.get("content") or "") if isinstance(delta, dict) else ""
                        if part:
                            local_parts.append(part)
                            await sync_to_async(on_chunk)(part)

            text = "".join(local_parts)
            nonlocal last_finish_reason
            if finish_reason:
                last_finish_reason = finish_reason

            if (
                AIModelService._should_auto_continue(finish_reason, stream_usage, effective_max_tokens)
                and continuation < AIModelService.MAX_AUTO_CONTINUATIONS
            ):
                continuation += 1
                next_payload = dict(payload)
                next_messages = list(next_payload.get("messages") or [])
                next_messages.append({"role": "assistant", "content": text})
                next_messages.append({"role": "user", "content": AIModelService.CONTINUE_USER_MESSAGE})
                next_payload["messages"] = next_messages
                await sync_to_async(on_chunk)("\n\n")
                text += await _stream_once(next_payload)

            return text

        try:
            text = await _stream_once(data)
            if text:
                full_content.append(text)
        except Exception as e:
            logger.error(f"流式 API 调用失败: {repr(e)}")
            raise

        AIModelService._last_call_meta.set(
            {
                "mode": "stream",
                "auto_continuations": continuation,
                "finish_reason": last_finish_reason or "",
                "max_tokens": effective_max_tokens,
                "model": getattr(config, "model_name", None),
                "usage": last_usage,  # #261 成本观测
            }
        )
        return "".join(full_content)
    
    @staticmethod
    def _get_requirement_focus(task) -> str:
        meta = getattr(task, "kb_context_meta", None) or {}
        if isinstance(meta, dict) and meta.get("requirement_focus"):
            return str(meta["requirement_focus"])
        from .dify_kb_service import extract_requirement_focus

        return extract_requirement_focus(getattr(task, "title", "") or "", getattr(task, "requirement_text", "") or "")

    @staticmethod
    def _append_kb_context(user_message: str, task, *, kb_mode: str = "full") -> str:
        """
        kb_mode:
          - full: 生成阶段附带过滤后的知识库参考
          - focus: 评审/改写仅附带主需求聚焦说明（不再重复注入全文，避免偏题与超时）
          - none: 不附带知识库
        """
        if kb_mode == "none":
            return user_message

        focus = AIModelService._get_requirement_focus(task)
        if kb_mode == "focus":
            return (
                f"{user_message}\n\n"
                f"---\n\n"
                f"【主需求聚焦：{focus}】\n"
                f"评审/改写时必须以「{focus}」为范围，删除或修正与「{focus}」无关的用例"
                f"（例如主需求为 BOM 时，不应保留项目计划基线类用例）。"
            )

        kb_context = (getattr(task, "kb_context", None) or "").strip()
        graph_block = ""
        try:
            from apps.knowledge_graph.query import build_graph_relations_prompt_summary

            graph_block = build_graph_relations_prompt_summary(task)
        except Exception:
            graph_block = ""

        focus_scope = f"【主需求聚焦：{focus}】用例必须围绕此主题编写"
        if not kb_context and not graph_block:
            return f"{user_message}\n\n---\n\n{focus_scope}。"

        sections = [user_message, "---"]
        if graph_block:
            sections.append(graph_block)
        if kb_context:
            sections.extend(
                [
                    f"{focus_scope}，不得被参考文档中带偏。",
                    "【知识库增强参考（次要）】",
                    f"仅补充与「{focus}」相关的规则；勿写与「{focus}」无关的模块。",
                    "",
                    kb_context,
                ]
            )
        else:
            sections.append(f"{focus_scope}。")
        return "\n\n".join(sections)

    @staticmethod
    async def generate_test_cases_stream(task, on_chunk: Callable[[str], None]) -> str:
        """流式生成测试用例，每收到一段内容就调用 on_chunk(text)，返回完整内容。"""
        writer_prompt = AIModelService._effective_writer_system_prompt(task)
        attachments = AIModelService._get_task_image_attachments(task)
        focus = AIModelService._get_requirement_focus(task)
        user_message = AIModelService._append_kb_context(
            f"【主需求聚焦：{focus}】请根据以下内容生成测试用例（必须完整覆盖「{focus}」，勿写无关模块）：\n\n{task.requirement_text}",
            task,
            kb_mode="full",
        )
        messages = [
            {"role": "system", "content": writer_prompt},
            {"role": "user", "content": AIModelService._build_user_content_with_images(user_message, attachments)}
        ]
        return await AIModelService.call_openai_compatible_api_stream(
            task.writer_model_config, messages, on_chunk,
            min_tokens=AIModelService.MIN_WRITER_MAX_TOKENS,
        )
    
    @staticmethod
    async def call_deepseek_api(config: AIModelConfig, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """调用DeepSeek API (兼容OpenAI格式)"""
        return await AIModelService.call_openai_compatible_api(config, messages)
    
    @staticmethod
    async def call_qwen_api(config: AIModelConfig, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """调用千问API (兼容OpenAI格式)"""
        return await AIModelService.call_openai_compatible_api(config, messages)
    
    @staticmethod
    async def generate_test_cases(task: TestCaseGenerationTask) -> str:
        """生成测试用例"""
        writer_prompt = AIModelService._effective_writer_system_prompt(task)
        attachments = AIModelService._get_task_image_attachments(task)
        focus = AIModelService._get_requirement_focus(task)
        user_message = AIModelService._append_kb_context(
            f"【主需求聚焦：{focus}】请根据以下内容生成测试用例（必须完整覆盖「{focus}」，勿写无关模块）：\n\n{task.requirement_text}",
            task,
            kb_mode="full",
        )
        
        messages = [
            {"role": "system", "content": writer_prompt},
            {"role": "user", "content": AIModelService._build_user_content_with_images(user_message, attachments)}
        ]
        
        # 所有支持的模型都使用兼容OpenAI的接口
        response = await AIModelService.call_openai_compatible_api(
            task.writer_model_config, messages,
            min_tokens=AIModelService.MIN_WRITER_MAX_TOKENS,
        )
        
        return response['choices'][0]['message']['content']
    
    @staticmethod
    def _truncate_for_phase(text: str, max_chars: int) -> str:
        text = (text or "").strip()
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 20] + "\n\n...(内容已截断)..."

    @staticmethod
    async def review_test_cases(task: TestCaseGenerationTask, test_cases: str) -> str:
        """评审测试用例"""
        try:
            reviewer_prompt = task.reviewer_prompt_config.content
            focus = AIModelService._get_requirement_focus(task)
            cases = AIModelService._truncate_for_phase(test_cases, AIModelService.MAX_REVIEW_INPUT_CHARS)
            user_message = AIModelService._append_kb_context(
                f"【主需求聚焦：{focus}】\n\n需求内容：\n{task.requirement_text}\n\n"
                f"请评审以下测试用例是否覆盖「{focus}」，并指出与「{focus}」无关的用例：\n\n{cases}",
                task,
                kb_mode="focus",
            )
            
            messages = [
                {"role": "system", "content": reviewer_prompt},
                {"role": "user", "content": user_message},
            ]
            
            # 所有支持的模型都使用兼容OpenAI的接口
            response = await AIModelService.call_openai_compatible_api(
                task.reviewer_model_config, messages,
                min_tokens=AIModelService.MIN_REVIEWER_MAX_TOKENS,
            )
            
            return response['choices'][0]['message']['content']
        except Exception as e:
            logger.error(f"评审测试用例时出错: {e}")
            # 返回一个默认的评审结果
            return f"评审过程中出现错误: {str(e)}\n\n建议：测试用例结构完整，可以使用。"

    @staticmethod
    async def review_test_cases_stream(task: TestCaseGenerationTask, test_cases: str, on_chunk: Callable[[str], None]) -> str:
        """流式评审测试用例"""
        reviewer_prompt = task.reviewer_prompt_config.content
        focus = AIModelService._get_requirement_focus(task)
        cases = AIModelService._truncate_for_phase(test_cases, AIModelService.MAX_REVIEW_INPUT_CHARS)
        user_message = AIModelService._append_kb_context(
            f"【主需求聚焦：{focus}】\n\n需求内容：\n{task.requirement_text}\n\n"
            f"请评审以下测试用例是否覆盖「{focus}」，并指出与「{focus}」无关的用例：\n\n{cases}",
            task,
            kb_mode="focus",
        )
        messages = [
            {"role": "system", "content": reviewer_prompt},
            {"role": "user", "content": user_message},
        ]
        return await AIModelService.call_openai_compatible_api_stream(
            task.reviewer_model_config, messages, on_chunk,
            min_tokens=AIModelService.MIN_REVIEWER_MAX_TOKENS,
        )

    @staticmethod
    async def revise_test_cases(task: TestCaseGenerationTask, test_cases: str, review_feedback: str) -> str:
        """根据评审意见生成最终版用例（非流式）"""
        writer_prompt = AIModelService._effective_writer_system_prompt(task)
        attachments = AIModelService._get_task_image_attachments(task)
        focus = AIModelService._get_requirement_focus(task)
        cases = AIModelService._truncate_for_phase(test_cases, AIModelService.MAX_REVISE_INPUT_CHARS)
        feedback = AIModelService._truncate_for_phase(review_feedback, 8000)
        user_message = AIModelService._append_kb_context(
            (
                f"【主需求聚焦：{focus}】\n\n"
                f"需求内容：\n{task.requirement_text}\n\n"
                f"原测试用例：\n{cases}\n\n"
                f"评审意见：\n{feedback}\n\n"
                f"请输出最终版测试用例：必须围绕「{focus}」，删除与「{focus}」无关的用例，保留并完善相关用例。"
            ),
            task,
            kb_mode="focus",
        )
        messages = [
            {"role": "system", "content": writer_prompt},
            {"role": "user", "content": AIModelService._build_user_content_with_images(user_message, attachments)},
        ]
        response = await AIModelService.call_openai_compatible_api(
            task.writer_model_config, messages,
            min_tokens=AIModelService.MIN_WRITER_MAX_TOKENS,
        )
        return response['choices'][0]['message']['content']

    @staticmethod
    async def revise_test_cases_stream(
        task: TestCaseGenerationTask,
        test_cases: str,
        review_feedback: str,
        on_chunk: Callable[[str], None],
    ) -> str:
        """流式生成最终版用例"""
        writer_prompt = AIModelService._effective_writer_system_prompt(task)
        attachments = AIModelService._get_task_image_attachments(task)
        focus = AIModelService._get_requirement_focus(task)
        cases = AIModelService._truncate_for_phase(test_cases, AIModelService.MAX_REVISE_INPUT_CHARS)
        feedback = AIModelService._truncate_for_phase(review_feedback, 8000)
        user_message = AIModelService._append_kb_context(
            (
                f"【主需求聚焦：{focus}】\n\n"
                f"需求内容：\n{task.requirement_text}\n\n"
                f"原测试用例：\n{cases}\n\n"
                f"评审意见：\n{feedback}\n\n"
                f"请输出最终版测试用例：必须围绕「{focus}」，删除与「{focus}」无关的用例，保留并完善相关用例。"
            ),
            task,
            kb_mode="focus",
        )
        messages = [
            {"role": "system", "content": writer_prompt},
            {"role": "user", "content": AIModelService._build_user_content_with_images(user_message, attachments)},
        ]
        return await AIModelService.call_openai_compatible_api_stream(
            task.writer_model_config, messages, on_chunk,
            min_tokens=AIModelService.MIN_WRITER_MAX_TOKENS,
        )

    @staticmethod
    def _build_continue_refine_user_message(
        task: TestCaseGenerationTask,
        existing_cases: str,
        refinement_instructions: str,
    ) -> str:
        focus = AIModelService._get_requirement_focus(task)
        cases = AIModelService._truncate_for_phase(existing_cases, AIModelService.MAX_REVISE_INPUT_CHARS)
        instructions = AIModelService._truncate_for_phase((refinement_instructions or "").strip(), 8000)
        if not instructions:
            instructions = "（用户未填写文字说明，请结合新上传的界面/步骤截图优化现有用例）"
        return AIModelService._append_kb_context(
            (
                f"【主需求聚焦：{focus}】\n\n"
                f"原始需求：\n{task.requirement_text}\n\n"
                f"当前测试用例（请在此基础上修改，勿从零重写）：\n{cases}\n\n"
                f"本次补充要求（必须落实）：\n{instructions}\n\n"
                f"请输出更新后的**完整**测试用例：\n"
                f"1. 保留仍有效的现有用例，按补充要求增删改\n"
                f"2. 若有界面/步骤截图，仅用于完善操作步骤与预期结果，不作为新增需求条款\n"
                f"3. 保持相同 Markdown 表格格式，不要省略未改动的用例"
            ),
            task,
            kb_mode="focus",
        )

    @staticmethod
    async def continue_refine_test_cases(
        task: TestCaseGenerationTask,
        existing_cases: str,
        refinement_instructions: str,
    ) -> str:
        """在现有用例基础上按用户补充要求迭代修改（非流式）。"""
        writer_prompt = AIModelService._effective_writer_system_prompt(task)
        attachments = AIModelService._get_task_image_attachments(task)
        user_message = AIModelService._build_continue_refine_user_message(
            task, existing_cases, refinement_instructions
        )
        messages = [
            {"role": "system", "content": writer_prompt},
            {"role": "user", "content": AIModelService._build_user_content_with_images(user_message, attachments)},
        ]
        response = await AIModelService.call_openai_compatible_api(
            task.writer_model_config, messages,
            min_tokens=AIModelService.MIN_WRITER_MAX_TOKENS,
        )
        return response['choices'][0]['message']['content']

    @staticmethod
    async def continue_refine_test_cases_stream(
        task: TestCaseGenerationTask,
        existing_cases: str,
        refinement_instructions: str,
        on_chunk: Callable[[str], None],
    ) -> str:
        """在现有用例基础上按用户补充要求迭代修改（流式）。"""
        writer_prompt = AIModelService._effective_writer_system_prompt(task)
        attachments = AIModelService._get_task_image_attachments(task)
        user_message = AIModelService._build_continue_refine_user_message(
            task, existing_cases, refinement_instructions
        )
        messages = [
            {"role": "system", "content": writer_prompt},
            {"role": "user", "content": AIModelService._build_user_content_with_images(user_message, attachments)},
        ]
        return await AIModelService.call_openai_compatible_api_stream(
            task.writer_model_config, messages, on_chunk,
            min_tokens=AIModelService.MIN_WRITER_MAX_TOKENS,
        )


class TestCaseSkill(models.Model):
    """Skill 技能包

    每个 Skill 是一个完整的"技能包"：
    - system_prompt: 核心系统提示词（定义角色、输入说明、输出规范）
    - constraint_rules: 约束规则（自然语言描述，注入到提示词中）
    - output_format: 输出格式（markdown/json/excel/xmind）
    - skill_type: 技能类型（需求分析/需求评审/用例评审/用例生成/自定义）

    可通过 Hermes Agent 自然语言调用（"使用xxx技能，对xxx进行分析"），
    也可在用例生成页面选择使用。

    向后兼容：保留 writer_model_config / reviewer_model_config /
    writer_prompt_config / reviewer_prompt_config / generation_config 五个 FK，
    作为"高级配置"（不填则用系统默认活跃配置）。
    """
    SKILL_TYPE_CHOICES = [
        ('requirements_analysis', '需求分析'),
        ('requirement_reviewer', '需求评审'),
        ('testcase_reviewer', '用例评审'),
        ('testcase_generator', '用例生成'),
        ('digital_human', '数字人'),
        ('custom', '自定义'),
    ]

    OUTPUT_FORMAT_CHOICES = [
        ('markdown', 'Markdown 表格'),
        ('json', 'JSON 结构化'),
        ('excel', 'Excel 表格'),
        ('xmind', '飞书思维导图'),
    ]

    CATEGORY_CHOICES = [
        ('general', '通用'),
        ('api', 'API测试'),
        ('ui', 'UI测试'),
        ('performance', '性能测试'),
        ('security', '安全测试'),
        ('mobile', '移动端测试'),
        ('integration', '集成测试'),
        ('custom', '自定义'),
    ]

    # ── 基本信息 ──
    name = models.CharField(max_length=100, verbose_name='Skill名称')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    icon = models.CharField(max_length=10, blank=True, default='🎯', verbose_name='图标(emoji)')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general', verbose_name='分类')

    # ── 技能包核心字段 ──
    skill_type = models.CharField(
        max_length=30, choices=SKILL_TYPE_CHOICES, default='testcase_generator',
        verbose_name='技能类型'
    )
    system_prompt = models.TextField(
        blank=True, default='', verbose_name='系统提示词',
        help_text='技能的核心系统提示词，定义角色、输入说明、输出规范'
    )
    constraint_rules = models.TextField(
        blank=True, default='', verbose_name='约束规则',
        help_text='约束规则（自然语言描述），会注入到系统提示词中'
    )
    output_format = models.CharField(
        max_length=20, choices=OUTPUT_FORMAT_CHOICES, default='markdown',
        verbose_name='输出格式'
    )
    is_builtin = models.BooleanField(default=False, verbose_name='是否内置')
    version = models.CharField(max_length=20, default='1.0', verbose_name='版本号')

    # ── 团队模板（自定义输出列）──
    template_file = models.FileField(
        upload_to='skill_templates/', blank=True, null=True, verbose_name='团队模板文件'
    )
    template_columns = models.JSONField(
        default=list, blank=True, verbose_name='模板列名',
        help_text='上传 Excel/CSV 后自动解析首行得到的列名列表'
    )

    # ── 结构化技能包字段（通用、可移植）──
    author = models.CharField(
        max_length=100, blank=True, default='', verbose_name='作者',
        help_text='技能包作者，用于导入导出时的归属标记'
    )
    tags = models.JSONField(
        default=list, blank=True, verbose_name='标签',
        help_text='标签列表，如 ["api","security"]'
    )
    input_spec = models.JSONField(
        default=dict, blank=True, verbose_name='输入规范',
        help_text='期望的输入类型与说明，如 {"type":"prd|swagger|image|free","description":"..."}'
    )
    output_spec = models.JSONField(
        default=dict, blank=True, verbose_name='输出规范',
        help_text='输出格式与列定义，如 {"format":"markdown|json|excel|xmind","columns":[...],"description":"..."}'
    )
    tools = models.JSONField(
        default=list, blank=True, verbose_name='关联工具',
        help_text='该技能可使用的工具/能力标识列表，如 ["run_api_test","run_ui_test_suite"]'
    )

    # ── 技能包文件结构（对应 README.md / assets / input / references / scripts）──
    readme = models.TextField(
        blank=True, default='', verbose_name='README.md',
        help_text='技能包说明文档（Markdown）'
    )
    trigger_keywords = models.JSONField(
        default=list, blank=True, verbose_name='触发关键词',
        help_text='触发该 Skill 的关键词列表，如 ["生成测试用例", "PRD转测试用例"]'
    )
    package_files = models.JSONField(
        default=dict, blank=True, verbose_name='包内文件',
        help_text='结构化文件内容：{"assets": [...], "input": [...], "references": [...], "scripts": [...]}'
    )

    # ── 高级配置（向后兼容，可选） ──
    writer_model_config = models.ForeignKey(
        AIModelConfig, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='skills_as_writer', verbose_name='编写模型配置'
    )
    reviewer_model_config = models.ForeignKey(
        AIModelConfig, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='skills_as_reviewer', verbose_name='评审模型配置'
    )
    writer_prompt_config = models.ForeignKey(
        PromptConfig, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='skills_as_writer', verbose_name='编写提示词配置'
    )
    reviewer_prompt_config = models.ForeignKey(
        PromptConfig, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='skills_as_reviewer', verbose_name='评审提示词配置'
    )
    generation_config = models.ForeignKey(
        GenerationConfig, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='skills', verbose_name='生成行为配置'
    )

    # ── 管理字段 ──
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    sort_order = models.IntegerField(default=0, verbose_name='排序权重')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'testcase_skill'
        verbose_name = 'Skill技能包'
        verbose_name_plural = 'Skill技能包'
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return f"{self.icon} {self.name}"

    @classmethod
    def get_active_skills(cls):
        return cls.objects.filter(is_active=True).select_related(
            'writer_model_config', 'reviewer_model_config',
            'writer_prompt_config', 'reviewer_prompt_config',
            'generation_config',
        ).order_by('sort_order', '-created_at')

    def get_full_system_prompt(self) -> str:
        """组装完整的系统提示词：system_prompt + constraint_rules"""
        parts = [self.system_prompt]
        if self.constraint_rules.strip():
            parts.append(f"\n\n# 约束规则\n{self.constraint_rules}")
        return "\n".join(parts)

    def resolve_model_config(self):
        """解析 Skill 绑定的 writer 模型配置，没有则返回系统默认活跃配置"""
        if self.writer_model_config_id:
            return self.writer_model_config
        return AIModelConfig.objects.filter(
            role='writer', is_active=True
        ).order_by('-updated_at').first()

    def resolve_prompt_content(self) -> str:
        """解析 Skill 的提示词内容：优先 system_prompt，没有则从 writer_prompt_config 取"""
        if self.system_prompt.strip():
            return self.get_full_system_prompt()
        if self.writer_prompt_config_id and self.writer_prompt_config.content:
            return self.writer_prompt_config.content
        # 兜底：从默认活跃提示词取
        active_prompt = PromptConfig.objects.filter(
            prompt_type='writer', is_active=True
        ).order_by('-updated_at').first()
        return active_prompt.content if active_prompt else ''


class SkillArtifact(models.Model):
    """Skill 包内的独立文件（assets / input / references / scripts）。"""
    ARTIFACT_TYPE_CHOICES = [
        ('asset', 'assets'),
        ('input', 'input'),
        ('reference', 'references'),
        ('script', 'scripts'),
        ('other', 'other'),
    ]

    skill = models.ForeignKey(
        TestCaseSkill, on_delete=models.CASCADE, related_name='artifacts',
        verbose_name='所属 Skill'
    )
    artifact_type = models.CharField(
        max_length=20, choices=ARTIFACT_TYPE_CHOICES, default='other',
        verbose_name='文件类型'
    )
    path = models.CharField(max_length=500, verbose_name='包内路径')
    file = models.FileField(upload_to='skill_artifacts/%Y/%m/', blank=True, null=True, verbose_name='文件')
    text_content = models.TextField(blank=True, default='', verbose_name='文本内容')
    is_binary = models.BooleanField(default=False, verbose_name='是否二进制')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'skill_artifact'
        verbose_name = 'Skill 文件'
        verbose_name_plural = 'Skill 文件'
        ordering = ['artifact_type', 'path']
        unique_together = ['skill', 'path']

    def __str__(self):
        return f"{self.skill.name}/{self.path}"


from . import kb_models  # noqa: F401 — register KbFunction tables with Django