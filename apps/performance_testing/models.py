# -*- coding: utf-8 -*-
"""性能测试数据模型。"""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class PerformanceScript(models.Model):
    """性能测试脚本。"""

    SCRIPT_TYPE_CHOICES = [
        ("ONLINE", "在线编排"),
        ("JMX_RAW", "纯 JMX"),
        ("JMX_UPLOAD", "上传 JMX 创建"),
    ]

    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("published", "已发布"),
    ]

    #: 压测引擎。默认 JMETER：保持既有脚本的历史行为不变
    ENGINE_CHOICES = [
        ("JMETER", "JMeter"),
        ("BUILTIN", "内置引擎"),
        ("LOCUST", "Locust"),
    ]

    name = models.CharField(max_length=200, verbose_name="脚本名称")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    projects = models.ManyToManyField(
        "projects.Project",
        related_name="performance_scripts",
        blank=True,
        verbose_name="关联项目",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft", verbose_name="状态")
    script_type = models.CharField(
        max_length=16, choices=SCRIPT_TYPE_CHOICES, default="ONLINE", verbose_name="脚本模式"
    )
    # 在线编排：线程组/HTTP请求/变量/CSV/断言/定时器结构
    jmx_config = models.JSONField(default=dict, blank=True, verbose_name="在线编排配置")
    # 纯 JMX 模式：直接编辑 JMX XML 内容
    jmx_content = models.TextField(blank=True, default="", verbose_name="JMX 内容")
    # 上传 JMX 创建：上传的 JMX 文件
    jmx_file = models.FileField(upload_to="performance/jmx/", null=True, blank=True, verbose_name="JMX 文件")
    # 用户定义变量 [{name, value}, ...]
    variables = models.JSONField(default=list, blank=True, verbose_name="用户定义变量")
    # CSV 参数化数据集 [{name, file, delimiter, encoding, variable_names}, ...]
    csv_datasets = models.JSONField(default=list, blank=True, verbose_name="CSV 数据集")
    # 执行参数
    thread_count = models.PositiveIntegerField(default=10, verbose_name="线程数")
    ramp_up = models.PositiveIntegerField(default=5, verbose_name="Ramp-Up(秒)")
    duration = models.PositiveIntegerField(default=60, verbose_name="持续时间(秒)")
    # 实时报告开关
    realtime_enabled = models.BooleanField(default=False, verbose_name="启用实时报告")
    # 压测引擎（默认 JMeter，保证历史脚本行为不变）
    engine = models.CharField(max_length=16, choices=ENGINE_CHOICES, default="JMETER", verbose_name="压测引擎")
    # 验收目标（事后判定是否「通过」）：{max_p95_rt, max_avg_rt, min_tps, max_error_rate}
    perf_targets = models.JSONField(default=dict, blank=True, verbose_name="验收目标")
    # SLA 阈值（判定是否「违规」，支持运行期熔断）：
    # {enabled, abort_on_breach, breach_window, thresholds:{avg_response_time, p95_response_time, error_rate, min_tps}}
    sla_config = models.JSONField(default=dict, blank=True, verbose_name="SLA 阈值配置")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "perf_script"
        verbose_name = "性能测试脚本"
        verbose_name_plural = "性能测试脚本"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class PerformanceScriptCsvFile(models.Model):
    """性能脚本关联的 CSV 数据文件（参数化用）。"""

    script = models.ForeignKey(
        PerformanceScript,
        on_delete=models.CASCADE,
        related_name="csv_files",
        verbose_name="关联脚本",
    )
    file = models.FileField(upload_to="performance/csv/", verbose_name="CSV 文件")
    original_name = models.CharField(max_length=255, blank=True, default="", verbose_name="原始文件名")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")

    class Meta:
        db_table = "perf_script_csv_file"
        verbose_name = "性能脚本 CSV 文件"
        verbose_name_plural = "性能脚本 CSV 文件"
        ordering = ["-created_at"]

    def __str__(self):
        return self.original_name or self.file.name


class PerformanceBatchExecution(models.Model):
    """按项目批量执行性能测试。"""

    STATUS_CHOICES = [
        ("QUEUED", "排队中"),
        ("RUNNING", "执行中"),
        ("COMPLETED", "已完成"),
        ("FAILED", "失败"),
        ("PARTIAL", "部分完成"),
    ]

    batch_id = models.CharField(max_length=50, unique=True, verbose_name="批次ID")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="performance_batches", verbose_name="关联项目",
    )
    name = models.CharField(max_length=200, verbose_name="批次名称")
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="QUEUED", verbose_name="状态"
    )
    total_scripts = models.PositiveIntegerField(default=0, verbose_name="脚本总数")
    completed_scripts = models.PositiveIntegerField(default=0, verbose_name="已完成数")
    failed_scripts = models.PositiveIntegerField(default=0, verbose_name="失败数")
    # 执行参数（统一应用到批次内所有脚本）
    thread_count = models.PositiveIntegerField(default=10, verbose_name="线程数")
    ramp_up = models.PositiveIntegerField(default=5, verbose_name="Ramp-Up(秒)")
    duration = models.PositiveIntegerField(default=60, verbose_name="持续时间(秒)")
    realtime_enabled = models.BooleanField(default=False, verbose_name="启用实时报告")
    error_message = models.TextField(blank=True, default="", verbose_name="错误信息")
    report_path = models.TextField(blank=True, default="", verbose_name="项目级报告目录")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

    class Meta:
        db_table = "perf_batch_execution"
        verbose_name = "性能批量执行"
        verbose_name_plural = "性能批量执行"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.batch_id} ({self.get_status_display()})"


