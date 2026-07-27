# AI 测试代码：新版本与拉取代码（上游）迁移对比

## 一、当前项目已更新为新版本

已将 AI 测试相关代码恢复为新版本逻辑，包含以下改进。

---

## 二、当前项目相对上游的改进（已迁移）

### 1. `apps/ui_automation/ai_base.py`

| 项目 | 上游（拉取代码） | 当前项目（新版本） | 说明 |
|------|------------------|--------------------|------|
| **任务分析 `analyze_task`** | 简单 prompt：`Break down this task into steps: {task}. Return JSON list of strings.` | 详细 prompt：要求分解成具体步骤，含示例（百度搜索），多种 JSON 解析方式 | 任务分解更细，步骤更完整 |
| **浏览器等待** | `0.2, 0.05, 0.1` 秒 | `0.5, 0.2, 0.2` 秒 | 外部站点（如百度）加载更稳 |
| **Agent 重试** | `max_retries=1, max_failures=2` | `max_retries=2, max_failures=3` | 元素查找失败时多一次机会 |
| **Done 回调** | 仅 `return f"Finished: {text}"` | 向 callback 发送 `{'type': 'done_result', 'success': success, 'text': text}` | 前端可区分成功/失败 |
| **输入前自动点击** | 无 | 在 `input_text/input` 前自动执行 `click_element` 聚焦 | 提高百度等站点输入成功率 |
| **Prompt 规则** | 7 条（强调速度） | 10 条（顺序执行 + 输入前点击 + 验证） | 严格按步骤、不跳过输入 |

### 2. `apps/ui_automation/views.py`

| 项目 | 上游（拉取代码） | 当前项目（新版本） | 说明 |
|------|------------------|--------------------|------|
| **done_result 处理** | 无 | `agent_done_result` 变量，`on_step_update` 中处理 `type=='done_result'` | 接收 Agent 的完成结果 |
| **执行结束状态** | 非停止即 `passed` | 若 `agent_done_result.success==False` 则 `status='failed'`，并写入 Agent 的 `text` 到 logs | 失败时前端和日志能正确体现 |

---

## 三、上游有、当前项目未采用的（或已覆盖的）

对比上游 `testhub_platform_upstream` 的 `apps/ui_automation/`：

- **ai_base.py**：上游为“老版本”逻辑（简单 analyze、短等待、无自动点击、无 done_result）。当前项目已全部替换为新版本逻辑，**无需要从上游迁回的内容**。
- **views.py**：上游无 `done_result`/`agent_done_result` 相关逻辑；当前项目已新增并保留，**无需从上游迁移**。
- 其他文件（如 `ai_agent.py`, `models.py`, `urls.py` 等）：若上游有与 AI 测试无关的 bug 修复或小改动，可按需单独对比；本次只针对 **AI 测试执行与任务分析** 的迁移对比。

结论：**没有“未迁移过来”的、与 AI 测试相关的重要逻辑**；当前是新版本在原有上游基础上做了增强。

---

## 四、新版本代码要点汇总

1. **任务分析**：详细 prompt + 示例 + 多种 JSON 解析，避免只得到 1 个大步骤。
2. **执行顺序**：Prompt 中强调严格按 1→2→3 执行，且“输入”类任务必须生成 `input_text`。
3. **输入前点击**：规则要求先 `click_element` 再 `input_text`；代码在 `input_text` 前自动补一次 `click_element`，双保险。
4. **等待与重试**：略增页面等待与 Agent 重试/失败次数，便于外部站点和元素加载。
5. **失败反馈**：`done(success=False, text="...")` 通过 `done_result` 传到 views，写入 `status='failed'` 和日志，前端可展示失败原因。

---

## 五、若从上游重新拉取代码后的注意点

若将来从 `testhub_platform_upstream` 再次拉取或合并：

1. **ai_base.py**  
   - 保留当前项目的：`analyze_task` 详细 prompt、BrowserProfile 等待时间、Agent 的 max_retries/max_failures、done 回调里的 `done_result`、input 前自动点击、10 条 Prompt 规则。  
   - 避免被上游覆盖回“老版本”的简单 prompt 和短等待。

2. **views.py**  
   - 保留：`agent_done_result`、`on_step_update` 中对 `type=='done_result'` 的处理、以及根据 `agent_done_result.success` 设置 `status='failed'` 和日志的逻辑。  
   - 上游没有这些，合并时不要丢弃。

按上述保留，即能保证“新版本”的 AI 测试逻辑完整迁移、无遗漏。
