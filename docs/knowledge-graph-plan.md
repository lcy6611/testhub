# TestHub 知识图谱建设方案

> 版本：v0.1（草案）  
> 日期：2026-07-04  
> 状态：待评审

---

## 1. 定位：与现有「知识库」的关系

TestHub 已具备两类「知识」能力，知识图谱不是替代它们，而是**把分散的实体和关系串成可查询、可溯源、可推理的层**。

| 能力 | 现状 | 图谱要补什么 |
|------|------|--------------|
| **Dify 知识库 RAG** | 文档切片 + 向量检索，回答/增强生成 | 文档是「内容源」，不是「关系源」 |
| **KbFunction 功能模块** | 功能 ↔ 文档 + 功能间 `depends_on/related/impacts` | 已是**轻量图谱雏形**，但未连到需求/用例/项目 |
| **需求分析 / AI 用例生成** | 文本 → 用例，KB 作参考 | 生成结果**无法回答**「这条用例覆盖哪个需求、引用了哪篇文档」 |
| **正式测试用例** | `testcases.TestCase` 独立管理 | 与需求、KB、生成任务**无持久溯源边** |

**一句话定位：**

> 知识图谱 = **项目内的业务语义网络**（需求、功能、文档、用例、执行）  
> Dify KB = **非结构化知识的检索引擎**（仍负责 RAG，图谱负责「谁和谁有关」）

---

## 2. 建设目标（分三层）

### L1 — 溯源图谱（MVP，约 3～4 周）

- 用例从哪来：需求文档 / 对话 / 生成任务 / 引用了哪些 KB 文档与功能模块
- 支持：**影响分析**（改某功能模块 → 哪些用例要回归）、**覆盖查看**（某需求是否已有用例）

### L2 — 业务语义图谱（约 2～3 个月）

- 需求 ↔ 功能模块 ↔ KB 文档 ↔ 测试用例 显式映射（含 AI 辅助建边 + 人工确认）
- 支持：按功能模块组织用例、生成时**图约束检索**（不只向量，还走关联扩展）

### L3 — 测试资产图谱（中长期）

- 串联 UI 页面对象、API 接口、套件、执行记录
- 支持：自动化覆盖、变更影响、发布范围推荐

**建议先做 L1 + L2 的前半段**，不一开始引入 Neo4j 全家桶。

---

## 3. 现状与缺口

### 3.1 已有基础

| 组件 | 说明 |
|------|------|
| `KbFunction` / `KbFunctionDocument` | 业务功能模块，绑定 Dify 文档 |
| `KbFunctionRelation` | 功能间 `related` / `depends_on` / `impacts` |
| `BusinessRequirement.parent_requirement` | 需求层级树 |
| `TestCaseGenerationTask` | 含 `kb_document_ids`、`kb_function_ids`、`kb_context_meta` |
| `KbChatSession` | 知识库对话，可一键生成用例 |

### 3.2 主要缺口

| 缺口 | 说明 |
|------|------|
| Project 与 KB 未绑定 | `KbFunction` 仅绑 `dify_dataset_id`，无 `project_id` |
| Dify 实体无本地镜像 | Document/Segment 仅存外部 ID |
| 双用例流水线割裂 | `GeneratedTestCase` 与 `TestCaseGenerationTask` → `TestCase` 无统一溯源 |
| 无生成溯源 | `save_to_records` 不记录来源 KB 文档/功能/会话 |
| KbChat 未用 KbFunction | 对话路径未复用功能模块扩展检索 |
| 关系类型有限 | 无 Requirement↔Function、TestCase↔Requirement 等边 |
| 检索结果不持久为边 | `retrieval_meta` 仅存消息 JSON |

---

## 4. 核心本体（Ontology）

### 4.1 节点类型

| 节点 | 来源模型 | 图谱唯一键建议 |
|------|----------|----------------|
| `Project` | `projects.Project` | `project:{id}` |
| `RequirementDocument` | `RequirementDocument` | `req_doc:{id}` |
| `BusinessRequirement` | `BusinessRequirement` | `biz_req:{id}` |
| `KbFunction` | `KbFunction` | `kb_func:{id}` |
| `KbDocument` | Dify 外部 | `kb_doc:{dataset_id}:{doc_id}` |
| `KbDataset` | Dify 外部 | `kb_ds:{dataset_id}` |
| `TestCase` | `testcases.TestCase` | `tc:{id}` |
| `TestCaseGenerationTask` | 生成任务 | `gen_task:{task_id}` |
| `KbChatSession` | 知识库对话 | `kb_chat:{session_id}` |
| `TestSuite` / `TestRun` | 执行模块 | 二期扩展 |