class PerformanceExecution(models.Model):
    """性能测试执行记录。"""

    STATUS_CHOICES = [
        ("QUEUED", "排队中"),
        ("RUNNING", "执行中"),
        ("COMPLETED", "已完成"),
        ("FAILED", "失败"),
        ("CANCELLED", "已取消"),
    ]

    #: SLA 判定 / 验收判定的共用结果码
    SLA_RESULT_CHOICES = [
        ("PASSED", "通过"),
        ("FAILED", "未通过"),
        ("NOT_EVALUATED", "未评估"),
    ]

    execution_id = models.CharField(max_length=50, unique=True, verbose_name="执行ID")
    script = models.ForeignKey(
        PerformanceScript, on_delete=models.CASCADE, related_name="executions", verbose_name="脚本"
    )
    batch = models.ForeignKey(
        PerformanceBatchExecution, on_delete=models.CASCADE, null=True, blank=True,
        related_name="executions", verbose_name="所属批次",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="QUEUED", verbose_name="状态"
    )
    # 执行参数快照
    thread_count = models.PositiveIntegerField(default=10, verbose_name="线程数")
    ramp_up = models.PositiveIntegerField(default=5, verbose_name="Ramp-Up(秒)")
    duration = models.PositiveIntegerField(default=60, verbose_name="持续时间(秒)")
    realtime_enabled = models.BooleanField(default=False, verbose_name="启用实时报告")

    # 产物路径
    jmx_path = models.CharField(max_length=500, blank=True, default="", verbose_name="JMX 路径")
    jtl_path = models.CharField(max_length=500, blank=True, default="", verbose_name="JTL 路径")
    jmeter_log = models.TextField(blank=True, default="", verbose_name="JMeter 日志")
    report_path = models.CharField(max_length=500, blank=True, default="", verbose_name="HTML报告路径")
    error_message = models.TextField(blank=True, default="", verbose_name="错误信息")

    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

    # 判定结果（执行收尾时自动评估落库）
    sla_result = models.CharField(
        max_length=20, choices=SLA_RESULT_CHOICES, default="NOT_EVALUATED", verbose_name="SLA判定结果"
    )
    sla_detail = models.JSONField(default=list, blank=True, verbose_name="SLA逐项判定")
    verdict = models.CharField(
        max_length=20, choices=SLA_RESULT_CHOICES, default="NOT_EVALUATED", verbose_name="验收判定"
    )
    verdict_details = models.JSONField(default=list, blank=True, verbose_name="验收明细")

    # 执行环境（可选）：非空时执行使用其叠加出的 config_snapshot
    environment = models.ForeignKey(
        "PerformanceEnvironment", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="executions", verbose_name="执行环境",
    )
    # 生效配置快照：环境叠加后的 jmx_config（为空表示未使用环境、直接用脚本配置）
    config_snapshot = models.JSONField(default=dict, blank=True, verbose_name="生效配置快照")

    # 报告分享直链：token 即凭证，可在无登录态下只读打开报告
    share_token = models.CharField(
        max_length=64, blank=True, null=True, unique=True, verbose_name="分享令牌"
    )
    share_expires_at = models.DateTimeField(null=True, blank=True, verbose_name="分享过期时间")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "perf_execution"
        verbose_name = "性能执行记录"
        verbose_name_plural = "性能执行记录"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.execution_id} ({self.get_status_display()})"

    # ---------- 报告分享直链 ----------
    @property
    def share_enabled(self) -> bool:
        """分享是否仍然有效（有 token 且未过期）。"""
        if not self.share_token:
            return False
        if self.share_expires_at and self.share_expires_at < timezone.now():
            return False
        return True

    def generate_share_token(self, expires_in_days=None):
        """生成/重置分享令牌。``expires_in_days`` 为 None 或 <=0 表示永不过期。"""
        self.share_token = secrets.token_urlsafe(32)
        try:
            days = int(expires_in_days) if expires_in_days not in (None, "") else 0
        except (TypeError, ValueError):
            days = 0
        self.share_expires_at = timezone.now() + timedelta(days=days) if days > 0 else None
        self.save(update_fields=["share_token", "share_expires_at"])
        return self.share_token

    def revoke_share_token(self):
        """撤销分享令牌。"""
        self.share_token = None
        self.share_expires_at = None
        self.save(update_fields=["share_token", "share_expires_at"])


