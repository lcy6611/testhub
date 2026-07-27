# -*- coding: utf-8 -*-
"""统一执行诊断基础层的数据模型。

这些模型是「执行稳定性三件套」（证据链 / 自愈重试 / 失败诊断）的公共底座，
被 UI / API / APP 三端执行链路共享，避免各自重复造轮子。
所有新增字段在接入端均为 nullable / 可选，保证向后兼容。
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class ChainType(models.TextChoices):
    """执行链路类型。"""
    UI = 'UI', _('UI 自动化')
    API = 'API', _('接口测试')
    APP = 'APP', _('APP 自动化')
    PERF = 'PERF', _('性能测试')
    UNKNOWN = 'UNKNOWN', _('未知')


class FailureCategory(models.TextChoices):
    """失败分类枚举（规则优先诊断 + 可选 LLM 增强共用）。"""
    NETWORK_TIMEOUT = 'NETWORK_TIMEOUT', _('网络超时')
    CONNECTION_ERROR = 'CONNECTION_ERROR', _('连接失败')
    ASSERTION_ERROR = 'ASSERTION_ERROR', _('断言失败')
    LOCATOR_NOT_FOUND = 'LOCATOR_NOT_FOUND', _('定位器未找到')
    ELEMENT_NOT_FOUND = 'ELEMENT_NOT_FOUND', _('元素未找到')
    ELEMENT_NOT_INTERACTABLE = 'ELEMENT_NOT_INTERACTABLE', _('元素不可交互')
    AUTH_ERROR = 'AUTH_ERROR', _('鉴权失败')
    HTTP_4XX = 'HTTP_4XX', _('客户端错误(4xx)')
    HTTP_5XX = 'HTTP_5XX', _('服务端错误(5xx)')
    DEVICE_OFFLINE = 'DEVICE_OFFLINE', _('设备离线')
    APP_CRASH = 'APP_CRASH', _('应用崩溃')
    TIMEOUT = 'TIMEOUT', _('执行超时')
    UNKNOWN = 'UNKNOWN', _('未知错误')


class ExecutionEvidence(models.Model):
    """执行证据链条目。

    每一步执行（或整个执行）可挂载多种证据：截图、请求/响应、日志、HAR、视频、控制台等。
    execution_id 为字符串，以兼容三端不同的主键类型（UUID / int）。
    """
    EVIDENCE_TYPE_CHOICES = [
        ('SCREENSHOT', _('截图')),
        ('REQUEST_RESPONSE', _('请求响应')),
        ('LOG', _('日志')),
        ('HAR', _('HAR')),
        ('VIDEO', _('视频')),
        ('CONSOLE', _('控制台')),
        ('TRACE', _('调用链')),
        ('OTHER', _('其他')),
    ]

    chain = models.CharField(max_length=20, choices=ChainType.choices, default=ChainType.UNKNOWN, verbose_name=_('执行链路'))
    execution_id = models.CharField(max_length=64, db_index=True, verbose_name=_('执行ID'),
                                    help_text=_('套件执行 / 运行 ID，兼容 UUID 与自增主键'))
    step_key = models.CharField(max_length=128, blank=True, default='', db_index=True, verbose_name=_('步骤标识'),
                                help_text=_('执行内部的步骤标识（如步骤序号 / 用例ID），可为空表示整次执行'))
    evidence_type = models.CharField(max_length=40, choices=EVIDENCE_TYPE_CHOICES, verbose_name=_('证据类型'))
    payload = models.JSONField(default=dict, blank=True, verbose_name=_('证据内容'),
                               help_text=_('灵活结构：路径、状态码、URL、头部摘要、正文片段、时长等'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('采集时间'))

    class Meta:
        db_table = 'execution_evidence'
        verbose_name = _('执行证据')
        verbose_name_plural = _('执行证据')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['chain', 'execution_id']),
            models.Index(fields=['chain', 'execution_id', 'step_key']),
        ]

    def __str__(self):
        return f'[{self.chain}] {self.evidence_type} @ {self.execution_id}/{self.step_key or "-"}'


class RetryAttempt(models.Model):
    """单次执行步骤的重试尝试记录。

    与 retry.run_with_retry 配合：每一次失败尝试都会落一条记录，便于复盘重试是否生效、
    触发分类、以及自愈前后对比。
    """
    chain = models.CharField(max_length=20, choices=ChainType.choices, default=ChainType.UNKNOWN, verbose_name=_('执行链路'))
    execution_id = models.CharField(max_length=64, db_index=True, verbose_name=_('执行ID'))
    step_key = models.CharField(max_length=128, blank=True, default='', db_index=True, verbose_name=_('步骤标识'))
    attempt_no = models.PositiveIntegerField(default=1, verbose_name=_('尝试序号'))
    trigger_category = models.CharField(max_length=30, choices=FailureCategory.choices, default=FailureCategory.UNKNOWN,
                                        verbose_name=_('触发分类'))
    success = models.BooleanField(default=False, verbose_name=_('是否成功'))
    error_message = models.TextField(blank=True, default='', verbose_name=_('错误信息'))
    duration_ms = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('耗时(ms)'))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('记录时间'))

    class Meta:
        db_table = 'execution_retry_attempt'
        verbose_name = _('重试尝试')
        verbose_name_plural = _('重试尝试')
        ordering = ['execution_id', 'step_key', 'attempt_no']
        indexes = [
            models.Index(fields=['chain', 'execution_id']),
            models.Index(fields=['chain', 'execution_id', 'step_key']),
        ]

    def __str__(self):
        return f'[{self.chain}] #{self.attempt_no} {self.trigger_category} -> {"OK" if self.success else "FAIL"}'
