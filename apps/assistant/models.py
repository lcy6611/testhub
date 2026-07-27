from django.db import models
from django.utils import timezone
from apps.users.models import User


class DifyConfig(models.Model):
    """Dify API配置"""
    api_url = models.URLField(max_length=500, verbose_name='API URL', help_text='Dify API endpoint URL')
    api_key = models.CharField(max_length=500, verbose_name='API Key', help_text='Dify API密钥')
    dataset_api_key = models.CharField(
        max_length=500,
        blank=True,
        default='',
        verbose_name='知识库 API Key',
        help_text='Dify 知识库 Dataset API Key（dataset- 开头），用于 AI 用例生成时检索知识库',
    )
    # 兼容历史库：线上表里存在 app_type 且为 NOT NULL，但旧代码没声明该字段，导致插入时报 1364。
    # 这里补齐字段并给默认值，让 Django INSERT 时带上 app_type。
    app_type = models.CharField(
        max_length=20,
        default='workflow',
        verbose_name='应用类型',
        help_text='dify 应用类型（workflow/chat），用于决定调用哪个接口',
    )
    invoke_mode = models.CharField(
        max_length=20,
        choices=[('chat', '对话应用'), ('workflow', '工作流应用')],
        default='workflow',
        verbose_name='Dify 调用模式',
        help_text='AI 评测师调用 Dify 时使用的 API：chat-messages 或 workflows/run',
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'dify_configs'
        verbose_name = 'Dify配置'
        verbose_name_plural = 'Dify配置'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Dify Config - {'Active' if self.is_active else 'Inactive'}"
    
    @classmethod
    def get_active_config(cls):
        """获取当前激活的配置"""
        return cls.objects.filter(is_active=True).first()


class AssistantSession(models.Model):
    """智能助手会话记录"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assistant_sessions', verbose_name='用户')
    session_id = models.CharField(max_length=200, verbose_name='会话ID')
    conversation_id = models.CharField(max_length=200, blank=True, null=True, verbose_name='Dify对话ID')
    title = models.CharField(max_length=500, blank=True, verbose_name='会话标题')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'assistant_sessions'
        verbose_name = '智能助手会话'
        verbose_name_plural = '智能助手会话'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.title or self.session_id}"


class ChatMessage(models.Model):
    """聊天消息记录"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]
    
    session = models.ForeignKey(AssistantSession, on_delete=models.CASCADE, related_name='chat_messages', verbose_name='会话')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    content = models.TextField(verbose_name='消息内容')
    conversation_id = models.CharField(max_length=200, blank=True, null=True, verbose_name='Dify对话ID')
    message_id = models.CharField(max_length=200, blank=True, null=True, verbose_name='Dify消息ID')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    
    class Meta:
        db_table = 'chat_messages'
        verbose_name = '聊天消息'
        verbose_name_plural = '聊天消息'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}"


class AssistantMessage(models.Model):
    """智能助手消息记录（保留用于向后兼容）"""
    MESSAGE_TYPE_CHOICES = [
        ('user', '用户消息'),
        ('assistant', '助手回复'),
    ]
    
    session = models.ForeignKey(AssistantSession, on_delete=models.CASCADE, related_name='messages', verbose_name='会话')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, verbose_name='消息类型')
    content = models.TextField(verbose_name='消息内容')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    
    class Meta:
        db_table = 'assistant_messages'
        verbose_name = '智能助手消息'
        verbose_name_plural = '智能助手消息'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.get_message_type_display()}: {self.content[:50]}"


class HermesAgentConfig(models.Model):
    """质量数字人 Hermes 全局配置"""
    name = models.CharField(max_length=100, default='默认配置', verbose_name='配置名称')
    system_prompt = models.TextField(
        blank=True, default='', verbose_name='系统提示词',
        help_text='覆盖默认 Hermes 系统提示词，为空则使用内置默认'
    )
    model_config = models.ForeignKey(
        'requirement_analysis.AIModelConfig', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='hermes_configs', verbose_name='AI 模型配置'
    )
    avatar_url = models.CharField(max_length=500, blank=True, default='', verbose_name='数字人模型 URL')
    tts_enabled = models.BooleanField(default=True, verbose_name='TTS 朗读')
    active_skills = models.JSONField(default=list, blank=True, verbose_name='默认启用技能 ID 列表')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'hermes_agent_configs'
        verbose_name = '数字人配置'
        verbose_name_plural = '数字人配置'
        ordering = ['-is_active', '-updated_at']

    def __str__(self):
        return f"Hermes配置 - {self.name}"

    @classmethod
    def get_active_config(cls):
        return cls.objects.filter(is_active=True).first()


class HermesConversation(models.Model):
    """Hermes 多会话记录"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hermes_conversations', verbose_name='用户')
    title = models.CharField(max_length=500, blank=True, verbose_name='会话标题')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'hermes_conversations'
        verbose_name = 'Hermes 会话'
        verbose_name_plural = 'Hermes 会话'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.username} - {self.title or self.id}"


class HermesMessage(models.Model):
    """Hermes 会话消息记录"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]

    conversation = models.ForeignKey(
        HermesConversation, on_delete=models.CASCADE, related_name='messages', verbose_name='会话'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    content = models.TextField(blank=True, default='', verbose_name='消息内容')
    images = models.JSONField(default=list, blank=True, verbose_name='图片列表',
                              help_text='用户上传的图片信息，[{id, url, name}]')
    tool_calls = models.JSONField(default=list, blank=True, verbose_name='工具调用')
    thought_text = models.TextField(blank=True, default='', verbose_name='思考过程')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'hermes_messages'
        verbose_name = 'Hermes 消息'
        verbose_name_plural = 'Hermes 消息'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.get_role_display()}: {self.content[:50]}"


class HermesImage(models.Model):
    """Hermes 用户上传的图片"""
    conversation = models.ForeignKey(
        HermesConversation, on_delete=models.CASCADE, related_name='images', verbose_name='会话'
    )
    image = models.ImageField(upload_to='hermes/%Y/%m/', verbose_name='图片文件')
    name = models.CharField(max_length=255, blank=True, default='', verbose_name='原文件名')
    created_at = models.DateTimeField(default=timezone.now, verbose_name='创建时间')

    class Meta:
        db_table = 'hermes_images'
        verbose_name = 'Hermes 图片'
        verbose_name_plural = 'Hermes 图片'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.conversation_id} - {self.name or self.image.name}"
