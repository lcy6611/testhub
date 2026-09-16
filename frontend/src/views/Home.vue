<template>
  <div class="home-container">
    <div class="content-wrapper">
      <div class="header-actions">
        <el-dropdown @command="handleCommand">
          <span class="el-dropdown-link">
            <el-avatar :size="32" :icon="UserFilled" />
            <span class="username">{{ userStore.user?.username || '用户' }}</span>
            <el-icon class="el-icon--right"><arrow-down /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <h1 v-if="themeStore.homeTitle" class="main-title">{{ themeStore.homeTitle }}</h1>
      <p v-if="themeStore.homeSubtitle" class="subtitle">{{ themeStore.homeSubtitle }}</p>
      
      <div class="cards-container">
        <!-- AI用例生成 -->
        <div class="nav-card" @click="handleNavigate('ai')" role="button" tabindex="0">
          <div class="card-icon ai-icon">
            <el-icon><MagicStick /></el-icon>
          </div>
          <h3>AI用例生成</h3>
          <p>智能分析需求，自动生成测试用例</p>
        </div>

        <!-- Hermes 数字人 -->
        <div class="nav-card" @click="handleNavigate('hermes')" role="button" tabindex="0">
          <div class="card-icon hermes-icon">
            <el-icon><Cpu /></el-icon>
          </div>
          <h3>Hermes 数字人</h3>
          <p>自然语言驱动测试全流程</p>
        </div>

        <!-- 接口测试 -->
        <div class="nav-card" @click="handleNavigate('api')" role="button" tabindex="0">
          <div class="card-icon api-icon">
            <el-icon><Link /></el-icon>
          </div>
          <h3>接口测试</h3>
          <p>高效的接口自动化测试与管理</p>
        </div>

        <!-- UI自动化测试 -->
        <div class="nav-card" @click="handleNavigate('ui')" role="button" tabindex="0">
          <div class="card-icon ui-icon">
            <el-icon><Monitor /></el-icon>
          </div>
          <h3>UI自动化测试</h3>
          <p>可视化的Web/App UI自动化测试</p>
        </div>

        <!-- APP自动化测试 -->
        <div class="nav-card" @click="handleNavigate('app')" role="button" tabindex="0">
          <div class="card-icon ui-icon">
            <el-icon><Monitor /></el-icon>
          </div>
          <h3>APP自动化测试</h3>
          <p>基于 Airtest 的 Android APP 自动化测试</p>
        </div>

        <!-- 数据工厂 -->
        <div class="nav-card" @click="handleNavigate('data')" role="button" tabindex="0">
          <div class="card-icon data-icon">
            <el-icon><DataLine /></el-icon>
          </div>
          <h3>数据工厂</h3>
          <p>灵活的测试数据构造与管理</p>
        </div>
        <!-- AI 智能模式 -->
        <div class="nav-card" @click="handleNavigate('ai-intelligent')" role="button" tabindex="0">
          <div class="card-icon ai-intelligent-icon">
            <el-icon><Cpu /></el-icon>
          </div>
          <h3>AI 智能模式</h3>
          <p>基于自然语言的智能化测试执行</p>
        </div>
        <!-- AI评测师 -->
        <div class="nav-card" @click="handleNavigate('assistant')" role="button" tabindex="0">
          <div class="card-icon assistant-icon">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <h3>AI评测师</h3>
          <p>基于评测师知识库，提供专业软件测试问答</p>
        </div>
        <!-- 配置中心 -->
        <div class="nav-card" @click="handleNavigate('config')" role="button" tabindex="0">
          <div class="card-icon config-icon">
            <el-icon><Setting /></el-icon>
          </div>
          <h3>配置中心</h3>
          <p>系统环境、AI模型及通知配置</p>
        </div>
        <!-- 性能测试 -->
        <div class="nav-card" @click="handleNavigate('perf')" role="button" tabindex="0">
          <div class="card-icon perf-icon">
            <el-icon><DataLine /></el-icon>
          </div>
          <h3>性能测试</h3>
          <p>JMeter 压测引擎，在线编排与 JMX 导入</p>
        </div>
        <!-- 运维工具 -->
        <div class="nav-card" @click="handleNavigate('ops-tools')" role="button" tabindex="0">
          <div class="card-icon ops-icon">
            <el-icon><Tools /></el-icon>
          </div>
          <h3>运维工具</h3>
          <p>Text2SQL、日志查询、数据库连接、文件传输</p>
        </div>

        <!-- AI 评测（#261） -->
        <div class="nav-card" @click="handleNavigate('ai-eval')" role="button" tabindex="0">
          <div class="card-icon ai-eval-icon">
            <el-icon><DataBoard /></el-icon>
          </div>
          <h3>AI 评测</h3>
          <p>提示词版本、成本观测、效果看板与反馈</p>
        </div>

        <!-- 问题管理 -->
        <div class="nav-card" @click="handleNavigate('defects')" role="button" tabindex="0">
          <div class="card-icon defects-icon">
            <el-icon><Warning /></el-icon>
          </div>
          <h3>问题管理</h3>
          <p>BUG 全生命周期管理：截图、严重度、状态流转</p>
        </div>

        <!-- MCP 控制台 -->
        <div class="nav-card" @click="handleNavigate('mcp')" role="button" tabindex="0">
          <div class="card-icon mcp-icon">
            <el-icon><Link /></el-icon>
          </div>
          <h3>MCP 控制台</h3>
          <p>工具目录、危险操作审批闸、调用日志与接入配置</p>
        </div>

        <!-- 智能评分器 -->
        <div class="nav-card" @click="handleNavigate('llm-judge')" role="button" tabindex="0">
          <div class="card-icon judge-icon">
            <el-icon><DataBoard /></el-icon>
          </div>
          <h3>智能评分器</h3>
          <p>Rubric 评分标准、规则引擎门禁、单条/批量评分与数值知识库</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick, Link, Monitor, DataLine, Cpu, Setting, ChatDotRound, UserFilled, ArrowDown, Tools, Warning, DataBoard } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()
