<template>
  <div class="agent-view">
    <!-- 左侧：数字人形象 -->
    <div class="avatar-panel">
      <HermesAvatar
        :state="avatarState"
        :speak-text="speakText"
        @ready="onAvatarReady"
        @state-change="onAvatarStateChange"
      />
    </div>

    <!-- 右侧：对话区域 -->
    <div class="chat-panel">
    <!-- 顶部标题栏 -->
    <div class="agent-header">
      <div class="header-left">
        <el-icon class="header-icon"><MagicStick /></el-icon>
        <div>
          <span class="header-title">Hermes 质量数字人</span>
          <span class="header-sub">自然语言驱动测试全流程</span>
        </div>
      </div>
      <div class="header-actions">
        <el-tag v-if="loading" type="warning" effect="dark" size="small">
          <el-icon class="is-loading" style="margin-right:4px"><Loading /></el-icon>
          生成中
        </el-tag>
        <el-button v-if="loading" @click="stopRequest" :icon="CircleClose" type="danger" plain size="small" round>停止</el-button>
        <el-button @click="clearChat" :icon="Delete" plain size="small">清空对话</el-button>
      </div>
    </div>

    <!-- 消息区域 -->
    <div class="agent-messages" ref="messagesRef">
      <div v-if="messages.length === 0" class="empty-state">
        <el-icon class="empty-icon"><ChatRound /></el-icon>
        <p class="empty-title">和 Hermes 说点什么</p>
        <div class="suggestions">
          <el-button
            v-for="s in suggestions"
            :key="s"
            @click="sendMessage(s)"
            round
            plain
            size="default">
            {{ s }}
          </el-button>
        </div>
      </div>

      <template v-for="(msg, i) in messages" :key="i">
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="msg-row user">
          <div class="msg-avatar user-avatar">
            <el-icon><User /></el-icon>
          </div>
          <div class="msg-bubble user-bubble">{{ msg.content }}</div>
        </div>

        <!-- 助手消息 -->
        <div v-else-if="msg.role === 'assistant'" class="msg-row assistant">
          <div class="msg-avatar ai-avatar">
            <el-icon><MagicStick /></el-icon>
          </div>
          <div class="msg-content">
            <!-- 思考过程（暂时禁用，vLLM 流式 token 切得太碎体验差） -->
            <div v-if="false && msg.thoughtText" class="thought-block">
              <div class="thought-header" @click="msg.thoughtExpanded = !msg.thoughtExpanded">
                <el-icon class="thought-icon"><View /></el-icon>
                <span class="thought-title">思考过程</span>
                <el-tag size="small" type="info" effect="plain" round>{{ msg.thoughtText.length }} 字</el-tag>
                <el-icon class="expand-icon"><ArrowDown v-if="!msg.thoughtExpanded" /><ArrowUp v-else /></el-icon>
              </div>
              <div v-if="msg.thoughtExpanded" class="thought-body">
                <pre class="thought-text">{{ msg.thoughtText }}</pre>
              </div>
            </div>
            <!-- 工具调用过程 -->
            <template v-if="msg.toolCalls && msg.toolCalls.length">
              <div
                v-for="(tc, j) in msg.toolCalls"
                :key="j"
                class="tool-call-item">
                <div class="tool-call-header" @click="tc.expanded = !tc.expanded">
                  <el-icon class="tool-icon"><Tools /></el-icon>
                  <span class="tool-name">{{ tc.name }}</span>
                  <el-tag v-if="tc.executing" size="small" type="warning" effect="plain">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    <span style="margin-left:4px">执行中</span>
                  </el-tag>
                  <el-tag v-else-if="getToolBadge(tc)" :type="getToolBadge(tc).type" size="small" effect="dark">
                    {{ getToolBadge(tc).text }}
                  </el-tag>
                  <el-tag v-else size="small" :type="tc.result ? (tc.result.error ? 'danger' : 'success') : 'info'">
                    {{ tc.result ? (tc.result.error ? '失败' : '完成') : '等待中' }}
                  </el-tag>
                  <el-icon class="expand-icon"><ArrowDown v-if="!tc.expanded" /><ArrowUp v-else /></el-icon>
                </div>
                <div v-if="tc.expanded" class="tool-call-body">
                  <div class="tool-section">
                    <span class="tool-label">参数:</span>
                    <pre>{{ JSON.stringify(tc.arguments, null, 2) }}</pre>
                  </div>
                  <div v-if="tc.result" class="tool-section">
                    <span class="tool-label">结果:</span>
                    <div class="tool-result" v-html="renderToolResult(tc)"></div>
                  </div>
                </div>
              </div>
            </template>
            <!-- 文本回复 -->
            <div v-if="msg.content" class="msg-bubble ai-bubble" v-html="renderMarkdown(msg.content)"></div>
            <!-- 加载中 -->
            <div v-if="msg.loading" class="msg-loading">
              <el-icon class="loading-icon"><Loading /></el-icon>
              <span>{{ msg.loadingText || '思考中...' }}</span>
            </div>
          </div>
        </div>
      </template>
    </div>

    <!-- 输入区 -->
    <div class="agent-input">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        placeholder="输入你的需求，比如「查看所有项目」「帮我创建一个登录功能的测试用例」"
        @keydown.enter.exact.prevent="onEnter"
        :disabled="loading"
        resize="none" />
      <el-button
        type="primary"
        @click="sendMessage()"
        :loading="loading"
        :icon="Promotion"
        class="send-btn">
        发送
      </el-button>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import {
  MagicStick, ChatRound, User, Tools, ArrowDown, ArrowUp,
  Loading, Promotion, Delete, View, CircleClose,
} from '@element-plus/icons-vue'
import { agentChat } from '@/api/agent'
import HermesAvatar from '@/components/HermesAvatar.vue'

