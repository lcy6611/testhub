"""AI 用例深入分析服务。

输入：testcase 或草稿 steps
输出：suggestions(补充步骤) / risks(风险点) / summary
"""
from __future__ import annotations

import json
import re
import time
from typing import List, Dict, Any, Optional


ANALYSIS_PROMPT = """你是一位资深测试架构师。请基于给定的测试用例步骤，进行 **深入分析** 并输出 JSON 结果。

## 任务
1. **建议补充步骤**：覆盖边界值、异常流、安全、性能、兼容性、并发等被忽略的场景。
2. **风险点**：列出可能引发缺陷的高风险环节。
3. **总结**：一句话总结本用例的覆盖强度。

## 输出格式（必须是合法 JSON）
{
  "summary": "<一句话总结>",
  "suggestions": [
    { "category": "边界|异常|安全|性能|兼容|并发", "action": "<操作>", "expected": "<预期>" }
  ],
  "risks": [
    { "level": "high|medium|low", "title": "<风险点>", "mitigation": "<缓解建议>" }
  ]
}

## 用例信息
- 标题：{title}
- 描述：{description}
- 前置条件：{preconditions}
- 步骤：
{steps_text}

只输出 JSON，不要 Markdown 代码块或额外文字。
"""


def _format_steps(steps: List[Dict[str, Any]]) -> str:
    if not steps:
        return '（无）'
    return '\n'.join(
        f"{i+1}. 操作：{s.get('action','')}\n   预期：{s.get('expected','')}"
        for i, s in enumerate(steps)
    )


def _extract_json(text: str) -> Dict[str, Any]:
    """从 LLM 输出提取 JSON（兼容 ```json 包裹、尾部多余文本）。"""
    if not text:
        return {}
    text = text.strip()
    # 去掉 ```json 包裹
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    # 抓首个 { ... 末尾 } 区域
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        # 尝试宽松解析
        cleaned = text[start:end + 1]
        cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
        try:
            return json.loads(cleaned)
        except Exception:
            return {}


async def analyze_case_with_ai(
    *,
    title: str,
    description: str = '',
    preconditions: str = '',
    steps: List[Dict[str, Any]],
    ai_model,
    requirement=None,
) -> Dict[str, Any]:
    """调用 LLM 深入分析用例，返回 { summary, suggestions, risks, raw, tokens_used, elapsed_ms }。"""
    from apps.requirement_analysis.services import AIModelService

    steps_text = _format_steps(steps)
    req_text = ''
    if requirement:
        req_text = f"\n- 关联需求：{requirement.title}\n  需求描述：{requirement.description or ''}"

    prompt = ANALYSIS_PROMPT.format(
        title=title or '',
        description=description or '',
        preconditions=preconditions or '',
        steps_text=steps_text,
    ) + req_text

    messages = [
        {'role': 'system', 'content': '你是 TestHub 的 Hoteam-AI 测试分析专家，只输出合法 JSON。'},
        {'role': 'user', 'content': prompt},
    ]

    t0 = time.monotonic()
    try:
        resp = await AIModelService.call_openai_compatible_api(ai_model, messages)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        content = (resp.get('choices') or [{}])[0].get('message', {}).get('content', '')
        usage = resp.get('usage') or {}
        tokens = int(usage.get('total_tokens') or 0)
        parsed = _extract_json(content) or {}
        return {
            'summary': parsed.get('summary', ''),
            'suggestions': parsed.get('suggestions') or [],
            'risks': parsed.get('risks') or [],
            'raw': content,
            'tokens_used': tokens,
            'elapsed_ms': elapsed_ms,
            'prompt': prompt,
        }
    except Exception as e:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        return {
            'summary': f'AI 调用失败：{e}',
            'suggestions': [],
            'risks': [],
            'raw': str(e),
            'tokens_used': 0,
            'elapsed_ms': elapsed_ms,
            'prompt': prompt,
            'error': True,
        }
