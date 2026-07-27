# TestHub 平台基线版本文档

## 📌 版本信息

- **版本号**: v1.0.0-baseline
- **基线日期**: 2025-01-21
- **Git Commit**: 94f7020（当前工作区含未提交改动时，以提交后最新 commit 为准）
- **Git 分支**: main
- **本次基线说明**: AI 用例生成流式输出、失败态与错误信息展示、async 上下文修复

#### 本次基线包含的变更（AI 用例生成流式输出）
- **后端**：`output_mode` 支持 `stream`/`complete`；流式时调用 OpenAI 兼容接口 `stream=True`，按 chunk 写入 `stream_buffer` 并更新 `stream_position`；SSE `stream_progress` 推送 `type: content/review_content/final_content`；失败时 SSE/进度接口带回 `error_message`；流式回调中用 `sync_to_async` 包装 `task.save()`，避免 “You cannot call this from an async context” 报错。
- **前端**：发起生成时传 `output_mode`；流式模式下始终展示「实时生成内容」区域（含字符数、占位「等待内容输出...」）；SSE 收到 `content` 累积到 `streamedContent` 并展示；收到 `status: failed` 或 `fetchFinalResult` 得到失败态时不再弹出「生成完成」，改为展示「测试用例生成失败」及后端 `error_message`。
- **配置**：任务创建时 `output_mode` 取自请求或 `GenerationConfig.default_output_mode`；序列化与视图已支持 `output_mode` 写入任务。

---

## 🏗️ 技术栈版本

### 后端技术栈
- **Python**: 3.11+
- **Django**: 4.2.7
- **Django REST Framework**: 3.14.0
- **数据库**: MySQL 8.0+ (PyMySQL 1.1.0)
- **JWT认证**: djangorestframework-simplejwt 5.5.1
- **API文档**: drf-spectacular 0.27.0
- **任务调度**: Celery 5.3.4, APScheduler (via croniter 6.0.0)
- **HTTP客户端**: httpx 0.28.1, requests 2.32.4

### 前端技术栈
- **Node.js**: 18+
- **Vue**: 3.3.4
- **Vite**: 4.4.5
- **Element Plus**: 2.3.9
- **Pinia**: 2.1.6
- **Vue Router**: 4.2.4
- **Axios**: 1.5.0
- **ECharts**: 5.4.3

### AI 相关依赖
- **browser-use**: 0.10.1 (AI浏览器自动化)
- **langchain-openai**: 1.1.6 (LLM集成框架)

### 自动化测试依赖
- **Playwright**: >=1.40.0
- **Selenium**: 4.15.2
- **webdriver-manager**: 4.0.1
- **Allure**: 2.15.0 (测试报告)

---

## 📦 核心功能模块

### 1. 用户管理模块 (`apps/users/`)
- 用户注册、登录、JWT认证
- 用户配置和权限管理
- 用户头像、部门、职位信息

### 2. 项目管理模块 (`apps/projects/`)
- 多项目支持
- 项目成员和角色管理（负责人、管理员、开发者、测试者、观察者）
- 项目环境配置

### 3. 测试用例管理模块 (`apps/testcases/`)
- 测试用例创建、编辑、版本控制
- 步骤化用例设计（前置条件、操作步骤、预期结果）
- 用例附件和评论
- 用例标签和分类

### 4. 用例评审模块 (`apps/reviews/`)
- 评审流程管理
- 评审模板和检查清单
- 评审意见记录（整体、用例、步骤多层级）
- 评审状态跟踪

### 5. 测试执行模块 (`apps/executions/`)
- 测试计划管理
- 测试执行记录
- 执行历史追踪

### 6. 测试套件模块 (`apps/testsuites/`)
- 测试套件创建和管理
- 用例批量执行

### 7. 版本管理模块 (`apps/versions/`)
- 版本规划和测试用例关联

### 8. 测试报告模块 (`apps/reports/`)
- 测试报告生成和查看
- Allure报告集成

### 9. AI需求分析模块 (`apps/requirement_analysis/`)
- 需求文档上传（PDF/Word/TXT）
- AI自动解析需求文档
- 业务需求提取
- 基于需求自动生成测试用例（**支持实时流式输出**：边生成边展示「实时生成内容」、字符数、流式/完整输出模式）
- AI模型配置管理
- 提示词配置管理
- 生成行为配置（默认输出模式、是否自动评审等）
- 任务流式进度 SSE：`/api/requirement-analysis/testcase-generation/<task_id>/stream_progress/`

