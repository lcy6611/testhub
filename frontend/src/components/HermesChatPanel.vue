<template>
  <div class="chat-panel" :class="{ 'is-compact': compact }">
    <!-- 顶部标题栏 -->
    <div
      ref="headerRef"
      class="agent-header"
      :class="{ 'is-hover': headerHover, 'is-alert': loading }"
      @mouseenter="onHeaderEnter"
      @mouseleave="onHeaderLeave">
      <!-- 背景：觉醒之眼 HUD -->
      <div class="header-hud" aria-hidden="true">
        <div class="hud-grid"></div>
        <div class="hud-scanline"></div>
        <div class="hud-corner hud-tl"></div>
        <div class="hud-corner hud-tr"></div>
        <div class="hud-corner hud-bl"></div>
        <div class="hud-corner hud-br"></div>
        <div class="hud-lock" v-if="loading"></div>
        <svg class="bg-eyes-svg" viewBox="0 0 320 120" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <filter id="eye-glow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="6" result="blur1" />
              <feGaussianBlur stdDeviation="14" result="blur2" />
              <feGaussianBlur stdDeviation="28" result="blur3" />
              <feMerge>
                <feMergeNode in="blur3" />
                <feMergeNode in="blur2" />
                <feMergeNode in="blur1" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="pupil-glow" x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur stdDeviation="3" result="blur1" />
              <feGaussianBlur stdDeviation="8" result="blur2" />
              <feMerge>
                <feMergeNode in="blur2" />
                <feMergeNode in="blur1" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <radialGradient id="sclera-gradient" cx="50%" cy="55%" r="55%" fx="40%" fy="45%">
              <stop offset="0%" stop-color="#fffef5" />
              <stop offset="30%" stop-color="#fff5c2" />
              <stop offset="70%" stop-color="#ffd166" />
              <stop offset="100%" stop-color="#e69500" />
            </radialGradient>
            <radialGradient id="iris-gradient" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="#ff5e00" />
              <stop offset="55%" stop-color="#d60000" />
              <stop offset="100%" stop-color="#800000" />
            </radialGradient>
            <radialGradient id="iris-blue-gradient" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="#bfeaff" />
              <stop offset="55%" stop-color="#4db4ff" />
              <stop offset="100%" stop-color="#0a4f9c" />
            </radialGradient>
            <linearGradient id="eyelid-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="#0a0a0a" />
              <stop offset="100%" stop-color="#1a0505" />
            </linearGradient>
            <clipPath id="left-eye-clip">
              <path d="M132,74 C98,54 58,46 18,50 C58,80 98,80 132,74 Z" />
            </clipPath>
            <clipPath id="right-eye-clip">
              <path d="M188,74 C222,54 262,46 302,50 C262,80 222,80 188,74 Z" />
            </clipPath>
          </defs>

          <!-- 左眼眶底层（眼窝黑 + 外框） -->
          <g class="eye-socket left">
            <path class="socket-shape" d="M134,74 C98,54 56,46 14,54 C56,84 98,84 134,74 Z" />
            <rect class="eye-dark" x="2" y="20" width="140" height="80" />
          </g>
          <!-- 右眼眶底层 -->
          <g class="eye-socket right">
            <path class="socket-shape" d="M186,74 C222,54 264,46 306,54 C264,84 222,84 186,74 Z" />
            <rect class="eye-dark" x="178" y="20" width="140" height="80" />
          </g>

          <!-- 发光眼白 + 瞳孔：随鼠标注视移动 -->
          <g class="eye-gaze" :transform="'translate(' + eyeLook.x + ',' + eyeLook.y + ')'">
            <g clip-path="url(#left-eye-clip)">
              <!-- 战斗眼白：浅黄白发光 -->
              <path class="sclera" d="M132,74 C98,54 58,46 18,50 C58,80 98,80 132,74 Z" fill="url(#sclera-gradient)" filter="url(#eye-glow)" opacity="0.95" />
              <g class="iris-group">
                <!-- 红色虹膜 -->
                <ellipse cx="70" cy="63" rx="21" ry="15" fill="url(#iris-gradient)" filter="url(#pupil-glow)" />
                <!-- 黑色竖瞳 -->
                <ellipse cx="70" cy="63" rx="6.5" ry="14" fill="#000000" />
                <!-- 高光 -->
                <ellipse cx="62" cy="55" rx="9" ry="5.5" fill="#ffffff" opacity="0.6" filter="url(#pupil-glow)" />
                <circle cx="76" cy="69" r="2.5" fill="#ffffff" opacity="0.85" />
              </g>
            </g>
            <g clip-path="url(#right-eye-clip)">
              <path class="sclera" d="M188,74 C222,54 262,46 302,50 C262,80 222,80 188,74 Z" fill="url(#sclera-gradient)" filter="url(#eye-glow)" opacity="0.95" />
              <g class="iris-group iris-group--r">
                <ellipse cx="250" cy="63" rx="21" ry="15" fill="url(#iris-gradient)" filter="url(#pupil-glow)" />
                <ellipse cx="250" cy="63" rx="6.5" ry="14" fill="#000000" />
                <ellipse cx="242" cy="55" rx="9" ry="5.5" fill="#ffffff" opacity="0.6" filter="url(#pupil-glow)" />
                <circle cx="256" cy="69" r="2.5" fill="#ffffff" opacity="0.85" />
              </g>
            </g>
          </g>

          <!-- 上眼睑红色战斗眼线 -->
          <path class="eyeliner" d="M136,74 C98,46 54,40 12,50" fill="none" />
          <path class="eyeliner" d="M184,74 C222,46 266,40 308,50" fill="none" />

          <!-- 眼皮（顶层，偶尔覆盖） -->
          <g clip-path="url(#left-eye-clip)">
            <path class="eyelid" d="M132,74 C98,54 58,46 18,50 C58,80 98,80 132,74 Z" fill="url(#eyelid-gradient)" />
          </g>
          <g clip-path="url(#right-eye-clip)">
            <path class="eyelid eyelid--r" d="M188,74 C222,54 262,46 302,50 C262,80 222,80 188,74 Z" fill="url(#eyelid-gradient)" />
          </g>

          <!-- 眉骨阴影 -->
          <path class="brow-bar" d="M0,42 Q68,18 138,42 L136,48 Q68,24 2,48 Z" />
          <path class="brow-bar" d="M320,42 Q252,18 182,42 L184,48 Q252,24 318,48 Z" />
        </svg>
      </div>

      <div class="header-left">
        <div>
          <span class="header-title">Hermes 助手</span>
          <span v-if="!compact" class="header-sub">自然语言驱动测试全流程</span>
        </div>
      </div>
      <div class="header-actions">
        <el-tag v-if="loading" type="warning" effect="dark" size="small">
          <el-icon class="is-loading" style="margin-right:4px"><Loading /></el-icon>
          生成中
        </el-tag>
        <el-button v-if="loading" @click="stopRequest" :icon="CircleClose" type="danger" plain size="small" round>停止</el-button>
        <el-button :icon="Plus" plain size="small" @click="onNewConversation">新对话</el-button>
        <el-button @click="clearCurrentChat" :icon="Delete" plain size="small">清空</el-button>
        <el-button v-if="closable" @click="emit('close')" :icon="Close" plain size="small" circle title="关闭" />
      </div>
    </div>

    <!-- 消息区域 -->
    <div class="agent-messages" ref="messagesRef" @scroll="onMessagesScroll">
      <div v-if="hermesStore.messages.length === 0" class="empty-state">
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

      <template v-for="(msg, i) in hermesStore.messages" :key="i">
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
            <!-- 思考过程 -->
            <div v-if="msg.thoughtText" class="thought-block">
              <div class="thought-header" @click="msg.thoughtExpanded = !msg.thoughtExpanded">
                <el-icon class="thought-icon"><MagicStick /></el-icon>
                <span class="thought-title">思考过程</span>
                <el-tag size="small" type="info" effect="plain">{{ msg.thoughtText.length }} 字</el-tag>
                <el-icon class="expand-icon thought-expand"><ArrowDown v-if="!msg.thoughtExpanded" /><ArrowUp v-else /></el-icon>
              </div>
              <div v-show="msg.thoughtExpanded" class="thought-body" v-html="renderMarkdown(msg.thoughtText)"></div>
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
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onUpdated, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  MagicStick, ChatRound, User, Tools, ArrowDown, ArrowUp,
  Loading, Promotion, Delete, CircleClose, Plus, Close,
} from '@element-plus/icons-vue'
import { agentChat } from '@/api/agent'
import { useHermesStore } from '@/stores/hermes'
import * as echarts from 'echarts'

