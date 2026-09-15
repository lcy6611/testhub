# 智能评分器（llm_judge）移植验证报告

日期：2026-09-15
来源：开源版 `E:\PycharmProjects\a\testhub_platform` → 本平台 `apps/llm_judge`
截图：`.workbuddy/memory/screenshots/llm_judge/`（dashboard / single / batch / history / rubrics / knowledge，该目录已被 gitignore，不入库）

## 一、移植范围

| 层 | 内容 | 规模 |
|---|---|---|
| 后端 | `apps/llm_judge/`：`models.py`（Rubric/RubricDimension/RubricRule/JudgeRecord/JudgeBatch/KnowledgeBase/KBReportPeriod/KBMetric/KBMetricValue）、`judge_engine/` 全套、`rubric_templates/*.yaml`、`kb/financial_kb.json`、`views/serializers/urls/tasks/filters/admin/file_parser/kb_service/service` | 25 py + 3 yaml + 1 json，约 4156 行 |
| 前端 | `views/llm-judge/` 6 页 + `api/llm-judge.js` + 中英 i18n 词条 | 3389 + 327 行 |
| 接线 | `settings.LOCAL_APPS`、`backend/urls.py`（`/api/llm-judge/`）、`router`、`layout` 菜单/标题/面包屑、`Home.vue` 导航卡、`locales/index.js` | — |

## 二、平台适配（4 处，均为「照搬会坏」的点）

1. **LLM 配置兜底**（`judge_engine/config.py`）
   开源版只认 `OPENAI_API_KEY` / `OPENAI_BASE_URL`。本平台密钥统一收敛在配置中心
   `AIModelConfig`（`apps.requirement_analysis.models`），直接照搬会 `has_api_key=false`、开箱即废。
   新增 `_resolve_platform_llm()`：未显式配置 `OPENAI_API_KEY` 时，按平台既有约定
   `role='writer', is_active=True` → 回退任一 active 配置，取 `resolve_api_key()/base_url/model_name`。
   显式配置了 `OPENAI_API_KEY` 或 `JUDGE_MODEL` 环境变量时**完全不介入**。

2. **`JudgeEngine(cfg)` 上游 bug 修复**（`views.py::JudgeServiceConfigView.post`）
   `JudgeEngine.__init__` 首个位置参数是 `model`，上游却传了整个 `JudgeConfig` 实例，
   导致连通性测试必然报 `Object of type JudgeConfig is not JSON serializable`。
   改为按关键字传参（与 `judge_engine/service.py:66` 的正确写法一致）。

3. **`config/service` GET 返回生效配置**（`views.py`）
   原来直接读原始 settings，即使兜底生效也报「未配置密钥」，前端会误报。改为读 `JudgeConfig.from_settings()`。

4. **日均趋势改内存聚合**（`views.py::DashboardStatsView`）
   `TruncDate` 在 MySQL 上走 `CONVERT_TZ`，本环境 `mysql.time_zone_name` 为 0 行 → `CONVERT_TZ` 返回
   NULL → `day` 全为 null、趋势图空白。按平台既有约定（`apps/reports/views.py:167` 同款注释）改为
   Python 内存聚合并补全空缺日期。

5. **i18n 竖线转义**（`locales/lang/{zh-cn,en}/llm-judge.js`）
   文案含 `|||`，vue-i18n 把 `|` 当复数分隔符 → `Message compilation error: Plural must have messages`。
   改为字面量 `{'|'}{'|'}{'|'}`。

## 三、验证证据

| 项 | 命令/方式 | 结果 |
|---|---|---|
| django check | `manage.py check` | `System check identified no issues (0 silenced)` |
| 迁移 | `makemigrations llm_judge` + `migrate llm_judge` | 生成 `0001_initial.py`，10 张表建成 |
| Celery 注册 | `docker logs worker` | `. apps.llm_judge.tasks.score_batch_task` |
| LLM 连通 | `POST /api/llm-judge/config/service/` | `{"ok":true,"message":"连通成功: model=Qwen3.6-35B-A3B"}` |
| 单条评分 | `POST /api/llm-judge/judge/single/` | 真实评分落库：final_score=89.0 / green / acceptable / latency≈102s |
| 批量评分 | `POST /batches/` → 轮询 `/batches/1/progress/` | completed / progress=100 / scored=1 / mean=73.7 / yellow / blocked=false |
| 模板下载 | `?tpl=csv|xlsx|txt` | 均 200，Content-Type 正确（注意：`?format=` 会撞 DRF 的 format 覆盖而 404，前端用的是 `tpl`） |
| CSV 上传解析 | `POST /batch/upload/` | total_rows=2 / valid_rows=2 / errors=[] |
| XLSX 往返 | 下载 xlsx 模板再回传 | total_rows=3 / valid_rows=3 |
| 看板聚合 | `GET /dashboard/stats/` | 评分总数 2 / 通过率 100% / 绿1黄1红0 / 日均趋势 7 天有值 |
| 前端 6 页 | Playwright 逐页打开（1600×1000）+ 截图 | 6/6 正常渲染、零 error（仅 el-dialog `title` slot 的 3.0 弃用 warning） |
| 生产构建 | `npm run build` | ✓ built，产物含 BatchJudge/Dashboard/HistoryList/RubricList/SingleJudge/KnowledgeBase |

## 四、遗留（非阻塞）

- **评分标准预设为空**：`rubrics` 页显示「暂无数据」，`presets` 读 DB 所以「从预设克隆」暂时无内容。
  这是**上游行为**（开源版同样没有种子逻辑，3 个 YAML 仅作引擎兜底）。引擎侧不依赖它：
  单条/批量评分的标准选择器会显示「默认标准」，实际走 `judge_engine/rubric_templates/finance_rubric_v1.0.yaml`，功能可用。
  若要开箱即有可克隆模板，可加一条数据迁移把 3 个 YAML 灌入 `Rubric` 表。
- `knowledge` 页有 Element Plus `el-dialog title slot` 弃用 warning（3.0 才移除此 slot），与平台其他模块一致，不影响功能。
- 验证过程在开发库留下了 1 条评分记录 + 1 个批次（截图里的「移植验证批次」），可按需删除。

## 五、踩坑备忘

- 本机 `docker` 走 PATH 时会连 `127.0.0.1:2375` 失败，必须用完整路径
  `C:\Program Files\Docker\Docker\resources\bin\docker.exe`。
- backend 跑的是 **daphne（无自动重载）**，改 `settings.py`/`urls.py` 必须 `docker restart testhub_dev-backend-1`；
  新增 Celery 任务必须 `docker restart testhub_dev-worker-1`。
- Playwright 灌登录态**不能**用 `goto('/login') + evaluate(setItem)`：登录页启动时的 401 兜底会把
  localStorage 清空。必须用 `context.add_init_script()` 抢在应用 JS 之前注入（且该方法不接受参数数组，
  要把值 `json.dumps` 进脚本文本）。
- 前端改文件后若 dev server 未热更（挂载卷 inotify 不触发），`docker restart testhub_dev-frontend-1`。