class PerformanceSummary(models.Model):
    """执行汇总指标。"""

    execution = models.OneToOneField(
        PerformanceExecution, on_delete=models.CASCADE, related_name="summary", verbose_name="执行记录"
    )
    total_samples = models.PositiveIntegerField(default=0, verbose_name="总样本数")
    error_count = models.PositiveIntegerField(default=0, verbose_name="错误数")
    error_rate = models.FloatField(default=0.0, verbose_name="错误率(%)")
    avg_response_time = models.FloatField(default=0.0, verbose_name="平均响应时间(ms)")
    min_response_time = models.FloatField(default=0.0, verbose_name="最小响应时间(ms)")
    max_response_time = models.FloatField(default=0.0, verbose_name="最大响应时间(ms)")
    p90 = models.FloatField(default=0.0, verbose_name="P90(ms)")
    p95 = models.FloatField(default=0.0, verbose_name="P95(ms)")
    p99 = models.FloatField(default=0.0, verbose_name="P99(ms)")
    throughput = models.FloatField(default=0.0, verbose_name="吞吐量(req/s)")
    data_received = models.BigIntegerField(default=0, verbose_name="接收字节")
    data_sent = models.BigIntegerField(default=0, verbose_name="发送字节")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "perf_summary"
        verbose_name = "性能汇总"
        verbose_name_plural = "性能汇总"


class PerformanceMetric(models.Model):
    """按请求名分组的指标。"""

    execution = models.ForeignKey(
        PerformanceExecution, on_delete=models.CASCADE, related_name="metrics", verbose_name="执行记录"
    )
    sample_label = models.CharField(max_length=500, verbose_name="请求名称")
    sample_count = models.PositiveIntegerField(default=0, verbose_name="样本数")
    error_count = models.PositiveIntegerField(default=0, verbose_name="错误数")
    error_rate = models.FloatField(default=0.0, verbose_name="错误率(%)")
    avg = models.FloatField(default=0.0, verbose_name="平均(ms)")
    min = models.FloatField(default=0.0, verbose_name="最小(ms)")
    max = models.FloatField(default=0.0, verbose_name="最大(ms)")
    p90 = models.FloatField(default=0.0, verbose_name="P90(ms)")
    p95 = models.FloatField(default=0.0, verbose_name="P95(ms)")
    p99 = models.FloatField(default=0.0, verbose_name="P99(ms)")
    throughput = models.FloatField(default=0.0, verbose_name="吞吐量(req/s)")
    timeline = models.JSONField(default=list, blank=True, verbose_name="10秒时间线")
    top_errors = models.JSONField(default=list, blank=True, verbose_name="Top20错误")

    class Meta:
        db_table = "perf_metric"
        verbose_name = "性能指标"
        verbose_name_plural = "性能指标"
        indexes = [models.Index(fields=["execution"])]