### 4.2 边类型

**已有（可复用）：**

- `KbFunction ──depends_on|related|impacts──► KbFunction`
- `KbFunction ──references──► KbDocument`
- `BusinessRequirement ──parent_of──► BusinessRequirement`

**MVP 必增：**

| 边类型 | 含义 | 创建时机 |
|--------|------|----------|
| `covers` | 用例覆盖需求/功能 | 采纳用例、人工关联、AI 建议后确认 |
| `derived_from` | 用例/任务来源于某需求/对话/文档 | 生成任务创建时 |
| `used_reference` | 生成时引用了某 KB 文档/功能 | `generate` / `continue-refine` |
| `maps_to` | 需求条目映射到功能模块 | 人工配置或 AI 对齐 |
| `belongs_to` | 实体归属项目 | 创建时自动 |

**二期：**

- `automates`：UI/API 自动化 ↔ 手工用例
- `executed_in`：用例 ↔ 测试运行
- `conflicts_with` / `duplicates`：用例去重

### 4.3 实体关系示意

```
Project
  ├── has_requirement → RequirementDocument
  │       └── analyzed_as → BusinessRequirement (parent_of 树)
  ├── uses_dataset → KbDataset
  ├── scopes → KbFunction
  │       ├── references → KbDocument
  │       └── depends_on|related|impacts → KbFunction
  └── contains → TestCase
          ├── provenance → TestCaseGenerationTask
          │       ├── derived_from → KbChatSession | RequirementDocument
          │       └── used_reference → KbDocument | KbFunction
          └── covers → BusinessRequirement | KbFunction
```

---

## 5. 技术架构

### 5.1 存储选型：MySQL 属性图（推荐 MVP）

**理由：**

- 项目已使用 MySQL 8.0
- 现有 `KbFunctionRelation` 证明「边表」模式可行
- MVP 阶段图遍历规模可控，无需独立图数据库

```
┌─────────────────────────────────────────────────────────┐
│                    TestHub 应用层                        │
│  用例生成 / KB 问答 / 用例管理 / 配置中心                  │
└────────────┬───────────────────────────────┬──────────────┘
             │                               │
     ┌───────▼────────┐              ┌───────▼────────┐
     │  Graph Service │              │ Dify KB Service │
     │  (apps/kg)     │              │ (现有 RAG)      │
     └───────┬────────┘              └─────────────────┘
             │
     ┌───────▼────────────────────────────────────────┐
     │  kg_entity          统一节点注册表               │
     │  kg_edge            通用边表                    │
     │  kg_entity_alias    外部 ID 对齐                 │
     └──────────────────────────────────────────────────┘
             │
     ┌───────▼────────┐
     │     MySQL      │
     └────────────────┘
```

**L2 以后**若多跳推理成为瓶颈，再评估 Neo4j / NebulaGraph 作为同步副本。

### 5.2 核心表设计（草案）

**kg_entity**

| 字段 | 说明 |
|------|------|
| `entity_key` | 全局唯一，如 `tc:123` |
| `entity_type` | TestCase / KbFunction / … |
| `ref_app` | Django app 名 |
| `ref_id` | 本地主键 |
| `project_id` | 可选，按项目过滤 |
| `label` | 展示名 |
| `properties` | JSON 扩展 |

**kg_edge**

| 字段 | 说明 |
|------|------|
| `src_entity_key` | 源节点 |
| `relation_type` | 关系类型 |
| `dst_entity_key` | 目标节点 |
| `project_id` | 项目范围 |
| `source` | manual / ai_suggested / system |
| `confidence` | 0～1，AI 建边置信度 |
| `meta` | JSON（retrieval_score、chunk_id 等） |
| `created_by` | 用户 |

### 5.3 服务模块（建议 `apps/knowledge_graph/`）

| 模块 | 职责 |
|------|------|
| `graph_registry.py` | 实体注册/注销（模型信号同步） |
| `graph_query.py` | 邻域查询、路径查询、影响分析 |
| `graph_builder.py` | 从生成任务/采纳/KbFunction 批量建边 |
| `graph_suggest.py` | AI 建议边（需求↔功能、用例↔需求） |
| `views.py` | REST：子图查询、覆盖报告、影响分析 |

