<template>
  <div class="api-testing-layout">
    <!-- 顶部导航 -->
    <div class="top-nav">
      <h2>接口测试</h2>
      <el-menu
        :default-active="currentRoute"
        mode="horizontal"
        @select="handleMenuSelect"
        class="nav-menu"
      >
        <el-menu-item index="projects">项目管理</el-menu-item>
        <el-menu-item index="interfaces">接口管理</el-menu-item>
        <el-menu-item index="automation">自动化测试</el-menu-item>
        <el-menu-item index="history">请求历史</el-menu-item>
        <el-menu-item index="environments">环境管理</el-menu-item>
        <el-menu-item index="scheduled-tasks">定时任务</el-menu-item>
        <el-menu-item index="ai-generate">AI 生成</el-menu-item>
        <el-menu-item index="reports">测试报告</el-menu-item>
        <el-menu-item index="notification-logs">通知列表</el-menu-item>
        <el-menu-item index="notification-configs">通知配置</el-menu-item>
      </el-menu>
    </div>
    
    <!-- 内容区域 -->
    <div class="content">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const currentRoute = computed(() => {
  const path = route.path
  if (path.includes('/projects')) return 'projects'
  if (path.includes('/interfaces')) return 'interfaces' 
  if (path.includes('/automation')) return 'automation'
  if (path.includes('/history')) return 'history'
  if (path.includes('/environments')) return 'environments'
  if (path.includes('/scheduled-tasks')) return 'scheduled-tasks'
  if (path.includes('/ai-generate')) return 'ai-generate'
  if (path.includes('/reports')) return 'reports'
  if (path.includes('/notification-logs')) return 'notification-logs'
  if (path.includes('/notification-configs')) return 'notification-configs'
  return 'projects'
})

const handleMenuSelect = (index) => {
  router.push(`/api-testing/${index}`)
}
</script>

<style scoped>
.api-testing-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.top-nav {
  border-bottom: 1px solid #e4e7ed;
  background: white;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 30px;
}

.top-nav h2 {
  margin: 0;
  color: #303133;
  white-space: nowrap;
}

.nav-menu {
  flex: 1;
  border: none;
}

.content {
  flex: 1;
  overflow: hidden;
}
</style>