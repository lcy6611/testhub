"""缺陷实体与发布结论模型（#260 需求→缺陷闭环）。

设计要点：
- Defect 是真实缺陷实体，替换此前 TestRunCase.defects 仅存 JSON ID 列表的弱关联。
- ReleaseConclusion 记录一次"质量门禁"评估出的发布结论，可追溯到项目/版本/执行。
- 跨应用 FK 一律用字符串引用，避免应用加载顺序导致的循环导入。
- 在自有模型上扩展（借鉴开源 8 态状态机 + 流转历史/评论），保留 requirement/test_run 闭环。
"""
from django.db import models
from django.utils import timezone
from apps.users.models import User
from apps.projects.models import Project


class Defect(models.Model):
    """缺陷实体

    状态机在自有值（open/in_progress/resolved/closed/reopened）基础上，补齐
    new/fixed/rejected，形成 8 态，保持与历史数据兼容。
    """

    SEVERITY_CHOICES = [
        ('S1', '致命'),
        ('S2', '严重'),
        ('S3', '一般'),
        ('S4', '轻微'),
    ]

    # 8 态状态机：保留自有历史值 + 补齐 new/fixed/rejected
    STATUS_CHOICES = [
        ('new', '新建'),
        ('open', '待处理'),          # 自有历史值
        ('in_progress', '处理中'),    # 自有历史值
        ('resolved', '已修复'),       # 自有历史值
        ('fixed', '待验证'),
        ('closed', '已关闭'),         # 自有历史值
        ('rejected', '已驳回'),
        ('reopened', '重新打开'),     # 自有历史值
    ]

    PRIORITY_CHOICES = [
        ('P0', 'P0-紧急'),
        ('P1', 'P1-高'),
        ('P2', 'P2-中'),
        ('P3', 'P3-低'),
    ]

    TYPE_CHOICES = [
        ('functional', '功能缺陷'),
        ('ui', '界面缺陷'),
        ('compatibility', '兼容性缺陷'),
        ('performance', '性能缺陷'),
        ('security', '安全缺陷'),
        ('data', '数据缺陷'),
        ('other', '其他'),
    ]

    SOURCE_CHOICES = [
        ('manual', '手动创建'),
        ('execution', '用例执行'),
        ('performance', '性能测试'),
        ('hermes', '数字人'),
        ('ai', 'AI分析'),
        ('api_testing', '接口测试'),
        ('ui_automation', 'UI自动化'),
        ('app_automation', 'APP自动化'),
        ('production', '生产反馈'),
    ]

    # 缺陷编号（自动生成，格式 BUG-YYYYMMDD-NNNN）；历史数据为空(NULL)
    bug_code = models.CharField(
        max_length=32, unique=True, null=True, blank=True, verbose_name='缺陷编号'
    )
    title = models.CharField(max_length=300, verbose_name='缺陷标题')
    description = models.TextField(blank=True, verbose_name='缺陷描述')
    steps_to_reproduce = models.TextField(blank=True, verbose_name='复现步骤')
    expected_result = models.TextField(blank=True, verbose_name='预期结果')
    actual_result = models.TextField(blank=True, verbose_name='实际结果')
    severity = models.CharField(
        max_length=4, choices=SEVERITY_CHOICES, default='S3', verbose_name='严重程度'
    )
    priority = models.CharField(
        max_length=4, choices=PRIORITY_CHOICES, default='P2', verbose_name='优先级'
    )
    defect_type = models.CharField(
        max_length=30, choices=TYPE_CHOICES, default='functional', verbose_name='缺陷类型'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='open', verbose_name='状态'
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='defects', verbose_name='所属项目'
    )
    version = models.ForeignKey(
        'versions.Version',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='defects', verbose_name='发现版本'
    )
    module = models.CharField(max_length=120, blank=True, default='', verbose_name='所属模块')
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
    related_testcase = models.ForeignKey(
        'testcases.TestCase',
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='defects', verbose_name='关联用例'
    )
    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reported_defects', verbose_name='报告人'
    )
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_defects', verbose_name='指派人'
    )
    verifier = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_defects', verbose_name='验证人'
    )
    resolver = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_defects', verbose_name='处理人'
    )
    source = models.CharField(
        max_length=50, blank=True, default='manual',
        choices=SOURCE_CHOICES,
        verbose_name='缺陷来源'
    )
    due_at = models.DateTimeField(null=True, blank=True, verbose_name='期望修复时间')
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name='解决时间')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='关闭时间')
    environment = models.CharField(
        max_length=200, blank=True, default='', verbose_name='环境信息'
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'defects'
        verbose_name = '缺陷'
        verbose_name_plural = '缺陷'
        ordering = ['-created_at']

    def __str__(self):
        code = self.bug_code or f'#{self.id}'
        return f"[{code}] {self.title}"

    def save(self, *args, **kwargs):
        if not self.bug_code:
            today = timezone.localdate().strftime('%Y%m%d')
            prefix = f'BUG-{today}-'
            last = Defect.objects.filter(bug_code__startswith=prefix).order_by('-bug_code').first()
            next_number = 1
            if last and last.bug_code:
                try:
                    next_number = int(last.bug_code.rsplit('-', 1)[1]) + 1
                except (IndexError, ValueError):
                    next_number = 1
            self.bug_code = f'{prefix}{next_number:04d}'
        super().save(*args, **kwargs)


class DefectTransitionLog(models.Model):
    """缺陷状态流转历史（每次状态变更落一条记录）。"""

    defect = models.ForeignKey(
        Defect, on_delete=models.CASCADE, related_name='transition_logs', verbose_name='所属缺陷'
    )
    from_status = models.CharField(max_length=20, blank=True, verbose_name='原状态')
    to_status = models.CharField(max_length=20, verbose_name='目标状态')
    operator = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='defect_transitions', verbose_name='操作人'
    )
    target_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='defect_transition_targets', verbose_name='目标处理人'
    )
    comment = models.TextField(blank=True, verbose_name='流转说明')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='操作时间')

    class Meta:
        db_table = 'defect_transition_logs'
        verbose_name = '缺陷流转历史'
        verbose_name_plural = '缺陷流转历史'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.defect_id}: {self.from_status} -> {self.to_status}"


class DefectComment(models.Model):
    """缺陷评论。"""

    defect = models.ForeignKey(
        Defect, on_delete=models.CASCADE, related_name='comments', verbose_name='所属缺陷'
    )
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='defect_comments', verbose_name='评论人'
    )
    content = models.TextField(verbose_name='评论内容')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='评论时间')

    class Meta:
        db_table = 'defect_comments'
        verbose_name = '缺陷评论'
        verbose_name_plural = '缺陷评论'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.defect_id}-{self.author_id}: {self.content[:20]}"


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