const STORAGE_KEY = 'hermes_chat_history'
const STORAGE_SCHEMA = 2  // v2: thinking 流式字段从 thoughts[] 改为 thoughtText(字符串)
const inputText = ref('')
const messages = ref([])
const loading = ref(false)
const messagesRef = ref(null)
let currentController = null  // 用于中断进行中的请求

// 数字人形象状态
const avatarState = ref('idle')
const speakText = ref('')

function onAvatarReady(ok) {
  console.log('[AgentView] HermesAvatar ready:', ok)
}

function onAvatarStateChange(state) {
  // 可以在这里记录状态变化日志
}

function stopRequest() {
  if (currentController) {
    currentController.abort()
    currentController = null
  }
  loading.value = false
  avatarState.value = 'idle'
  speakText.value = ''
  // 找到最后一条助手消息，标记为已中断
  for (let i = messages.value.length - 1; i >= 0; i--) {
    if (messages.value[i].role === 'assistant') {
      messages.value[i].loading = false
      if (!messages.value[i].content) {
        messages.value[i].content = '⏹ 已中断'
      } else {
        messages.value[i].content += '\n\n⏹ 已中断'
      }
      break
    }
  }
}

// 从 localStorage 恢复历史对话
function loadHistory() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const parsed = JSON.parse(saved)
      // schema 不匹配（升级）→ 清空重来
      if (parsed && parsed.__schema !== STORAGE_SCHEMA) {
        console.log('[Hermes] localStorage schema 升级，清空旧历史')
        localStorage.removeItem(STORAGE_KEY)
        return
      }
      if (Array.isArray(parsed.messages)) {
        messages.value = parsed.messages.map(m => ({
          ...m,
          // 重置临时状态
          loading: false,
          loadingText: '',
          // 兼容旧字段 thoughts[]：合并成 thoughtText
          thoughtText: m.thoughtText != null
            ? m.thoughtText
            : (Array.isArray(m.thoughts) ? m.thoughts.join('') : ''),
          thoughtExpanded: false,
          // toolCalls 恢复展开状态
          toolCalls: (m.toolCalls || []).map(tc => ({
            ...tc,
            expanded: false,
            executing: false,
          })),
        }))
      }
    }
  } catch (e) {
    // 解析失败忽略
  }
}

