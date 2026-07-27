# -*- coding: utf-8 -*-
"""AI 评测与反馈闭环 — 模型层。

包含：
- PromptVersion  版本化提示词库（替代旧 PromptConfig 无版本的问题）
- AICallLog      AI 调用成本/用量观测（成本治理基础）
- EvalDataset    评测数据集
- EvalCase       评测用例（输入/期望/判分标准）
- EvalRun        评测运行
- EvalResult     评测结果（逐用例）
- AiFeedback     人工反馈（反馈学习入口）
"""
import json

from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class PromptVersion(models.Model):
    """版本化提示词。同一 key 下版本号自增，仅一个 is_active。"""
    CATEGORY_CHOICES = [
        ("writer", "用例编写"),
        ("reviewer", "用例评审"),
        ("general", "通用"),
        ("custom", "自定义"),
    ]

    key = models.CharField(max_length=80, verbose_name="提示词标识")
    name = models.CharField(max_length=160, verbose_name="名称")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="general", verbose_name="类别")
    version = models.PositiveIntegerField(default=1, verbose_name="版本号")
    content = models.TextField(verbose_name="提示词内容")
    is_active = models.BooleanField(default=False, verbose_name="是否启用")
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children", verbose_name="父版本"
    )
    change_note = models.TextField(blank=True, verbose_name="变更说明")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="创建者")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "ai_prompt_version"
        verbose_name = "版本化提示词"
        verbose_name_plural = "版本化提示词"
        unique_together = (("key", "version"),)
        ordering = ["key", "-version"]

    def __str__(self):
        return f"{self.key} v{self.version}"

    def save(self, *args, **kwargs):
        if not self.pk:
            last = PromptVersion.objects.filter(key=self.key).order_by("-version").first()
            self.version = (last.version + 1) if last else 1
        super().save(*args, **kwargs)
        if self.is_active:
            PromptVersion.objects.filter(key=self.key).exclude(pk=self.pk).update(is_active=False)