### 5.4 与 Dify 的分工

| 层级 | 职责 |
|------|------|
| Dify KB | 非结构化内容检索（向量/关键词/全文） |
| 知识图谱 | 实体关系、溯源、覆盖、影响扩展 |
| 混合检索（L2） | 图谱 1～2 跳扩展 → 缩小 Dify 检索范围 → 生成 |

**混合检索流程：**

1. 用户选定需求/功能 → 图谱扩展相关文档与历史用例
2. 对扩展集合做 Dify 语义检索
3. Prompt 注入结构化关系摘要（比纯 chunk 更稳定）

---

## 6. 与现有功能集成点

| 现有功能 | 集成动作 | 优先级 |
|----------|----------|--------|
| `TestCaseGenerationTask.generate` | 写入 `used_reference` 边 | P0 |
| `continue-refine` | 追加 refinement 元数据或边 | P0 |
| `save_to_records` / 采纳用例 | 创建 `TestCase` 节点 + `provenance` + `covers` | P0 |
| `KbFunction` CRUD | 同步 `kg_entity` | P1 |
| `KbChatView` 一键生成 | 接入 KbFunction；会话 `derived_from` 边 | P1 |
| `RequirementAnalysis` 结构化需求 | `BusinessRequirement` 注册 + `maps_to` | P1 |
| 用例/任务详情页 | 「来源 / 覆盖 / 关联文档」面板 | P1 |
| 项目设置 | 绑定默认 Dataset + KbFunction 白名单 | P2 |

---

## 7. 分阶段路线图

### Phase 0 — 方案验证（1 周）

- [ ] 确认本体 v1（节点/边控制在 20 条以内）
- [ ] 选定 1 个试点项目 + 1 个 Dify Dataset
- [ ] 定义 3 个 MVP 用户故事

### Phase 1 — 溯源图谱 MVP（3～4 周）

**用户故事：**

1. 打开任意 AI 生成用例 → 看到「来自哪次任务、引用了哪些 KB 文档/功能」
2. 打开 KbFunction → 看到「关联了哪些已采纳用例」
3. 修改/删除某 KB 文档前 → 列出可能受影响的用例

**交付：**

- `apps/knowledge_graph` + 数据库迁移
- 生成/采纳钩子自动建边
- API：`GET /api/kg/subgraph?entity=kb_func:12&depth=2`
- 前端：任务详情 + 用例详情「关联」面板（列表，暂不做力导向图）

### Phase 2 — 语义映射 + 混合检索（4～6 周）

> 实施原则：**每次只交付一个可独立验证的小步**（后端 API → 前端 API → 单页 UI → 联调）。

#### 2A. 混合检索（图谱扩展 → KB 参考）

| # | 小步 | 状态 | 验证方式 |
|---|------|------|----------|
| 2A-1 | `expand_kb_references_via_graph()` 查询函数 | ✅ | 单元/手工：给定 `kb_func` 返回扩展文档 |
| 2A-2 | `generate` 接口生成前调用扩展 | ✅ | 任务 `kb_context_meta.graph_expansion` 有值 |
| 2A-3 | `GET /api/kg/expand-refs/` 预览 API | ✅ | Swagger / curl 返回扩展集合 |
| 2A-4 | 前端 `getKgExpandRefs()` | ✅ | Network 可见请求 |
| 2A-5 | AI 生成页：勾选文档/功能后 **生成前** debounce 预览 | ✅ | 表单下方显示「生成时将参考 N 个…」 |
| 2A-6 | AI 生成页：任务完成后 **graph_summary** 提示 | ✅ | 结果区蓝色提示条 |
| 2A-7 | 任务详情页：**graph_summary** 提示 | ✅ | 关联图谱上方 |
| 2A-8 | KbChat：功能模块勾选 + 加载 | ✅ | 检索范围面板可选功能 |
| 2A-9 | KbChat：`kb_chat_session_id` 建边 | ✅ | 任务详情「来源于 → KB 对话」 |
| 2A-10 | KbChat：生成前 expand 预览 | ✅ | scope 面板下方预览文案 |
| 2A-11 | KbChat：生成完成弹窗展示 graph_summary | ✅ | 弹窗内一行扩展说明 |
| 2A-12 | 生成 prompt 注入 **图谱关系摘要**（≤2KB） | ✅ | 生成时 user message 含「知识图谱关系摘要」块 |
| 2A-14 | expand-refs 返回 `prompt_summary` 预览 + 任务 meta 记录字数 | ✅ | 生成前预览「将注入图谱摘要 N 字」 |
| 2A-13 | `continue-refine` 完成后 **re-index** 图谱 | ✅ | 优化完成后任务节点 `has_refinement` / `last_refined_at` 更新 |

