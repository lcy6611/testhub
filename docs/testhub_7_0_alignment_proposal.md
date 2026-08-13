# TestHub 7.0 新功能对齐方案

> 依据 2026-08-13 发布《TestHub星球版7.0》13 项 Release 清单，结合 `testhub_platform` 现状代码盘点，梳理对齐/补强路线。
> 现状盘点基于 `apps/` + `frontend/` 只读探查（Explore agent，2026-08-13）。

## 一、现状盘点（13 项对照）

| # | 7.0 功能 | 现状 | 关键证据 | 缺口 |
|---|---------|------|---------|------|
| 1 | Playwright 录制回放 | 部分 | `ui_automation/playwright_engine.py`、`test_executor.py` 回放引擎在；`ScriptList.vue` 脚本编辑器在；`UiScriptGeneration.playwright_code` 字段在 | **无 codegen 实时录制入口（全仓无 record/codegen 关键字）**，录制→回传 py 链路缺失 |
| 2 | Hermes & 知识库打通 | 有 | `agent_tools.py` 注册 `search_knowledge_base`/`list_knowledge_bases`，调 `dify_kb_service.retrieve_from_dataset` | 检索已通；检索→生成→保存为分步工具，无单一整合入口 |
| 3 | Hermes & 飞书打通 | 无 | `assistant` 内无飞书机器人绑定/远程任务代码（仅 `kb_hub/feishu.py` 文档同步 + 通知 webhook） | 无远程任务下发通道 |
| 4 | Hermes 上传文件 | 部分 | `assistant/views.py` 支持 multipart `files` 上传至 Dify `/files/upload`（聊天附件） | 无专属"需求文档上传"工具，未落库为平台知识库/需求 |
| 5 | 助手图标可拖动悬停 | 无 | `HermesAvatar.vue` 及 assistant 目录无 `draggable/drag/拖动/position:fixed` | 图标不可拖动 |
| 6 | 兼容 DeepSeek V4 reasoning_content | 有 | `agent_engine.py`(L579-585) 处理 `reasoning_content`；`ai_base.py`(L894) deepseek 特判 | — |
| 7 | AI 用例生成思考过程展示 | 有 | `HermesChatView.vue`(L107-155)、`AgentView.vue` `thoughtText` 流式、`AIExecutionReport.vue` `step.thinking` | — |
| 8 | 测试计划用例悬浮预览+右侧抽屉 | 无 | `ExecutionDetailView.vue` 仅 el-table 状态/备注列；无 `el-drawer`、`@mouseenter` | 无悬浮预览、无点击抽屉 |
| 9 | 执行状态标记与备注合并 | 无 | `ExecutionDetailView.vue`(L205-230) 状态为独立 `el-select`、备注为独立 `el-input` | 未合并为一步 |
| 10 | 修复 APP 投屏高清断开 | 无 | `app_automation` 仅 adb `screencap`/airtest 截图，无 `mirror/投屏/高清` | 无设备投屏能力本身 |
| 11 | 修复 create_test_case 未存操作步骤 | 无（未落地） | `_create_testcase`(`agent_tools.py` L55-80) 仅存文本 `steps`，未建 `step_details`（TestCaseStep） | 结构化步骤未保存 |
| 12 | 修复 run_api_test 接口测试 | 有（已可跑） | 注册 `execute_api_request`/`execute_api_suite`，调 `api_testing.utils` | 工具名不同但能力具备 |
| 13 | 定时任务新增「录制脚本执行」 | 无 | `UiScheduledTask.TASK_TYPE_CHOICES`=[TEST_SUITE,TEST_CASE]；`AIScheduledTask`=[AI_SUITE,AI_CASE] | 无 RECORD_SCRIPT 类型 |

**汇总**：已有 5 项（2/6/7/12 + 11 的反面即接口可跑）、部分 3 项（1/4）、缺失 5 项（3/5/8/9/10/13）。其中 #11 列在"修复"清单但代码显示结构化步骤仍缺失，修复未生效。

## 二、分层落地路线

