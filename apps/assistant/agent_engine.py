# -*- coding: utf-8 -*-
"""
Agent 引擎 —— Function Calling 循环。

流程：
  用户输入 → LLM(带 tools) → LLM 决定调哪个工具
                                ↓
                        后端执行工具
                                ↓
                        结果返回给 LLM → 继续推理
                                ↓
                        LLM 生成最终回复 → 返回用户

支持 SSE 流式输出，前端实时看到工具调用过程。
"""

import json
import logging
import re
import time
import requests
from typing import Dict, Any, List, Generator

from .agent_tools import get_tools_for_llm, execute_tool

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 20  # 最大工具调用轮次，防止死循环。知识库未来 20+ 文档时 search_knowledge_base 需要更多轮次
LLM_TIMEOUT = 180  # 单次 LLM 调用超时（秒），对带 reasoning 的模型（DeepSeek-R1/QwQ）要放宽


def _summarize_tool_result(tool_name: str, result: Any) -> str:
    """把工具返回结果压缩成 1 句话，便于前端在思考过程面板展示。

    目标：用户能一眼看出"刚才调用了什么工具、返回了什么关键信息"，而不是一坨 JSON。
    """
    if not isinstance(result, dict):
        return f"📦 {tool_name} 返回：{str(result)[:120]}"

    # 错误优先
    if result.get("error"):
        return f"❌ {tool_name} 失败：{str(result['error'])[:120]}"

    # 通用 keys
    if "count" in result:
        items = result.get("items") or result.get("results") or result.get("data") or []
        n = result.get("count", len(items) if isinstance(items, list) else 0)
        return f"✅ {tool_name} 返回 {n} 条结果"

    # 列表型
    if "items" in result and isinstance(result["items"], list):
        return f"✅ {tool_name} 返回 {len(result['items'])} 条结果"
    if "results" in result and isinstance(result["results"], list):
        return f"✅ {tool_name} 返回 {len(result['results'])} 条结果"

    # 单条/详情型
    if "id" in result and "name" in result:
        return f"✅ {tool_name} 已获取：{result['name']}"
    if "detail" in result:
        return f"✅ {tool_name} 已获取详情"

    # 执行结果类（带 success 字段）
    if "success" in result:
        msg = result.get("message") or result.get("msg") or "已完成"
        return f"✅ {tool_name}：{msg}" if result["success"] else f"⚠️ {tool_name}：{msg}"

    return f"✅ {tool_name} 已完成"