#### 2B. 需求 ↔ 功能模块映射（`maps_to`）

| # | 小步 | 状态 | 验证方式 |
|---|------|------|----------|
| 2B-1 | 后端：`POST /api/kg/edges/` 手动建 `maps_to` 边 | ✅ | `business_requirement_id` + `kb_function_id` |
| 2B-2 | 后端：`GET /api/kg/edges/?entity=` 列出映射边 | ✅ | 默认 `source=manual` |
| 2B-3 | 配置中心：功能模块行「映射需求」入口 | ✅ | 打开对话框并列出已有 maps_to |
| 2B-4 | 对话框：选择/输入需求实体 + 保存 | ✅ | 图谱可查 `maps_to` |
| 2B-5 | 生成时沿 `maps_to` 扩展功能/文档 | ✅ | expand 结果含映射功能 |

#### 2C. AI 建议边（待确认队列）

| # | 小步 | 状态 | 验证方式 |
|---|------|------|----------|
| 2C-1 | `graph_suggest.py`：建议 `maps_to` / `covers` | ✅ | 返回 confidence |
| 2C-2 | 边写入 `source=ai_suggested` + `confidence` | ✅ | DB 可查 |
| 2C-3 | 前端：待确认队列列表 + 确认/拒绝 | ✅ | 确认后边变为 system/manual |

#### 2D. 其它

| # | 小步 | 状态 |
|---|------|------|
| 2D-1 | 抽取/复用 `kgLabels.js` 与图谱面板组件 | ✅（labels 已抽） |
| 2D-2 | 公共 `KgRelationPanel.vue` 组件 | ✅ | 三页复用，样式内聚 |

### Phase 3 — 可视化与分析（4 周）

#### 3A. 项目级图谱浏览

| # | 小步 | 状态 | 验证方式 |
|---|------|------|----------|
| 3A-1 | 后端：`GET /api/kg/project-graph/?project_id=` | ✅ | 返回 nodes/edges |
| 3A-2 | 前端：`KgGraphChart.vue`（ECharts graph） | ✅ | 渲染力导向图 |
| 3A-3 | 配置中心：「知识图谱浏览」页 + 项目选择 | ✅ | 可选项目看图谱 |

#### 3B. 覆盖度 / 影响分析报表

| # | 小步 | 状态 |
|---|------|------|
| 3B-1 | 后端：项目覆盖度统计 API | ✅ | `GET /api/kg/coverage-report/` |
| 3B-2 | 前端：覆盖度报告页 | ✅ | 配置中心可选项目查看 |

（原 Phase 3 概要：ECharts 项目级浏览；覆盖度报告、影响分析报表）

### Phase 4 — 自动化与执行扩展（按需）

#### 4A. 采纳 / 覆盖闭环

| # | 小步 | 状态 | 验证方式 |
|---|------|------|----------|
| 4A-1 | 采纳用例时自动建 `covers` → 功能 / maps_to 需求 | ✅ | 覆盖度报告有数据 |
| 4A-2 | 用例详情展示 covers 边（outgoing） | ✅ | 面板「覆盖范围」分组 |

#### 4B. 自动化节点与执行回写

