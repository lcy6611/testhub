from django.db import models
from django.utils import timezone

from apps.users.models import User
from apps.projects.models import Project


class OpsEnvironment(models.Model):
    """运维环境（SSH / 本地 / 数据库）配置"""
    ACCESS_METHOD_CHOICES = [
        ('ssh', 'SSH'),
        ('local', '本地'),
        ('db', '数据库直连'),
    ]
    STATUS_CHOICES = [
        ('ready', '已就绪'),
        ('connecting', '连接中'),
        ('error', '连接失败'),
        ('disconnected', '未连接'),
    ]
    DB_TYPE_CHOICES = [
        ('mysql', 'MySQL'),
        ('postgresql', 'PostgreSQL'),
        ('sqlite', 'SQLite'),
        ('oracle', 'Oracle'),
    ]

    name = models.CharField(max_length=100, verbose_name='环境名称')
    category = models.CharField(max_length=100, blank=True, default='', verbose_name='所属分类')
    access_method = models.CharField(max_length=20, choices=ACCESS_METHOD_CHOICES, default='ssh', verbose_name='访问方式')

    # SSH / 本地通用
    host = models.CharField(max_length=200, blank=True, default='', verbose_name='主机地址')
    port = models.IntegerField(default=22, verbose_name='端口')
    username = models.CharField(max_length=100, blank=True, default='', verbose_name='用户名')
    password = models.CharField(max_length=200, blank=True, default='', verbose_name='密码')
    ssh_key = models.TextField(blank=True, default='', verbose_name='SSH 私钥')

    # 数据库
    db_type = models.CharField(max_length=20, choices=DB_TYPE_CHOICES, blank=True, default='', verbose_name='数据库类型')
    db_name = models.CharField(max_length=100, blank=True, default='', verbose_name='数据库名')
    db_host = models.CharField(max_length=200, blank=True, default='', verbose_name='数据库主机')
    db_port = models.IntegerField(null=True, blank=True, verbose_name='数据库端口')
    db_username = models.CharField(max_length=100, blank=True, default='', verbose_name='数据库用户名')
    db_password = models.CharField(max_length=200, blank=True, default='', verbose_name='数据库密码')

    # 附加信息
    database_scope = models.CharField(max_length=200, blank=True, default='', verbose_name='数据库范围')
    current_dir = models.CharField(max_length=500, blank=True, default='', verbose_name='默认目录')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='disconnected', verbose_name='状态')
    last_sync = models.DateTimeField(null=True, blank=True, verbose_name='最近同步')

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='ops_environments', verbose_name='关联项目')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ops_environment'
        verbose_name = '运维环境'
        verbose_name_plural = '运维环境'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Text2SQLRecord(models.Model):
    """Text2SQL 查询记录"""
    MODE_CHOICES = [
        ('query', '查询模式'),
        ('dml', '数据变更模式'),
    ]
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('generated', '已生成 SQL'),
        ('validated', '已校验'),
        ('executed', '已执行'),
        ('failed', '失败'),
    ]

    environment = models.ForeignKey(OpsEnvironment, on_delete=models.CASCADE, related_name='text2sql_records', verbose_name='环境')
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='query', verbose_name='模式')
    question = models.TextField(verbose_name='自然语言问题')
    generated_sql = models.TextField(blank=True, default='', verbose_name='生成的 SQL')
    validated_sql = models.TextField(blank=True, default='', verbose_name='校验后的 SQL')
    result = models.JSONField(default=dict, blank=True, verbose_name='执行结果')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name='状态')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'text2sql_record'
        verbose_name = 'Text2SQL 记录'
        verbose_name_plural = 'Text2SQL 记录'
        ordering = ['-created_at']


class LogQuerySession(models.Model):
    """日志查询会话"""
    environment = models.ForeignKey(OpsEnvironment, on_delete=models.CASCADE, related_name='log_sessions', verbose_name='环境')
    log_dir = models.CharField(max_length=500, blank=True, default='', verbose_name='日志目录')
    current_file = models.CharField(max_length=500, blank=True, default='', verbose_name='当前文件')
    content = models.TextField(blank=True, default='', verbose_name='日志内容')
    keywords = models.JSONField(default=list, blank=True, verbose_name='关键字')
    tail_lines = models.IntegerField(default=200, verbose_name='最近行数')
    is_realtime = models.BooleanField(default=False, verbose_name='实时查询')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'log_query_session'
        verbose_name = '日志查询会话'
        verbose_name_plural = '日志查询会话'
        ordering = ['-created_at']


class FileTransferTask(models.Model):
    """内网文件传输任务"""
    DIRECTION_CHOICES = [
        ('upload', '上传到服务器'),
        ('download', '下载到本地'),
    ]
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('running', '传输中'),
        ('success', '成功'),
        ('failed', '失败'),
    ]

    name = models.CharField(max_length=200, verbose_name='任务名称')
    environment = models.ForeignKey(OpsEnvironment, on_delete=models.CASCADE, related_name='file_transfers', verbose_name='目标环境')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='upload', verbose_name='方向')
    remote_path = models.CharField(max_length=500, verbose_name='远程路径')
    local_file = models.FileField(upload_to='ops_transfer/%Y/%m/', blank=True, null=True, verbose_name='本地文件')
    size = models.PositiveIntegerField(null=True, blank=True, verbose_name='文件大小(bytes)')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name='状态')
    error_message = models.TextField(blank=True, default='', verbose_name='错误信息')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='创建者')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='完成时间')

    class Meta:
        db_table = 'file_transfer_task'
        verbose_name = '文件传输任务'
        verbose_name_plural = '文件传输任务'
        ordering = ['-created_at']
