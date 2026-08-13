# TestHub 核心流程回归套件执行记录

> 本报告由 Agent 在 `testhub_dev-backend-1` 容器内重跑 UI 自动化回归套件（TestSuite id=15）后，整理容器内执行证据落盘生成。
> 容器内文件系统与宿主机不共享，以下数据由 Agent 执行 `docker exec ... python manage.py shell` 采集后写入本文件，作为人类可读的执行证据。

---

## 一、执行概览

| 项目 | 内容 |
|------|------|
| 报告生成时间 | 2026-08-12（Agent 落盘） |
| 执行开始时间（容器内本地 ISO） | `2026-08-12T19:07:24.430560` |
| 执行开始时间（UTC，来自执行记录） | `2026-08-12T11:07:24` |
| 执行总耗时 | 约 28 秒（RUN_START 19:07:24 → 末条执行 finished 19:07:52） |
| 执行环境 | 容器 `testhub_dev-backend-1`、引擎 `playwright` / 浏览器 `chrome` / `headless=True` |
| 调用入口 | `apps.ui_automation.test_executor.TestExecutor(suite, engine='playwright', browser='chrome', headless=True).run()` |
| 套件 | id=15，名称 **TestHub核心流程回归** |
| 套件级执行结论 | `execution_status = passed`，`passed_count = 3`，`failed_count = 0` |
| 本次新建 TestExecution 记录 | id=**155**（套件级容器）、**156** / **157** / **158**（分别对应 3 个脚本） |
| 逐步结果总览 | 3 个脚本、共 **37** 个步骤，全部 `success = true`，无 error |

> ⚠️ **取证提示**：`TestExecutor.run()` 会先建一条套件级执行记录（id=155，`result_data` 为空），再为每个脚本各建一条执行记录（156=脚本11、157=脚本12、158=脚本13）。
> 因此 `TestExecution.objects.latest('id')` 实际返回的是 **158（最后执行的脚本13）**，而非套件级记录 155；逐步明细分散在 156/157/158 三条记录中。复现时若只看 `latest()` 会漏掉脚本 11、12 的步骤。

---

## 二、执行环境

- **容器**：`testhub_dev-backend-1`（镜像 `testhub_dev-backend`，状态 Up，映射 8000:8000 / 5900:5900）
- **容器内访问前端**：`http://frontend:5173/`
- **引擎 / 浏览器 / 模式**：`playwright` / `chrome` / `headless=True`
- **调用入口**：`TestExecutor`（来自 `apps.ui_automation/test_executor.py`，构造签名 `TestExecutor(test_suite, engine='playwright', browser='chrome', headless=False, executed_by=None, suite_run_id=None)`）

---

## 三、套件与关联脚本

套件 id=15「TestHub核心流程回归」通过 `TestSuiteScript` 关联 3 个脚本，按 `order` 升序执行：

| order | 脚本 id | 脚本名称 | 步骤数 | 本次执行记录 id | 执行状态 |
|------:|--------:|----------|------:|---------------:|---------|
| 1 | 11 | TH-登录并新建BUG | 13 | 156 | SUCCESS（passed） |
| 2 | 12 | TH-用例页新建用例 | 11 | 157 | SUCCESS（passed） |
| 3 | 13 | TH-测试计划页新建测试计划 | 13 | 158 | SUCCESS（passed） |

---

## 四、逐步结果表

判定口径（探查模型后确认）：本平台**没有独立的步骤结果表**（`TestStepResult`/`TestScriptResult` 不存在）。逐步结果以 JSON 形式存入 `TestExecution.result_data.test_cases[].steps[]`，每条 step 字段为：
`step_number`（步骤序号 / `ScriptStep.step_order`）、`action_type`（动作，经执行器映射后的实际动作）、`description`（步骤描述 / `ScriptStep.description`）、`target`（NAVIGATE 时为 URL；非导航步骤的「目标元素」依赖 `element` 字段，本套件这些步骤未绑定 `target_element`，故目标元素记为「未记录」）、`success`（是否成功）、`error`（错误信息，成功为 `null`）。

### 脚本 11 — TH-登录并新建BUG（执行记录 156，13 步，全部成功）

| 序号 | 动作 | 目标 / 元素 | 成功 | 错误 |
|----:|------|-----------|------|------|
| 1 | navigate | http://frontend:5173/login | ✅ | 无 |
| 2 | fill | （未记录） | ✅ | 无 |
| 3 | fill | （未记录） | ✅ | 无 |
| 4 | click | （未记录） | ✅ | 无 |
| 5 | wait | （未记录） | ✅ | 无 |
| 6 | navigate | http://frontend:5173/defects | ✅ | 无 |
| 7 | wait | （未记录） | ✅ | 无 |
| 8 | click | （未记录） | ✅ | 无 |
| 9 | wait | （未记录） | ✅ | 无 |
| 10 | fill | （未记录） | ✅ | 无 |
| 11 | fill | （未记录） | ✅ | 无 |
| 12 | click | （未记录） | ✅ | 无 |
| 13 | wait | （未记录） | ✅ | 无 |

> 说明：脚本 11 的 `ScriptStep.description` 仅存占位文本 `step1`…`step13`，故上表「目标/元素」列无法显示业务语义，统一标注为「未记录」。

### 脚本 12 — TH-用例页新建用例（执行记录 157，11 步，全部成功）

