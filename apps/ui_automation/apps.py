from django.apps import AppConfig


class UiAutomationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.ui_automation'
    verbose_name = 'UI自动化测试'

    def ready(self):
        """Django 启动时加载 ai_base，确保 Agent/TokenCost 补丁在首次请求前生效"""
        try:
            from . import ai_base  # noqa: F401
        except Exception:
            pass

