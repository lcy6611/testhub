<template>
  <div class="ui-env-config">
    <div class="page-header">
      <h1>🖥️ UI自动化环境配置</h1>
      <p>检测和管理浏览器驱动环境</p>
    </div>

    <div class="main-content">
      <div class="check-section">
        <el-button type="primary" size="large" @click="checkEnvironment" :loading="checking">
          <el-icon><Refresh /></el-icon>
          检测环境
        </el-button>
        <div v-if="lastCheckTime" class="last-check">
          上次检测时间: {{ lastCheckTime }}
        </div>
      </div>

      <div v-if="environmentData" class="env-status-grid">
        <div class="os-info-card">
          <h3>🖥️ 操作系统</h3>
          <div class="os-name">{{ environmentData.os }}</div>
        </div>

        <!-- 系统浏览器 (Selenium) -->
        <div class="section-title">
          <h3>🌐 系统浏览器 (Selenium支持)</h3>
        </div>
        <div class="browser-cards">
          <div v-for="browser in environmentData.system_browsers" :key="browser.name" class="browser-card">
              <div class="browser-content">
                <div class="browser-icon">
                  <img :src="getBrowserIcon(browser.name)" :alt="browser.name" />
                </div>
                <div class="browser-info">
                  <h3>{{ formatBrowserName(browser.name) }}</h3>
                  <div class="status-row">
                    <el-tag :type="browser.installed ? 'success' : 'info'" effect="dark">
                      {{ browser.installed ? (browser.version || '已安装') : '未安装' }}
                    </el-tag>
                  </div>
                </div>
              </div>
          </div>
        </div>

        <!-- Playwright 浏览器 -->
        <div class="section-title">
          <h3>🎭 Playwright 浏览器</h3>
        </div>
        <div class="browser-cards">
          <div v-for="browser in environmentData.playwright_browsers" :key="browser.name" class="browser-card">
              <div class="browser-content">
                <div class="browser-icon">
                  <img :src="getBrowserIcon(browser.name)" :alt="browser.name" />
                </div>
                <div class="browser-info">
                  <h3>{{ formatBrowserName(browser.name) }}</h3>
                  <div class="status-row">
                    <el-tag :type="browser.installed ? 'success' : 'warning'" effect="dark">
                      {{ browser.installed ? (browser.version || '已安装') : '未安装' }}
                    </el-tag>
                  </div>
                </div>
                <div class="browser-actions" v-if="!browser.installed">
                  <el-button 
                    type="primary" 
                    size="small" 
                    @click="installDriver(browser.name)"
                    :loading="installing === browser.name"
                  >
                    一键安装
                  </el-button>
                </div>
              </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const checking = ref(false)
const installing = ref(null)
const lastCheckTime = ref('')
const environmentData = ref(null)

const getBrowserIcon = (name) => {
  const iconMap = {
    'chrome': 'https://raw.githubusercontent.com/alrra/browser-logos/main/src/chrome/chrome_48x48.png',
    'firefox': 'https://raw.githubusercontent.com/alrra/browser-logos/main/src/firefox/firefox_48x48.png',
    'safari': 'https://raw.githubusercontent.com/alrra/browser-logos/main/src/safari/safari_48x48.png',
    'edge': 'https://raw.githubusercontent.com/alrra/browser-logos/main/src/edge/edge_48x48.png',
    'chromium': 'https://raw.githubusercontent.com/alrra/browser-logos/main/src/chromium/chromium_48x48.png',
    'webkit': 'https://raw.githubusercontent.com/alrra/browser-logos/main/src/webkit/webkit_48x48.png'
  }
  return iconMap[name] || ''
}

const formatBrowserName = (name) => {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

const checkEnvironment = async () => {
  checking.value = true
  try {
    const response = await api.get('/ui-automation/config/environment/check_environment/')
    environmentData.value = response.data
    lastCheckTime.value = new Date().toLocaleString()
    ElMessage.success('环境检测完成')
  } catch (error) {
    console.error('环境检测失败:', error)
    ElMessage.error('环境检测失败')
  } finally {
    checking.value = false
  }
}

const installDriver = async (browserName) => {
  installing.value = browserName
  try {
    await api.post('/ui-automation/config/environment/install_driver/', { browser: browserName })
    ElMessage.success(`${formatBrowserName(browserName)} 驱动安装成功`)
    // Re-check environment
    await checkEnvironment()
  } catch (error) {
    console.error('驱动安装失败:', error)
    ElMessage.error(`驱动安装失败: ${error.response?.data?.error || error.message}`)
  } finally {
    installing.value = null
  }
}

onMounted(() => {
  checkEnvironment()
})
</script>

<style scoped>
.ui-env-config {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  text-align: center;
  margin-bottom: 40px;
}

.page-header h1 {
  font-size: 2.5rem;
  color: #2c3e50;
  margin-bottom: 10px;
}

.page-header p {
  color: #666;
  font-size: 1.1rem;
}

.check-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 40px;
  gap: 10px;
}

.last-check {
  font-size: 0.9rem;
  color: #999;
}

.env-status-grid {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.os-info-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  text-align: center;
}

.os-name {
  font-size: 1.5rem;
  font-weight: bold;
  color: #409EFF;
  margin-top: 10px;
}

.section-title {
  margin: 20px 0 10px;
  border-left: 4px solid #409EFF;
  padding-left: 10px;
}

.section-title h3 {
  margin: 0;
  font-size: 1.2rem;
  color: var(--el-text-color-primary);
}

.browser-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
}

.browser-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  transition: transform 0.3s;
  cursor: default;
}

.browser-card:hover {
  transform: translateY(-5px);
}

.browser-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
}

.browser-icon {
  width: 64px;
  height: 64px;
  margin-bottom: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.browser-icon img {
  width: 48px;
  height: 48px;
  object-fit: contain;
}

.browser-info {
  width: 100%;
  text-align: center;
  margin-bottom: 15px;
}

.browser-info h3 {
  margin: 0 0 10px;
  color: var(--el-text-color-primary);
  font-size: 1.1rem;
}

.status-row {
  display: flex;
  justify-content: center;
  margin-bottom: 5px;
}

.browser-actions {
  margin-top: 10px;
  width: 100%;
  display: flex;
  justify-content: center;
}
</style>