class PerformanceReport(models.Model):
    """性能测试报告（基于执行记录）。"""

    execution = models.OneToOneField(
        PerformanceExecution, on_delete=models.CASCADE, related_name="report", verbose_name="执行记录"
    )
    name = models.CharField(max_length=200, verbose_name="报告名称")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "perf_report"
        verbose_name = "性能测试报告"
        verbose_name_plural = "性能测试报告"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class PerformanceScheduledTask(models.Model):
    """性能测试定时任务。"""

    STATUS_CHOICES = [
        ("enabled", "启用"),
        ("disabled", "禁用"),
    ]

    name = models.CharField(max_length=200, verbose_name="任务名称")
    script = models.ForeignKey(
        PerformanceScript, on_delete=models.CASCADE, related_name="scheduled_tasks", verbose_name="关联脚本"
    )
    cron = models.CharField(max_length=200, verbose_name="Cron 表达式")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="enabled", verbose_name="状态")
    thread_count = models.PositiveIntegerField(default=10, verbose_name="线程数")
    ramp_up = models.PositiveIntegerField(default=5, verbose_name="Ramp-Up(秒)")
    duration = models.PositiveIntegerField(default=60, verbose_name="持续时间(秒)")
    realtime_enabled = models.BooleanField(default=False, verbose_name="启用实时报告")
    description = models.TextField(blank=True, default="", verbose_name="描述")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "perf_scheduled_task"
        verbose_name = "性能定时任务"
        verbose_name_plural = "性能定时任务"
        ordering = ["-updated_at"]

    def __str__(self):
        return self.name