SYSTEM_PROMPT = """你是 TestHub 质量数字人 Hermes，一个智能测试管理助手。你联通了平台全部 16 个模块。

# 你能做什么（共 44 个工具）

## 项目管理
- list_projects / create_project / get_project_detail

## 测试用例
- list_testcases / get_testcase_detail / create_testcase / update_testcase / delete_testcase

## 测试套件（通用）
- list_test_suites / create_test_suite

## 测试计划与执行
- list_test_plans / create_test_plan / list_test_runs / start_test_run / update_run_case_status / list_execution_history

## 版本管理
- list_versions / create_version

## 用例评审
- list_reviews / create_review / submit_review_decision

## API 测试
- list_api_requests / execute_api_request / list_api_test_suites / execute_api_suite / list_api_environments

## UI 自动化
- list_ui_test_suites / run_ui_test_suite（**优先用这个**）/ run_ui_automation（自然语言任务）

## APP 自动化
- list_app_test_suites / list_app_devices / run_app_test_suite（需先 list_app_devices 取 device_id）

## 报告与统计
- list_test_reports（API 测试执行报告）/ get_dashboard_stats（全局仪表盘）

## 性能测试报告（用户说"性能报告/压测报告/执行结果"都走这里）
- list_performance_scripts（看有什么脚本）/ get_performance_script_detail（脚本详情）
- get_performance_dashboard（全局仪表板：脚本总数/执行总数/成功率/最近一次摘要）
- get_performance_execution_status（**按执行ID查单次执行状态**，含 started_at / completed_at / 状态/线程数等元信息）
- get_performance_execution_summary（**按执行ID查单次执行汇总指标**：总样本/错误率/平均/P90/P95/P99/吞吐量 + 汇总按指标拆开的明细）
- 用户问"最新的性能报告"= 先 get_performance_dashboard 拿最近一次 execution_id → 再 get_performance_execution_summary
- 用户问"某次压测结果"= 直接 get_performance_execution_status + get_performance_execution_summary

## 数据工厂
- generate_test_data / list_data_tools

## AI 能力
- ai_generate_testcases（异步生成用例）/ get_generation_task_status（轮询生成结果）
- list_knowledge_bases（查看所有知识库及文档数量）/ search_knowledge_base（跨库或指定库检索，不传 dataset_id 自动搜全部）
- chat_ai_evaluator（AI 评测师问答，依赖 Dify app- API Key）

## 知识图谱
- query_kg_subgraph（实体子图查询）/ get_project_coverage（项目覆盖度报告）

## 需求分析
- list_requirement_docs

## 配置中心
- list_dify_configs / list_ai_model_configs（只读）

## 用户
- list_users（指派评审人/执行人时用）

# 强制规则（务必遵守）
1. **必须用工具回答** —— 用户问"有什么项目/用例/计划"时，**必须**调用对应工具，不要凭空编造
2. 拿到工具返回结果后，再用自然语言/表格总结给用户
3. 一次只问一件事，结果太多时分页或筛选
4. 工具返回错误时，直接告诉用户错误内容和建议，不要假装成功
5. **修改类操作**（create/update/delete/submit）先确认用户意图再执行
6. **不要凭空给数据** —— 工具列表里没有的功能直接说"平台未集成"，
   不要用相近的工具（如 `get_performance_dashboard`）冒充回复。
   典型反例：用户问"服务器使用情况/CPU/内存/磁盘/网络"——平台没有
   主机资源监控工具，应明确告知并建议接入 Prometheus/Grafana 或运维 SSH 工具。
7. **表格单元格里禁止加 emoji 前缀**（📊/📦/⏱/📈 等），
   除非工具返回里本身就带 emoji；不要为了"好看"自己塞。
8. **表格里的字符串必须原样保留**：
   - ISO 时间格式 `2026-07-25T16:33:00` / `2026-07-25T16:33:00.123` 的 `T`、冒号、小数点一律保留，不要省略、不要用空格替换、不要截断
   - 字段值含 `|` 时，必须用 `\\|` 转义，不能直接写导致破坏表格
   - 空值写 `-` 或留空，不要编造"暂无"/"N/A"（除非原数据就是"暂无"）
9. **表格列数必须严格一致** —— 表头列数 = 分隔行列数 = 每行数据列数，三者**完全相同**。
   - 缺列：补 `-`（示例：`| 数据 | - | - |`）
   - 多列：要么把多出的内容用 `<br>` 折到上一列，要么拆成多张表
   - 典型反例：表头 5 列、数据 8 列 → 立刻被前端切坏
10. **key-value 概要表**（如执行元信息：执行ID/状态/线程数/Ramp-Up/持续时间...）一律用**两列** `| 字段 | 值 |`，不要把所有字段塞到一行的多列里
11. **每个指标单独一行** —— 性能报告里有多个指标（样本数/错误数/错误率/平均/P90/P95/P99/吞吐量），必须每个指标一行：
    ```
    | 指标 | 值 |
    | --- | --- |
    | 样本数 | 1734 |
    | 错误数 | 0 |
    | 错误率 | 0.0% |
    | 平均响应时间 | 84.2 ms |
    | P90 | 164.0 ms |
    | P95 | 326.4 ms |
    | P99 | 2406.0 ms |
    | 吞吐量 | 91.32 req/s |
    ```
    **绝对禁止**把多个指标塞一行：`| HTTP Request | 1734 | 0 | 0.0% | 84.2ms | ...`（表头 2 列、数据 8 列 = 灾难）
12. **不要擅自转换单位** —— 工具返回 `10s` 就写 `10s`，返回 `10秒` 就写 `10秒`，返回 `91.32 req/s` 就写 `91.32 req/s`，**禁止**改成 `10秒` / `91.32/秒` / `91.32 次每秒` 等
13. **禁止重复输出指标** —— 上面已经用两列 `指标|值` 展示过的数据，下面不要再写"按请求明细 / 整体指标 / 性能概况"等多列横向表。重复写表 = 列数失控 = 必渲染坏
14. **写完表必须自检三件套**：表头 + 分隔行 + ≥1 行数据。缺任意一项 → 整张表删掉（不要输出残缺的表）

# 执行自动化的标准流程
当用户说"跑一下XX的测试"/"执行自动化"时：
1. 先调对应类型的 list_*_test_suites 查平台有什么
2. 对 APP 自动化，**还要先 list_app_devices** 拿 device_id
3. 找到对应套件后再调 run_*_test_suite 执行
4. 不要让用户再写一遍任务描述——平台里有的就直接用

# 评审流程
当用户要发起评审时：list_users 取评审人 ID → create_review 创建 → submit_review_decision 提交意见

# 回复风格
- 中文，简洁
- **查询类场景（list/get 返回多条数据）必须用标准 Markdown 表格输出**，格式严格如下：
  ```
  | 列1 | 列2 | 列3 |
  | --- | --- | --- |
  | 数据 | 数据 | 数据 |
  ```
  - 每个数据行都必须以 `|` 开头、以 `|` 结尾，且**每行单独成行（不要挤在一行里）**
  - 必须有且仅有一行分隔行 `| --- | --- | ... |`（列数与表头一致）
  - 列数不超过 5 列，超出请拆成多张表
  - 表格后的补充说明请用 `### 补充说明` 单独成段，**不要塞进表格最后一格**
  - 严禁输出孤立的 `**`、`--`、`---`、`*` 等装饰符号行
  - **严禁输出 `TABLE 1`、`TABLE 2`、`TABLE 3` 等伪表格标题**（LLM 偶尔会把工具返回结果用"TABLE N"标注，是错误的）
  - **严禁按状态（active/paused/已完成/已暂停）重新分组输出伪表格**——主表格里已经包含所有项目，不要重复输出
  - **工具返回结果不要在正文里再次渲染**——直接基于工具返回的原始数据整理成主表格+补充说明即可
- 不要罗列过多无关信息
"""

