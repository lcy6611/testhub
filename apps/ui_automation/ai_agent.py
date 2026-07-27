import logging
import asyncio
from .ai_base import BaseBrowserAgent

logger = logging.getLogger('django')

class BrowserAgent(BaseBrowserAgent):
    """
    Standard Browser Agent. 支持文本/视觉/自动模式，由 execution_mode 与配置决定。
    """
    def __init__(self, execution_mode='text', enable_gif=True, case_name=None, headless=None):
        super().__init__(execution_mode=execution_mode, enable_gif=enable_gif, case_name=case_name, headless=headless)

# ============================================================================
# EXPORTED FUNCTIONS (FACTORY)
# ============================================================================

def get_agent_class(execution_mode='text'):
    # 始终返回文本模式实现
    return BrowserAgent

def run_ai_task_sync(task_description: str, planned_tasks=None, callback=None, should_stop=None, execution_mode='text'):
    agent = BrowserAgent(execution_mode=execution_mode)
    return asyncio.run(agent.run_task(task_description, planned_tasks, callback, should_stop))
    
def analyze_task_sync(task_description: str, execution_mode='text'):
    agent = BrowserAgent(execution_mode='text')
    return asyncio.run(agent.analyze_task(task_description))

def _resolve_ai_execution_mode(execution_mode: str) -> str:
    """解析 auto/text/vision，与配置中心 effective_mode 逻辑一致。"""
    mode = (execution_mode or 'text').strip().lower()
    if mode in ('vision', 'text'):
        return mode
    if mode != 'auto':
        return 'text'
    from apps.requirement_analysis.models import AIModelConfig
    if AIModelConfig.objects.filter(role='browser_use_text', is_active=True).first():
        return 'text'
    if AIModelConfig.objects.filter(role='browser_use_vision', is_active=True).first():
        return 'vision'
    return 'text'


def run_full_process_sync(task_description: str, analysis_callback=None, step_callback=None, should_stop=None, execution_mode='text', enable_gif=True, case_name=None, headless=None):
    """统一入口：文本模式走文本流水线，视觉模式走视觉流水线。headless 对所有模式生效。"""
    resolved_mode = _resolve_ai_execution_mode(execution_mode)
    logger.info(
        f"DEBUG: run_full_process_sync execution_mode={execution_mode} -> {resolved_mode}, "
        f"enable_gif={enable_gif}, headless={headless}"
    )

    if resolved_mode == 'vision':
        from .vision_runner import run_vision_pipeline_sync
        return run_vision_pipeline_sync(
            task_description,
            analysis_callback=analysis_callback,
            step_callback=step_callback,
            should_stop=should_stop,
            enable_gif=enable_gif,
            case_name=case_name,
            headless=headless,
        )

    agent = BrowserAgent(execution_mode='text', enable_gif=enable_gif, case_name=case_name, headless=headless)

    logger.info(f"DEBUG: Agent created ({type(agent).__name__}), starting asyncio.run")
    return asyncio.run(agent.run_full_process(task_description, analysis_callback, step_callback, should_stop))

