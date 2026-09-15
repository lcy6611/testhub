import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

// 静态导入常用组件来避免动态导入问题
import Login from '@/views/auth/Login.vue'
import Register from '@/views/auth/Register.vue'
import Layout from '@/layout/index.vue'
import ProjectList from '@/views/projects/ProjectList.vue'

const routes = [
  {
    path: '/',
    redirect: '/home'
  },
  {
    path: '/home',
    name: 'Home',
    component: () => import('@/views/Home.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresGuest: true }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { requiresGuest: true }
  },
  {
    path: '/ai-generation/assistant',
    name: 'Assistant',
    component: () => import('@/views/assistant/AssistantView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ai-generation/agent',
    redirect: '/hermes'
  },
  {
    path: '/ai-generation',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: 'requirement-analysis'
      },
      {
        path: 'requirement-analysis',
        name: 'RequirementAnalysis',
        component: () => import('@/views/requirement-analysis/RequirementAnalysisView.vue')
      },
      {
        path: 'kb-chat',
        name: 'KbChat',
        component: () => import('@/views/requirement-analysis/KbChatView.vue')
      },
      {
        path: 'projects',
        name: 'Projects',
        component: ProjectList
      },
      {
        path: 'projects/:id',
        name: 'ProjectDetail',
        component: () => import('@/views/projects/ProjectDetail.vue')
      },
      {
        path: 'testcases',
        name: 'TestCases',
        component: () => import('@/views/testcases/TestCaseList.vue')
      },
      {
        path: 'testcases/create',
        name: 'CreateTestCase',
        component: () => import('@/views/testcases/TestCaseForm.vue')
      },
      {
        path: 'testcases/:id',
        name: 'TestCaseDetail',
        component: () => import('@/views/testcases/TestCaseDetail.vue')
      },
      {
        path: 'testcases/:id/edit',
        name: 'EditTestCase',
        component: () => import('@/views/testcases/TestCaseEdit.vue')
      },
      {
        path: 'versions',
        name: 'Versions',
        component: () => import('@/views/versions/VersionList.vue')
      },
      {
        path: 'reviews',
        name: 'Reviews',
        component: () => import('@/views/reviews/ReviewList.vue')
      },
      {
        path: 'reviews/create',
        name: 'CreateReview',
        component: () => import('@/views/reviews/ReviewForm.vue')
      },
      {
        path: 'reviews/:id',
        name: 'ReviewDetail',
        component: () => import('@/views/reviews/ReviewDetail.vue')
      },
      {
        path: 'reviews/:id/edit',
        name: 'EditReview',
        component: () => import('@/views/reviews/ReviewForm.vue')
      },
      {
        path: 'review-templates',
        name: 'ReviewTemplates',
        component: () => import('@/views/reviews/ReviewTemplateList.vue')
      },
      {
        path: 'testsuites',
        name: 'TestSuites',
        component: () => import('@/views/testsuites/TestSuiteList.vue')
      },
      {
        path: 'executions',
        name: 'Executions',
        component: () => import('@/views/executions/ExecutionListView.vue')
      },
      {
        path: 'executions/:id',
        name: 'ExecutionDetail',
        component: () => import('@/views/executions/ExecutionDetailView.vue')
      },
      {
        path: 'reports',
        name: 'AiTestReport',
        component: () => import('@/views/reports/AiTestReport.vue')
      },

          {
            path: 'prompt-config',
            name: 'PromptConfig',
            component: () => import('@/views/requirement-analysis/PromptConfig.vue')
          },
          {
            path: 'skill-config',
            name: 'SkillConfig',
            component: () => import('@/views/requirement-analysis/SkillConfig.vue')
          },
      {
        path: 'generated-testcases',
        name: 'GeneratedTestCases',
        component: () => import('@/views/requirement-analysis/GeneratedTestCaseList.vue')
      },
      {
        path: 'task-detail/:taskId',
        name: 'TaskDetail',
        component: () => import('@/views/requirement-analysis/TaskDetail.vue')
      },
      {
        path: 'kg-browse',
        name: 'KnowledgeGraphBrowse',
        component: () => import('@/views/configuration/KnowledgeGraphBrowseView.vue')
      },
      {
        path: 'kg-coverage',
        name: 'KnowledgeGraphCoverage',
        component: () => import('@/views/configuration/KnowledgeGraphCoverageView.vue')
      },
      {
        path: 'kb-functions',
        name: 'KbFunctionConfig',
        component: () => import('@/views/configuration/KbFunctionConfigView.vue')
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/UserProfile.vue')
      }
    ]
  },
  {
    path: '/hermes',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'HermesChat',
        component: () => import('@/views/assistant/HermesChatView.vue')
      }
    ]
  },
  {
    path: '/api-testing',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: 'dashboard'
      },
      {
        path: 'dashboard',
        name: 'ApiDashboard',
        component: () => import('@/views/api-testing/Dashboard.vue')
      },
      {
        path: 'projects',
        name: 'ApiProjects',
        component: () => import('@/views/api-testing/ProjectManagement.vue')
      },
      {
        path: 'interfaces',
        name: 'ApiInterfaces',
        component: () => import('@/views/api-testing/InterfaceManagement.vue')
      },
      {
        path: 'automation',
        name: 'ApiAutomation',
        component: () => import('@/views/api-testing/AutomationTesting.vue')
      },
      {
        path: 'history',
        name: 'ApiHistory',
        component: () => import('@/views/api-testing/RequestHistory.vue')
      },
      {
        path: 'environments',
        name: 'ApiEnvironments',
        component: () => import('@/views/api-testing/EnvironmentManagement.vue')
      },
      {
        path: 'reports',
        name: 'ApiReports',
        component: () => import('@/views/api-testing/ReportView.vue')
      },
      {
        path: 'scheduled-tasks',
        name: 'ApiScheduledTasks',
        component: () => import('@/views/api-testing/ScheduledTasks.vue')
      },
      {
        path: 'ai-generate',
        name: 'ApiAiGenerate',
        component: () => import('@/views/api-testing/AiGenerate.vue')
      },
      {
        path: 'notification-logs',
        name: 'ApiNotificationLogs',
        component: () => import('@/views/notification/NotificationLogs.vue')
      }
    ]
  },
  {
    path: '/data-factory',
    name: 'DataFactory',
    component: () => import('@/views/data-factory/DataFactory.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ui-automation',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: 'dashboard'
      },
      {
        path: 'dashboard',
        name: 'UiDashboard',
        component: () => import('@/views/ui-automation/dashboard/Dashboard.vue')
      },
      {
        path: 'projects',
        name: 'UiProjects',
        component: () => import('@/views/ui-automation/projects/ProjectList.vue')
      },
      {
        path: 'elements-enhanced',
        name: 'UiElementsEnhanced',
        component: () => import('@/views/ui-automation/elements/ElementManagerEnhanced.vue')
      },
      {
        path: 'test-cases',
        name: 'UiTestCases',
        component: () => import('@/views/ui-automation/test-cases/TestCaseManager.vue')
      },
      {
        path: 'scripts-enhanced',
        name: 'UiScriptsEnhanced',
        component: () => import('@/views/ui-automation/scripts/ScriptEditorEnhanced.vue')
      },
      {
        path: 'scripts',
        name: 'UiScripts',
        component: () => import('@/views/ui-automation/scripts/ScriptList.vue')
      },
      {
        path: 'suites',
        name: 'UiSuites',
        component: () => import('@/views/ui-automation/suites/SuiteList.vue')
      },
      {
        path: 'executions',
        name: 'UiExecutions',
        component: () => import('@/views/ui-automation/executions/ExecutionList.vue')
      },
      {
        path: 'reports',
        name: 'UiReports',
        component: () => import('@/views/ui-automation/reports/ReportList.vue')
      },
      {
        path: 'scheduled-tasks',
        name: 'UiScheduledTasks',
        component: () => import('@/views/ui-automation/scheduled-tasks/ScheduledTasks.vue')
      },
      {
        path: 'notification-logs',
        name: 'UiNotificationLogs',
        component: () => import('@/views/ui-automation/notification/NotificationLogs.vue')
      },
      {
        path: 'ai-generate',
        name: 'UiAiGenerate',
        component: () => import('@/views/ui-automation/AiGenerate.vue')
      },
      {
        path: 'generate-from-case',
        name: 'UiGenerateFromCase',
        component: () => import('@/views/ui-automation/CaseScriptGenerator.vue')
      },
      {
        path: 'generate-records',
        name: 'UiGenerateRecords',
        component: () => import('@/views/ui-automation/CaseScriptRecords.vue')
      },
      {
        path: 'generate-result/:id',
        name: 'UiGenerateResult',
        component: () => import('@/views/ui-automation/CaseScriptResult.vue')
      }
    ]
  },
  {
    path: '/data-factory',
    name: 'DataFactory',
    component: () => import('@/views/data-factory/DataFactory.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/defects',
    name: 'DefectList',
    component: () => import('@/views/defects/DefectListView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/defects/kanban',
    name: 'DefectKanban',
    component: () => import('@/views/defects/DefectKanbanView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/defects/stats',
    name: 'DefectStats',
    component: () => import('@/views/defects/DefectStatsView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/defects/:id',
    name: 'DefectDetail',
    component: () => import('@/views/defects/DefectDetailView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/ai-intelligent-mode',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: 'testing'
      },
      {
        path: 'testing',
        name: 'AITesting',
        component: () => import('@/views/ui-automation/ai/AITesting.vue')
      },
      {
        path: 'projects',
        name: 'AIProjectList',
        component: () => import('@/views/ui-automation/ai/AIProjectList.vue')
      },
      {
        path: 'cases',
        name: 'AICaseList',
        component: () => import('@/views/ui-automation/ai/AICaseList.vue')
      },
      {
        path: 'suites',
        name: 'AISuiteList',
        component: () => import('@/views/ui-automation/ai/AISuiteList.vue')
      },
      {
        path: 'execution-records',
        name: 'AIExecutionRecords',
        component: () => import('@/views/ui-automation/ai/AIExecutionRecords.vue')
      },
      {
        path: 'reports',
        name: 'AIReports',
        component: () => import('@/views/ui-automation/ai/AIReportList.vue')
      },
      {
        path: 'scheduled-tasks',
        name: 'AIScheduledTasks',
        component: () => import('@/views/ui-automation/ai/AIScheduledTasks.vue')
      },
      {
        path: 'notification-logs',
        name: 'AINotificationLogs',
        component: () => import('@/views/ui-automation/ai/AINotificationLogs.vue')
      },
      {
        path: 'ai-generate',
        name: 'AIAiGenerate',
        component: () => import('@/views/ui-automation/ai/AiGenerate.vue')
      }
    ]
  },
  {
    path: '/data-factory',
    name: 'DataFactory',
    component: () => import('@/views/data-factory/DataFactory.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/configuration',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        component: () => import('@/views/configuration/ConfigurationCenter.vue'),
        children: [
          {
            path: '',
            redirect: 'ai-model'
          },
          {
            path: 'ai-model',
            name: 'ConfigAIModel',
            component: () => import('@/views/requirement-analysis/AIModelConfig.vue')
          },
          {
            path: 'generation-config',
            name: 'ConfigGenerationConfig',
            component: () => import('@/views/requirement-analysis/GenerationConfigView.vue')
          },
          {
            path: 'ui-env',
            name: 'ConfigUIEnv',
            component: () => import('@/views/configuration/UIEnvironmentConfig.vue')
          },
          {
            path: 'ai-mode',
            name: 'ConfigAIMode',
            component: () => import('@/views/configuration/AIIntelligentModeConfig.vue')
          },
          {
            path: 'scheduled-task',
            name: 'ConfigScheduledTask',
            component: () => import('@/views/ui-automation/notification/NotificationConfigs.vue')
          },
          {
            path: 'dify',
            name: 'DifyConfig',
            component: () => import('@/views/configuration/DifyConfig.vue')
          },
          {
            // 2026-07-24 v3.1：知识中枢已下沉为配置中心的二级折叠子菜单，路径前缀改为 /configuration/knowledge-hub
            // 兼容历史链接：旧的 /configuration/kb-hub /knowledge-library /knowledge-hub 都重定向到新 home
            path: 'kb-hub',
            redirect: '/configuration/knowledge-hub/config'
          },
          {
            path: 'knowledge-library',
            redirect: '/configuration/knowledge-hub/kbs'
          },
          {
            path: 'knowledge-hub',
            redirect: '/configuration/knowledge-hub/home'
          },
          {
            path: 'performance-testing',
            name: 'ConfigPerformanceTesting',
            component: () => import('@/views/configuration/PerformanceTestingConfig.vue')
          },
          {
            path: 'skill-config',
            name: 'ConfigSkillConfig',
            component: () => import('@/views/requirement-analysis/SkillConfig.vue')
          },
          {
            path: 'hermes-config',
            name: 'ConfigHermes',
            component: () => import('@/views/configuration/HermesConfig.vue')
          }
        ]
      },
      {
        path: 'appearance',
        name: 'Appearance',
        component: () => import('@/views/configuration/AppearanceSettings.vue'),
        meta: { requiresAuth: true }
      },
      {
        // 2026-07-24 项目概览：按 project_id 聚合全平台数据（KB/需求/用例/图谱/自动化/性能）
        path: 'project-overview',
        name: 'ProjectOverview',
        component: () => import('@/views/configuration/ProjectOverviewView.vue'),
        meta: { requiresAuth: true, title: '项目概览' }
      }
    ]
  },
  // ====== 知识中枢（2026-07-24 v3.1：下沉为配置中心的二级折叠子菜单，平级兄弟路由避免双层 padding） ======
  {
    path: '/configuration/knowledge-hub',
    component: Layout,
    meta: { requiresAuth: true, title: '知识中枢' },
    children: [
      {
        path: '',
        redirect: 'home'
      },
      {
        path: 'home',
        name: 'KnowledgeHubHome',
        component: () => import('@/views/knowledge-hub/KnowledgeHubHomeView.vue')
      },
      {
        path: 'kbs',
        name: 'KnowledgeHubLibrary',
        component: () => import('@/views/knowledge-hub/KnowledgeLibraryView.vue')
      },
      {
        path: 'documents',
        name: 'KnowledgeHubDocuments',
        component: () => import('@/views/knowledge-hub/KnowledgeDocumentsView.vue')
      },
      {
        path: 'qa',
        name: 'KnowledgeHubQa',
        component: () => import('@/views/knowledge-hub/KnowledgeQaView.vue')
      },
      {
        path: 'config',
        name: 'KnowledgeHubConfig',
        component: () => import('@/views/knowledge-hub/KnowledgeHubConfigView.vue')
      },
      {
        path: 'manual',
        name: 'KnowledgeHubManual',
        component: () => import('@/views/knowledge-hub/KnowledgeManualView.vue')
      }
    ]
  },
  // APP自动化测试路由
  {
    path: '/app-automation',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: 'dashboard'
      },
      {
        path: 'dashboard',
        name: 'AppAutomationDashboard',
        component: () => import('@/views/app-automation/dashboard/Dashboard.vue')
      },
      {
        path: 'projects',
        name: 'AppProjectList',
        component: () => import('@/views/app-automation/projects/ProjectList.vue')
      },
      {
        path: 'devices',
        name: 'AppDeviceList',
        component: () => import('@/views/app-automation/devices/DeviceList.vue')
      },
      {
        path: 'packages',
        name: 'AppPackageList',
        component: () => import('@/views/app-automation/packages/PackageList.vue')
      },
      {
        path: 'elements',
        name: 'AppElementList',
        component: () => import('@/views/app-automation/elements/ElementList.vue')
      },
      {
        path: 'scene-builder',
        name: 'AppSceneBuilder',
        component: () => import('@/views/app-automation/test-cases/SceneBuilder.vue'),
        meta: { title: '用例编排' }
      },
      {
        path: 'test-cases',
        name: 'AppTestCaseList',
        component: () => import('@/views/app-automation/test-cases/TestCaseList.vue')
      },
      {
        path: 'test-suites',
        name: 'AppTestSuiteList',
        component: () => import('@/views/app-automation/suites/SuiteList.vue')
      },
      {
        path: 'scheduled-tasks',
        name: 'AppScheduledTasks',
        component: () => import('@/views/app-automation/scheduled-tasks/ScheduledTasks.vue')
      },
      {
        path: 'notification-logs',
        name: 'AppNotificationLogs',
        component: () => import('@/views/app-automation/notification/NotificationLogs.vue')
      },
      {
        path: 'executions',
        name: 'AppExecutionList',
        component: () => import('@/views/app-automation/executions/ExecutionList.vue')
      },
      {
        path: 'reports',
        name: 'AppReportList',
        component: () => import('@/views/app-automation/reports/ReportList.vue')
      },
      {
        path: 'ai-generate',
        name: 'AppAiGenerate',
        component: () => import('@/views/app-automation/AiGenerate.vue')
      }
    ]
  },
  // 性能测试路由
  {
    path: '/performance-testing',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: 'dashboard'
      },
      {
        path: 'dashboard',
        name: 'PerfDashboard',
        component: () => import('@/views/performance/Dashboard.vue')
      },
      {
        path: 'dashboard/:id',
        name: 'PerfDashboardDetail',
        component: () => import('@/views/performance/DashboardDetail.vue')
      },
      {
        path: 'projects',
        name: 'PerfProjects',
        component: () => import('@/views/performance/ProjectManagement.vue')
      },
      {
        path: 'scripts',
        name: 'PerfScriptEditor',
        component: () => import('@/views/performance/ScriptEditor.vue')
      },
      {
        path: 'scripts/create',
        name: 'PerfScriptCreate',
        component: () => import('@/views/performance/ScriptEditor.vue')
      },
      {
        path: 'scripts/:id',
        name: 'PerfScriptEdit',
        component: () => import('@/views/performance/ScriptEditor.vue')
      },
      {
        path: 'executions',
        name: 'PerfExecutions',
        component: () => import('@/views/performance/ExecutionList.vue')
      },
      {
        path: 'executions/:id',
        name: 'PerfExecutionDetail',
        component: () => import('@/views/performance/ExecutionDetail.vue')
      },
      {
        path: 'batch-executions/:id',
        name: 'PerfBatchExecutionDetail',
        component: () => import('@/views/performance/BatchExecutionDetail.vue')
      },
      {
        path: 'reports',
        name: 'PerfReports',
        component: () => import('@/views/performance/ReportManagement.vue')
      },
      {
        path: 'scheduled-tasks',
        name: 'PerfScheduledTasks',
        component: () => import('@/views/performance/ScheduledTasks.vue')
      },
      {
        path: 'ai-generate',
        name: 'PerfAiGenerate',
        component: () => import('@/views/performance/AiGenerate.vue')
      }
    ]
  },
  // 运维工具路由
  {
    path: '/ops-tools',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: 'text2sql'
      },
      {
        path: 'text2sql',
        name: 'OpsText2SQL',
        component: () => import('@/views/ops-tools/Text2SQL.vue')
      },
      {
        path: 'logs',
        name: 'OpsLogQuery',
        component: () => import('@/views/ops-tools/LogQuery.vue')
      },
      {
        path: 'environments',
        name: 'OpsEnvironments',
        component: () => import('@/views/ops-tools/EnvironmentManager.vue')
      },
      {
        path: 'files',
        name: 'OpsFileTransfer',
        component: () => import('@/views/ops-tools/FileTransfer.vue')
      }
    ]
  },
  // AI 评测与反馈闭环
  {
    path: '/ai-eval',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: 'dashboard' },
      {
        path: 'dashboard',
        name: 'AIEval',
        component: () => import('@/views/ai-eval/AIEvalCenter.vue')
      }
    ]
  },
  // 文档中心（扫描磁盘 Markdown，纯文件驱动）
  {
    path: '/docs',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'DocCenter',
        component: () => import('@/views/docs/DocCenterView.vue'),
        meta: { requiresAuth: true, title: '文档中心' }
      }
    ]
  },
  // 监控中心（探测 + 告警 + 通知渠道，后端 /api/monitor/，定期由 Django-Q2 调度）
  {
    path: '/monitor',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: 'dashboard' },
      {
        path: 'dashboard',
        name: 'MonitorDashboard',
        component: () => import('@/views/monitor/Dashboard.vue'),
        meta: { requiresAuth: true, title: '监控看板' }
      },
      {
        path: 'targets',
        name: 'MonitorTargets',
        component: () => import('@/views/monitor/MonitorTargets.vue'),
        meta: { requiresAuth: true, title: '监控目标' }
      },
      {
        path: 'checks',
        name: 'MonitorChecks',
        component: () => import('@/views/monitor/CheckLogs.vue'),
        meta: { requiresAuth: true, title: '探测历史' }
      },
      {
        path: 'alerts',
        name: 'MonitorAlerts',
        component: () => import('@/views/monitor/Alerts.vue'),
        meta: { requiresAuth: true, title: '告警记录' }
      },
      {
        path: 'channels',
        name: 'MonitorChannels',
        component: () => import('@/views/monitor/NotificationChannels.vue'),
        meta: { requiresAuth: true, title: '通知渠道' }
      }
    ]
  },
  // MCP 控制台（工具目录 + 危险操作审批闸 + 调用日志 + 连接配置），后端 /api/mcp/
  {
    path: '/mcp',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: 'console' },
      {
        path: 'console',
        name: 'McpConsole',
        component: () => import('@/views/mcp/McpConsole.vue'),
        meta: { requiresAuth: true, title: 'MCP 控制台' }
      }
    ]
  },
  // 缺陷管理(开源对比)：照搬开源 defects，独立 app_label / defects_oss_* 表，后端 /api/defects-oss/
  {
    path: '/defects_oss',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: 'dashboard' },
      { path: 'dashboard', name: 'DefectsOssDashboard', component: () => import('@/views/defects_oss/DefectDashboard.vue'), meta: { requiresAuth: true, title: '缺陷看板' } },
      { path: 'list', name: 'DefectsOssList', component: () => import('@/views/defects_oss/DefectList.vue'), meta: { requiresAuth: true, title: '缺陷列表' } },
      { path: 'create', name: 'DefectsOssCreate', component: () => import('@/views/defects_oss/DefectForm.vue'), meta: { requiresAuth: true, title: '新建缺陷' } },
      { path: 'reports', name: 'DefectsOssReport', component: () => import('@/views/defects_oss/DefectReport.vue'), meta: { requiresAuth: true, title: '缺陷报表' } },
      { path: ':id', name: 'DefectsOssDetail', component: () => import('@/views/defects_oss/DefectDetail.vue'), meta: { requiresAuth: true, title: '缺陷详情' } },
      { path: ':id/edit', name: 'DefectsOssEdit', component: () => import('@/views/defects_oss/DefectForm.vue'), meta: { requiresAuth: true, title: '编辑缺陷' } }
    ]
  },
  // ====== 知识中枢（2026-07-24 v3.1：下沉为配置中心的二级折叠子菜单）======
  // 顶层只保留一条旧链接兜底 redirect，所有子路由挂在 /configuration/knowledge-hub 下
  {
    path: '/knowledge-hub',
    redirect: '/configuration/knowledge-hub/home'
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  console.log('路由守卫:', {
    to: to.path,
    from: from.path,
    hasToken: !!userStore.token,
    hasUser: !!userStore.user,
    isAuthenticated: userStore.isAuthenticated
  })

  // 只在应用初始化或从登录页面导航时初始化认证
  // 修复：字段名是 accessToken，旧的 userStore.token 始终是 undefined 导致 initAuth 从不触发
  if (!userStore.user && userStore.accessToken) {
    try {
      console.log('初始化认证...')
      await userStore.initAuth()
      console.log('认证初始化完成:', {
        hasUser: !!userStore.user,
        isAuthenticated: userStore.isAuthenticated
      })
    } catch (error) {
      console.error('认证初始化失败:', error)
    }
  }

  if (to.meta.requiresAuth && !userStore.isAuthenticated) {
    console.log('需要认证但未认证，跳转到登录页')
    next('/login')
  } else if (to.meta.requiresGuest && userStore.isAuthenticated) {
    console.log('访客页面但已认证，跳转到项目页')
    next('/home')
  } else {
    console.log('路由守卫通过，继续导航')
    next()
  }
})

router.afterEach((to, from) => {
  console.log(`Navigated from ${from.path} to ${to.path}`)
})

export default router