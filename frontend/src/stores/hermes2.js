import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getHermesConversations,
  createHermesConversation,
  deleteHermesConversation,
  updateHermesConversationTitle,
  clearHermesConversationMessages,
  getHermesConfig,
} from '@/api/agent'
import { ElMessage } from 'element-plus'

function withTimeout(promise, ms, msg = '请求超时') {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error(msg)), ms))
  ])
}

export const useHermesStore = defineStore('hermes', () => {
  // 会话列表
  const conversations = ref([])
  const currentConversationId = ref(null)
  const loadingConversations = ref(false)

  // 当前会话消息
  const messages = ref([])
  const loading = ref(false)

  // 数字人全局配置
  const hermesConfig = ref(null)

  // 数字人形象状态（由 HermesChatView 驱动，layout sidebar 底部的 HermesAvatar 读取）
  const avatarState = ref('idle')
  const speakText = ref('')
  const avatarReady = ref(false)

  const currentConversation = computed(() =>
    conversations.value.find(c => c.id === currentConversationId.value)
  )

  async function loadHermesConfig() {
    try {
      const res = await getHermesConfig()
      hermesConfig.value = res.data
    } catch (err) {
      // 404 表示未配置，静默忽略
      if (err?.response?.status !== 404) {
        console.error('加载 Hermes 配置失败', err)
      }
      hermesConfig.value = null
    }
  }

  async function loadConversations(timeoutMs = 10000) {
    loadingConversations.value = true
    try {
      const res = await withTimeout(getHermesConversations(), timeoutMs, '加载会话列表超时')
      // 兼容 DRF 分页格式 {count, results} 与直接数组
      const list = Array.isArray(res.data) ? res.data : (res.data?.results || [])
      conversations.value = list
    } catch (err) {
      ElMessage.error(err?.message || '加载会话列表失败')
      console.error(err)
    } finally {
      loadingConversations.value = false
    }
  }

  async function createConversation(title = '') {
    try {
      const res = await createHermesConversation({ title })
      const conversation = res.data
      conversations.value.unshift(conversation)
      currentConversationId.value = conversation.id
      messages.value = []
      return conversation
    } catch (err) {
      ElMessage.error('创建会话失败')
      console.error(err)
      return null
    }
  }

  function selectConversation(id) {
    currentConversationId.value = id
    const conversation = conversations.value.find(c => c.id === id)
    if (conversation && Array.isArray(conversation.messages)) {
      messages.value = conversation.messages.map(m => ({
        ...m,
        thoughtExpanded: false,
        toolCalls: (m.tool_calls || []).map(tc => ({ ...tc, expanded: false, executing: false })),
      }))
    } else {
      messages.value = []
    }
  }

  async function removeConversation(id) {
    try {
      await deleteHermesConversation(id)
      conversations.value = conversations.value.filter(c => c.id !== id)
      if (currentConversationId.value === id) {
        currentConversationId.value = null
        messages.value = []
      }
    } catch (err) {
      ElMessage.error('删除会话失败')
      console.error(err)
    }
  }

  async function renameConversation(id, title) {
    try {
      const res = await updateHermesConversationTitle(id, title)
      const idx = conversations.value.findIndex(c => c.id === id)
      if (idx !== -1) {
        conversations.value[idx] = { ...conversations.value[idx], ...res.data }
      }
    } catch (err) {
      ElMessage.error('重命名失败')
      console.error(err)
    }
  }

  async function clearConversation(id) {
    try {
      await clearHermesConversationMessages(id)
      const conversation = conversations.value.find(c => c.id === id)
      if (conversation) {
        conversation.messages = []
      }
      if (currentConversationId.value === id) {
        messages.value = []
      }
    } catch (err) {
      ElMessage.error('清空会话失败')
      console.error(err)
    }
  }

  function appendUserMessage(content) {
    messages.value.push({ role: 'user', content })
  }

  function createAssistantPlaceholder() {
    const assistantMsg = {
      role: 'assistant',
      content: '',
      toolCalls: [],
      thoughtText: '',
      thoughtExpanded: true,
      loading: true,
      loadingText: '思考中...',
    }
    messages.value.push(assistantMsg)
    return assistantMsg
  }

  function setLoading(value) {
    loading.value = value
  }

  function setAvatarState(state) {
    avatarState.value = state
  }

  function setSpeakText(text) {
    speakText.value = text
  }

  function setAvatarReady(ok) {
    avatarReady.value = ok
  }

  return {
    conversations,
    currentConversationId,
    currentConversation,
    loadingConversations,
    messages,
    loading,
    hermesConfig,
    avatarState,
    speakText,
    avatarReady,
    loadHermesConfig,
    loadConversations,
    createConversation,
    selectConversation,
    removeConversation,
    renameConversation,
    clearConversation,
    appendUserMessage,
    createAssistantPlaceholder,
    setLoading,
    setAvatarState,
    setSpeakText,
    setAvatarReady,
  }
}
