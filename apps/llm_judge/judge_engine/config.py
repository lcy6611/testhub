"""评分引擎配置：从 Django settings 读取（兼容纯环境变量模式用于单元测试）。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _get_setting(key: str, default=None):
    """优先从 Django settings 读取，回退到环境变量。"""
    try:
        from django.conf import settings as _s
        # Django settings 可能没配置该项（_get_setting 会抛 AttributeError 或返回 default）
        val = getattr(_s, key, None)
        if val is not None:
            return val
    except Exception:
        pass
    return os.environ.get(key, default)


def _resolve_platform_llm() -> Optional[dict]:
    """平台适配：复用配置中心里已启用的 AIModelConfig。

    仅作为兜底：未显式配置 OPENAI_API_KEY 时，借用平台统一收敛的 LLM 网关与密钥，
    避免评分器「装好了但调不动模型」。取不到时返回 None，由调用方继续走环境变量。
    """
    try:
        from apps.requirement_analysis.models import AIModelConfig

        cfg = (AIModelConfig.objects.filter(role='writer', is_active=True).order_by('-updated_at').first()
               or AIModelConfig.objects.filter(is_active=True).first())
        if not cfg:
            return None
        api_key = cfg.resolve_api_key() if hasattr(cfg, 'resolve_api_key') else (cfg.api_key or '')
        if not api_key:
            return None
        return {
            'api_key': api_key,
            'base_url': cfg.base_url or None,
            'model_name': cfg.model_name or None,
        }
    except Exception:
        return None


@dataclass
class JudgeConfig:
    """评分引擎运行时配置。"""
    openai_api_key: str = ''
    openai_base_url: Optional[str] = None
    judge_model: str = 'deepseek-chat'
    judge_mock: bool = False
    n_runs: int = 3
    judge_models: list = field(default_factory=list)
    cache_timeout: int = 3600
    rule_llm_fallback: bool = False
    rubric_dir: Path = None
    kb_dir: Path = None

    @classmethod
    def from_settings(cls) -> 'JudgeConfig':
        """从 Django settings 构造配置（Django 启动时调用）。"""
        rubric_dir = _get_setting('JUDGE_RUBRIC_DIR')
        kb_dir = _get_setting('JUDGE_KB_DIR')
        judge_models_env = _get_setting('JUDGE_MODELS', '')
        api_key = _get_setting('OPENAI_API_KEY', '') or ''
        base_url = _get_setting('OPENAI_BASE_URL') or None
        judge_model = _get_setting('JUDGE_MODEL', 'deepseek-chat')

        # 平台适配：未显式配置 OPENAI_API_KEY 时，借用配置中心的 AIModelConfig（网关/密钥统一收敛）。
        # 注意：显式配置了 OPENAI_API_KEY 或 JUDGE_MODEL 环境变量时完全不介入。
        if not api_key:
            platform_llm = _resolve_platform_llm()
            if platform_llm:
                api_key = platform_llm['api_key']
                base_url = base_url or platform_llm['base_url']
                if not os.environ.get('JUDGE_MODEL') and platform_llm['model_name']:
                    judge_model = platform_llm['model_name']

        return cls(
            openai_api_key=api_key,
            openai_base_url=base_url,
            judge_model=judge_model,
            judge_mock=bool(_get_setting('JUDGE_MOCK', False)),
            n_runs=int(_get_setting('JUDGE_N_RUNS', 3)),
            judge_models=[m.strip() for m in str(judge_models_env).split(',') if m.strip()],
            cache_timeout=int(_get_setting('JUDGE_CACHE_TIMEOUT', 3600)),
            rule_llm_fallback=bool(_get_setting('JUDGE_RULE_LLM_FALLBACK', False)),
            rubric_dir=Path(rubric_dir) if rubric_dir else None,
            kb_dir=Path(kb_dir) if kb_dir else None,
        )

    @classmethod
    def from_env(cls) -> 'JudgeConfig':
        """纯环境变量模式（单元测试用，不依赖 Django）。"""
        return cls(
            openai_api_key=os.environ.get('OPENAI_API_KEY', ''),
            openai_base_url=os.environ.get('OPENAI_BASE_URL') or None,
            judge_model=os.environ.get('JUDGE_MODEL', 'deepseek-chat'),
            judge_mock=os.environ.get('JUDGE_MOCK') == '1',
            n_runs=int(os.environ.get('JUDGE_N_RUNS', '3')),
            judge_models=[m.strip() for m in os.environ.get('JUDGE_MODELS', '').split(',') if m.strip()],
            cache_timeout=int(os.environ.get('JUDGE_CACHE_TIMEOUT', '3600')),
            rule_llm_fallback=os.environ.get('JUDGE_RULE_LLM_FALLBACK') == '1',
        )


# 全局默认配置实例（懒加载）
_config_cache: Optional[JudgeConfig] = None


def get_config() -> JudgeConfig:
    """获取全局配置（首次调用时从 settings 加载并缓存）。"""
    global _config_cache
    if _config_cache is None:
        try:
            _config_cache = JudgeConfig.from_settings()
        except Exception:
            _config_cache = JudgeConfig.from_env()
    return _config_cache


def reload_config():
    """重新加载配置（配置变更后调用）。"""
    global _config_cache
    _config_cache = None