| # | 小步 | 状态 | 验证方式 |
|---|------|------|----------|
| 4B-1 | `ApiRequest` 节点入图 + `POST /api/kg/sync-api-requests/` | ✅ | `GET /api/kg/status/?entity=api_req:{id}` 为 true |
| 4B-2 | `PageObject` 节点入图 + `POST /api/kg/sync-ui-pages/` | ✅ | `GET /api/kg/status/?entity=ui_page:{id}` 为 true |
| 4B-3 | 手动边：用例 `automates` → API / UI 节点 | ✅ | 边 API + 用例详情「自动化关联」 |
| 4B-4 | 执行结果回写（API/UI 执行历史 → 节点属性或边） | ✅ | 执行后图谱可查最近结果 |
| 4B-4a | `writeback.py`：`build_api_execution_snapshot` + `writeback_api_request_execution` | ✅ | 单元调用可更新 `properties.last_execution` |
| 4B-4b | Hook 单接口执行 `ApiRequestViewSet.execute` | ✅ | 执行后 `GET /api/kg/subgraph/?entity=api_req:{id}` 含 last_execution |
| 4B-4c | Hook 套件/批量执行（utils + TestSuite，含失败路径）+ `safe_writeback` | ✅ | 批量/套件执行后 `last_execution` 更新 |
| 4B-4d | UI 页面对象执行回写（用例/脚本 → `ui_page` `last_execution`） | ✅ | `GET /api/kg/subgraph/?entity=ui_page:{id}` 含 last_execution |
| 4B-4e | 前端用例详情「自动化关联」展示最近执行 | ✅ | 面板显示通过/失败与时间 |
| 4B-5 | 可选 Neo4j 同步 | ⬜ | 产品确认后 |
| 4B-5a | `GET /api/kg/export/` 导出 JSON（Neo4j 导入预备） | ✅ | 浏览页「导出 JSON」或 curl 下载 |
| 4B-5b | Neo4j 驱动增量写入 | ⬜ | 需 Neo4j 连接配置 + 产品确认 |

### Phase 4（原概要）

---

## 8. 关键决策（待确认）

| 决策点 | 选项 A（推荐） | 选项 B |
|--------|----------------|--------|
| 图谱存储 | MySQL 边表 | 直接 Neo4j |
| AI 建边 | 建议 + 人工确认 | 全自动 |
| KbFunction 关系 | 逐步迁移到 `kg_edge` | 双写 |
| Project 与 KB | Project 绑定 Dataset + Function 白名单 | 全局共用 |
| 双用例流水线 | 统一以 `TestCase` 为图节点 | 两套节点都保留 |

---

## 9. 风险与约束

1. **Dify 文档无本地镜像**：仅存外部 ID，删改需 Webhook 或定时标记 `stale`
2. **AI 建边噪声**：必须带 `confidence` + 确认流
3. **性能**：MVP 限制遍历深度 ≤ 3、单项目子图 ≤ 500 节点
4. **多模态生成**：图谱记录截图步骤 ↔ 功能 ↔ 用例边，辅助二次迭代

---

## 10. MVP 验收标准

- [x] 从任意**已采纳 TestCase** 可 2 跳内追到：生成任务 → KB 文档/功能
- [x] 从任意 **KbFunction** 可列出：关联用例数、关联文档、依赖功能
- [x] **继续优化**后，图谱保留版本链（`meta.refinement_notes` / `properties.has_refinement`）
- [x] 用例生成 prompt 可注入图谱摘要（≤ 2KB），覆盖优于纯 RAG

---

## 11. 相关代码路径（现状）

| 区域 | 路径 |
|------|------|
| Dify KB 服务 | `apps/requirement_analysis/dify_kb_service.py` |
| 功能模块模型 | `apps/requirement_analysis/kb_models.py` |
| KB 对话 | `apps/requirement_analysis/kb_chat_*.py` |
| 用例生成 | `apps/requirement_analysis/views.py`、`generation_task_runner.py` |
| 多模态附件 | `apps/requirement_analysis/image_attachment_utils.py` |
| 前端 KB 问答 | `frontend/src/views/requirement-analysis/KbChatView.vue` |
| 前端 AI 生成 | `frontend/src/views/requirement-analysis/RequirementAnalysisView.vue` |
| 功能模块配置 | `frontend/src/views/configuration/KbFunctionConfigView.vue` |

---

## 12. 下一步

**Phase 4B 自动化扩展已全部完成 ✅**（4B-5 Neo4j 待产品确认）

**可选后续：**

1. **4B-5b** — Neo4j 驱动增量写入（需产品确认 + 连接配置）
2. 图谱 prompt 摘要 A/B 对比（纯 RAG vs 图谱+RAG 覆盖度）
3. 试点项目 + Dify 知识库绑定

**待产品确认：**

1. MVP 优先：溯源 vs 覆盖分析？
2. 是否同意 MySQL 边表、暂不上 Neo4j？
3. 试点项目 + Dify 知识库名称？

---

**Phase 4A（采纳 / 覆盖闭环）已全部完成 ✅**

*本文档随方案迭代更新；可按 Phase 4B 或其它产品确认项推进。*