# LLM 偶尔会乱输出 TABLE N 伪表格标题 + 按状态分组的伪表格
# 这些是 LLM 幻觉产物，需要后端兜底清洗
_PSEUDO_LABEL = re.compile(r"^\s*TABLE[\s_]*\d+\s*$", re.IGNORECASE)
# 按 status 分组的伪表格行：
#   - "| active |2026-07-10 ... |"
#   - "| paused [2026-07-10 ... ] |"
#   - "| active: 3 个项目 |"
# 特征：整行只含一个 status 关键词（active/paused/...） + 至多一个日期
_STATUS_KW = r"(?:active|paused|in_progress|pending|completed|archived|cancelled|done|已暂停|进行中|已完成|已取消|已归档)"
_DATE = r"\d{4}[-/]?\d{2}[-/]?\d{2}(?:[ Tt]\d{1,2}:\d{2}(?::\d{2})?)?"
_PSEUDO_GROUP = re.compile(
    rf"^\s*\|?\s*{_STATUS_KW}\s*\|[^|\n]*\|?\s*$",
    re.IGNORECASE,
)


def _strip_pseudo_tables(text: str) -> str:
    """清洗 LLM 输出的 TABLE N 伪表格标题 + 按 status 分组的伪表格行"""
    cleaned_lines = []
    for ln in text.split("\n"):
        s = ln.strip()
        if not s:
            cleaned_lines.append(ln)
            continue
        if _PSEUDO_LABEL.match(s) or _PSEUDO_GROUP.match(s):
            continue  # 丢弃
        cleaned_lines.append(ln)
    return "\n".join(cleaned_lines)