class PerformanceConfig(models.Model):
    """性能测试全局配置（单例）。"""

    jmeter_path = models.CharField(
        max_length=500, blank=True, default="", verbose_name="JMeter 可执行路径",
        help_text="绝对路径，如 /opt/apache-jmeter-5.6.3/bin/jmeter；留空则使用环境变量或 PATH 中的 jmeter"
    )
    realtime_report_enabled = models.BooleanField(default=False, verbose_name="启用实时报告")
    influxdb_url = models.CharField(max_length=500, blank=True, default="", verbose_name="InfluxDB URL")
    influxdb_org = models.CharField(max_length=200, blank=True, default="testhub", verbose_name="InfluxDB Org")
    influxdb_bucket = models.CharField(max_length=200, blank=True, default="jmeter", verbose_name="InfluxDB Bucket")
    influxdb_token = models.CharField(max_length=500, blank=True, default="", verbose_name="InfluxDB Token")
    influxdb_measurement = models.CharField(max_length=200, blank=True, default="jmeter", verbose_name="InfluxDB Measurement")
    influxdb_application = models.CharField(max_length=200, blank=True, default="testhub", verbose_name="InfluxDB Application")
    max_threads = models.PositiveIntegerField(default=1000, verbose_name="最大线程数")
    max_duration = models.PositiveIntegerField(default=7200, verbose_name="最大持续时间(秒)")
    # Prometheus 监控对接
    prometheus_enabled = models.BooleanField(default=False, verbose_name="启用 Prometheus 监控")
    prometheus_url = models.CharField(
        max_length=500, blank=True, default="", verbose_name="Prometheus URL",
        help_text="如 http://10.0.x.x:9090（Docker 内部可用 http://prometheus:9090）"
    )
    prometheus_step = models.PositiveIntegerField(default=15, verbose_name="采集步长(秒)")
    # 默认监控目标列表：[{name, type, instance, job, metrics}], type: app_server/db/redis/gateway/custom
    monitor_targets = models.JSONField(
        default=list, blank=True, verbose_name="监控目标列表",
        help_text="执行性能测试时按时间窗采集这些目标的资源指标"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "perf_config"
        verbose_name = "性能测试配置"
        verbose_name_plural = "性能测试配置"

    def __str__(self):
        return "性能测试全局配置"

    @classmethod
    def get_singleton(cls) -> "PerformanceConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PerformanceMonitorMetric(models.Model):
    """执行期间的服务器/服务资源监控指标（来自 Prometheus）。"""

    TARGET_TYPE_CHOICES = [
        ("app_server", "应用服务器"),
        ("db", "数据库"),
        ("redis", "Redis/缓存"),
        ("gateway", "网关"),
        ("custom", "自定义微服务"),
    ]

    execution = models.ForeignKey(
        PerformanceExecution, on_delete=models.CASCADE,
        related_name="monitor_metrics", verbose_name="执行记录"
    )
    target_name = models.CharField(max_length=200, verbose_name="监控目标名称")
    target_type = models.CharField(
        max_length=50, choices=TARGET_TYPE_CHOICES, default="app_server", verbose_name="目标类型"
    )
    metric_key = models.CharField(max_length=100, verbose_name="指标键")
    metric_label = models.CharField(max_length=100, verbose_name="指标中文名")
    metric_unit = models.CharField(max_length=20, default="", verbose_name="单位")
    # 时间线：[{t: "相对秒或时间戳", v: 数值}]
    timeline = models.JSONField(default=list, blank=True, verbose_name="时间线")
    min_value = models.FloatField(default=0.0, verbose_name="最小")
    avg_value = models.FloatField(default=0.0, verbose_name="平均")
    max_value = models.FloatField(default=0.0, verbose_name="最大")
    peak_value = models.FloatField(default=0.0, verbose_name="峰值")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "perf_monitor_metric"
        verbose_name = "监控指标"
        verbose_name_plural = "监控指标"
        ordering = ["target_name", "metric_key"]
        indexes = [models.Index(fields=["execution"])]

    def __str__(self):
        return f"{self.target_name}/{self.metric_label}"


class PerformanceBaseline(models.Model):
    """性能基线：每个脚本维护一条「当前基线」，用于历史对比与劣化判定。

    设置基线即覆盖（update_or_create），基线来源执行仍可在 ``execution`` 上追溯。
    """

    #: 默认容忍度：响应时间劣化超过 20% / 吞吐量下降超过 15% 视为劣化
    DEFAULT_TOLERANCE = {"rt_degrade_pct": 20, "tps_degrade_pct": 15}

    script = models.OneToOneField(
        PerformanceScript, on_delete=models.CASCADE, related_name="baseline", verbose_name="脚本"
    )
    execution = models.ForeignKey(
        PerformanceExecution, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="baselines", verbose_name="基线来源执行",
    )
    metrics = models.JSONField(default=dict, blank=True, verbose_name="基线指标快照")
    tolerance = models.JSONField(
        default=dict, blank=True, verbose_name="容忍度(JSON:{rt_degrade_pct,tps_degrade_pct})"
    )
    note = models.TextField(blank=True, default="", verbose_name="备注")
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="perf_baselines", verbose_name="设置人",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "perf_baseline"
        verbose_name = "性能基线"
        verbose_name_plural = "性能基线"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"脚本 {self.script_id} 的性能基线"


class PerformanceComparisonReport(models.Model):
    """多轮执行对照报告：持久化指标矩阵快照 + 可选 AI 对照分析。"""

    script = models.ForeignKey(
        PerformanceScript, on_delete=models.CASCADE, related_name="comparison_reports", verbose_name="脚本"
    )
    title = models.CharField(max_length=200, verbose_name="报告标题")
    #: 参与对比的执行主键列表（2~5 个，保持用户选择顺序）
    execution_ids = models.JSONField(default=list, verbose_name="参与对比的执行ID列表")
    reference_execution_id = models.IntegerField(null=True, blank=True, verbose_name="基准执行ID")
    snapshot = models.JSONField(default=dict, verbose_name="对照快照")
    ai_analysis = models.TextField(null=True, blank=True, verbose_name="AI对照分析")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="perf_comparison_reports", verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "perf_comparison_report"
        verbose_name = "性能对照报告"
        verbose_name_plural = "性能对照报告"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class PerformanceEnvironment(models.Model):
    """压测环境：跨脚本复用的命名环境（一套 base_url / 请求头 / 变量）。

    解决同一套接口在 dev/staging/prod 等多环境压测时反复手工改 URL 的问题。
    """

    SCOPE_CHOICES = [
        ("GLOBAL", "全局环境"),
        ("PROJECT", "项目环境"),
    ]

    name = models.CharField(max_length=200, verbose_name="环境名称")
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default="PROJECT", verbose_name="作用域")
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, null=True, blank=True,
        related_name="perf_environments", verbose_name="关联项目",
    )
    base_url = models.CharField(max_length=500, blank=True, default="", verbose_name="基础地址")
    headers = models.JSONField(default=dict, blank=True, verbose_name="全局请求头")
    verify_ssl = models.BooleanField(default=False, verbose_name="校验 SSL 证书")
    variables = models.JSONField(default=list, blank=True, verbose_name="环境变量")
    is_active = models.BooleanField(default=False, verbose_name="是否激活")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="perf_environments", verbose_name="创建者",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "perf_environment"
        verbose_name = "压测环境"
        verbose_name_plural = "压测环境"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.name} ({self.get_scope_display()})"

    def save(self, *args, **kwargs):
        """保证同作用域内只有一个激活环境（GLOBAL 全局唯一；PROJECT 每项目唯一）。"""
        super().save(*args, **kwargs)
        if self.is_active:
            qs = PerformanceEnvironment.objects.filter(scope=self.scope, is_active=True)
            if self.scope == "PROJECT":
                qs = qs.filter(project=self.project)
            qs.exclude(pk=self.pk).update(is_active=False)
