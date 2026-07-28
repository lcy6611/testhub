"""缺陷实体与发布结论模型（#260 需求→缺陷闭环）。

设计要点：
- Defect 是真实缺陷实体，替换此前 TestRunCase.defects 仅存 JSON ID 列表的弱关联。
- ReleaseConclusion 记录一次"质量门禁"评估出的发布结论，可追溯到项目/版本/执行。
- 跨应用 FK 一律用字符串引用，避免应用加载顺序导致的循环导入。
"""
from django.db import models
from django.utils import timezone
from apps.users.models import User
from apps.projects.models import Project


class Defect(models.Model):
    """缺陷实体"""

    SEVERITY_CHOICES = [
        ('S1', '致命'),
        ('S2', '严重'),
        ('S3', '一般'),
        ('S4', '轻微'),
    ]

    STATUS_CHOICES = [
        ('open', '待处理'),
        ('in_progress', '处理中'),
        ('resolved', '已修复'),
        ('closed', '已关闭'),
        ('reopened', '重新打开'),
    ]

    title = models.CharField(max_length=300, verbose_name='缺陷标题')
    description = models.TextField(blank=True, verbose_name='缺陷描述')
    severity = models.CharField(
        max_length=4, choices=SEVERITY_CHOICES, default='S3', verbose_name='严重程度'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='open', verbose_name='状态'
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='defects', verbose_name='所属项目'
    )
    requirement = models.ForeignKey(
        'requirement_analysis.BusinessRequirement',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='defects', verbose_name='关联需求'
    )
    test_run_case = models.ForeignKey(
        'executions.TestRunCase',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='defects_obj', verbose_name='关联执行用例'
    )
    test_run = models.ForeignKey(
        'executions.TestRun',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='defects', verbose_name='关联执行'
    )
    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reported_defects', verbose_name='报告人'
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_defects', verbose_name='指派人'
    )
    steps_to_reproduce = models.TextField(blank=True, verbose_name='复现步骤')
    environment = models.CharField(
        max_length=200, blank=True, default='', verbose_name='环境信息'
    )
    source = models.CharField(
        max_length=50, blank=True, default='manual',
        verbose_name='缺陷来源',
        help_text='manual=手动创建 / execution=用例执行 / performance=性能测试 / hermes=数字人 / ai=AI分析'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'defects'
        verbose_name = '缺陷'
        verbose_name_plural = '缺陷'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title}"


class DefectAttachment(models.Model):
    """缺陷附件（截图/日志/录像等）。"""
    KIND_CHOICES = [
        ('screenshot', '截图'),
        ('log', '日志'),
        ('video', '录像'),
        ('other', '其他'),
    ]

    defect = models.ForeignKey(
        Defect, on_delete=models.CASCADE, related_name='attachments', verbose_name='所属缺陷'
    )
    kind = models.CharField(
        max_length=20, choices=KIND_CHOICES, default='screenshot', verbose_name='附件类型'
    )
    file = models.FileField(upload_to='defects/%Y/%m/', verbose_name='文件')
    original_name = models.CharField(max_length=255, blank=True, verbose_name='原始文件名')
    size_bytes = models.PositiveIntegerField(default=0, verbose_name='文件大小(字节)')
    mime_type = models.CharField(max_length=100, blank=True, verbose_name='MIME 类型')
    caption = models.CharField(max_length=300, blank=True, verbose_name='说明')
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='uploaded_defect_attachments', verbose_name='上传者'
    )
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name='上传时间')

    class Meta:
        db_table = 'defect_attachments'
        verbose_name = '缺陷附件'
        verbose_name_plural = '缺陷附件'
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.defect_id}-{self.original_name or self.file.name}"


class ReleaseConclusion(models.Model):
    """发布结论（质量门禁评估结果落库）"""

    CONCLUSION_CHOICES = [
        ('GO', '可发布'),
        ('CONDITIONAL_GO', '有条件发布'),
        ('NO_GO', '不可发布'),
    ]

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE,
        related_name='release_conclusions', verbose_name='所属项目'
    )
    version = models.ForeignKey(
        'versions.Version',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='release_conclusions', verbose_name='关联版本'
    )
    test_run = models.ForeignKey(
        'executions.TestRun',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='release_conclusions', verbose_name='关联执行'
    )
    conclusion = models.CharField(
        max_length=20, choices=CONCLUSION_CHOICES, verbose_name='发布结论'
    )
    metrics = models.JSONField(default=dict, verbose_name='评估指标')
    reasons = models.JSONField(default=list, verbose_name='结论原因')
    thresholds = models.JSONField(default=dict, verbose_name='使用阈值')
    note = models.TextField(blank=True, verbose_name='备注')
    approver = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_releases', verbose_name='审批人'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'release_conclusions'
        verbose_name = '发布结论'
        verbose_name_plural = '发布结论'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_conclusion_display()} - {self.project.name}"