### P0 — 核心能力（录制闭环 + 修复缺陷 + 治"假绿"）
| 项 | 动作 | 切入点 |
|---|------|-------|
| #1 录制回放 | 新增录制入口：前端配置 URL → 后端生成 `playwright codegen --target python -o 文件 URL` 命令 → 用户跑 Inspector 录制 → 回传 py → 解析为 `UiScriptGeneration.playwright_code` → 脚本编辑器回放 | 新增 `ui_automation/recorder.py`（命令生成）+ `ScriptList.vue` 录制页 + 回传接口 |
| #13 录制脚本执行 | `UiScheduledTask.TASK_TYPE_CHOICES` 加 `RECORD_SCRIPT`，执行器分支调指定 `UiScriptGeneration` 回放 | `models.py`(L836) + 调度器 |
| #11 结构化步骤 | `_create_testcase` 解析 `steps` 为 `TestCaseStep` 记录，与 `_get_testcase_detail` 的 `step_details` 对齐 | `agent_tools.py` L55-80 |
| 前置：执行器结果断言 | 修 `test_executor.py` 的 passed 判定，从"动作不抛异常"升级为"动作成功 + 业务结果落库"——否则录制越多越假绿（Suite 15 已实测 3/3 假绿） | `test_executor.py` `run_suite_scripts` |

### P1 — 体验交互
| 项 | 动作 | 切入点 |
|---|------|-------|
| #8 悬浮+抽屉 | `ExecutionDetailView.vue` 加 `el-popover` 悬浮预览 + `el-drawer` 点击抽屉 | 前端 executions 详情 |
| #9 状态备注合并 | 执行状态与备注合并为一个内联组件（状态变更即带备注） | `ExecutionDetailView.vue` L205-230 |
| #5 图标拖动 | `HermesAvatar.vue` 加 `draggable` + 持久化 `position` 到 localStorage/用户配置 | 前端 assistant 组件 |
| #4 需求文档上传 | 上传接口支持"需求文档"类型，落库 knowledge_base/requirement，供 Hermes 生成用例取上下文 | `assistant/views.py` L283-345 |

### P2 — 生态集成（非核心，量较大）
| 项 | 动作 | 切入点 |
|---|------|-------|
| #3 飞书打通 | 飞书机器人绑定 Hermes + 远程任务通道（先有远程任务 API，再接飞书 webhook） | 新建 `assistant/remote_task` + 飞书 webhook |
| #10 APP 投屏高清 | 先建设备投屏（scrcpy/mirror）再修高清切换断开；量大，建议独立排期 | `app_automation` |

### P3 — 已具备（核对即可）
#2 / #6 / #7 / #12 已落地，Release 时只做回归核对，无需开发。

## 三、与"平台测自己"工作的衔接
- 我们已用 UI 自动化引擎回归 TestHub 自身（Suite 15：登录→新建BUG/用例/测试计划），并实测发现**执行器"假绿"缺陷**（`passed=3` 但仅新建BUG真落库，用例/计划被必填校验拦截却判通过）。
- **P0 的"执行器结果断言"是前置必做项**：不修断言，#1 录制回放产出的脚本同样无法被可信验证。
- #1 录制回放恰能降低我们自建 Suite 的成本——但应在断言修复后引入，避免"录制一堆假绿脚本"。

## 四、建议里程碑
- **M1（P0）**：执行器结果断言 + 录制回放入口 + 定时任务录制类型 + #11 结构化步骤。目标：UI 自动化从"手写脚本"升级为"录制即生成"，且结果可信。
- **M2（P1）**：测试计划详情交互优化（#8/#9）+ 助手图标拖动（#5）+ 需求文档上传（#4）。
- **M3（P2）**：飞书远程任务（#3）+ APP 投屏（#10，独立排期）。

## 五、待确认
- 阳哥平台是否需要对齐"星球版"全部功能，还是只取录制回放 + 执行器断言等核心项？（#3/#10 投入大，可暂缓）
- #1 录制命令运行环境：codegen 需在能访问目标站的网络跑（容器内 `frontend` 服务名或用户本机），方案需明确落点。
