/**
 * 知识库对话 / KB Chat API
 */
import request from '@/utils/api'
import { useUserStore } from '@/stores/user'

export function getKbChatSessions() {
  return request({
    url: '/requirement-analysis/kb-chat/sessions/',
    method: 'get'
  })
}

export function createKbChatSession(data) {
  return request({
    url: '/requirement-analysis/kb-chat/sessions/',
    method: 'post',
    data
  })
}

export function updateKbChatSession(sessionId, data) {
  return request({
    url: `/requirement-analysis/kb-chat/sessions/${sessionId}/`,
    method: 'patch',
    data
  })
}

export function deleteKbChatSession(sessionId) {
  return request({
    url: `/requirement-analysis/kb-chat/sessions/${sessionId}/`,
    method: 'delete'
  })
}

export function getKbChatMessages(sessionId) {
  return request({
    url: `/requirement-analysis/kb-chat/sessions/${sessionId}/messages/`,
    method: 'get'
  })
}

export function generateTestcasesFromKbChat(sessionId, data = {}) {
  return request({
    url: `/requirement-analysis/kb-chat/sessions/${sessionId}/generate-testcases/`,
    method: 'post',
    data,
    timeout: 60000
  })
}

/**
 * 流式发送知识库对话消息（SSE over fetch）
 */
export async function streamKbChatMessage(payload, callbacks = {}) {
  const { onChunk, onDone, onError } = callbacks
  const userStore = useUserStore()
  const token = userStore.accessToken
  if (!token) {
    const error = new Error('未登录或登录已过期，请重新登录')
    onError?.(error)
    throw error
  }

  const resp = await fetch('/api/requirement-analysis/kb-chat/send_message/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  })

  if (!resp.ok) {
    let detail = `请求失败 (${resp.status})`
    try {
      const err = await resp.json()
      detail = err.detail || err.error || detail
    } catch (_) {
      /* ignore */
    }
    const error = new Error(detail)
    onError?.(error)
    throw error
  }

  const reader = resp.body?.getReader()
  if (!reader) {
    const error = new Error('浏览器不支持流式响应')
    onError?.(error)
    throw error
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let donePayload = null
  let streamError = null

  const parseSseLine = (line) => {
    const trimmed = (line || '').trim()
    if (!trimmed.startsWith('data:')) return
    const jsonText = trimmed.slice(5).trim()
    if (!jsonText) return
    let event
    try {
      event = JSON.parse(jsonText)
    } catch (_) {
      return
    }
    if (event.type === 'chunk') {
      onChunk?.(event.content || '')
    } else if (event.type === 'done') {
      donePayload = event
    } else if (event.type === 'error') {
      streamError = new Error(event.detail || '对话失败')
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parts = buffer.split(/\r?\n/)
    buffer = parts.pop() || ''
    for (const line of parts) {
      parseSseLine(line)
    }
  }

  if (buffer.trim()) {
    parseSseLine(buffer)
  }

  if (streamError) {
    onError?.(streamError)
    throw streamError
  }

  if (donePayload) {
    onDone?.(donePayload)
  }
  return donePayload
}

export {
  getDifyKnowledgeBases,
  getDifyKnowledgeBaseDocuments
} from './requirement-analysis'