**支持的AI模型**:
- DeepSeek
- 通义千问 (Qwen)
- 硅基流动 (SiliconFlow)
- 其他自定义模型

### 10. 智能助手模块 (`apps/assistant/`)
- Dify AI助手集成
- 多会话管理
- 聊天历史记录

### 11. API测试模块 (`apps/api_testing/`)
- API项目和集合管理
- HTTP/WebSocket请求管理
- 环境变量管理（全局和局部）
- 测试套件和自动化执行
- 请求历史和结果追踪
- 定时任务和通知（邮件/Webhook）
- Allure报告生成

### 12. UI自动化测试模块 (`apps/ui_automation/`)
- 元素库管理（多种定位策略：ID、XPath、CSS等）
- 页面对象模式（POM）
- 测试脚本编辑和执行
- 测试套件批量执行
- 多浏览器支持（Chrome/Firefox/Edge）
- 执行截图和视频录制
- 定时任务调度（Cron表达式、固定间隔、单次执行）
- **AI智能模式**:
  - 基于Browser-use框架的智能浏览器自动化
  - 支持文本模式（DOM解析）和视觉模式（截图识别）
  - 支持多种AI模型：OpenAI、Anthropic、Google Gemini、DeepSeek、硅基流动等

---

## ⚙️ 配置说明

### AI模型配置位置

#### 1. 需求分析模块AI模型配置
- **后端模型**: `apps/requirement_analysis/models.py` - `AIModelConfig`
- **前端页面**: `frontend/src/views/requirement-analysis/AIModelConfig.vue`
- **API路由**: `/api/requirement-analysis/api/ai-models/`
- **配置角色**:
  - `writer`: 测试用例编写专家
  - `reviewer`: 测试评审专家
  - `browser_use_text`: Browser Use文本模式

#### 2. UI自动化AI智能模式配置
- **后端视图**: `apps/ui_automation/views_config.py` - `AIIntelligentModeConfigViewSet`
- **前端页面**: `frontend/src/views/configuration/AIIntelligentModeConfig.vue`
- **API路由**: `/api/ui-automation/config/ai-mode/`
- **使用模型**: `AIModelConfig` (role='browser_use_text')

#### 3. 智能助手（Dify）配置
- **后端模型**: `apps/assistant/models.py` - `DifyConfig`
- **前端页面**: `frontend/src/views/configuration/DifyConfig.vue`

### 支持的AI模型提供商
- OpenAI (GPT-4, GPT-3.5)
- Azure OpenAI
- Anthropic (Claude)
- Google Gemini
- DeepSeek
- 硅基流动 (SiliconFlow)
- 通义千问 (Qwen)
- 其他自定义模型

### JWT安全配置
- **Access Token**: 30分钟有效期
- **Refresh Token**: 7天有效期
- **自动刷新**: Token过期前5分钟自动刷新
- **Token黑名单**: 登出时自动加入黑名单
- **请求队列**: Token刷新期间请求自动排队

### 数据库配置
- **数据库类型**: MySQL 8.0+
- **字符集**: utf8mb4
- **主要数据表**:
  - 用户相关: `users_user`, `user_profiles`
  - 项目管理: `projects`, `project_members`, `project_environments`
  - 测试用例: `testcases`, `testcase_steps`, `testcase_attachments`, `testcase_comments`
  - 用例评审: `testcase_reviews`, `review_assignments`, `review_comments`
  - 需求分析: `requirement_documents`, `requirement_analyses`, `business_requirements`, `generated_test_cases`, `ai_model_config`, `prompt_config`
  - API测试: `api_projects`, `api_collections`, `api_requests`, `api_environments`, `test_suites`, `request_history`
  - UI自动化: `ui_projects`, `ui_elements`, `ui_page_objects`, `ui_test_scripts`, `ui_test_cases`, `ui_test_suites`, `ui_test_executions`, `ai_cases`
  - JWT安全: `blacklisted_token`, `outstanding_token`

---

## 📁 项目结构

