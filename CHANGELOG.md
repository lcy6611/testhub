# 更新日志

所有重要的项目变更都会记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0-baseline] - 2025-01-27

### 📌 基线版本标记

这是TestHub智能测试管理平台的基线版本，用于版本追溯和后续开发参考。

### ✨ 核心功能

#### 用户与权限
- 用户注册、登录、JWT双Token认证机制
- 用户配置和权限管理
- Token自动刷新和黑名单机制

#### 项目管理
- 多项目支持
- 项目成员和角色管理（负责人、管理员、开发者、测试者、观察者）
- 项目环境配置

#### 测试用例管理
- 测试用例创建、编辑、版本控制
- 步骤化用例设计（前置条件、操作步骤、预期结果）
- 用例附件和评论
- 用例标签和分类

#### 用例评审
- 评审流程管理
- 评审模板和检查清单
- 评审意见记录（整体、用例、步骤多层级）
- 评审状态跟踪

#### 测试执行
- 测试计划管理
- 测试执行记录
- 执行历史追踪
- 测试报告生成

#### AI需求分析
- 需求文档上传（PDF/Word/TXT）
- AI自动解析需求文档
- 业务需求提取
- 基于需求自动生成测试用例
- AI模型配置管理（DeepSeek、通义千问、硅基流动等）
- 提示词配置管理

#### 智能助手
- Dify AI助手集成
- 多会话管理
- 聊天历史记录

#### API测试
- API项目和集合管理
- HTTP/WebSocket请求管理
- 环境变量管理（全局和局部）
- 测试套件和自动化执行
- 请求历史和结果追踪
- 定时任务和通知（邮件/Webhook）
- Allure报告生成

#### UI自动化测试
- 元素库管理（多种定位策略）
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

#### 统一配置中心
- 环境检测（系统浏览器和Playwright环境）
- 驱动管理（一键安装和更新浏览器驱动）
- AI模型配置（统一管理多种AI模型的API配置）
- 连接测试（支持AI模型连接测试和验证）

### 🔧 技术栈

#### 后端
- Django 4.2.7
- Django REST Framework 3.14.0
- MySQL 8.0+ (PyMySQL 1.1.0)
- JWT认证 (djangorestframework-simplejwt 5.5.1)
- Celery 5.3.4 (任务调度)
- Playwright >=1.40.0, Selenium 4.15.2
- browser-use 0.10.1 (AI浏览器自动化)

#### 前端
- Vue 3.3.4
- Vite 4.4.5
- Element Plus 2.3.9
- Pinia 2.1.6
- Vue Router 4.2.4
- Axios 1.5.0
- ECharts 5.4.3

### 📝 已知问题

- 前端构建文件（frontend/dist/）未纳入版本控制
- 部分配置文件（.env）包含敏感信息，需单独管理

### 🔄 后续计划

- 性能优化和缓存机制
- 更多AI模型支持
- 测试数据管理
- CI/CD集成
- 移动端适配

---

[1.0.0-baseline]: https://github.com/your-repo/testhub_platform/tree/7d0bfa3bce57abf87d869a74c22de300f090342c
