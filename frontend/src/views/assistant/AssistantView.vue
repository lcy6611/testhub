<template>
  <div class="assistant-layout">
    <!-- 左侧侧边栏 -->
    <div class="sidebar">
      <div class="new-chat-btn-wrapper">
        <el-button type="primary" class="new-chat-btn" @click="startNewChat" :icon="Plus">
          新会话
        </el-button>
      </div>
      
      <div class="history-list">
        <div class="history-label">历史会话</div>
        <div class="session-scroll-area">
          <div 
            v-for="session in historySessionsDescending" 
            :key="session.id"
            :class="['session-item', { active: currentSession?.id === session.id }]"
            @click="switchToSession(session)"
          >
            <div class="session-title-wrapper">
              <el-icon class="chat-icon"><ChatDotRound /></el-icon>
              <span class="session-title" :title="session.title">{{ session.title || '新会话' }}</span>
            </div>
            <div class="session-actions" @click.stop>
              <el-popconfirm title="确定删除此会话吗？" @confirm="deleteSession(session.id)">
                <template #reference>
                  <el-icon class="delete-icon"><Delete /></el-icon>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </div>
      
      <div class="user-profile">
        <el-dropdown trigger="click" @command="handleCommand">
          <div class="user-info">
            <el-avatar :size="32" :icon="UserFilled" />
            <span class="username">{{ userStore.user?.username || '用户' }}</span>
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="home">返回首页</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 右侧主内容区 -->
    <div class="main-content">
      <!-- 场景1：新会话（居中输入框） -->
      <div v-if="isNewChatMode" class="welcome-screen">
        <div class="welcome-content">
          <div class="logo-area">
            <div class="logo-circle">
              <el-icon><Cpu /></el-icon>
            </div>
            <h1>AI 评测师</h1>
            <p>我是您的专业测试助手，有什么可以帮您？</p>
          </div>
          
          <div class="center-input-wrapper">
            <div class="welcome-dify-select">
              <el-select
                v-model="selectedDifyConfigId"
                size="small"
                placeholder="选择Dify应用"
                style="width: 100%"
                :disabled="difyConfigs.length === 0"
              >
                <el-option
                  v-for="cfg in difyConfigs"
                  :key="cfg.id"
                  :label="formatDifyConfigLabel(cfg)"
                  :value="cfg.id"
                  :disabled="!cfg.has_api_key"
                />
              </el-select>
              <div v-if="difyConfigs.length > 0 && evaluatorReadyConfigs.length === 0" class="dify-config-warning">
                当前无可用配置：请在「配置中心 → AI评测师配置」填写应用 API Key（app-）
              </div>
            </div>
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="3"
              placeholder="输入您的问题，按回车发送..."
              class="center-input"
              resize="none"
              @keydown.enter.exact.prevent="handleEnter"
            />
            <input
              ref="fileInputRef"
              type="file"
              multiple
              accept="image/*,application/pdf,text/plain"
              style="display: none"
              @change="onFilesSelected"
            />
            <div class="welcome-upload-row">
              <el-button
                type="default"
                class="welcome-upload-btn"
                :disabled="sending"
                @click="openFileDialog"
              >
                上传
              </el-button>
              <div class="welcome-selected-files-tip" v-if="selectedFiles.length > 0">
                已选 {{ selectedFiles.length }} 个文件
              </div>
            </div>
            <div class="input-actions">
              <el-button 
                type="primary" 
                circle 
                :icon="Promotion" 
                :disabled="!inputMessage.trim()"
                @click="sendMessage"
              />
            </div>
          </div>
          
          <div class="suggestion-chips">
            <div class="chip" @click="useSuggestion('如何设计登录接口的测试用例？')">接口测试用例</div>
            <div class="chip" @click="useSuggestion('帮我生成一份性能测试计划模板')">性能测试计划</div>
            <div class="chip" @click="useSuggestion('解释一下边界值分析法')">测试理论</div>
            <div class="chip" @click="useSuggestion('Python Selenium 元素定位失败怎么办？')">自动化调试</div>
          </div>
        </div>
      </div>

      <!-- 场景2：对话界面 -->
      <div v-else class="chat-screen">
        <div class="chat-header">
          <span class="chat-title">{{ currentSession?.title || '新会话' }}</span>
          <div class="chat-header-right">
            <el-select
              v-model="selectedDifyConfigId"
              size="small"
              placeholder="选择Dify应用"
              style="width: 280px"
              :disabled="difyConfigs.length === 0"
            >
              <el-option
                v-for="cfg in difyConfigs"
                :key="cfg.id"
                :label="formatDifyConfigLabel(cfg)"
                :value="cfg.id"
                :disabled="!cfg.has_api_key"
              />
            </el-select>
            <span class="chat-time" v-if="currentSession">{{ formatDate(currentSession.updated_at) }}</span>
          </div>
        </div>
        
        <div class="messages-container" ref="messagesContainer">
          <div 
            v-for="(message, index) in messages" 
            :key="message.id || index"
            :class="['message-row', message.role]"
          >
            <div class="avatar">
              <el-avatar v-if="message.role === 'user'" :size="36" :icon="User" class="user-avatar" />
              <el-avatar v-else :size="36" :icon="Cpu" class="ai-avatar" />
            </div>
            <div class="message-bubble">
              <div class="message-content" v-html="formatMessageContent(message.content)"></div>
              <div class="message-status" v-if="message.isPending">
                <el-icon class="is-loading"><Loading /></el-icon> 思考中...
              </div>
            </div>
          </div>
          
          <!-- 底部占位，确保滚动到底部 -->
          <div style="height: 20px;"></div>
        </div>

        <div class="chat-footer">
          <div class="input-box">
            <el-input
              v-model="inputMessage"
              type="textarea"
              :rows="1"
              :autosize="{ minRows: 1, maxRows: 5 }"
              placeholder="输入消息..."
              resize="none"
              @keydown.enter.exact.prevent="handleEnter"
            />
            <input
              ref="fileInputRef"
              type="file"
              multiple
              accept="image/*,application/pdf,text/plain"
              style="display: none"
              @change="onFilesSelected"
            />
            <el-button
              type="default"
              class="upload-btn"
              :disabled="sending"
              @click="openFileDialog"
            >
              上传
            </el-button>
            <div class="selected-files-tip" v-if="selectedFiles.length > 0">
              已选 {{ selectedFiles.length }} 个文件
            </div>
            <el-button 
              type="primary" 
              class="send-btn"
              :disabled="!inputMessage.trim() || sending"
              @click="sendMessage"
            >
              <el-icon><Promotion /></el-icon>
            </el-button>
          </div>
          <div class="footer-tip">内容由 AI 生成，请仔细甄别</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, ChatDotRound, User, Cpu, Promotion, Loading, UserFilled, ArrowDown } from '@element-plus/icons-vue'
