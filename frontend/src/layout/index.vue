<template>
  <div class="layout">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside width="240px">
        <div class="logo" @click="router.push('/home')" style="cursor: pointer;">
          <h2>TestHub</h2>
        </div>

        <el-menu
          :default-active="$route.path"
          router
        >
          <!-- Hermes 数字人 -->
          <template v-if="currentModule === 'hermes'">
            <el-menu-item index="/hermes">
              <el-icon><Cpu /></el-icon>
              <span>Hermes 数字人</span>
            </el-menu-item>
          </template>

          <!-- AI用例生成模块菜单 -->
          <template v-if="currentModule === 'ai-generation'">
            <el-sub-menu index="requirement">
              <template #title>
                <el-icon><MagicStick /></el-icon>
                <span>智能用例生成</span>
              </template>
              <el-menu-item index="/ai-generation/requirement-analysis">AI用例生成</el-menu-item>
              <el-menu-item index="/ai-generation/kb-chat">知识库问答</el-menu-item>
              <el-menu-item index="/ai-generation/generated-testcases">AI生成用例记录</el-menu-item>
              <el-menu-item index="/ai-generation/prompt-config">提示词配置</el-menu-item>
            </el-sub-menu>
            <el-sub-menu index="kg">
              <template #title>
                <el-icon><Share /></el-icon>
                <span>知识图谱</span>
              </template>
              <el-menu-item index="/ai-generation/kg-browse">图谱浏览</el-menu-item>
              <el-menu-item index="/ai-generation/kg-coverage">覆盖度报告</el-menu-item>
              <el-menu-item index="/ai-generation/kb-functions">功能模块配置</el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/ai-generation/projects">
              <el-icon><Folder /></el-icon>
              <span>项目管理</span>
            </el-menu-item>
            <el-menu-item index="/ai-generation/testcases">
              <el-icon><Document /></el-icon>
              <span>测试用例</span>
            </el-menu-item>
            <el-menu-item index="/ai-generation/versions">
              <el-icon><Flag /></el-icon>
              <span>版本管理</span>
            </el-menu-item>
            <el-sub-menu index="reviews">
              <template #title>
                <el-icon><Check /></el-icon>
                <span>评审管理</span>
              </template>
              <el-menu-item index="/ai-generation/reviews">评审列表</el-menu-item>
              <el-menu-item index="/ai-generation/review-templates">评审模板</el-menu-item>
            </el-sub-menu>

            <el-menu-item index="/ai-generation/executions">
              <el-icon><VideoPlay /></el-icon>
              <span>测试计划</span>
            </el-menu-item>
            <el-menu-item index="/ai-generation/reports">
              <el-icon><DataAnalysis /></el-icon>
              <span>测试报告</span>
            </el-menu-item>
          </template>

          <!-- 接口测试模块菜单 -->
          <template v-else-if="currentModule === 'api-testing'">
            <el-menu-item index="/api-testing/dashboard">
              <el-icon><Odometer /></el-icon>
              <span>数据看板</span>
            </el-menu-item>
            <el-menu-item index="/api-testing/projects">
              <el-icon><Folder /></el-icon>
              <span>项目管理</span>
            </el-menu-item>
            <el-menu-item index="/api-testing/interfaces">
              <el-icon><Link /></el-icon>
              <span>接口管理</span>
            </el-menu-item>
            <el-menu-item index="/api-testing/automation">
              <el-icon><VideoPlay /></el-icon>
              <span>自动化测试</span>
            </el-menu-item>
            <el-menu-item index="/api-testing/history">
              <el-icon><Timer /></el-icon>
              <span>请求历史</span>
            </el-menu-item>
            <el-menu-item index="/api-testing/environments">
              <el-icon><Setting /></el-icon>
              <span>环境管理</span>
            </el-menu-item>
            <el-menu-item index="/api-testing/reports">
              <el-icon><DataAnalysis /></el-icon>
              <span>测试报告</span>
            </el-menu-item>
            <el-menu-item index="/api-testing/scheduled-tasks">
              <el-icon><AlarmClock /></el-icon>
              <span>定时任务</span>
            </el-menu-item>
            <el-menu-item index="/api-testing/notification-logs">
              <el-icon><Bell /></el-icon>
              <span>通知列表</span>
            </el-menu-item>
          </template>

          <!-- UI自动化测试模块菜单 -->
          <template v-else-if="currentModule === 'ui-automation'">
            <el-menu-item index="/ui-automation/dashboard">
              <el-icon><Odometer /></el-icon>
              <span>数据看板</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/projects">
              <el-icon><Folder /></el-icon>
              <span>项目管理</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/elements-enhanced">
              <el-icon><Aim /></el-icon>
              <span>元素管理</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/test-cases">
              <el-icon><Document /></el-icon>
              <span>用例管理</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/scripts-enhanced">
              <el-icon><Edit /></el-icon>
              <span>脚本生成</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/scripts">
              <el-icon><DocumentCopy /></el-icon>
              <span>脚本列表</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/suites">
              <el-icon><Collection /></el-icon>
              <span>套件管理</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/executions">
              <el-icon><VideoPlay /></el-icon>
              <span>执行记录</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/reports">
              <el-icon><DataAnalysis /></el-icon>
              <span>测试报告</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/scheduled-tasks">
              <el-icon><AlarmClock /></el-icon>
              <span>定时任务</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/notification-logs">
              <el-icon><Bell /></el-icon>
              <span>通知列表</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/ai-generate">
              <el-icon><MagicStick /></el-icon>
              <span>AI 生成</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/generate-from-case">
              <el-icon><MagicStick /></el-icon>
              <span>用例生成UI脚本</span>
            </el-menu-item>
            <el-menu-item index="/ui-automation/generate-records">
              <el-icon><DocumentCopy /></el-icon>
              <span>生成记录</span>
            </el-menu-item>
          </template>

          <!-- APP 自动化测试模块菜单 -->
          <template v-else-if="currentModule === 'app-automation'">
            <el-menu-item index="/app-automation/dashboard">
              <el-icon><Odometer /></el-icon>
              <span>Dashboard</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/projects">
              <el-icon><Folder /></el-icon>
              <span>项目管理</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/devices">
              <el-icon><Monitor /></el-icon>
              <span>设备管理</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/packages">
              <el-icon><Document /></el-icon>
              <span>包名管理</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/elements">
              <el-icon><Aim /></el-icon>
              <span>元素管理</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/scene-builder">
              <el-icon><Edit /></el-icon>
              <span>用例编排</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/test-cases">
              <el-icon><Document /></el-icon>
              <span>测试用例</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/test-suites">
              <el-icon><Collection /></el-icon>
              <span>测试套件</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/executions">
              <el-icon><VideoPlay /></el-icon>
              <span>执行记录</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/reports">
              <el-icon><DataAnalysis /></el-icon>
              <span>测试报告</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/scheduled-tasks">
              <el-icon><AlarmClock /></el-icon>
              <span>定时任务</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/notification-logs">
              <el-icon><Bell /></el-icon>
              <span>通知列表</span>
            </el-menu-item>
            <el-menu-item index="/app-automation/ai-generate">
              <el-icon><MagicStick /></el-icon>
              <span>AI 生成</span>
            </el-menu-item>
          </template>

          <!-- AI 智能模式模块菜单 -->
          <template v-else-if="currentModule === 'ai-intelligent-mode'">
            <el-menu-item index="/ai-intelligent-mode/testing">
              <el-icon><VideoPlay /></el-icon>
              <span>AI 智能测试</span>
            </el-menu-item>
            <el-menu-item index="/ai-intelligent-mode/projects">
              <el-icon><Folder /></el-icon>
              <span>项目管理</span>
            </el-menu-item>
            <el-menu-item index="/ai-intelligent-mode/cases">
              <el-icon><Document /></el-icon>
              <span>AI 用例管理</span>
            </el-menu-item>
            <el-menu-item index="/ai-intelligent-mode/suites">
              <el-icon><Collection /></el-icon>
              <span>套件管理</span>
            </el-menu-item>
            <el-menu-item index="/ai-intelligent-mode/execution-records">
              <el-icon><Timer /></el-icon>
              <span>AI 执行记录</span>
            </el-menu-item>
            <el-menu-item index="/ai-intelligent-mode/reports">
              <el-icon><Document /></el-icon>
              <span>测试报告</span>
            </el-menu-item>
            <el-menu-item index="/ai-intelligent-mode/scheduled-tasks">
              <el-icon><AlarmClock /></el-icon>
              <span>定时任务</span>
            </el-menu-item>
            <el-menu-item index="/ai-intelligent-mode/notification-logs">
              <el-icon><Bell /></el-icon>
              <span>通知列表</span>
            </el-menu-item>
            <el-menu-item index="/ai-intelligent-mode/ai-generate">
              <el-icon><MagicStick /></el-icon>
              <span>AI 生成</span>
            </el-menu-item>
          </template>

          <!-- 配置中心模块菜单 -->
          <template v-else-if="currentModule === 'configuration'">
            <!-- 2026-07-24 项目概览：放在最前面，按 project_id 聚合全平台数据 -->
            <el-menu-item index="/configuration/project-overview">
              <el-icon><DataBoard /></el-icon>
              <span>项目概览</span>
            </el-menu-item>
            <el-menu-item index="/configuration/ai-model">
              <el-icon><Cpu /></el-icon>
              <span>AI模型配置</span>
            </el-menu-item>
            <el-menu-item index="/configuration/skill-config">
              <el-icon><MagicStick /></el-icon>
              <span>Skill 技能配置</span>
            </el-menu-item>
            <el-menu-item index="/configuration/hermes-config">
              <el-icon><ChatDotRound /></el-icon>
              <span>数字人配置</span>
            </el-menu-item>
            <el-menu-item index="/configuration/ui-env">
              <el-icon><Monitor /></el-icon>
              <span>UI环境配置</span>
            </el-menu-item>
            <el-menu-item index="/configuration/ai-mode">
              <el-icon><MagicStick /></el-icon>
              <span>AI智能模式配置</span>
            </el-menu-item>
            <el-menu-item index="/configuration/scheduled-task">
              <el-icon><Timer /></el-icon>
              <span>定时任务配置</span>
            </el-menu-item>
            <el-menu-item index="/configuration/dify">
              <el-icon><ChatDotRound /></el-icon>
              <span>AI评测师配置</span>
            </el-menu-item>
            <!-- 知识中枢（2026-07-24 v3.2）：下沉为配置中心下的二级折叠子菜单，引擎切换下移至主页紫色横幅右上角 -->
            <el-sub-menu index="knowledge-hub">
              <template #title>
                <el-icon><DataLine /></el-icon>
                <span class="submenu-title">知识中枢</span>
              </template>
              <el-menu-item index="/configuration/knowledge-hub/home">
                <el-icon><HomeFilled /></el-icon>
                <span>知识中枢首页</span>
              </el-menu-item>
              <el-menu-item index="/configuration/knowledge-hub/kbs">
                <el-icon><Files /></el-icon>
                <span>知识库管理</span>
              </el-menu-item>
              <el-menu-item index="/configuration/knowledge-hub/documents">
                <el-icon><Document /></el-icon>
                <span>文档管理</span>
              </el-menu-item>
              <el-menu-item index="/configuration/knowledge-hub/qa">
                <el-icon><ChatDotRound /></el-icon>
                <span>知识问答</span>
              </el-menu-item>
              <el-menu-item index="/configuration/knowledge-hub/config">
                <el-icon><Setting /></el-icon>
                <span>中枢配置</span>
              </el-menu-item>
              <el-menu-item index="/configuration/knowledge-hub/manual">
                <el-icon><Reading /></el-icon>
                <span>操作手册</span>
              </el-menu-item>
            </el-sub-menu>
            <el-menu-item index="/configuration/performance-testing">
              <el-icon><Odometer /></el-icon>
              <span>性能测试配置</span>
            </el-menu-item>
          </template>

          <!-- 性能测试模块菜单 -->
          <template v-else-if="currentModule === 'performance-testing'">
            <el-menu-item index="/performance-testing/dashboard">
              <el-icon><DataLine /></el-icon>
              <span>数据看板</span>
            </el-menu-item>
            <el-menu-item index="/performance-testing/projects">
              <el-icon><Folder /></el-icon>
              <span>项目管理</span>
            </el-menu-item>
            <el-menu-item index="/performance-testing/scripts">
              <el-icon><Edit /></el-icon>
              <span>脚本编排</span>
            </el-menu-item>
            <el-menu-item index="/performance-testing/executions">
              <el-icon><VideoPlay /></el-icon>
              <span>执行记录</span>
            </el-menu-item>
            <el-menu-item index="/performance-testing/reports">
              <el-icon><Document /></el-icon>
              <span>报告管理</span>
            </el-menu-item>
            <el-menu-item index="/performance-testing/scheduled-tasks">
              <el-icon><Timer /></el-icon>
              <span>定时任务</span>
            </el-menu-item>
            <el-menu-item index="/performance-testing/ai-generate">
              <el-icon><MagicStick /></el-icon>
              <span>AI 生成</span>
            </el-menu-item>
          </template>

          <!-- 运维工具模块菜单 -->
          <template v-else-if="currentModule === 'ops-tools'">
            <el-menu-item index="/ops-tools/environments">
              <el-icon><Setting /></el-icon>
              <span>环境管理</span>
            </el-menu-item>
            <el-menu-item index="/ops-tools/logs">
              <el-icon><Document /></el-icon>
              <span>日志查询</span>
            </el-menu-item>
            <el-menu-item index="/ops-tools/text2sql">
              <el-icon><DataLine /></el-icon>
              <span>Text2SQL</span>
            </el-menu-item>
            <el-menu-item index="/ops-tools/files">
              <el-icon><Folder /></el-icon>
              <span>内网文件传输</span>
            </el-menu-item>
          </template>
        </el-menu>

        <!-- Hermes 数字人形象（仅在 Hermes 模块显示；位于 el-menu 之下，高度自适应不溢出） -->
        <div v-if="currentModule === 'hermes'" class="sidebar-avatar">
          <HermesAvatar
            :state="hermesStore.avatarState"
            :speak-text="hermesStore.speakText"
            :model-url="currentModelUrl"
            @ready="onAvatarReady"
            @state-change="onAvatarStateChange"
          />
          <!-- Hermes 换装下拉（置于数字人底部，替代原表情按钮位置，背景透明） -->
          <div class="avatar-selector">
            <el-select
              v-model="currentModelId"
              placeholder="切换形象"
              size="small"
              @change="onAvatarModelChange"
              style="width: 100%">
              <el-option
                v-for="m in avatarOptions"
                :key="m.id"
                :value="m.id"
                :label="m.name" />
            </el-select>
          </div>
        </div>
      </el-aside>

      <!-- 主体内容 -->
      <el-container>
        <!-- 顶部导航 -->
        <el-header height="60px">
          <div class="header-content">
            <div class="header-left">
              <el-breadcrumb separator="/">
                <el-breadcrumb-item :to="{ path: '/home' }">首页</el-breadcrumb-item>
                <el-breadcrumb-item v-if="moduleName">{{ moduleName }}</el-breadcrumb-item>
                <el-breadcrumb-item>{{ breadcrumbTitle }}</el-breadcrumb-item>
              </el-breadcrumb>
            </div>
            <div class="header-right">
              <el-dropdown @command="handleCommand">
                <span class="user-info">
                  <el-avatar :size="32" :src="userStore.user?.avatar" />
                  <span class="username">{{ userStore.user?.username }}</span>
                  <el-icon><ArrowDown /></el-icon>
                </span>
                <template #dropdown>
                  <el-dropdown-menu>
                  <el-dropdown-item command="profile">个人设置</el-dropdown-item>
                  <el-dropdown-item command="appearance">外观设置</el-dropdown-item>
                  <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </el-header>

        <!-- 页面内容 -->
        <el-main :class="{ 'no-padding': currentModule === 'hermes' }">
          <router-view />
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useHermesStore } from '@/stores/hermes'
import { useKbHubStore } from '@/stores/kb-hub'
import { ElMessage } from 'element-plus'
import HermesAvatar, { PRESET_MODELS } from '@/components/HermesAvatar.vue'
import {
  Monitor, Folder, Document, Flag, Check, Collection, VideoPlay,
  DataAnalysis, ChatDotRound, DocumentCopy, Link, MagicStick,
  Odometer, Timer, Setting, AlarmClock, Bell, Aim, Edit, Cpu, DataLine, Files,
  Reading, HomeFilled, DataBoard
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const hermesStore = useHermesStore()
const kbHubStore = useKbHubStore()

// ───── 数字人形象切换（顶栏下拉） ─────
const AVATAR_MODEL_KEY = 'hermes_avatar_model_id'
const avatarOptions = ref([
  ...PRESET_MODELS,
  { id: 'custom', name: '🔗 自定义 URL（来自配置中心）', url: '' },
])
const currentModelId = ref(localStorage.getItem(AVATAR_MODEL_KEY) || PRESET_MODELS[0].id)
const currentModelUrl = ref('')
const savedCustomUrl = ref(localStorage.getItem('hermes_model_url') || '')

function recomputeModelUrl() {
  const opt = avatarOptions.value.find(m => m.id === currentModelId.value)
  if (!opt || currentModelId.value === 'custom') {
    // 优先用后端配置的自定义 URL；空则退回 haru 默认
    currentModelUrl.value = savedCustomUrl.value
      || hermesStore.hermesConfig?.avatar_url
      || PRESET_MODELS[0].url
  } else {
    currentModelUrl.value = opt.url
  }
}

function onAvatarModelChange(newId) {
  localStorage.setItem(AVATAR_MODEL_KEY, newId)
  recomputeModelUrl()
  if (newId === 'custom' && !savedCustomUrl.value && !hermesStore.hermesConfig?.avatar_url) {
    ElMessage.warning('尚未配置自定义数字人 URL，请到「配置中心 → Hermes 数字人」中填写')
  } else {
    const opt = avatarOptions.value.find(m => m.id === newId)
    ElMessage.success(`已切换到：${opt?.name || newId}`)
  }
}

function onAvatarReady(ok) {
  if (ok) hermesStore.setAvatarReady(true)
}

function onAvatarStateChange(state) {
  // 可在 store 记录状态历史
}

onMounted(() => {
  recomputeModelUrl()
})

// 后端 hermesConfig 加载完成后，如果当前是 custom 模式，重新计算 URL
watch(() => hermesStore.hermesConfig?.avatar_url, () => {
  if (currentModelId.value === 'custom') recomputeModelUrl()
})

const currentModule = computed(() => {
  if (route.path.startsWith('/hermes')) return 'hermes'
  if (route.path.startsWith('/ai-generation')) return 'ai-generation'
  if (route.path.startsWith('/api-testing')) return 'api-testing'
  if (route.path.startsWith('/ui-automation')) return 'ui-automation'
  if (route.path.startsWith('/app-automation')) return 'app-automation'
  if (route.path.startsWith('/ai-intelligent-mode')) return 'ai-intelligent-mode'
  if (route.path.startsWith('/configuration')) return 'configuration'
  if (route.path.startsWith('/performance-testing')) return 'performance-testing'
  if (route.path.startsWith('/ops-tools')) return 'ops-tools'
  return ''
})

const moduleName = computed(() => {
  const map = {
    'hermes': 'Hermes 数字人',
    'ai-generation': 'AI用例生成',
    'api-testing': '接口测试',
    'ui-automation': 'UI自动化测试',
    'app-automation': 'APP自动化测试',
    'ai-intelligent-mode': 'AI 智能模式',
    'configuration': '配置中心',
    'performance-testing': '性能测试',
    'ops-tools': '运维工具'
  }
  return map[currentModule.value] || ''
})

const breadcrumbTitle = computed(() => {
  const routeMap = {
    // Hermes 数字人
    '/hermes': 'Hermes 数字人',

    // AI用例生成
    '/ai-generation/requirement-analysis': 'AI用例生成',
    '/ai-generation/generated-testcases': 'AI生成用例记录',
    '/ai-generation/prompt-config': '提示词配置',
    '/ai-generation/skill-config': 'Skill 配置',
    '/ai-generation/projects': '项目管理',
    '/ai-generation/testcases': '测试用例',
    '/ai-generation/versions': '版本管理',
    '/ai-generation/reviews': '评审列表',
    '/ai-generation/review-templates': '评审模板',
    '/ai-generation/testsuites': '测试套件',
    '/ai-generation/executions': '执行记录',
    '/ai-generation/reports': '测试报告',
    '/ai-generation/kg-browse': '知识图谱浏览',
    '/ai-generation/kg-coverage': '覆盖度报告',
    '/ai-generation/kb-functions': '功能模块配置',

    // 接口测试
    '/api-testing/dashboard': '数据看板',
    '/api-testing/projects': '项目管理',
    '/api-testing/interfaces': '接口管理',
    '/api-testing/automation': '自动化测试',
    '/api-testing/history': '请求历史',
    '/api-testing/environments': '环境管理',
    '/api-testing/reports': '测试报告',
    '/api-testing/scheduled-tasks': '定时任务',
    '/api-testing/ai-generate': 'AI 生成',
    '/api-testing/notification-logs': '通知列表',
    
    // UI自动化测试
    '/ui-automation/dashboard': '数据看板',
    '/ui-automation/projects': '项目管理',
    '/ui-automation/elements-enhanced': '元素管理',
    '/ui-automation/test-cases': '用例管理',
    '/ui-automation/scripts-enhanced': '脚本生成',
    '/ui-automation/scripts': '脚本列表',
    '/ui-automation/suites': '套件管理',
    '/ui-automation/executions': '执行记录',
    '/ui-automation/reports': '测试报告',
    '/ui-automation/scheduled-tasks': '定时任务',
    '/ui-automation/ai-generate': 'AI 生成',
    '/ui-automation/generate-from-case': '用例生成UI脚本',
    '/ui-automation/generate-records': '生成记录',
    '/ui-automation/notification-logs': '通知列表',

    // APP自动化测试
    '/app-automation/dashboard': 'Dashboard',
    '/app-automation/projects': '项目管理',
    '/app-automation/devices': '设备管理',
    '/app-automation/packages': '包名管理',
    '/app-automation/elements': '元素管理',
    '/app-automation/scene-builder': '用例编排',
    '/app-automation/test-cases': '测试用例',
    '/app-automation/test-suites': '测试套件',
    '/app-automation/scheduled-tasks': '定时任务',
    '/app-automation/ai-generate': 'AI 生成',
    '/app-automation/notification-logs': '通知列表',
    '/app-automation/executions': '执行记录',
    '/app-automation/reports': '测试报告',
    
    // AI 智能模式
    '/ai-intelligent-mode/testing': 'AI 智能测试',
    '/ai-intelligent-mode/projects': '项目管理',
    '/ai-intelligent-mode/cases': 'AI 用例管理',
    '/ai-intelligent-mode/suites': '套件管理',
    '/ai-intelligent-mode/execution-records': 'AI 执行记录',
    '/ai-intelligent-mode/reports': '测试报告',
    '/ai-intelligent-mode/scheduled-tasks': '定时任务',
    '/ai-intelligent-mode/ai-generate': 'AI 生成',
    '/ai-intelligent-mode/notification-logs': '通知列表',
    
    
    // 配置中心
    '/configuration/ai-model': 'AI模型配置',
    '/configuration/project-overview': '项目概览',
    '/configuration/skill-config': 'Skill 技能配置',
    '/configuration/hermes-config': '数字人配置',
    '/configuration/ui-env': 'UI环境配置',
    '/configuration/ai-mode': 'AI智能模式配置',
    '/configuration/scheduled-task': '定时任务配置',
    '/configuration/dify': 'AI评测师配置',
    // 历史兼容：原配置中心下的两个 KB 菜单已合并到 knowledge-hub 子菜单
    '/configuration/kb-hub': '知识中枢配置（迁移中）',
    '/configuration/knowledge-library': '知识库管理（迁移中）',
    '/configuration/performance-testing': '性能测试配置',
    // 知识中枢（2026-07-24 v3.1：下沉为配置中心二级菜单，路径前缀 /configuration/knowledge-hub）
    '/configuration/knowledge-hub': '知识中枢',
    '/configuration/knowledge-hub/home': '知识中枢首页',
    '/configuration/knowledge-hub/kbs': '知识库管理',
    '/configuration/knowledge-hub/documents': '文档管理',
    '/configuration/knowledge-hub/qa': '知识问答',
    '/configuration/knowledge-hub/config': '中枢配置',
    '/configuration/knowledge-hub/manual': '操作手册',

    // 性能测试
    '/performance-testing/dashboard': '数据看板',
    '/performance-testing/projects': '项目管理',
    '/performance-testing/scripts': '脚本编排',
    '/performance-testing/scripts/create': '新建脚本',
    '/performance-testing/executions': '执行记录',
    '/performance-testing/reports': '报告管理',
    '/performance-testing/scheduled-tasks': '定时任务',
    '/performance-testing/ai-generate': 'AI 生成',

    // 运维工具
    '/ops-tools/environments': '环境管理',
    '/ops-tools/logs': '日志查询',
    '/ops-tools/text2sql': 'Text2SQL',
    '/ops-tools/files': '内网文件传输',

    '/profile': '个人设置'
  }
  return routeMap[route.path] || route.meta.title || ''
})

const handleCommand = (command) => {
  if (command === 'logout') {
    userStore.logout()
    ElMessage.success('退出登录成功')
    router.push('/login')
  } else if (command === 'profile') {
    router.push('/ai-generation/profile')
  } else if (command === 'appearance') {
    router.push('/configuration/appearance')
  }
}

// 进入配置中心（含知识中枢）时加载默认引擎（保证主页右上角按钮显示最新）
onMounted(() => {
  if (currentModule.value === 'configuration') kbHubStore.loadDefaultEngine()
})
watch(currentModule, (m) => {
  if (m === 'configuration') kbHubStore.loadDefaultEngine()
})
</script>

<style lang="scss" scoped>
.layout {
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.layout > .el-container {
  height: 100%;
  overflow: hidden;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--app-sidebar-bg, #001529);
  color: var(--app-sidebar-text, #ffffff);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
  transition: background-color 0.3s ease;

  h2 {
    margin: 0;
    font-weight: 600;
  }
}

  .el-aside {
  background-color: var(--app-sidebar-bg, #001529);
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: background-color 0.3s ease;

  :deep(.el-menu) {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    border-right: none;
    background-color: transparent !important;
    color: var(--app-sidebar-text, #ffffff);

    &::-webkit-scrollbar {
      width: 0; /* 隐藏侧边栏滚动条但保留功能 */
    }

    /* 内嵌二级菜单背景必须与侧边栏一致 */
    .el-menu--inline,
    .el-sub-menu .el-menu {
      background-color: var(--app-sidebar-bg, #001529) !important;
    }

    .el-menu-item,
    .el-sub-menu__title {
      color: var(--app-sidebar-text, #ffffff) !important;

      .el-icon {
        color: inherit !important;
      }

      &:hover,
      &:focus {
        background-color: var(--app-sidebar-bg-hover, rgba(255, 255, 255, 0.05)) !important;
        color: var(--app-sidebar-text, #ffffff) !important;
      }
    }

    .el-menu-item.is-active {
      color: var(--app-sidebar-active, #409eff) !important;
      background-color: var(--app-sidebar-bg-hover, rgba(255, 255, 255, 0.05)) !important;

      .el-icon {
        color: inherit !important;
      }
    }

    .el-sub-menu.is-active .el-sub-menu__title {
      color: var(--app-sidebar-active, #409eff) !important;

      .el-icon {
        color: inherit !important;
      }
    }

    .el-sub-menu .el-menu-item {
      color: var(--app-sidebar-text, #ffffff) !important;

      &:hover,
      &:focus,
      &.is-active {
        color: var(--app-sidebar-active, #409eff) !important;
        background-color: var(--app-sidebar-bg-hover, rgba(255, 255, 255, 0.05)) !important;
      }
    }
  }

  .sidebar-avatar {
    flex: 1 1 auto;        /* 吃光 el-menu 之外的剩余高度，不再写死 500px 避免溢出 */
    min-height: 360px;     /* 给数字人 + 5 个表情按钮 + 状态徽章最小可用空间 */
    max-height: 480px;
    flex-shrink: 1;
    background: transparent;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .avatar-selector {
    position: absolute;          /* 置于数字人底部，替代原表情按钮位置 */
    bottom: 8px;
    left: 50%;
    transform: translateX(-50%);
    width: calc(100% - 16px);
    z-index: 5;
    padding: 0;
    background: transparent;     /* 背景透明 */
    border: none;

    :deep(.el-select) { width: 100%; }

    /* 选择框背景透明 + 浅色边框，在深色侧边栏上仍清晰可见 */
    :deep(.el-select__wrapper),
    :deep(.el-input__wrapper) {
      background-color: transparent;
      box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.35) inset;
      color: #fff;
    }
    :deep(.el-select__placeholder) { color: rgba(255, 255, 255, 0.7); }
  }
}

/* 知识中枢 submenu 标题：左侧图标+文字，引擎切换已移到主页紫色横幅右上角 */
.submenu-title {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 内部容器 (Header + Main) */
.el-container .el-container {
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.el-header {
  background-color: var(--app-card-bg, #ffffff);
  border-bottom: 1px solid var(--app-border, #e8e8e8);
  backdrop-filter: blur(var(--app-panel-blur, 0px));
  -webkit-backdrop-filter: blur(var(--app-panel-blur, 0px));
  padding: 0;
  flex-shrink: 0;
  transition: background-color 0.3s ease, border-color 0.3s ease;

  .header-content {
    height: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 20px;
  }

  .user-info {
    display: flex;
    align-items: center;
    cursor: pointer;

    .username {
      margin: 0 8px;
      color: var(--app-text, #303133);
    }
  }
}

.el-main {
  background-color: var(--app-bg-soft, #f5f5f5);
  padding: 20px;
  flex: 1;
  overflow-y: auto; /* 内容区域独立滚动 */
  overflow-x: hidden;
  transition: background-color 0.3s ease;

  &.no-padding {
    padding: 0;
  }
}
</style>