def _fix_markdown_tables(text: str) -> str:
    """修复 LLM 输出的不规范 Markdown 表格。

    1. 段落中嵌入的表头（"叙述：| ID |...|）→ 剥离到独立行
    2. 缺分隔行 / 分隔行列数不符 → 按表头列数重建正确分隔行
    3. LLM 把整表压成一行无换行 → 识别 `||`（行边界）切回多行
    4. 数据行末尾被粘进「### 补充说明」等 → 剥离为独立段落
    """
    import re
    if not text or "|" not in text:
        return text

    # --- 阶段 -1：先清洗 TABLE N 伪表格标题 + 按 status 分组的伪表格行 ---
    text = _strip_pseudo_tables(text)

    # --- 阶段 0：剥离段落中嵌入的表头 ---
    # LLM 常输出 "系统中共有 5 个项目，列表如下：| ID |项目名称 |...|"
    # 把表格行片段切到独立行，避免被前端当成段落渲染
    text = re.sub(
        r"(^|\n)([^|\n]{0,80}?[:：,，]\s*)(\|[^\n|]{1,60}(?:\|[^\n|]{1,60}){2,}\|)",
        lambda m: m.group(1) + m.group(2).rstrip() + "\n" + m.group(3),
        text,
    )

    # --- 阶段 1：检测"无换行的表格"，把整段压行的表切回多行 ---
    pipe_count = text.count("|")
    has_sep_marker = re.search(r"\|\s*-{2,}\s*\|", text) is not None
    nl_count = text.count("\n")
    if pipe_count > 10 and (nl_count <= 3 or (has_sep_marker and nl_count < pipe_count // 2)):
        text = _split_inline_table(text)

    # --- 阶段 2：按行处理，重建分隔行 + 剥离说明段落 ---
    is_sep_line = lambda s: bool(re.match(r"^\s*\|[\s\-:|]+\|\s*$", s.strip()))
    starts_pipe = lambda s: s.strip().startswith("|") and s.strip().count("|") >= 2
    TRAILING_HINT = re.compile(r"补充说明|总结说明|总结|注意事项|注意：|说明：|备注")
    TRAILING_KWS = ("###", "补充说明", "总结说明", "总结", "注意事项", "注意：", "说明：", "备注")

    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if starts_pipe(line):
            block = [lines[i]]
            j = i + 1
            while j < len(lines) and starts_pipe(lines[j]):
                block.append(lines[j])
                j += 1

            header = block[0].strip()
            col_count = header.count("|") - 1
            sep = "| " + " | ".join(["---"] * col_count) + " |"

            rebuilt = [header, sep]
            outside = []
            for b in block[1:]:
                bs = b.strip()
                if is_sep_line(bs):
                    # 原有分隔行（可能列数错误）→ 丢弃，统一用重建的 sep
                    continue
                # 剥离数据行末尾被粘进的说明：找说明关键词前的最后一个 `|`
                cut = None
                for kw in TRAILING_KWS:
                    idx = bs.find(kw)
                    if idx > 0:
                        pipe_pos = bs.rfind("|", 0, idx)
                        if pipe_pos > 0:
                            cut = pipe_pos
                            break
                if cut is not None:
                    data_part = bs[:cut].strip()
                    hint_part = bs[cut:].lstrip("|").strip().lstrip("#").strip()
                    if data_part.count("|") >= 2:
                        rebuilt.append(data_part if data_part.endswith("|") else data_part + " |")
                    if hint_part:
                        outside.append(hint_part)
                    continue
                if TRAILING_HINT.search(bs):
                    outside.append(bs.lstrip("#").strip())
                    continue
                rebuilt.append(bs)

            out.extend(rebuilt)
            out.extend(outside)
            i = j
            continue
        out.append(line)
        i += 1
    # --- 阶段 3：剥离"无表头多列行"和"有表头无数据的多列块" ---
    # LLM 偶尔会重复输出或写到一半丢数据，整体剥离避免污染前端渲染
    return _clean_orphan_table_blocks("\n".join(out))


def _split_inline_table(text: str) -> str:
    """把"无换行的表格"按 `|...|` 块切分回多行。

    LLM 经常把整个 markdown 表格压成一行：`header|sep|r1|r2|...|说明文本`
    切分策略：从分隔行（`| --- |`）和换行符这两个锚点同时切。
    """
    import re

    if "\n" in text:
        segments = text.split("\n")
        result = []
        for seg in segments:
            if seg.count("|") > 4 and "\n" not in seg:
                result.append(_split_one_inline_segment(seg))
            else:
                result.append(seg)
        return "\n".join(result)
    else:
        return _split_one_inline_segment(text)


def _split_one_inline_segment(seg: str) -> str:
    """把一个无换行的表格段切成多行。

    特征：行尾是 `|`、行首是 `|`，所以 `||` 就是"行边界"。
    把所有 `||` 替换为 `|\n|`，每行就独立了。
    """
    if "||" not in seg:
        return seg
    return seg.replace("||", "|\n|")


def _clean_orphan_table_blocks(text: str) -> str:
    """剥离 LLM 输出的"残缺表格"，作为最后兜底。

    算法：**两遍扫描**
    1. 第一遍标记所有合法表格的行范围（表头行 + 分隔行 + 任意数据行）
    2. 第二遍剥离不在任何合法范围内的多列行

    目标 A —— 无表头多列行：
        | HTTP Request | 1734 | 0 | 0.0% | 84.2 ms | 164.0 ms | 326.4 ms | 91.32 req/s |
        （前面无 `| --- |` 分隔行 + 后面也无 → 孤儿 → 剥离）

    目标 B —— 有表头+分隔行但完全无数据：
        | 请求名 | 样本数 | 错误数 | ...  |
        | --- | --- | --- | --- |
        （之后没有 `|` 开头的数据行 → 整块 2 行都剥离）
    """
    import re
    if not text or "|" not in text:
        return text

    lines = text.split("\n")
    n = len(lines)
    blocks: List[tuple] = []
    i = 0
    while i < n:
        s = lines[i].strip()
        is_candidate_header = s.endswith("|") and s.count("|") >= 3
        if is_candidate_header:
            if i + 1 < n:
                next_s = lines[i + 1].strip()
                is_sep = (
                    bool(re.match(r"^\|?[\s\-:|]+\|?$", next_s))
                    and next_s.count("-") >= 3
                    and next_s.endswith("|")
                )
                if is_sep:
                    header_pipes = s.count("|")
                    sep_pipes = next_s.count("|")
                    if header_pipes == sep_pipes:
                        # 合法表头+分隔 + 列数匹配，再向后收集所有 starts_with `|` 的连续行
                        start = i
                        j = i + 2
                        while j < n:
                            sj = lines[j].strip()
                            if sj.startswith("|") and sj.endswith("|") and sj.count("|") == header_pipes:
                                j += 1
                                continue
                            if not sj:
                                # 空行跳过（不属于表）
                                j += 1
                                continue
                            break
                        # 数据行：要求至少 1 行匹配列数
                        has_data = any(
                            lines[k].strip().startswith("|")
                            and lines[k].strip().endswith("|")
                            and lines[k].strip().count("|") == header_pipes
                            for k in range(i + 2, j)
                        )
                        if has_data:
                            blocks.append((start, j))
                            i = j
                            continue
        i += 1

    def in_block(idx: int) -> bool:
        for start, end in blocks:
            if start <= idx < end:
                return True
        return False

    # 第二遍：剥离不在合法块内的多列行（≥5 `|`）
    out: List[str] = []
    i = 0
    while i < n:
        line = lines[i]
        s = line.strip()
        is_multi_col = s.endswith("|") and s.count("|") >= 5
        if is_multi_col and not in_block(i):
            next_line = lines[i + 1].strip() if i + 1 < n else ""
            is_next_sep = (
                bool(re.match(r"^\|?[\s\-:|]+\|?$", next_line))
                and next_line.count("-") >= 3
                and next_line.endswith("|")
            )
            if is_next_sep and next_line.count("|") == s.count("|"):
                header_label = s.strip("|").strip().replace("|", " · ")[:60]
                out.append(f"> ⚠️ 表头 `{header_label}` 无数据行，已忽略")
                i += 2
                continue
            else:
                out.append("> ⚠️ 检测到一条无表头的多列数据行，已忽略（上方 key-value 表已包含完整指标）")
                i += 1
                continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _build_url(base_url: str) -> str:
    base_url = (base_url or "").rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    if base_url.endswith("/v1") or "/v1/" in base_url:
        return f"{base_url}/chat/completions"
    return f"{base_url}/v1/chat/completions"


def _call_llm_sync(
    config,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """同步（非流式）调用 LLM。保留为非流式场景的 fallback。"""
    url = _build_url(config.base_url)

    payload = {
        "model": config.model_name,
        "messages": messages,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    t0 = time.time()
    logger.info(f"[LLM] sync 调用 {config.model_name} timeout={LLM_TIMEOUT}s, messages={len(messages)}, tools={len(tools)}")
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT)
        resp.raise_for_status()
        logger.info(f"[LLM] sync 响应耗时 {time.time() - t0:.1f}s, status={resp.status_code}")
        return resp.json()
    except requests.exceptions.Timeout:
        logger.error(f"[LLM] sync 超时 {time.time() - t0:.1f}s (limit={LLM_TIMEOUT}s) — model={config.model_name}")
        raise
    except Exception as e:
        logger.error(f"[LLM] sync 调用失败 {type(e).__name__}: {e} 耗时 {time.time() - t0:.1f}s")
        raise


def _stream_llm(
    config,
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
) -> Generator[Dict[str, Any], None, None]:
    """流式调用 LLM，逐 chunk yield 增量内容。

    yield 形式：
      - {"kind": "content", "text": "..."}        —— 文本增量
      - {"kind": "tool_calls", "delta": {...}}     —— 工具调用增量（OpenAI 格式）
      - {"kind": "finish", "reason": "..."}        —— 结束原因
      - {"kind": "usage", "prompt_tokens": N, ...} —— token 用量（部分模型返回）
    """
    url = _build_url(config.base_url)

    payload = {
        "model": config.model_name,
        "messages": messages,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    t0 = time.time()
    logger.info(f"[LLM] stream 调用 {config.model_name} timeout={LLM_TIMEOUT}s, messages={len(messages)}, tools={len(tools)}")
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=LLM_TIMEOUT, stream=True)
        if resp.status_code != 200:
            # 流式失败时退回非流式
            logger.warning(f"[LLM] stream status={resp.status_code}，回退到 sync")
            full = _call_llm_sync(config, messages, tools)
            choice = (full.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            content = msg.get("content") or ""
            if content:
                yield {"kind": "content", "text": content}
            for tc in msg.get("tool_calls") or []:
                yield {"kind": "tool_calls", "delta": tc}
            yield {"kind": "finish", "reason": choice.get("finish_reason", "stop")}
            return

        # ⚠️ 必须 decode_unicode=False + 手动 utf-8 decode：
        # requests 的 decode_unicode=True 会"自动检测编码"，经常猜错（按 Latin-1），
        # 把 UTF-8 多字节序列（如 `\xe9\xa1\xb9`）的每个字节当成单字符，
        # 下游 JSON encode 后变成双重 UTF-8 编码（每个中文 6 字节乱码）。
        for raw_line in resp.iter_lines(decode_unicode=False):
            if not raw_line:
                continue
            if isinstance(raw_line, bytes):
                raw_line = raw_line.decode("utf-8", errors="replace")
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                yield {"kind": "finish", "reason": "stop"}
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choice = (chunk.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            # reasoning 模型（DeepSeek-R1/QwQ）的思维链处理：
            # 1) OpenAI 兼容模式：独立字段 reasoning_content → 直接忽略
            # 2) vLLM merge_reasoning_content=True：拼到 content 字段，可能：
            #    a) 用 <think>...</think> 标签包裹 → 正则剥除
            #    b) 裸 base64/XML 拼到 content → 用启发式判断（连续 100+ 字符 base64/不可打印）
            if delta.get("reasoning_content"):
                # 模式 1：直接丢弃 reasoning_content，不展示
                pass
            else:
                text = delta.get("content")
                if text:
                    # 剥 <think>...</think> 标签
                    if "<think>" in text or "</think>" in text:
                        import re as _re
                        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
                    # 启发式：检测裸 base64 reasoning（vLLM 行为）
                    # 特征：连续 100+ 字符只含 base64 字符（[A-Za-z0-9+/=]）且无中文/标点
                    if text and len(text) >= 100 and not any('\u4e00' <= c <= '\u9fff' for c in text):
                        base64_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n")
                        non_b64 = sum(1 for c in text if c not in base64_chars and not c.isspace())
                        if non_b64 / len(text) < 0.02:
                            # 几乎全是 base64，判定为裸 reasoning，跳过
                            logger.debug(f"[LLM] 跳过裸 base64 reasoning chunk ({len(text)} chars)")
                            text = ""
                    if text and text.strip():
                        yield {"kind": "content", "text": text}
            if delta.get("tool_calls"):
                for tc in delta["tool_calls"]:
                    yield {"kind": "tool_calls", "delta": tc}
            finish = choice.get("finish_reason")
            if finish:
                yield {"kind": "finish", "reason": finish}
            usage = chunk.get("usage")
            if usage:
                yield {"kind": "usage", **usage}
        logger.info(f"[LLM] stream 完成耗时 {time.time() - t0:.1f}s")
    except requests.exceptions.Timeout:
        logger.error(f"[LLM] stream 超时 {time.time() - t0:.1f}s (limit={LLM_TIMEOUT}s) — model={config.model_name}")
        raise
    except Exception as e:
        logger.error(f"[LLM] stream 调用失败 {type(e).__name__}: {e} 耗时 {time.time() - t0:.1f}s")
        raise


def run_agent(
    config,
    user_message: str,
    history: List[Dict[str, Any]] = None,
    system_prompt: str = None,
    current_user=None,
) -> Generator[Dict[str, Any], None, None]:
    """
    运行 Agent 循环，yield 事件 dict。

    事件类型：
      - {"type": "thinking", "content": "..."}     —— LLM 正在思考
      - {"type": "tool_call", "name": "...", "arguments": {...}}  —— 调用工具
      - {"type": "tool_result", "name": "...", "result": {...}}   —— 工具返回
      - {"type": "message", "content": "..."}      —— LLM 最终回复
      - {"type": "error", "content": "..."}        —— 错误
      - {"type": "done"}                           —— 结束
    """
    tools = get_tools_for_llm()
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        for iteration in range(MAX_ITERATIONS):
            # 每轮 LLM 调用前先发"思考中..."占位，让前端有即时反馈
            # （避免长 LLM 推理 + 长工具调用造成 60-120s 视觉空白）
            if iteration == 0:
                yield {"type": "thinking", "content": f"🧠 正在分析问题，准备调用工具..."}
            else:
                yield {"type": "thinking", "content": f"🔄 整合上一步结果，继续推理（{iteration + 1}/{MAX_ITERATIONS}）..."}

            # === 流式调用 LLM：每个 chunk 立刻 yield，前端持续 reset 看门狗 ===
            content_buf: List[str] = []
            tool_calls_buf: Dict[int, Dict[str, Any]] = {}  # index -> {id, name, arguments_str}
            finish_reason = ""
            last_yield_len = 0  # 上次 yield 的累积长度，用于控制 flush 频率

            try:
                for chunk in _stream_llm(config, messages, tools):
                    kind = chunk.get("kind")
                    if kind == "content":
                        content_buf.append(chunk.get("text", ""))
                        # 找 flush 边界（句号/换行/累积足够长）
                        full = "".join(content_buf)
                        if len(full) - last_yield_len >= 40:
                            flush_until = len(full)
                            for sep in ["\n\n", "。", "！", "？", ". ", "! ", "? "]:
                                idx = full.find(sep, last_yield_len)
                                if idx != -1 and idx + len(sep) <= len(full):
                                    flush_until = idx + len(sep)
                                    break
                            if flush_until - last_yield_len >= 20:
                                piece = full[last_yield_len:flush_until].strip()
                                if piece:
                                    yield {"type": "thinking", "content": piece}
                                last_yield_len = flush_until
                    elif kind == "tool_calls":
                        delta = chunk.get("delta") or {}
                        idx = delta.get("index", 0)
                        if idx not in tool_calls_buf:
                            tool_calls_buf[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                        if delta.get("id"):
                            tool_calls_buf[idx]["id"] = delta["id"]
                        if delta.get("type"):
                            tool_calls_buf[idx]["type"] = delta["type"]
                        fn = delta.get("function") or {}
                        if fn.get("name"):
                            tool_calls_buf[idx]["function"]["name"] = fn["name"]
                        if fn.get("arguments"):
                            tool_calls_buf[idx]["function"]["arguments"] += fn["arguments"]
                    elif kind == "finish":
                        finish_reason = chunk.get("reason", "stop")
                # 强制 flush 最后一段
                full = "".join(content_buf)
                if last_yield_len < len(full):
                    piece = full[last_yield_len:].strip()
                    if piece:
                        yield {"type": "thinking", "content": piece}
            except requests.exceptions.Timeout:
                yield {"type": "error", "content": f"LLM 调用超时（>{LLM_TIMEOUT}s），请稍后重试或检查模型服务"}
                yield {"type": "done"}
                return
            except requests.exceptions.ConnectionError as e:
                yield {"type": "error", "content": f"无法连接 LLM 服务: {str(e)[:200]}"}
                yield {"type": "done"}
                return
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else "?"
                body = (e.response.text[:500] if e.response is not None else "")
                yield {"type": "error", "content": f"LLM API 返回错误 {status_code}: {body}"}
                yield {"type": "done"}
                return
            except Exception as e:
                logger.exception("LLM 调用异常")
                yield {"type": "error", "content": f"LLM 调用异常: {str(e)}"}
                yield {"type": "done"}
                return

            # 构造完整 assistant 消息（用于 append 到 messages）
            full_content = "".join(content_buf)
            tool_calls = [tool_calls_buf[k] for k in sorted(tool_calls_buf.keys())] if tool_calls_buf else None
            assistant_msg = {"role": "assistant"}
            if full_content:
                assistant_msg["content"] = full_content
            # 注意：OpenAI 兼容接口严格要求 tool_calls 消息要么 content 是字符串，
            # 要么**省略** content 字段。设成 None 会被某些实现（如 vLLM）拒为 400。
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls

            # 如果 LLM 要调用工具
            if tool_calls:
                messages.append(assistant_msg)
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    tool_name = fn.get("name", "")
                    try:
                        tool_args = json.loads(fn.get("arguments", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        tool_args = {}

                    yield {"type": "tool_call", "name": tool_name, "arguments": tool_args}

                    # 标记"正在执行"（前端可显示 loading 状态）
                    yield {"type": "executing", "name": tool_name}

                    # 执行工具（同步）
                    try:
                        # 注入当前用户供工具使用（创建缺陷/用例时需要报告人字段）
                        tool_args_with_user = dict(tool_args)
                        if current_user is not None and '_user' not in tool_args_with_user:
                            tool_args_with_user['_user'] = current_user
                        result = execute_tool(tool_name, tool_args_with_user)
                    except Exception as e:
                        logger.exception(f"工具 {tool_name} 执行异常")
                        result = {"error": f"工具执行异常: {str(e)}"}

                    yield {"type": "tool_result", "name": tool_name, "result": result}

                    # 把工具结果也作为一条思考记录，让用户看到工具返回了啥
                    summary = _summarize_tool_result(tool_name, result)
                    if summary:
                        yield {"type": "thinking", "content": summary}

                    # 把工具结果加入消息历史（截断避免多轮累积后 context 爆炸）
                    result_str = json.dumps(result, ensure_ascii=False, default=str)
                    if len(result_str) > 2000:
                        result_str = result_str[:2000] + f"...(truncated, full {len(result_str)} chars)"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result_str,
                    })

                # 继续下一轮，让 LLM 看到工具结果后继续推理
                continue

            # 没有工具调用，LLM 直接回复
            if full_content:
                # 后处理：补齐 LLM 表格可能遗漏的分隔行 / 切分被压行的表格
                if "|" in full_content:
                    full_content = _fix_markdown_tables(full_content)
                yield {"type": "message", "content": full_content}

            yield {"type": "done"}
            return

        # 超过最大轮次
        yield {"type": "message", "content": "已达到最大工具调用轮次（20 轮），知识库检索结果较多时可能需要更细化的提问，请尝试缩小问题范围或分步提问。"}
        yield {"type": "done"}

    except Exception as e:
        logger.exception("Agent 执行异常")
        yield {"type": "error", "content": f"Agent 执行失败: {str(e)}"}
        yield {"type": "done"}
