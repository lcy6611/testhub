# -*- coding: utf-8 -*-
from django.apps import AppConfig


class ExecutionCommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.execution_common'
    verbose_name = '统一执行诊断'