```
testhub_platform/
├── apps/                          # Django应用模块（12个核心模块）
│   ├── users/                     # 用户管理
│   ├── projects/                  # 项目管理
│   ├── testcases/                 # 测试用例管理
│   ├── testsuites/                # 测试套件管理
│   ├── executions/                # 测试执行管理
│   ├── reports/                   # 测试报告
│   ├── reviews/                   # 用例评审管理
│   ├── versions/                  # 版本管理
│   ├── requirement_analysis/      # AI需求分析
│   ├── assistant/                 # 智能助手
│   ├── api_testing/               # API测试
│   └── ui_automation/             # UI自动化测试
├── backend/                       # Django项目配置
│   ├── settings.py                # 项目设置
│   ├── urls.py                    # URL路由
│   └── middleware.py             # 中间件
├── frontend/                       # Vue3前端应用
│   ├── src/
│   │   ├── api/                   # API接口
│   │   ├── components/            # 公共组件
│   │   ├── views/                 # 页面视图
│   │   ├── stores/                 # Pinia状态管理
│   │   ├── router/                # 路由配置
│   │   └── utils/                 # 工具函数
│   └── package.json
├── media/                         # 媒体文件
├── logs/                          # 日志文件
├── allure/                        # Allure测试报告工具
├── requirements.txt               # Python依赖
└── manage.py                      # Django管理脚本
```

---

## 🔧 环境要求

- **Python**: 3.11+
- **Node.js**: 18+
- **MySQL**: 8.0+
- **Redis**: 用于Celery任务队列（可选）
- **浏览器驱动**: ChromeDriver / GeckoDriver (用于UI自动化)

---

## 📝 重要文件清单

### 配置文件
- `backend/settings.py` - Django主配置文件
- `requirements.txt` - Python依赖
- `frontend/package.json` - 前端依赖
- `.env` - 环境变量配置（需自行创建）

### 核心模型文件
- `apps/users/models.py` - 用户模型
- `apps/projects/models.py` - 项目模型
- `apps/testcases/models.py` - 测试用例模型
- `apps/requirement_analysis/models.py` - AI需求分析模型（含AIModelConfig）
- `apps/api_testing/models.py` - API测试模型
- `apps/ui_automation/models.py` - UI自动化模型

### API路由文件
- `backend/urls.py` - 主路由配置
- `apps/*/urls.py` - 各模块路由配置

### 前端核心文件
- `frontend/src/router/index.js` - 路由配置
- `frontend/src/stores/user.js` - 用户状态管理
- `frontend/src/utils/api.js` - API请求封装

---

## 🚀 部署说明

### 后端部署
1. 创建虚拟环境: `python -m venv venv`
2. 激活虚拟环境: `venv\Scripts\activate` (Windows)
3. 安装依赖: `pip install -r requirements.txt`
4. 配置环境变量: 创建`.env`文件
5. 初始化数据库: `python manage.py migrate`
6. 创建超级用户: `python manage.py createsuperuser`
7. 启动服务: `python manage.py runserver`

### 前端部署
1. 进入前端目录: `cd frontend`
2. 安装依赖: `npm install`
3. 开发模式: `npm run dev`
4. 生产构建: `npm run build`

---

## 📊 功能特性总结

### ✅ 已实现功能
- [x] 用户认证和权限管理（JWT双Token机制）
- [x] 项目管理和团队协作
- [x] 测试用例全生命周期管理
- [x] 用例评审流程
- [x] 测试执行和报告
- [x] AI需求分析和用例生成
- [x] AI智能助手（Dify集成）
- [x] API测试（HTTP/WebSocket）
- [x] UI自动化测试（Selenium/Playwright）
- [x] AI智能浏览器自动化（Browser-use）
- [x] 统一配置中心
- [x] 定时任务调度
- [x] 通知系统（邮件/Webhook）
- [x] Allure测试报告

### 🔄 待优化功能
- [ ] 性能优化和缓存机制
- [ ] 更多AI模型支持
- [ ] 测试数据管理
- [ ] 持续集成/持续部署（CI/CD）集成
- [ ] 移动端适配

---

## 📌 基线版本标记

此文档标记了TestHub平台的基线版本（v1.0.0-baseline），记录了：
- 当前代码状态
- 技术栈版本
- 功能模块清单
- 配置说明
- 项目结构

**基线用途**:
- 版本追溯和回滚参考
- 新功能开发基准
- 问题排查参考点
- 部署配置参考

---

**创建时间**: 2025-01-27  
**创建人**: 系统自动生成  
**Git Commit**: 7d0bfa3bce57abf87d869a74c22de300f090342c
