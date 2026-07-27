# -*- coding: utf-8 -*-
from django.contrib import admin

from .models import ExecutionEvidence, RetryAttempt


@admin.register(ExecutionEvidence)
class ExecutionEvidenceAdmin(admin.ModelAdmin):
    list_display = ('id', 'chain', 'execution_id', 'step_key', 'evidence_type', 'created_at')
    list_filter = ('chain', 'evidence_type')
    search_fields = ('execution_id', 'step_key')
    readonly_fields = ('created_at',)


@admin.register(RetryAttempt)
class RetryAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'chain', 'execution_id', 'step_key', 'attempt_no', 'trigger_category', 'success', 'created_at')
    list_filter = ('chain', 'trigger_category', 'success')
    search_fields = ('execution_id', 'step_key')
    readonly_fields = ('created_at',)