// 持久化历史对话（去掉临时状态，限制条数）
function saveHistory() {
  try {
    const toSave = {
      __schema: STORAGE_SCHEMA,
      messages: messages.value
        .filter(m => !m.loading) // 不保存正在加载的消息
        .slice(-50) // 最多保存最近50条
        .map(m => ({
          role: m.role,
          content: m.content || '',
          toolCalls: (m.toolCalls || []).map(tc => ({
            name: tc.name,
            arguments: tc.arguments,
            result: tc.result,
          })),
          thoughtText: m.thoughtText || '',
        })),
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  } catch (e) {
    // 存储满或其他错误，忽略
  }
}

onMounted(() => {
  loadHistory()
  window.addEventListener('beforeunload', saveHistory)
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', saveHistory)
})

watch(messages, () => {
  saveHistory()
}, { deep: true })

const suggestions = [
  '查看所有项目',
  '帮我查一下系统里有哪些测试用例',
  '生成5个测试用的手机号',
  '查看最近的API测试报告',
]

function renderMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

function onEnter() {
  if (!loading.value) sendMessage()
}

// 给关键工具加特殊徽章（让用户一眼看到干了什么大事）
const TOOL_BADGES = {
  search_knowledge_base: { text: '已检索知识库', type: 'success' },
  chat_ai_evaluator: { text: '已咨询 AI 评测师', type: 'success' },
  run_ui_test_suite: { text: '已执行 UI 套件', type: 'primary' },
  run_app_test_suite: { text: '已执行 APP 套件', type: 'primary' },
  execute_api_suite: { text: '已执行接口套件', type: 'primary' },
  execute_api_request: { text: '已执行接口', type: 'primary' },
  ai_generate_testcases: { text: '已启动 AI 用例生成', type: 'primary' },
  generate_test_data: { text: '已生成测试数据', type: 'success' },
  create_testcase: { text: '已创建用例', type: 'success' },
  update_testcase: { text: '已更新用例', type: 'success' },
  delete_testcase: { text: '已删除用例', type: 'danger' },
  create_review: { text: '已创建评审', type: 'success' },
  submit_review_decision: { text: '已提交评审', type: 'success' },
  create_test_plan: { text: '已创建计划', type: 'success' },
  create_test_suite: { text: '已创建套件', type: 'success' },
  create_version: { text: '已创建版本', type: 'success' },
  create_project: { text: '已创建项目', type: 'success' },
  start_test_run: { text: '已启动执行', type: 'primary' },
  get_project_coverage: { text: '已生成覆盖度报告', type: 'success' },
  get_dashboard_stats: { text: '已获取仪表盘', type: 'success' },
}
function getToolBadge(tc) {
  if (!tc.result) return null  // 还在执行中交给其他分支
  if (tc.result.error) return null  // 失败用红色 tag
  return TOOL_BADGES[tc.name] || null
}

// 工具结果的美化渲染：知识库检索走"按段落工整展示"，其他工具回退到 JSON
function escHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderKbResult(r) {
  // r = { dataset, document, score, paragraphs: [...], content: '...' }
  const dataset = escHtml(r.dataset || '知识库')
  const doc = escHtml(r.document || '')
  const score = (typeof r.score === 'number') ? `相关度 ${r.score}` : ''
  // 优先用后端切好的 paragraphs，否则按换行/句号再切一次兜底
  let paras = Array.isArray(r.paragraphs) && r.paragraphs.length
    ? r.paragraphs
    : (r.content || '').split(/\n|(?<=[。！？；!?;])\s*/).filter(s => s && s.trim())
  paras = paras.filter(p => p && p.trim()).slice(0, 8)  // 单条最多 8 段
  const body = paras.length
    ? `<ol class="kb-paras">${paras.map(p => `<li>${escHtml(p.trim())}</li>`).join('')}</ol>`
    : `<div class="kb-empty">(无内容)</div>`
  const meta = `<div class="kb-meta">📚 ${dataset}${doc ? ` · 📄 ${doc}` : ''}${score ? ` · ⭐ ${score}` : ''}</div>`
  return `<div class="kb-card">${meta}${body}</div>`
}

function renderToolResult(tc) {
  const r = tc.result
  if (!r) return ''
  // 失败
  if (r.error) {
    return `<div class="tool-result-error">❌ ${escHtml(r.error)}</div>`
  }
  // 知识库检索：按段落工整展示
  if (tc.name === 'search_knowledge_base' && Array.isArray(r.results) && r.results.length) {
    const summary = `<div class="kb-summary">🔎 关键词：<b>${escHtml(r.query || '')}</b> · 命中 <b>${r.total ?? r.results.length}</b> 条 · 检索知识库：${escHtml((r.datasets_searched || []).join('、') || '-')}</div>`
    const cards = r.results.map(renderKbResult).join('')
    const partial = (r.partial_errors && r.partial_errors.length)
      ? `<details class="kb-warn"><summary>部分检索方法失败（已自动回退）</summary><pre>${escHtml(r.partial_errors.join('\n'))}</pre></details>`
      : ''
    return summary + cards + partial
  }
  // 其他工具结果：JSON 兜底（但格式化）
  return `<pre class="tool-result-json">${escHtml(JSON.stringify(r, null, 2))}</pre>`
}

async function sendMessage(text) {
  const content = (text || inputText.value).trim()
  if (!content || loading.value) return

  inputText.value = ''
  loading.value = true
  avatarState.value = 'thinking'

  // 添加用户消息
  messages.value.push({ role: 'user', content })

  // 添加助手消息占位
  const assistantMsg = {
    role: 'assistant',
    content: '',
    toolCalls: [],
    thoughtText: '',
    thoughtExpanded: true,  // 默认展开思考过程，让用户实时看到 AI 思路
    loading: true,
    loadingText: '思考中...',
  }
  messages.value.push(assistantMsg)

  await scrollToBottom()

  // 构建历史
  const history = messages.value
    .filter(m => m !== assistantMsg)
    .slice(-10)
    .map(m => ({
      role: m.role,
      content: m.content || (m.toolCalls?.length ? '[调用了工具]' : ''),
    }))

  // 创建 abort controller（点停止时可中断）
  currentController = new AbortController()

  // 看门狗：90 秒内没有任何 SSE 事件就视为卡死，主动 abort 并提示
  let watchdog = null
  const resetWatchdog = () => {
    if (watchdog) clearTimeout(watchdog)
    watchdog = setTimeout(() => {
      if (currentController) {
        currentController.abort()
      }
      assistantMsg.content = assistantMsg.content
        ? `${assistantMsg.content}\n\n⏱ 数字人长时间无响应（90s 无新事件），已自动终止。请检查 LLM 服务或 Dify 配置。`
        : '⏱ 数字人长时间无响应（90s 无新事件），已自动终止。请检查 LLM 服务或 Dify 配置。'
      assistantMsg.loading = false
      loading.value = false
      ElMessage.error('数字人无响应，建议重试')
    }, 90000)
  }
  resetWatchdog()

  try {
    const reader = await agentChat(content, history, currentController.signal)
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      resetWatchdog()  // 每收到一个 chunk 就重置看门狗

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (!data) continue

        try {
          const event = JSON.parse(data)
          handleEvent(event, assistantMsg)
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      // 用户主动停止 或 看门狗触发，UI 已被处理
    } else {
      assistantMsg.content = `❌ ${err.message || '请求失败'}`
      ElMessage.error(err.message || '数字人请求失败')
    }
  } finally {
    if (watchdog) clearTimeout(watchdog)
    watchdog = null
    currentController = null
    assistantMsg.loading = false
    loading.value = false
    // 回到待机状态（除非已经是 error）
    if (avatarState.value !== 'error') {
      avatarState.value = 'idle'
    }
    speakText.value = ''
    await scrollToBottom()
    // 流式结束/中断后立刻持久化，避免用户刷新时最后一条未保存
    saveHistory()
  }
}

function handleEvent(event, msg) {
  switch (event.type) {
    case 'thinking':
      // 流式累加到一个字符串（不切碎），避免每段 1-2 字符被切成一堆 step
      if (msg.thoughtText == null) msg.thoughtText = ''
      msg.thoughtText += event.content
      // 有思考内容时自动展开
      msg.thoughtExpanded = true
      // header 状态条只显示思考的尾部（一句话），不刷整段
      const tail = msg.thoughtText.slice(-60).replace(/^[\s,，。.!?！？、]*/, '')
      msg.loadingText = '思考中: ' + (tail || '...')
      avatarState.value = 'thinking'
      break
    case 'tool_call':
      msg.toolCalls.push({
        name: event.name,
        arguments: event.arguments,
        result: null,
        expanded: false,
        executing: false,
      })
      msg.loadingText = `调用工具: ${event.name}`
      // 保持思考过程展开状态，让用户能连续看到"推理→调工具→拿到结果"的完整链路
      avatarState.value = 'working'
      break
    case 'executing':
      // 工具正在执行中（同步调用可能耗时长），标记最后一个工具为 executing
      if (msg.toolCalls.length > 0) {
        msg.toolCalls[msg.toolCalls.length - 1].executing = true
      }
      msg.loadingText = `执行工具: ${event.name || msg.toolCalls[msg.toolCalls.length - 1]?.name}...`
      avatarState.value = 'working'
      break
    case 'tool_result':
      if (msg.toolCalls.length > 0) {
        const last = msg.toolCalls[msg.toolCalls.length - 1]
        last.result = event.result
        last.executing = false
      }
      msg.loadingText = '继续推理...'
      avatarState.value = 'thinking'
      break
    case 'message':
      msg.content += event.content
      msg.loading = false
      avatarState.value = 'speaking'
      // TTS 朗读回复（只有开启时才会发声）
      speakText.value = event.content
      break
    case 'error':
      msg.content = `❌ ${event.content}`
      msg.loading = false
      avatarState.value = 'error'
      speakText.value = ''
      break
    case 'done':
      msg.loading = false
      // 兜底：如果整个流结束后没有任何内容，给出明确提示，避免空白气泡
      if (!msg.content && msg.toolCalls.length === 0) {
        msg.content = '我这边没有拿到可直接回答的内容，可能是问题信息不够明确。你可以补充具体想查的测试类型或相关 ID，我帮你进一步定位。'
      }
      // 延迟回到 idle，让说话动画播完
      setTimeout(() => {
        if (avatarState.value !== 'error') {
          avatarState.value = 'idle'
        }
      }, 1000)
      speakText.value = ''
      break
  }
  scrollToBottom()
}

async function scrollToBottom() {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

function clearChat() {
  messages.value = []
  inputText.value = ''
  loading.value = false
  avatarState.value = 'idle'
  speakText.value = ''
  localStorage.removeItem(STORAGE_KEY)
}
</script>

<style scoped>
.agent-view {
  display: flex;
  height: calc(100vh - 80px);
  background: #f5f7fa;
  overflow: hidden;
  min-height: 0;
}

/* 左侧形象面板 */
.avatar-panel {
  width: 300px;
  flex: 0 0 300px;          /* 关键：固定 300px 宽，不参与 flex 拉伸 */
  height: 100%;              /* 关键：高度跟父级，不无限撑开 */
  min-height: 0;             /* 防止 flex item 被内容撑大 */
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
  border-right: 1px solid #1a1a2e;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 右侧对话面板 */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.agent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-icon {
  font-size: 28px;
  color: #409eff;
}
.header-title {
  font-size: 18px;
  font-weight: 600;
  margin-right: 8px;
}
.header-sub {
  font-size: 13px;
  color: #909399;
}

.agent-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
}
.empty-icon {
  font-size: 64px;
  color: #c0c4cc;
}
.empty-title {
  font-size: 18px;
  color: #606266;
  margin: 0;
}
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: center;
  max-width: 600px;
}