import api from '@/utils/api'

const router = useRouter()
const userStore = useUserStore()

// 状态
const historySessions = ref([])
const currentSession = ref(null)
const messages = ref([])
const inputMessage = ref('')
const sending = ref(false)
const messagesContainer = ref(null)

// 上传附件（图片/文件）支持
const fileInputRef = ref(null)
const selectedFiles = ref([])

// Dify 多应用选择（对话/工作流都能通过不同的 Dify 配置切换）
const difyConfigs = ref([])
const selectedDifyConfigId = ref(null)

const formatDifyConfigLabel = (cfg) => {
  const name = cfg.app_type || '配置'
  const mode = (cfg.invoke_mode || 'workflow') === 'chat' ? '对话' : '工作流'
  if (!cfg.has_api_key) {
    return `${name} (${mode}) · 未配置 app Key`
  }
  const masked = cfg.api_key_masked || 'app-****'
  return `${name} (${mode}) · ${masked}`
}

const evaluatorReadyConfigs = computed(() =>
  difyConfigs.value.filter(cfg => cfg.has_api_key)
)

const selectedDifyConfig = computed(() =>
  difyConfigs.value.find(cfg => cfg.id === selectedDifyConfigId.value) || null
)

const handleCommand = (command) => {
  if (command === 'logout') {
    handleLogout()
  } else if (command === 'home') {
    router.push('/home')
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

// 计算属性
const historySessionsDescending = computed(() => {
  return [...historySessions.value].sort((a, b) => 
    new Date(b.updated_at) - new Date(a.updated_at)
  )
})

const isNewChatMode = computed(() => {
  // 如果没有当前会话，或者当前会话没有消息且没有ID（临时会话），则显示新会话模式
  return !currentSession.value || (!currentSession.value.id && messages.value.length === 0)
})

// 方法
const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  const now = new Date()
  // 如果是今天，只显示时间
  if (date.toDateString() === now.toDateString()) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

const formatMessageContent = (content) => {
  if (!content) return ''
  // 简单的 markdown 处理，实际项目中建议使用 markdown-it
  return content
    .replace(/\n/g, '<br>')
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 开启新会话
const startNewChat = () => {
  currentSession.value = { title: '新会话' } // 临时会话对象
  messages.value = []
  inputMessage.value = ''
  selectedFiles.value = []
  if (fileInputRef.value) fileInputRef.value.value = ''
}

// 切换会话
const switchToSession = async (session) => {
  if (!session?.id) return
  if (currentSession.value?.id === session.id) return
  
  try {
    currentSession.value = { ...session }
    const response = await api.get(`/assistant/sessions/${session.id}/messages/`)
    messages.value = response.data
    scrollToBottom()
  } catch (error) {
    console.error('加载消息失败:', error)
    ElMessage.error('加载消息失败')
  }
}

// 删除会话
const deleteSession = async (sessionId) => {
  if (!sessionId) return
  try {
    await api.delete(`/assistant/sessions/${sessionId}/`)
    historySessions.value = historySessions.value.filter(s => s.id !== sessionId)
    
    if (currentSession.value?.id === sessionId) {
      startNewChat()
    }
    ElMessage.success('会话已删除')
  } catch (error) {
    console.error('删除会话失败:', error)
    ElMessage.error('删除会话失败')
  }
}

// 使用建议
const useSuggestion = (text) => {
  inputMessage.value = text
  sendMessage()
}

// 处理回车发送
const handleEnter = (e) => {
  if (!e.shiftKey && !sending.value) {
    sendMessage()
  }
}

const openFileDialog = () => {
  if (fileInputRef.value) fileInputRef.value.click()
}

const onFilesSelected = (e) => {
  const list = e?.target?.files ? Array.from(e.target.files) : []
  selectedFiles.value = list
}

const clearSelectedFiles = () => {
  selectedFiles.value = []
  if (fileInputRef.value) fileInputRef.value.value = ''
}

// 发送消息
const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text || sending.value) return

  if (!selectedDifyConfig.value?.has_api_key) {
    ElMessage.error('当前 Dify 配置未填写应用 API Key（app-），无法使用 AI 评测师。请前往配置中心填写。')
    return
  }
  
  inputMessage.value = ''
  sending.value = true
  
  // 1. 立即上屏用户消息
  const tempUserMsg = {
    role: 'user',
    content: text,
    created_at: new Date().toISOString()
  }
  messages.value.push(tempUserMsg)
  
  // 2. 添加一个临时的"思考中"消息
  const tempAiMsg = {
    role: 'assistant',
    content: '',
    isPending: true
  }
  messages.value.push(tempAiMsg)
  scrollToBottom()
  
  try {
    // 如果是新会话（没有ID），先创建会话
    let sessionId = currentSession.value?.session_id || ''
    let isFirstMessage = false
    
    if (!sessionId) {
      isFirstMessage = true
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`
      // 智能生成标题（取前10个字）
      const title = text.length > 10 ? text.substring(0, 10) + '...' : text
      
      const sessionRes = await api.post('/assistant/sessions/', {
        session_id: newSessionId,
        title: title
      })
      
      currentSession.value = sessionRes.data
      sessionId = currentSession.value?.session_id || ''
      
      // 立即添加到历史列表
      historySessions.value.unshift(currentSession.value)
    } else {
      // 如果是已有会话，使用 session_id 字段
      sessionId = currentSession.value?.session_id || ''
    }
    if (!sessionId) {
      throw new Error('会话ID缺失，请刷新页面后重试')
    }
    
    // 3. 发送请求（支持上传文件）
    let response
    if (selectedFiles.value.length > 0) {
      const formData = new FormData()
      formData.append('session_id', sessionId)
      formData.append('message', text)
      if (selectedDifyConfigId.value) {
        formData.append('dify_config_id', selectedDifyConfigId.value)
      }
      selectedFiles.value.forEach(f => {
        formData.append('files', f)
      })

      response = await api.post('/assistant/chat/send_message/', formData, {
        timeout: 60000,
      })
    } else {
      response = await api.post('/assistant/chat/send_message/', {
        session_id: sessionId,
        message: text,
        dify_config_id: selectedDifyConfigId.value
      }, {
        timeout: 60000
      })
    }
    
    // 4. 替换临时消息为真实消息
    messages.value.pop() // 移除思考中
    messages.value.pop() // 移除临时用户消息（因为后端返回了完整的用户消息对象）
    
    messages.value.push(response.data.user_message)
    messages.value.push(response.data.assistant_message)
    
    clearSelectedFiles()
    
    // 更新会话的 conversation_id
    if (response.data.conversation_id && currentSession.value) {
      currentSession.value.conversation_id = response.data.conversation_id
    }
    
    // 如果是第一次对话，更新历史列表中的会话信息（比如 updated_at）
    if (!isFirstMessage) {
      const index = historySessions.value.findIndex(s => s.id === currentSession.value.id)
      if (index !== -1) {
        historySessions.value[index] = { ...currentSession.value, updated_at: new Date().toISOString() }
        // 重新排序（移到最前）
        const updatedSession = historySessions.value.splice(index, 1)[0]
        historySessions.value.unshift(updatedSession)
      }
    }
    
  } catch (error) {
    console.error('发送失败:', error)
    // 移除临时消息，显示错误
    messages.value.pop() // 移除思考中
    messages.value.pop() // 移除临时用户消息
    const err = error?.response?.data
    const msg = err?.error || error?.message || '发送失败，请重试'
    const detail = err?.detail || err?.workflow_detail || err?.chat_detail || err?.fallback_detail
    const hint = err?.hint
    if (typeof hint === 'string' && hint) {
      ElMessage.error(`${msg}：${detail || hint}`)
    } else if (typeof detail === 'string' && detail.length > 0 && detail.length < 800) {
      ElMessage.error(`${msg}：${detail}`)
    } else {
      ElMessage.error(msg)
    }
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

// 加载历史
const loadHistory = async () => {
  try {
    const response = await api.get('/assistant/sessions/')
    historySessions.value = response.data.results || response.data || []
  } catch (error) {
    console.error('加载历史失败:', error)
  }
}

// 拉取所有 Dify 配置，供对话时选择使用
const loadDifyConfigs = async () => {
  try {
    const response = await api.get('/assistant/config/dify/all/')
    const list = Array.isArray(response.data) ? response.data : []
    difyConfigs.value = list
    if (list.length > 0) {
      const withAppKey = list.filter(i => i.has_api_key)
      const active = withAppKey.find(i => i.is_active) || withAppKey[0] || list.find(i => i.is_active) || list[0]
      selectedDifyConfigId.value = active?.id ?? null
    } else {
      selectedDifyConfigId.value = null
    }
  } catch (error) {
    console.error('加载 Dify 配置失败:', error)
  }
}

onMounted(() => {
  loadDifyConfigs()
  loadHistory()
  startNewChat()
})
</script>

<style scoped lang="scss">
.assistant-layout {
  display: flex;
  height: 100vh;
  background: #fff;
  overflow: hidden;
}

/* 左侧侧边栏 */
.sidebar {
  width: 260px;
  background: #001529; /* 与主布局一致的深色背景 */
  border-right: 1px solid #1f1f1f;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  color: rgba(255, 255, 255, 0.65);
  
  .new-chat-btn-wrapper {
    padding: 20px;
    
    .new-chat-btn {
      width: 100%;
      height: 40px;
      border-radius: 4px; /* 稍微减小圆角以匹配整体风格 */
      font-size: 14px;
      background: #1890ff;
      border-color: #1890ff;
      color: white;
      
      &:hover {
        background: #40a9ff;
        border-color: #40a9ff;
      }
    }
  }
  
  .history-list {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    
    .history-label {
      padding: 0 20px 10px;
      font-size: 12px;
      color: rgba(255, 255, 255, 0.45);
    }
    
    .session-scroll-area {
      flex: 1;
      overflow-y: auto;
      padding: 0 10px;
      
      &::-webkit-scrollbar {
        width: 4px;
      }
      &::-webkit-scrollbar-thumb {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 2px;
      }
    }
    
    .session-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 10px 12px;
      margin-bottom: 4px;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s;
      color: rgba(255, 255, 255, 0.65);
      
      &:hover {
        background: rgba(255, 255, 255, 0.08);
        color: white;
        
        .session-actions {
          opacity: 1;
        }
      }
      
      &.active {
        background: #1890ff;
        color: white;
      }
      
      .session-title-wrapper {
        display: flex;
        align-items: center;
        gap: 8px;
        flex: 1;
        overflow: hidden;
        
        .chat-icon {
          font-size: 16px;
        }
        
        .session-title {
          font-size: 14px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
      
      .session-actions {
        opacity: 0;
        transition: opacity 0.2s;
        
        .delete-icon {
          font-size: 14px;
          color: rgba(255, 255, 255, 0.45);
          &:hover {
            color: #ff4d4f;
          }
        }
      }
    }
  }
  
  .user-profile {
    padding: 16px;
    border-top: 1px solid #1f1f1f;
    
    .user-info {
      display: flex;
      align-items: center;
      cursor: pointer;
      padding: 8px;
      border-radius: 4px;
      transition: all 0.2s;
      
      &:hover {
        background: rgba(255, 255, 255, 0.08);
      }
      
      .username {
        margin: 0 8px;
        font-size: 14px;
        color: rgba(255, 255, 255, 0.85);
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      
      .el-icon {
        color: rgba(255, 255, 255, 0.45);
      }
    }
  }
}

/* 右侧主内容区 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  background: #fff;
}

/* 场景1：欢迎页（新会话） */
.welcome-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding-bottom: 100px;
  
  .welcome-content {
    width: 100%;
    max-width: 800px;
    padding: 0 20px;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  
  .logo-area {
    text-align: center;
    margin-bottom: 40px;
    
    .logo-circle {
      width: 80px;
      height: 80px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 20px;
      box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
      
      .el-icon {
        font-size: 40px;
        color: white;
      }
    }
    
    h1 {
      font-size: 28px;
      color: #303133;
      margin: 0 0 10px;
    }
    
    p {
      color: #909399;
      font-size: 16px;
      margin: 0;
    }
  }
  
  .center-input-wrapper {
    width: 100%;
    position: relative;
    margin-bottom: 30px;

    .welcome-dify-select {
      width: 100%;
      margin-bottom: 14px;

      :deep(.el-select__wrapper) {
        border-radius: 16px;
      }

      .dify-config-warning {
        margin-top: 8px;
        font-size: 12px;
        color: #e6a23c;
        line-height: 1.5;
      }
    }
    
    .center-input {
      :deep(.el-textarea__inner) {
        border-radius: 16px;
        padding: 16px 50px 16px 20px;
        font-size: 16px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
        border: 1px solid #e4e7ed;
        transition: all 0.3s;
        
        &:focus {
          box-shadow: 0 4px 20px rgba(64, 158, 255, 0.15);
          border-color: #409eff;
        }
      }
    }
    
    .input-actions {
      position: absolute;
      right: 10px;
      bottom: 10px;
    }

    .welcome-upload-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-top: 8px;
      padding-right: 90px; // 给右下角发送按钮留空间
    }

    .welcome-upload-btn {
      height: 32px;
      padding: 0 12px;
      border-radius: 8px;
    }

    .welcome-selected-files-tip {
      font-size: 12px;
      color: #909399;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }
  
  .suggestion-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    justify-content: center;
    
    .chip {
      padding: 8px 16px;
      background: #f5f7fa;
      border-radius: 20px;
      font-size: 14px;
      color: #606266;
      cursor: pointer;
      transition: all 0.2s;
      
      &:hover {
        background: #e6f1fc;
        color: #409eff;
      }
    }
  }
}

/* 场景2：对话页 */
.chat-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  
  .chat-header {
    height: 60px;
    border-bottom: 1px solid #f0f2f5;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    flex-shrink: 0;
    
    .chat-title {
      font-size: 16px;
      font-weight: 600;
      color: #303133;
    }
    
    .chat-time {
      font-size: 12px;
      color: #909399;
    }

    .chat-header-right {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }
  }
  
  .messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    background: #fff;
    
    .message-row {
      display: flex;
      gap: 16px;
      margin-bottom: 24px;
      
      &.user {
        flex-direction: row-reverse;
        
        .message-bubble {
          background: #409eff;
          color: white;
          border-radius: 12px 12px 0 12px;
          
          :deep(pre) {
            background: rgba(0, 0, 0, 0.1);
          }
          
          :deep(code) {
            background: rgba(0, 0, 0, 0.1);
            color: #fff;
          }
        }
      }
      
      &.assistant {
        .message-bubble {
          background: #f5f7fa;
          color: #303133;
          border-radius: 12px 12px 12px 0;
        }
      }
      
      .avatar {
        flex-shrink: 0;
        margin-top: 2px;
        
        .user-avatar {
          background: #c0c4cc;
        }
        
        .ai-avatar {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
      }
      
      .message-bubble {
        max-width: 70%;
        padding: 12px 16px;
        font-size: 15px;
        line-height: 1.6;
        position: relative;
        
        .message-content {
          word-wrap: break-word;
          
          :deep(p) {
            margin: 0 0 8px 0;
            &:last-child { margin: 0; }
          }
          
          :deep(pre) {
            background: #282c34;
            color: #abb2bf;
            padding: 12px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 8px 0;
          }
          
          :deep(code) {
            font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
            font-size: 13px;
          }
        }
        
        .message-status {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 13px;
          color: #909399;
          
          .is-loading {
            animation: rotating 2s linear infinite;
          }
        }
      }
    }
  }
  
  .chat-footer {
    padding: 20px 24px;
    border-top: 1px solid #f0f2f5;
    background: #fff;
    
    .input-box {
      position: relative;
      border: 1px solid #e4e7ed;
      border-radius: 12px;
      padding: 8px;
      background: #fff;
      transition: all 0.3s;
      
      &:focus-within {
        border-color: #409eff;
        box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
      }
      
      :deep(.el-textarea__inner) {
        border: none;
        box-shadow: none;
        padding: 8px 50px 8px 8px;
        background: transparent;
      }
      
      .send-btn {
        position: absolute;
        right: 8px;
        bottom: 8px;
        width: 32px;
        height: 32px;
        padding: 0;
        border-radius: 8px;
      }

      .upload-btn {
        position: absolute;
        right: 48px;
        bottom: 8px;
        height: 32px;
        padding: 0 10px;
        border-radius: 8px;
      }

      .selected-files-tip {
        margin-top: 4px;
        font-size: 12px;
        color: #909399;
        padding-right: 100px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
    }
    
    .footer-tip {
      text-align: center;
      font-size: 12px;
      color: #c0c4cc;
      margin-top: 8px;
    }
  }
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>