// 首页标题来自外观设置（可在「外观与皮肤设置」里自定义）
const themeStore = useThemeStore()

const handleCommand = (command) => {
  if (command === 'logout') {
    handleLogout()
  }
}

const handleLogout = () => {
  ElMessageBox.confirm('确定要退出登录吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    userStore.logout()
    router.push('/login')
    ElMessage.success('已退出登录')
  }).catch(() => {})
}

const handleNavigate = (type) => {
  const routes = {
    'ai': '/ai-generation/requirement-analysis',
    'hermes': '/hermes',
    'api': '/api-testing/dashboard',
    'ui': '/ui-automation/dashboard',
    'app': '/app-automation/dashboard',
    'data': '/data-factory',
    'ai-intelligent': '/ai-intelligent-mode/testing',
    'assistant': '/ai-generation/assistant',
    'config': '/configuration/ai-model',
    'perf': '/performance-testing/scripts',
    'ops-tools': '/ops-tools/text2sql',
    'ai-eval': '/ai-eval/dashboard',
    'defects': '/defects',
    'mcp': '/mcp/console',
    'llm-judge': '/llm-judge/dashboard'
  }

  if (routes[type]) {
    const routeData = router.resolve({ path: routes[type] })
    window.open(routeData.href, '_blank')
  }
}
</script>

<style scoped lang="scss">
.home-container {
  min-height: 100vh;
  position: relative;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
}

.home-container::before {
  content: '';
  position: absolute;
  inset: 0;
  /* 替换为你的背景图：放到 frontend/src/assets/images 下，并按下面文件名命名 */
  background: url('../assets/images/home-bg.png') no-repeat center/cover;
  z-index: 0;
  /* 可根据实际效果调节透明度：值越大图越明显 */
  opacity: 0.9;
}

.home-container::after {
  content: '';
  position: absolute;
  inset: 0;
  /* 保留原有浅色氛围，避免背景图过暗影响内容可读性 */
  background: linear-gradient(135deg, rgba(245, 247, 250, 0.92) 0%, rgba(195, 207, 226, 0.92) 100%);
  z-index: 1;
}

.content-wrapper {
  text-align: center;
  max-width: 1200px;
  width: 100%;
  position: relative;
  z-index: 2;
}

.header-actions {
  position: absolute;
  top: 0;
  right: 0;
  padding: 10px;
  
  .el-dropdown-link {
    display: flex;
    align-items: center;
    cursor: pointer;
    color: #5e6d82;
    
    .username {
      margin: 0 8px;
      font-size: 14px;
    }
    
    &:hover {
      color: #409eff;
    }
  }
}

.main-title {
  font-size: 3.5rem;
  color: #2c3e50;
  margin-bottom: 1rem;
  font-weight: 700;
  letter-spacing: 2px;
}

.subtitle {
  font-size: 1.5rem;
  color: #5e6d82;
  margin-bottom: 4rem;
}

.cards-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 30px;
  padding: 20px;
}

.nav-card {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 16px;
  padding: 40px 20px;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  align-items: center;

  &:hover {
    transform: translateY(-10px);
    box-shadow: 0 20px 30px rgba(0, 0, 0, 0.1);
    background: #fff;
  }

  h3 {
    font-size: 1.5rem;
    color: #2c3e50;
    margin: 20px 0 10px;
  }

  p {
    color: #7f8c8d;
    line-height: 1.5;
    margin: 0;
  }
}

.card-icon {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  margin-bottom: 10px;
  transition: all 0.3s ease;

  &.ai-icon {
    background: #e8f4ff;
    color: #409eff;
  }

  &.api-icon {
    background: #f0f9eb;
    color: #67c23a;
  }

  &.ui-icon {
    background: #fdf6ec;
    color: #e6a23c;
  }

  &.data-icon {
    background: #f4f4f5;
    color: #909399;
  }

  &.ai-intelligent-icon {
    background: #f0f5ff;
    color: #2f54eb;
  }

  &.config-icon {
    background: #e6fffb;
    color: #13c2c2;
  }

  &.assistant-icon {
    background: #fff7e6;
    color: #fa8c16;
  }

  &.perf-icon {
    background: #fff0f6;
    color: #eb2f96;
  }

  &.hermes-icon {
    background: #f0f5ff;
    color: #2f54eb;
  }

  &.ops-icon {
    background: #e6f7ff;
    color: #1890ff;
  }


  &.ai-eval-icon {
    background: #f9f0ff;
    color: #722ed1;
  }

  &.defects-icon {
    background: #fef0f0;
    color: #f56c6c;
  }

  &.judge-icon {
    background: #fffbe6;
    color: #faad14;
  }
}

.nav-card:hover .card-icon {
  transform: scale(1.1);
}
</style>