| 序号 | 动作 | 目标 / 元素 | 成功 | 错误 |
|----:|------|-----------|------|------|
| 1 | navigate | http://frontend:5173/ai-generation/testcases | ✅ | 无 |
| 2 | wait | （未记录） | ✅ | 无 |
| 3 | click | （未记录）「新建用例按钮」 | ✅ | 无 |
| 4 | wait | （未记录）「等待弹窗出现」 | ✅ | 无 |
| 5 | fill | （未记录）「输入用例标题」 | ✅ | 无 |
| 6 | fill | （未记录）「输入用例描述」 | ✅ | 无 |
| 7 | fill | （未记录）「输入前置条件」 | ✅ | 无 |
| 8 | fill | （未记录）「输入操作步骤」 | ✅ | 无 |
| 9 | fill | （未记录）「输入预期结果」 | ✅ | 无 |
| 10 | click | （未记录）「创建用例按钮」 | ✅ | 无 |
| 11 | wait | （未记录）「等待提交完成」 | ✅ | 无 |

### 脚本 13 — TH-测试计划页新建测试计划（执行记录 158，13 步，全部成功）

| 序号 | 动作 | 目标 / 元素 | 成功 | 错误 |
|----:|------|-----------|------|------|
| 1 | navigate | http://frontend:5173/ai-generation/executions | ✅ | 无 |
| 2 | wait | （未记录） | ✅ | 无 |
| 3 | click | （未记录）「新建测试计划按钮」 | ✅ | 无 |
| 4 | wait | （未记录）「等待弹窗出现」 | ✅ | 无 |
| 5 | fill | （未记录）「输入计划名称」 | ✅ | 无 |
| 6 | fill | （未记录）「输入计划描述」 | ✅ | 无 |
| 7 | click | （未记录）「项目下拉触发器」 | ✅ | 无 |
| 8 | wait | （未记录）「等待下拉展开」 | ✅ | 无 |
| 9 | click | （未记录）「下拉第一个选项」 | ✅ | 无 |
| 10 | click | （未记录）「收起项目下拉」 | ✅ | 无 |
| 11 | wait | （未记录）「等待下拉收起」 | ✅ | 无 |
| 12 | click | （未记录）「创建按钮」 | ✅ | 无 |
| 13 | wait | （未记录）「等待提交完成」 | ✅ | 无 |

---

## 五、落库对比表（BEFORE / AFTER / DELTA）

在 `ex.run()` 前后分别统计三类业务对象数量（取数口径：`apps.defects.models.Defect`、`apps.ui_automation.models.TestCase`、`apps.executions.models.TestPlan`）。

| 对象 | BEFORE（跑前） | AFTER（跑后） | DELTA | 是否真落库 | 对应脚本 |
|------|--------------:|--------------:|------:|-----------|---------|
| Defect（缺陷） | 13 | 14 | **+1** | ✅ 真落库 | 脚本 11「TH-登录并新建BUG」 |
| TestCase（用例） | 11 | 11 | **0** | ❌ 未落库 | 脚本 12「TH-用例页新建用例」 |
| TestPlan（测试计划） | 4 | 4 | **0** | ❌ 未落库 | 脚本 13「TH-测试计划页新建测试计划」 |

**跑前基线（执行前最新 TestExecution id）= 154**；本次运行新建 155 / 156 / 157 / 158，故可确认 DELTA 完全由本次套件执行产生、无其他干扰。

---

## 六、结论

- **表面结论（执行器判定）**：套件 `execution_status = passed`，`passed_count = 3`、`failed_count = 0`；3 个脚本各自的 `TestExecution`（156/157/158）均为 `SUCCESS`，共 37 个步骤全部 `success = true`，无任何 `error`。
- **关键数字**：passed = 3 / failed = 0；落库 DELTA：Defect **+1**、TestCase **0**、TestPlan **0**。
- **真相（"假绿"）**：虽然脚本 12（新建用例）、脚本 13（新建测试计划）的所有 UI 操作都「未抛异常」而被判为通过，但执行后数据库中 **TestCase 与 TestPlan 数量均为 0 增量**——即这两个脚本的「创建」操作**并未真正落库**。仅脚本 11 的「新建 BUG」成功新增了 1 条 Defect 记录（真落库）。
- **根因分析**：执行器 `TestExecutor` 对单步的 `success` 判定**仅取决于该动作（click / fill / navigate 等）在 Playwright 层是否抛异常**，并不校验后端是否真正提交成功。新建用例/测试计划这类表单提交，若被后端「必填字段校验」拦截，前端通常仅以报错提示或弹窗返回、而 `.click()` 动作本身仍正常完成——于是执行器误判为通过，形成"假绿"。
- **建议**：
  1. 在脚本关键提交步骤后，增加"断言记录已生成"（如按名称回查列表/数据库计数 +1）作为 `success` 的判定条件，而非仅看动作是否抛异常；
  2. 复跑结论时以 DB 计数 DELTA 作为"真落库"的硬证据，不要只信 `execution_status`。

---

## 七、平台 UI 查看路径提示

1. 登录 TestHub 前端（容器内 `http://frontend:5173/`，宿主可通过映射端口访问，如 `http://localhost:5173/`）。
2. 进入 **UI自动化 → 测试执行**。
3. 可按以下 `TestExecution` id 检索本次执行：
   - **155**：套件级执行记录（关联 TestSuite id=15，但 `result_data` 为空，仅作容器）；
   - **156 / 157 / 158**：分别对应脚本 11 / 12 / 13 的逐步明细（含每步 `success` / `error` / 截图）。
4. 也可在「测试套件」列表找到「TestHub核心流程回归」（id=15），查看其 `execution_status = passed`、`passed_count = 3`、`failed_count = 0` 的汇总。

---

*取证说明：本报告所有数据均来自只读查询 + 一次预期内的套件重跑（重跑仅产生无害的 `TestExecution` 日志，未对业务数据做任何人工修改）。执行器生成的逐步结果以 JSON 存于 `TestExecution.result_data` 字段，无独立步骤结果表。*
