from django.db import models
from django.utils import timezone
from apps.users.models import User

class Project(models.Model):
    """项目模型"""
    STATUS_CHOICES = [
        ('active', '进行中'),
        ('paused', '暂停'),
        ('completed', '已完成'),
        ('archived', '已归档'),
    ]
    
    name = models.CharField(max_length=200, verbose_name='项目名称')
    description = models.TextField(blank=True, verbose_name='项目描述')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='状态')
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects', verbose_name='负责人')
    members = models.ManyToManyField(User, through='ProjectMember', related_name='joined_projects', verbose_name='成员')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'projects'
        verbose_name = '项目'
        verbose_name_plural = '项目'
        ordering = ['-created_at']

class ProjectMember(models.Model):
    """项目成员"""
    ROLE_CHOICES = [
        ('owner', '负责人'),
        ('admin', '管理员'),
        ('developer', '开发者'),
        ('tester', '测试者'),
        ('viewer', '观察者'),
    ]
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='tester', verbose_name='角色')
    joined_at = models.DateTimeField(default=timezone.now, verbose_name='加入时间')
    
    class Meta:
        db_table = 'project_members'
        unique_together = ['project', 'user']
        verbose_name = '项目成员'
        verbose_name_plural = '项目成员'

class ProjectEnvironment(models.Model):
    """项目环境"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='environments')
    name = models.CharField(max_length=100, verbose_name='环境名称')
    base_url = models.URLField(verbose_name='基础URL')
    description = models.TextField(blank=True, verbose_name='环境描述')
    variables = models.JSONField(default=dict, verbose_name='环境变量')
    is_default = models.BooleanField(default=False, verbose_name='是否默认')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    
    class Meta:
        db_table = 'project_environments'
        verbose_name = '项目环境'
        verbose_name_plural = '项目环境'


MODULE_CHOICES = [
    ('ui_automation', 'UI自动化'),
    ('api_testing', 'API测试'),
    ('app_automation', 'APP自动化'),
]


class ProjectMapping(models.Model):
    """核心项目 ↔ 各自动化模块项目的映射表。

    用于打通 projects.Project 与 UiProject / ApiProject / AppProject，
    使知识图谱等跨模块功能能按核心项目过滤各模块数据。
    """
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name='module_mappings',
        verbose_name='核心项目',
    )
    module = models.CharField(max_length=32, choices=MODULE_CHOICES, verbose_name='模块')
    external_project_id = models.PositiveIntegerField(verbose_name='模块项目ID')
    external_project_name = models.CharField(max_length=200, blank=True, default='', verbose_name='模块项目名称（冗余）')
    auto_matched = models.BooleanField(default=False, verbose_name='是否自动匹配')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'project_mappings'
        verbose_name = '项目映射'
        verbose_name_plural = '项目映射'
        unique_together = [('module', 'external_project_id')]
        indexes = [
            models.Index(fields=['project', 'module']),
        ]

    def __str__(self):
        return f'{self.project.name} → {self.module}#{self.external_project_id}'