const props = defineProps({
  compact: { type: Boolean, default: false },
  closable: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const hermesStore = useHermesStore()
const inputText = ref('')
const loading = ref(false)
const messagesRef = ref(null)
let currentController = null
let userScrolledUp = false

// 表头交互：鼠标注视 + 悬停警戒
const headerRef = ref(null)
const headerHover = ref(false)
const eyeLook = ref({ x: 0, y: 0 })
// 跟随鼠标：整个窗口内移动都让眼睛朝鼠标方向注视（视口坐标）
function onWindowMove(e) {
  const el = headerRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const nx = Math.max(-1, Math.min(1, (e.clientX - (rect.left + rect.width / 2)) / (rect.width / 2)))
  const ny = Math.max(-1, Math.min(1, (e.clientY - (rect.top + rect.height / 2)) / (rect.height / 2)))
  eyeLook.value = { x: Math.round(nx * 16), y: Math.round(ny * 9) }
}
function onHeaderLeave() {
  headerHover.value = false
}
function onHeaderEnter() {
  headerHover.value = true
}

function onMessagesScroll() {
  const el = messagesRef.value
  if (!el) return
  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 100
  if (atBottom) {
    userScrolledUp = false
  } else if (el.scrollHeight > el.clientHeight + 100) {
    userScrolledUp = true
  }
}

function onNewConversation() {
  hermesStore.createConversation()
}

function clearCurrentChat() {
  const id = hermesStore.currentConversationId
  if (!id) {
    hermesStore.messages = []
    return
  }
  ElMessageBox.confirm('确定清空当前会话的所有消息？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    hermesStore.clearConversation(id)
  }).catch(() => {})
}

function stopRequest() {
  if (currentController) {
    currentController.abort()
    currentController = null
  }
  loading.value = false
  hermesStore.setAvatarState('idle')
  hermesStore.setSpeakText('')
  for (let i = hermesStore.messages.length - 1; i >= 0; i--) {
    if (hermesStore.messages[i].role === 'assistant') {
      hermesStore.messages[i].loading = false
      if (!hermesStore.messages[i].content) {
        hermesStore.messages[i].content = '⏹ 已中断'
      } else {
        hermesStore.messages[i].content += '\n\n⏹ 已中断'
      }
      break
    }
  }
}

onMounted(async () => {
  await hermesStore.loadHermesConfig()
  await hermesStore.loadConversations()
  if (!hermesStore.conversations.length) {
    await hermesStore.createConversation()
  } else {
    hermesStore.selectConversation(hermesStore.conversations[0].id)
  }
  window.addEventListener('mousemove', onWindowMove)
})

watch(() => hermesStore.messages, () => {
  scrollToBottom()
}, { deep: true })

const suggestions = [
  '查看所有项目',
  '帮我查一下系统里有哪些测试用例',
  '生成5个测试用的手机号',
  '查看最近的API测试报告',
]

function normalizeMarkdownBlocks(text) {
  return text
    .replace(/\|\|/g, '|')
    .replace(/^(#{1,6})([^\s#])/gm, '$1 $2')
    .replace(/([^\n])(#{1,6}\s)/g, '$1\n$2')
    .replace(/^(\s*-{1,2}\s*)$/gm, '---')
    .replace(/^(\s*-{2,}\s*)$/gm, '---')
    .replace(/([^\n])(---)([^\n])/g, '$1\n$2\n$3')
    .replace(/([^\n])(\*\*\*)([^\n])/g, '$1\n$2\n$3')
    .replace(/^\s*\|(\s*\|)*\s*$/gm, '')
    .replace(/^(\s*)[-*+]\s+(\|.*\|.*)$/gm, '$1$2')
    .replace(/^(\s*)[-*+]\s+(\|[^|]+)(\s*)$/gm, '$1$2|$3')
    .replace(/([^\n])(>\s)/g, '$1\n$2')
    .replace(/([^\n])([-*+]\s)/g, '$1\n$2')
    .replace(/([^\n])(\d+\.\s)/g, '$1\n$2')
    .replace(/\n{3,}/g, '\n\n')
}

function renderMarkdown(text) {
  if (!text) return ''

  const codeBlocks = []
  const chartBlocks = []
  text = text.replace(/```([\w-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
    const langTrim = lang.trim().toLowerCase()
    if (langTrim === 'echarts') {
      const key = `__CHART_${chartBlocks.length}__`
      chartBlocks.push(code.trim())
      return '\n' + key + '\n'
    }
    const key = `__CODE_BLOCK_${codeBlocks.length}__`
    codeBlocks.push({ lang: lang.trim(), code })
    return '\n' + key + '\n'
  })

  text = normalizeMarkdownBlocks(text)

  // 先提取 Markdown 表格（此时 | 尚未被 escHtml 转义），再转义正文
  const tables = []
  text = renderMarkdownTables(text, tables)
  let html = escHtml(text)

  const lines = html.split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) { i++; continue }

    const cbMatch = trimmed.match(/^__CODE_BLOCK_(\d+)__$/)
    if (cbMatch) {
      const { lang, code } = codeBlocks[parseInt(cbMatch[1])]
      const cls = lang ? ` class="language-${lang}"` : ''
      out.push(`<pre class="md-pre"><code${cls}>${escHtml(code)}</code></pre>`)
      i++; continue
    }

    const chMatch = trimmed.match(/^__CHART_(\d+)__$/)
    if (chMatch) {
      const optionJson = chartBlocks[parseInt(chMatch[1])] || ''
      out.push(`<div class="md-chart"><script type="application/json">${escHtml(optionJson)}<\/script></div>`)
      i++; continue
    }

    const tbMatch = trimmed.match(/^__TABLE_(\d+)__$/)
    if (tbMatch) {
      out.push(tables[parseInt(tbMatch[1])])
      i++; continue
    }

    if (/^(---|\*\*\*|___)\s*$/.test(trimmed)) {
      out.push('<hr class="md-hr">')
      while (i + 1 < lines.length && /^(---|\*\*\*|___)\s*$/.test(lines[i + 1].trim())) {
        i++
      }
      i++; continue
    }

    const hMatch = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (hMatch) {
      const level = hMatch[1].length
      out.push(`<h${level} class="md-h${level}">${processInline(hMatch[2])}</h${level}>`)
      i++; continue
    }

    if (/^[-*+]\s+/.test(trimmed)) {
      const items = []
      while (i < lines.length) {
        const l = lines[i].trim()
        if (/^[-*+]\s+/.test(l)) {
          items.push(processInline(l.replace(/^[-*+]\s+/, '')))
          i++
        } else if (l && items.length && !/^(\d+\.\s|>|#{1,6}\s|[-*+]\s)/.test(l)) {
          items[items.length - 1] += '<br>' + processInline(l)
          i++
        } else break
      }
      out.push('<ul class="md-list">' + items.map(it => `<li>${it}</li>`).join('') + '</ul>')
      continue
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items = []
      while (i < lines.length) {
        const l = lines[i].trim()
        if (/^\d+\.\s+/.test(l)) {
          items.push(processInline(l.replace(/^\d+\.\s+/, '')))
          i++
        } else if (l && items.length && !/^([-+*]\s|>|#{1,6}\s|\d+\.\s)/.test(l)) {
          items[items.length - 1] += '<br>' + processInline(l)
          i++
        } else break
      }
      out.push('<ol class="md-list">' + items.map(it => `<li>${it}</li>`).join('') + '</ol>')
      continue
    }

    if (/^>\s?/.test(line)) {
      const items = []
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        items.push(processInline(lines[i].replace(/^>\s?/, '')))
        i++
      }
      out.push('<blockquote class="md-quote">' + items.join('<br>') + '</blockquote>')
      continue
    }

    out.push('<p class="md-p">' + processInline(line) + '</p>')
    i++
  }

  let cleaned = out
    .map(s => s.trim())
    .filter(Boolean)
    .filter(s => {
      const text = s.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim()
      if (/^[-*_]+$/.test(text)) return false
      if (/^[\s]*[-*_]{1,3}[\s]*$/.test(text)) return false
      if (/^#+\s*$/.test(text)) return false
      return true
    })
  cleaned = cleaned
    .map(s => s
      .replace(/<p[^>]*>\s*(<br\s*\/?>|\s)*\s*<\/p>/gi, '')
      .replace(/<p[^>]*>\s*<\/?strong>\s*<\/p>/gi, '')
      .replace(/<p[^>]*>\s*<\/?em>\s*<\/p>/gi, '')
    )
    .filter(Boolean)
  return cleaned.join('\n')
}

function renderMarkdownTables(text, tables) {
  const lines = text.split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const trimmedNow = lines[i].trim()
    if (trimmedNow.startsWith('|') || isLikelySeparatorLine(trimmedNow)) {
      const block = []
      while (i < lines.length) {
        const t = lines[i].trim()
        if (t.startsWith('|') || isLikelySeparatorLine(t)) {
          block.push(lines[i])
          i++
        } else break
      }
      const parsed = parseMarkdownTable(block)
      if (parsed) {
        const key = `__TABLE_${tables.length}__`
        tables.push(parsed)
        out.push(key)
      } else {
        out.push(block.join('\n'))
      }
    } else {
      out.push(lines[i])
      i++
    }
  }
  return out.join('\n')
}

function isLikelySeparatorLine(t) {
  if (!t) return false
  return /^-+$/.test(t.replace(/\s/g, '')) && t.length <= 50
}

function parseMarkdownTable(block) {
  if (block.length < 1) return null

  const rawRows = []
  block.forEach((line) => {
    const trimmed = line.trim()
    if (isLikelySeparatorLine(trimmed)) {
    } else if (trimmed.startsWith('|')) {
      if (trimmed.endsWith('|')) {
        rawRows.push(trimmed.slice(1, -1).split('|').map(c => c.trim()))
      } else {
        rawRows.push(trimmed.slice(1).split('|').map(c => c.trim()))
      }
    }
  })

  if (rawRows.length < 1) return null

  let sepIdx = rawRows.findIndex(r => r.length && r.every(cell => /^:?-+-?:?$/.test(cell)))
  let headers, aligns, bodyRows

  if (sepIdx === -1) {
    headers = rawRows[0]
    aligns = headers.map(() => 'left')
    bodyRows = rawRows.slice(1)
  } else {
    headers = rawRows[sepIdx - 1] || []
    aligns = rawRows[sepIdx].map(cell => {
      const left = cell.startsWith(':')
      const right = cell.endsWith(':')
      if (left && right) return 'center'
      if (right) return 'right'
      return 'left'
    })
    bodyRows = rawRows.slice(sepIdx + 1)
  }

  if (!headers.length) return null
  let colCount = headers.length

  bodyRows = bodyRows.filter(r => r.some(c => c && c.trim()))

  bodyRows.forEach(row => {
    while (row.length < colCount) row.push('')
    if (row.length > colCount) row = row.slice(0, colCount)
  })

  let html = '<table class="md-table"><thead><tr>'
  headers.forEach((h, idx) => {
    html += `<th style="text-align:${aligns[idx] || 'left'}">${processInline(escHtml(h))}</th>`
  })
  html += '</tr></thead><tbody>'
  bodyRows.forEach(cells => {
    html += '<tr>'
    cells.forEach((c, idx) => {
      html += `<td style="text-align:${aligns[idx] || 'left'}">${processInline(escHtml(c || ''))}</td>`
    })
    html += '</tr>'
  })
  html += '</tbody></table>'
  return html
}

function processInline(text) {
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/!\[([^[\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2" class="md-img">')
    .replace(/\[([^[\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="md-link">$1</a>')
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/___(.+?)___/g, '<strong><em>$1</em></strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/_(.+?)_/g, '<em>$1</em>')
}

function onEnter() {
  if (!loading.value) sendMessage()
}

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
  if (!tc.result) return null
  if (tc.result.error) return null
  return TOOL_BADGES[tc.name] || null
}

function escHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

function renderKbResult(r) {
  const dataset = escHtml(r.dataset || '知识库')
  const doc = escHtml(r.document || '')
  const score = (typeof r.score === 'number') ? `相关度 ${r.score}` : ''
  let paras = Array.isArray(r.paragraphs) && r.paragraphs.length
    ? r.paragraphs
    : (r.content || '').split(/\n|(?<=[。！？；!?;])\s*/).filter(s => s && s.trim())
  paras = paras.filter(p => p && p.trim()).slice(0, 8)
  const body = paras.length
    ? `<ol class="kb-paras">${paras.map(p => `<li>${escHtml(p.trim())}</li>`).join('')}</ol>`
    : `<div class="kb-empty">(无内容)</div>`
  const meta = `<div class="kb-meta">📚 ${dataset}${doc ? ` · 📄 ${doc}` : ''}${score ? ` · ⭐ ${score}` : ''}</div>`
  return `<div class="kb-card">${meta}${body}</div>`
}

function renderToolResult(tc) {
  const r = tc.result
  if (!r) return ''
  if (r.error) {
    return `<div class="tool-result-error">❌ ${escHtml(r.error)}</div>`
  }
  if (tc.name === 'search_knowledge_base' && Array.isArray(r.results) && r.results.length) {
    const summary = `<div class="kb-summary">🔎 关键词：<b>${escHtml(r.query || '')}</b> · 命中 <b>${r.total ?? r.results.length}</b> 条 · 检索知识库：${escHtml((r.datasets_searched || []).join('、') || '-')}</div>`
    const cards = r.results.map(renderKbResult).join('')
    const partial = (r.partial_errors && r.partial_errors.length)
      ? `<details class="kb-warn"><summary>部分检索方法失败（已自动回退）</summary><pre>${escHtml(r.partial_errors.join('\n'))}</pre></details>`
      : ''
    return summary + cards + partial
  }
  return `<pre class="tool-result-json">${escHtml(JSON.stringify(r, null, 2))}</pre>`
}

async function sendMessage(text) {
  const content = (text || inputText.value).trim()
  if (!content || loading.value) return

  if (!hermesStore.currentConversationId) {
    await hermesStore.createConversation()
  }

  inputText.value = ''
  loading.value = true
  hermesStore.setLoading(true)
  hermesStore.setAvatarState('thinking')

  hermesStore.appendUserMessage(content)
  const assistantMsg = hermesStore.createAssistantPlaceholder()

  await scrollToBottom(true)

  currentController = new AbortController()

  let watchdog = null
  const resetWatchdog = () => {
    if (watchdog) clearTimeout(watchdog)
    watchdog = setTimeout(() => {
      if (currentController) {
        currentController.abort()
      }
      assistantMsg.content = assistantMsg.content
        ? `${assistantMsg.content}\n\n⏱ 数字人长时间无响应（90s 无新事件），已自动终止。请检查 LLM 服务或配置。`
        : '⏱ 数字人长时间无响应（90s 无新事件），已自动终止。请检查 LLM 服务或配置。'
      assistantMsg.loading = false
      loading.value = false
      hermesStore.setLoading(false)
      ElMessage.error('数字人无响应，建议重试')
    }, 90000)
  }
  resetWatchdog()

  const activeSkillIds = hermesStore.hermesConfig?.active_skills || []
  const skill_id = activeSkillIds.length ? activeSkillIds[0] : null

  try {
    const reader = await agentChat(
      content,
      [],
      currentController.signal,
      {
        conversation_id: hermesStore.currentConversationId,
        skill_id,
      }
    )
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      resetWatchdog()

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
      // 用户主动停止 或 看门狗触发
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
    hermesStore.setLoading(false)
    if (hermesStore.avatarState !== 'error') {
      hermesStore.setAvatarState('idle')
    }
    hermesStore.setSpeakText('')
    await scrollToBottom()
  }
}

function handleEvent(event, msg) {
  switch (event.type) {
    case 'thinking':
      if (msg.thoughtText == null) msg.thoughtText = ''
      msg.thoughtText += event.content
      msg.thoughtExpanded = true
      const tail = msg.thoughtText.slice(-60).replace(/^[\s,，。.!?！？、]*/, '')
      msg.loadingText = '思考中: ' + (tail || '...')
      hermesStore.setAvatarState('thinking')
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
      hermesStore.setAvatarState('working')
      break
    case 'executing':
      if (msg.toolCalls.length > 0) {
        msg.toolCalls[msg.toolCalls.length - 1].executing = true
      }
      msg.loadingText = `执行工具: ${event.name || msg.toolCalls[msg.toolCalls.length - 1]?.name}...`
      hermesStore.setAvatarState('working')
      break
    case 'tool_result':
      if (msg.toolCalls.length > 0) {
        const last = msg.toolCalls[msg.toolCalls.length - 1]
        last.result = event.result
        last.executing = false
      }
      msg.loadingText = '继续推理...'
      hermesStore.setAvatarState('thinking')
      break
    case 'message':
      msg.content += event.content
      msg.loading = false
      hermesStore.setAvatarState('speaking')
      hermesStore.setSpeakText(event.content)
      break
    case 'error':
      msg.content = `❌ ${event.content}`
      msg.loading = false
      hermesStore.setAvatarState('error')
      hermesStore.setSpeakText('')
      break
    case 'done':
      msg.loading = false
      msg.thoughtExpanded = false
      if (!msg.content && msg.toolCalls.length === 0) {
        msg.content = '我这边没有拿到可直接回答的内容，可能是问题信息不够明确。你可以补充具体想查的测试类型或相关 ID，我帮你进一步定位。'
      }
      setTimeout(() => {
        if (hermesStore.avatarState !== 'error') {
          hermesStore.setAvatarState('idle')
        }
      }, 1000)
      hermesStore.setSpeakText('')
      break
  }
  scrollToBottom()
}

async function scrollToBottom(force = false) {
  await nextTick()
  const el = messagesRef.value
  if (!el) return
  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 100
  if (force || atBottom || !userScrolledUp) {
    el.scrollTop = el.scrollHeight
  }
}

const chartInstances = new Map()
function initCharts() {
  if (!messagesRef.value) return
  const chartDivs = messagesRef.value.querySelectorAll('.md-chart')
  chartDivs.forEach((div) => {
    if (div.dataset.initialized) return
    const script = div.querySelector('script[type="application/json"]')
    const optionJson = script ? script.textContent : ''
    if (!optionJson) return
    try {
      const option = JSON.parse(optionJson)
      const chart = echarts.init(div)
      chart.setOption(option, true)
      chartInstances.set(div, chart)
      div.dataset.initialized = 'true'
    } catch (e) {
      console.warn('ECharts 配置解析失败:', e)
      div.textContent = '图表配置解析失败'
    }
  })
}

function disposeCharts() {
  chartInstances.forEach((chart) => {
    chart.dispose()
  })
  chartInstances.clear()
}

onUpdated(() => {
  initCharts()
})

onUnmounted(() => {
  disposeCharts()
  window.removeEventListener('mousemove', onWindowMove)
})
</script>

<style scoped>
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
  background: #f5f7fa;
  height: 100%;
}

.agent-header {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: linear-gradient(135deg, #070708 0%, #0f0806 100%);
  border-bottom: 1px solid rgba(255, 140, 0, 0.22);
  color: #fff;
  overflow: hidden;
}
.is-compact .agent-header {
  padding: 12px 14px;
}
.header-hud {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  overflow: hidden;
}
/* 科技网格 */
.hud-grid {
  position: absolute;
  inset: -50%;
  background-image:
    linear-gradient(rgba(255, 160, 40, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 160, 40, 0.06) 1px, transparent 1px);
  background-size: 26px 26px;
  animation: hud-grid-move 18s linear infinite;
  opacity: 0.5;
}
@keyframes hud-grid-move {
  0% { transform: translate(0, 0); }
  100% { transform: translate(26px, 26px); }
}
/* 横向扫描线 */
.hud-scanline {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  top: -4%;
  background: linear-gradient(90deg, transparent, rgba(255, 180, 40, 0.75), transparent);
  box-shadow: 0 0 12px rgba(255, 140, 0, 0.55);
  animation: hud-scan 5s linear infinite;
  opacity: 0.7;
}
@keyframes hud-scan {
  0% { top: -4%; opacity: 0; }
  10% { opacity: 0.85; }
  90% { opacity: 0.85; }
  100% { top: 104%; opacity: 0; }
}
/* 四角 HUD 框 */
.hud-corner {
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 160, 40, 0.55);
}
.hud-tl { top: 8px; left: 8px; border-right: none; border-bottom: none; }
.hud-tr { top: 8px; right: 8px; border-left: none; border-bottom: none; }
.hud-bl { bottom: 8px; left: 8px; border-right: none; border-top: none; }
.hud-br { bottom: 8px; right: 8px; border-left: none; border-top: none; }
/* 锁定准星光圈（AI 思考时显示） */
.hud-lock {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 230px;
  height: 230px;
  margin: -115px 0 0 -115px;
  border-radius: 50%;
  border: 1px dashed rgba(255, 140, 0, 0.45);
  box-shadow: 0 0 20px rgba(255, 120, 0, 0.3) inset;
  animation: lock-spin 4s linear infinite;
}
.hud-lock::before {
  content: '';
  position: absolute;
  inset: 34px;
  border-radius: 50%;
  border: 1px solid rgba(255, 140, 0, 0.3);
}
@keyframes lock-spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.bg-eyes-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  transition: filter 0.3s ease;
}

/* 战斗之眼 */
.eye-socket .socket-shape {
  fill: #050505;
  stroke: rgba(220, 0, 0, 0.45);
  stroke-width: 2;
}
.eye-socket .eye-dark {
  fill: #080300;
}
.eye-gaze .sclera {
  transform-box: fill-box;
  transform-origin: center;
  animation: sclera-breathe 4s infinite ease-in-out;
}
.eye-gaze ellipse[fill="url(#iris-gradient)"] {
  transform-box: fill-box;
  transform-origin: center;
  animation: pupil-breathe 4s infinite ease-in-out;
}
/* 红色战斗眼线 */
.eyeliner {
  fill: none;
  stroke: #ff1a1a;
  stroke-width: 3.2;
  stroke-linecap: round;
  filter: drop-shadow(0 0 5px #ff0000) drop-shadow(0 0 10px #ff3300);
  opacity: 0.9;
}
/* 眼皮：缓慢掠过的闭眼 */
.eyelid {
  transform-box: fill-box;
  transform-origin: center top;
  animation: eye-blink 8s infinite ease-in-out;
}
.eyelid--r {
  animation-delay: 0.2s;
}
/* 虹膜组：思考时可叠加扫视动画 */
.iris-group {
  transform-box: fill-box;
  transform-origin: center;
}
.iris-group--r {
  animation-delay: 0.12s;
}
/* AI 思考：快速眨眼 + 虹膜急促左右扫视 */
.agent-header.is-alert .eyelid {
  animation-duration: 1.1s;
}
.agent-header.is-alert .iris-group {
  animation: thinking-scan 0.55s infinite ease-in-out alternate;
}
/* 眉骨阴影 */
.brow-bar {
  fill: rgba(0, 0, 0, 0.6);
}

/* 悬停警戒：眼睛更亮 */
.agent-header.is-hover .bg-eyes-svg {
  filter: brightness(1.22) saturate(1.2);
}
.agent-header.is-hover .hud-corner {
  border-color: rgba(255, 180, 60, 0.95);
}
/* AI 思考：虹膜变浅蓝 + 急促脉冲 + 扫描加速 + 内发光 */
.agent-header.is-alert .iris-group ellipse[fill="url(#iris-gradient)"] {
  fill: url(#iris-blue-gradient);
}
.agent-header.is-alert .eye-gaze ellipse[fill="url(#iris-gradient)"] {
  animation: alert-pupil-pulse 0.9s infinite ease-in-out;
}
.agent-header.is-alert .hud-scanline {
  animation-duration: 1.4s;
  opacity: 1;
}
.agent-header.is-alert .hud-corner {
  border-color: rgba(255, 80, 20, 1);
}
.agent-header.is-alert {
  box-shadow: inset 0 0 36px rgba(255, 60, 0, 0.45);
}

@keyframes sclera-breathe {
  0%, 100% {
    filter: brightness(0.9);
    opacity: 0.92;
  }
  50% {
    filter: brightness(1.2);
    opacity: 1;
  }
}

@keyframes pupil-breathe {
  0%, 100% {
    filter: brightness(0.9);
  }
  50% {
    filter: brightness(1.25);
  }
}

@keyframes eye-blink {
  0%, 94%, 100% {
    transform: scaleY(0);
    opacity: 0;
  }
  96%, 98% {
    transform: scaleY(1);
    opacity: 1;
  }
}

@keyframes alert-pupil-pulse {
  0%, 100% { filter: brightness(1) drop-shadow(0 0 4px #2aa8ff); }
  50% { filter: brightness(1.8) drop-shadow(0 0 14px #4db4ff); }
}
@keyframes thinking-scan {
  0% { transform: translateX(-4px); }
  100% { transform: translateX(4px); }
}

.header-left {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-actions {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}
.header-actions :deep(.el-button.is-plain) {
  --el-button-bg-color: rgba(255, 255, 255, 0.12);
  --el-button-border-color: rgba(255, 255, 255, 0.35);
  --el-button-text-color: #fff;
  --el-button-hover-text-color: #0f766e;
  --el-button-hover-bg-color: #fff;
  --el-button-hover-border-color: #fff;
}
.header-actions :deep(.el-button.is-plain.is-circle) {
  padding: 6px;
}
.header-title {
  font-size: 17px;
  font-weight: 600;
  margin-right: 6px;
  color: #fff;
}
.header-sub {
  display: block;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.75);
  margin-top: 2px;
}

.agent-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.is-compact .agent-messages {
  padding: 12px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
}
.empty-icon {
  font-size: 48px;
  color: #c0c4cc;
}
.empty-title {
  font-size: 16px;
  color: #606266;
  margin: 0;
}
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.msg-row {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  max-width: 92%;
}
.msg-row.user {
  margin-left: auto;
  flex-direction: row-reverse;
}
.msg-row.assistant {
  margin-right: auto;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 16px;
  color: #fff;
}
.user-avatar { background: #409eff; }
.ai-avatar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }

.msg-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.msg-bubble {
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
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
.ai-bubble :deep(.md-table) {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
  border: 1px solid var(--el-color-primary-light-7, #d9ecff);
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}
.ai-bubble :deep(.md-table th),
.ai-bubble :deep(.md-table td) {
  border: 1px solid var(--el-color-primary-light-8, #e6f0fa);
  padding: 6px 10px;
  line-height: 1.5;
  vertical-align: middle;
  text-align: left;
  word-break: break-word;
}
.ai-bubble :deep(.md-table th) {
  background: var(--el-color-primary-light-9, #ecf5ff);
  color: var(--el-color-primary, #409eff);
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
}
.ai-bubble :deep(.md-table tbody tr:nth-child(even)) { background: #fafbfc; }
.ai-bubble :deep(.md-table tbody tr:hover) { background: #f0f7ff; }
.ai-bubble :deep(.md-table code) {
  background: rgba(64, 158, 255, 0.08);
  color: #409eff;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
}
.ai-bubble :deep(.md-p) { margin: 10px 0; }
.ai-bubble :deep(.md-p:first-child) { margin-top: 0; }
.ai-bubble :deep(.md-p:last-child) { margin-bottom: 0; }
.ai-bubble :deep(.md-h1) { font-size: 18px; margin: 14px 0 8px 0; }
.ai-bubble :deep(.md-h2) { font-size: 16px; margin: 12px 0 6px 0; }
.ai-bubble :deep(.md-h3) { font-size: 15px; margin: 10px 0 6px 0; }
.ai-bubble :deep(.md-h4),
.ai-bubble :deep(.md-h5),
.ai-bubble :deep(.md-h6) { font-size: 14px; margin: 8px 0 4px 0; }
.ai-bubble :deep(.md-list) {
  margin: 10px 0;
  padding-left: 20px;
}
.ai-bubble :deep(.md-list li) { margin: 4px 0; }
.ai-bubble :deep(.md-quote) {
  margin: 10px 0;
  padding: 8px 12px;
  border-left: 4px solid #409eff;
  background: #f5f7fa;
  border-radius: 4px;
  color: #606266;
}
.ai-bubble :deep(.md-hr) {
  border: none;
  border-top: 1px solid #e4e7ed;
  margin: 12px 0;
}
.ai-bubble :deep(.md-pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 10px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 6px 0;
}
.ai-bubble :deep(.md-pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: 13px;
  font-family: 'Courier New', Consolas, monospace;
}
.ai-bubble :deep(.md-link) {
  color: #409eff;
  text-decoration: none;
}
.ai-bubble :deep(.md-link:hover) { text-decoration: underline; }
.ai-bubble :deep(.md-img) {
  display: block;
  max-width: 100%;
  max-height: 240px;
  width: auto;
  height: auto;
  margin: 6px 0;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
}

.tool-call-item {
  background: #f8f9fb;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  font-size: 13px;
}

.thought-block {
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-left: 3px solid #e6a23c;
  border-radius: 8px;
  overflow: hidden;
  font-size: 13px;
}
.thought-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  background: #fcf6e8;
}
.thought-header:hover { background: #faeccd; }
.thought-icon { color: #e6a23c; }
.thought-title {
  font-weight: 500;
  color: #8b5a00;
  flex: 1;
}
.thought-expand { color: #909399; margin-left: auto; }
.thought-body {
  padding: 8px 14px 10px;
  color: #5c4a1f;
  line-height: 1.7;
  max-height: 360px;
  overflow-y: auto;
  background: #fffaef;
  border-top: 1px solid #faecd8;
}
.thought-body :deep(.md-p) { margin: 6px 0; }
.thought-body :deep(.md-list) { margin: 6px 0; padding-left: 20px; }
.thought-body :deep(.md-list li) { margin: 3px 0; }
.thought-body :deep(code) {
  background: #f5e8c8;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
  color: #8b5a00;
}
.thought-body :deep(.md-pre) {
  background: #2d2a1f;
  color: #f5e8c8;
  padding: 10px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 6px 0;
}
.thought-body :deep(.md-pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
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
  max-height: 200px;
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
  gap: 10px;
  padding: 10px 14px 12px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  flex-shrink: 0;
}
.is-compact .agent-input {
  padding: 8px 12px 10px;
}
.agent-input :deep(.el-textarea__inner) {
  border-radius: 8px;
}
.send-btn {
  height: 52px;
  border-radius: 8px;
}

.ai-bubble :deep(.md-chart) {
  width: 100%;
  height: 260px;
  margin: 10px 0;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}
</style>
