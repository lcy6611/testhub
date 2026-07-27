from django.apps import AppConfig


class AiEvalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ai_eval'
    label = 'ai_eval'
    verbose_name = 'AI 评测与反馈闭环'