.msg-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  max-width: 85%;
}
.msg-row.user {
  margin-left: auto;
  flex-direction: row-reverse;
}
.msg-row.assistant {
  margin-right: auto;
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
  color: #fff;
}
.user-avatar { background: #409eff; }
.ai-avatar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }

.msg-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

/* 思考过程 */
.thought-block {
  background: #f0f5ff;
  border: 1px solid #d6e4ff;
  border-radius: 8px;
  overflow: hidden;
  font-size: 13px;
  margin-bottom: 4px;
}
.thought-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  user-select: none;
}
.thought-header:hover { background: #e0e8ff; }
.thought-icon { color: #79bbff; font-size: 16px; }
.thought-title { font-weight: 500; color: #606266; }
.thought-body {
  padding: 4px 12px 10px;
  border-top: 1px solid #d6e4ff;
}
.thought-item {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  line-height: 1.5;
}
.thought-step {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #79bbff;
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.thought-text {
  color: #606266;
  word-break: break-word;
  white-space: pre-wrap;
  margin: 0;
  font-family: inherit;
  font-size: 13px;
  line-height: 1.6;
  max-height: 360px;
  overflow-y: auto;
}

.msg-bubble {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.user-bubble {
  background: #409eff;
  color: #fff;
  border-top-right-radius: 4px;
}
.ai-bubble {
  background: #fff;
  color: #303133;
  border: 1px solid #e4e7ed;
  border-top-left-radius: 4px;
}
.ai-bubble :deep(code) {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.tool-call-item {
  background: #f8f9fb;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  font-size: 13px;
}
.tool-call-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}
.tool-call-header:hover { background: #ecf0f5; }
.tool-icon { color: #e6a23c; }
.tool-name { font-weight: 500; }
.expand-icon { margin-left: auto; color: #909399; }
.tool-call-body {
  padding: 8px 12px;
  border-top: 1px solid #e4e7ed;
}
.tool-section { margin-bottom: 8px; }
.tool-label {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}
.tool-call-body pre {
  margin: 4px 0 0;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  font-size: 12px;
  overflow-x: auto;
  max-height: 200px;
  overflow-y: auto;
}

/* 知识库检索结果 — 工整段落卡片 */
.tool-result { margin-top: 4px; font-size: 13px; line-height: 1.7; color: #303133; }
.kb-summary {
  padding: 6px 10px;
  background: #ecf5ff;
  border-left: 3px solid #409eff;
  border-radius: 3px;
  margin-bottom: 8px;
  color: #303133;
}
.kb-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 8px;
  background: #fafbfc;
}
.kb-meta {
  font-size: 12px;
  color: #606266;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px dashed #e4e7ed;
}
.kb-paras {
  margin: 4px 0 0;
  padding-left: 22px;
}
.kb-paras li {
  margin: 4px 0;
  word-break: break-word;
  white-space: pre-wrap;
}
.kb-empty { color: #909399; font-style: italic; }
.kb-warn { margin-top: 8px; font-size: 12px; color: #e6a23c; }
.kb-warn summary { cursor: pointer; }
.kb-warn pre { background: #fdf6ec; padding: 6px 8px; border-radius: 3px; }
.tool-result-error {
  padding: 6px 10px;
  background: #fef0f0;
  border-left: 3px solid #f56c6c;
  border-radius: 3px;
  color: #f56c6c;
}
.tool-result-json {
  margin: 4px 0 0;
  padding: 8px;
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  font-size: 12px;
  max-height: 240px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.msg-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
  font-size: 13px;
  padding: 4px 0;
}
.loading-icon {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.agent-input {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  align-items: flex-end;
}
.agent-input :deep(.el-textarea__inner) {
  border-radius: 8px;
}
.send-btn {
  height: 56px;
  border-radius: 8px;
}
</style>