class AICallLog(models.Model):
    """每次 LLM 调用的成本/用量观测记录。"""
    STATUS_CHOICES = [("success", "成功"), ("failure", "失败")]

    module = models.CharField(max_length=60, verbose_name="调用模块")
    feature = models.CharField(max_length=80, blank=True, verbose_name="功能点")
    provider = models.CharField(max_length=40, blank=True, verbose_name="供应商")
    model_name = models.CharField(max_length=100, blank=True, verbose_name="模型")
    model_config_id = models.IntegerField(null=True, blank=True, verbose_name="模型配置ID")
    prompt_version_id = models.IntegerField(null=True, blank=True, verbose_name="提示词版本ID")
    prompt_key = models.CharField(max_length=80, blank=True, verbose_name="提示词标识")
    project_id = models.IntegerField(null=True, blank=True, verbose_name="项目ID")
    user_id = models.IntegerField(null=True, blank=True, verbose_name="用户ID")
    input_tokens = models.IntegerField(default=0, verbose_name="输入tokens")
    output_tokens = models.IntegerField(default=0, verbose_name="输出tokens")
    total_tokens = models.IntegerField(default=0, verbose_name="总tokens")
    cost = models.FloatField(default=0.0, verbose_name="估算成本(元)")
    latency_ms = models.IntegerField(null=True, blank=True, verbose_name="耗时(ms)")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="success", verbose_name="状态")
    error = models.TextField(blank=True, verbose_name="错误信息")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="调用时间")

    class Meta:
        db_table = "ai_call_log"
        verbose_name = "AI调用日志"
        verbose_name_plural = "AI调用日志"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["module"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["project_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.module}/{self.feature} {self.model_name} {self.total_tokens}t"


class EvalDataset(models.Model):
    """评测数据集。"""
    name = models.CharField(max_length=160, verbose_name="数据集名称")
    description = models.TextField(blank=True, verbose_name="说明")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="eval_datasets", verbose_name="关联项目"
    )
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="创建者")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "ai_eval_dataset"
        verbose_name = "评测数据集"
        verbose_name_plural = "评测数据集"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class EvalCase(models.Model):
    """评测用例：输入 + 期望/判分标准。"""
    dataset = models.ForeignKey(
        EvalDataset, on_delete=models.CASCADE, related_name="cases", verbose_name="所属数据集"
    )
    name = models.CharField(max_length=200, verbose_name="用例名称")
    input_text = models.TextField(verbose_name="输入内容")
    expected_output = models.TextField(blank=True, verbose_name="期望输出")
    criteria = models.TextField(blank=True, verbose_name="判分标准")
    tags = models.CharField(max_length=200, blank=True, verbose_name="标签(逗号分隔)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "ai_eval_case"
        verbose_name = "评测用例"
        verbose_name_plural = "评测用例"
        ordering = ["id"]

    def __str__(self):
        return self.name


class EvalRun(models.Model):
    """一次评测运行。"""
    STATUS_CHOICES = [
        ("pending", "待运行"),
        ("running", "运行中"),
        ("completed", "已完成"),
        ("failed", "失败"),
    ]

    dataset = models.ForeignKey(EvalDataset, on_delete=models.CASCADE, related_name="runs", verbose_name="数据集")
    prompt_version = models.ForeignKey(
        PromptVersion, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="使用的提示词版本"
    )
    model_config = models.ForeignKey(
        "requirement_analysis.AIModelConfig", on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="评测模型配置"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending", verbose_name="状态")
    total = models.IntegerField(default=0, verbose_name="用例总数")
    summary = models.TextField(blank=True, verbose_name="汇总(JSON)")
    error = models.TextField(blank=True, verbose_name="错误信息")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="触发者")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "ai_eval_run"
        verbose_name = "评测运行"
        verbose_name_plural = "评测运行"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Run#{self.id} {self.dataset_id} {self.status}"

    def get_summary(self):
        if not self.summary:
            return {}
        try:
            return json.loads(self.summary)
        except Exception:
            return {}


class EvalResult(models.Model):
    """评测结果（逐用例）。"""
    run = models.ForeignKey(EvalRun, on_delete=models.CASCADE, related_name="results", verbose_name="所属运行")
    case = models.ForeignKey(EvalCase, on_delete=models.CASCADE, verbose_name="评测用例")
    output = models.TextField(blank=True, verbose_name="模型输出")
    score = models.FloatField(null=True, blank=True, verbose_name="得分(0-100)")
    passed = models.BooleanField(null=True, blank=True, verbose_name="是否通过")
    judge_note = models.TextField(blank=True, verbose_name="判分说明")
    scored_by = models.CharField(max_length=10, blank=True, verbose_name="判分方式(auto/manual)")
    latency_ms = models.IntegerField(null=True, blank=True, verbose_name="耗时(ms)")
    tokens = models.IntegerField(default=0, verbose_name="tokens")
    cost = models.FloatField(default=0.0, verbose_name="成本(元)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "ai_eval_result"
        verbose_name = "评测结果"
        verbose_name_plural = "评测结果"
        unique_together = (("run", "case"),)
        ordering = ["id"]

    def __str__(self):
        return f"Result#{self.id} run={self.run_id} case={self.case_id}"


class AiFeedback(models.Model):
    """人工对 AI 产出的反馈（反馈学习入口）。"""
    RATING_CHOICES = [
        ("positive", "赞"),
        ("negative", "踩"),
        ("neutral", "中性"),
    ]

    module = models.CharField(max_length=60, verbose_name="来源模块")
    source_id = models.IntegerField(null=True, blank=True, verbose_name="来源对象ID")
    rating = models.CharField(max_length=10, choices=RATING_CHOICES, default="neutral", verbose_name="评价")
    comment = models.TextField(blank=True, verbose_name="反馈内容")
    correction = models.TextField(blank=True, verbose_name="修正后内容")
    related_eval_result = models.ForeignKey(
        EvalResult, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="关联评测结果"
    )
    converted_to_case = models.BooleanField(default=False, verbose_name="已转为评测用例")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="反馈人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="反馈时间")

    class Meta:
        db_table = "ai_feedback"
        verbose_name = "AI反馈"
        verbose_name_plural = "AI反馈"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Feedback#{self.id} {self.module} {self.rating}"
