# -*- coding: utf-8 -*-
"""
execution_common —— 三端（UI / API / APP）统一执行诊断基础层。

提供：
- 失败分类（FailureCategory）
- 执行证据链（ExecutionEvidence）
- 重试尝试记录（RetryAttempt）
- 通用重试原语（retry.py，复用 tenacity）
- 规则优先 + 可插拔 LLM 增强的失败诊断（diagnosis.py）
- 证据采集助手（evidence.py）
"""
