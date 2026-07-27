import api from '@/utils/api'

// Agent 对话使用 SSE 流式，需要用 fetch 而非 axios
export async function agentChat(message, history = [], signal, options = {}) {
  // 从 Pinia store 拿 token（与 axios 拦截器保持一致）
  const token = localStorage.getItem('access_token') || ''
  const body = {
    message,
    history,
    conversation_id: options.conversation_id || null,
    skill_id: options.skill_id || null,
    images: options.images || [],
  }
  const resp = await fetch('/api/assistant/agent/chat/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
  })

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    throw new Error(err.detail || `HTTP ${resp.status}`)
  }

  return resp.body.getReader()
}

// 上传 Hermes 会话图片
export function uploadHermesImage(conversationId, file) {
  const formData = new FormData()
  formData.append('image', file)
  formData.append('name', file.name)
  if (conversationId) {
    formData.append('conversation_id', conversationId)
  }
  return api.post('/assistant/hermes/upload-image/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// Hermes 会话 CRUD
export function getHermesConversations(params) {
  return api.get('/assistant/hermes/conversations/', { params })
}

export function createHermesConversation(data) {
  return api.post('/assistant/hermes/conversations/', data)
}

export function deleteHermesConversation(id) {
  return api.delete(`/assistant/hermes/conversations/${id}/`)
}

export function updateHermesConversationTitle(id, title) {
  return api.post(`/assistant/hermes/conversations/${id}/update_title/`, { title })
}

export function clearHermesConversationMessages(id) {
  return api.delete(`/assistant/hermes/conversations/${id}/clear_messages/`)
}

// Hermes 数字人配置
export function getHermesConfig() {
  return api.get('/assistant/hermes/config/active/')
}

export function getHermesConfigs() {
  return api.get('/assistant/hermes/config/')
}

export function createHermesConfig(data) {
  return api.post('/assistant/hermes/config/', data)
}

export function updateHermesConfig(id, data) {
  return api.put(`/assistant/hermes/config/${id}/`, data)
}

export function deleteHermesConfig(id) {
  return api.delete(`/assistant/hermes/config/${id}/`)
}
