<template>
  <div class="hermes-chat-view">
    <!-- 左侧：会话列表 -->
    <div class="conversation-panel">
      <div class="conversation-header">
        <div class="header-brand">
          <el-icon class="brand-icon"><Cpu /></el-icon>
          <span class="brand-title">Hermes</span>
        </div>
        <el-button type="primary" size="small" :icon="Plus" @click="onNewConversation">
          新建
        </el-button>
      </div>

      <div class="conversation-list" v-loading="hermesStore.loadingConversations">
        <div
          v-for="conv in hermesStore.conversations"
          :key="conv.id"
          :class="['conversation-item', { active: conv.id === hermesStore.currentConversationId }]"
          @click="hermesStore.selectConversation(conv.id)"
        >
          <el-icon class="conv-icon"><ChatDotRound /></el-icon>
          <div class="conv-info">
            <div class="conv-title" :title="conv.title || '新会话'">
              {{ conv.title || '新会话' }}
            </div>
            <div class="conv-time">{{ formatTime(conv.updated_at) }}</div>
          </div>
          <el-dropdown
            class="conv-actions"
            trigger="click"
            @command="(cmd) => handleConvCommand(cmd, conv)"
            @click.stop
          >
            <el-icon><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="rename">重命名</el-dropdown-item>
                <el-dropdown-item command="clear">清空消息</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <div v-if="!hermesStore.conversations.length" class="conversation-empty">
          <el-icon><ChatLineRound /></el-icon>
          <p>暂无会话，点击「新建」开始</p>
        </div>
      </div>
    </div>

    <!-- 右侧：聊天区 -->
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
          <el-button @click="clearCurrentChat" :icon="Delete" plain size="small">清空当前对话</el-button>
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
              <!-- 思考过程（LLM reasoning / 工具结果摘要）—— 可折叠，默认展开 -->
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
  </div>
</template>

<script setup>
import { ref, nextTick, watch, onMounted, onUpdated, onUnmounted, h, render } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  MagicStick, ChatRound, User, Tools, ArrowDown, ArrowUp, Plus,
  Loading, Promotion, Delete, CircleClose, Cpu, ChatDotRound,
  MoreFilled, ChatLineRound,
} from '@element-plus/icons-vue'
import { agentChat } from '@/api/agent'
import { useHermesStore } from '@/stores/hermes'
import dayjs from 'dayjs'
import * as echarts from 'echarts'

const hermesStore = useHermesStore()
const inputText = ref('')
const loading = ref(false)
const messagesRef = ref(null)
let currentController = null
let userScrolledUp = false

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

function formatTime(ts) {
  if (!ts) return ''
  return dayjs(ts).format('MM-DD HH:mm')
}

function onNewConversation() {
  hermesStore.createConversation()
}

async function handleConvCommand(cmd, conv) {
  if (cmd === 'rename') {
    try {
      const { value } = await ElMessageBox.prompt('请输入新标题', '重命名会话', {
        inputValue: conv.title || '',
        confirmButtonText: '确定',
        cancelButtonText: '取消',
      })
      if (value !== null) {
        await hermesStore.renameConversation(conv.id, value.trim())
      }
    } catch {
      // 取消
    }
  } else if (cmd === 'clear') {
    try {
      await ElMessageBox.confirm('确定清空该会话的所有消息？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
      await hermesStore.clearConversation(conv.id)
    } catch {
      // 取消
    }
  } else if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm('确定删除该会话？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
      await hermesStore.removeConversation(conv.id)
    } catch {
      // 取消
    }
  }
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
  // 把标题、分隔线、表格、引用、列表等块级标记从正文行中分离，清理模型输出的多余符号
  return text
    // 统一双竖线 || 为单竖线
    .replace(/\|\|/g, '|')
    // 标题 # 后面没有空格则补一个空格
    .replace(/^(#{1,6})([^\s#])/gm, '$1 $2')
    // 标题前没有换行则加一个换行
    .replace(/([^\n])(#{1,6}\s)/g, '$1\n$2')
    // 分隔线：1 个或 2 个连续 '-' 也规范成 ---（模型常把表格分隔线拆成 -/--）
    .replace(/^(\s*-{1,2}\s*)$/gm, '---')
    // 分隔线：2 个以上连续 '-' 规范化成 ---
    .replace(/^(\s*-{2,}\s*)$/gm, '---')
    // 分隔线前后没有换行则加换行
    .replace(/([^\n])(---)([^\n])/g, '$1\n$2\n$3')
    .replace(/([^\n])(\*\*\*)([^\n])/g, '$1\n$2\n$3')
    // 删除只包含 | 的空表格/分隔行
    .replace(/^\s*\|(\s*\|)*\s*$/gm, '')
    // 把列表项里的表格行（* | x | y | 或 * | x | y）转成普通表格行
    .replace(/^(\s*)[-*+]\s+(\|.*\|.*)$/gm, '$1$2')
    // 把 * | 单行内容也补齐成表格行（| a |）
    .replace(/^(\s*)[-*+]\s+(\|[^|]+)(\s*)$/gm, '$1$2|$3')
    // 引用前换行
    .replace(/([^\n])(>\s)/g, '$1\n$2')
    // 列表前换行
    .replace(/([^\n])([-*+]\s)/g, '$1\n$2')
    .replace(/([^\n])(\d+\.\s)/g, '$1\n$2')
    // 合并连续 3 个以上空行
    .replace(/\n{3,}/g, '\n\n')
}

function renderMarkdown(text) {
  if (!text) return ''

  // 1. 提取代码块，用占位符保护，避免内部被转义/解析
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

  // 2. 块级结构规范化：把标题、分隔线等从正文行里分离出来
  text = normalizeMarkdownBlocks(text)

  // 3. 基础 HTML 转义
  let html = escHtml(text)

  // 3. 解析 Markdown 表格，表格 HTML 也用占位符保护
  const tables = []
  html = renderMarkdownTables(html, tables)

  // 4. 按块级元素逐行解析
  const lines = html.split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    if (!trimmed) { i++; continue }

    // 代码块占位符
    const cbMatch = trimmed.match(/^__CODE_BLOCK_(\d+)__$/)
    if (cbMatch) {
      const { lang, code } = codeBlocks[parseInt(cbMatch[1])]
      const cls = lang ? ` class="language-${lang}"` : ''
      out.push(`<pre class="md-pre"><code${cls}>${escHtml(code)}</code></pre>`)
      i++; continue
    }

    // 图表占位符
    const chMatch = trimmed.match(/^__CHART_(\d+)__$/)
    if (chMatch) {
      const optionJson = chartBlocks[parseInt(chMatch[1])] || ''
      out.push(`<div class="md-chart"><script type="application/json">${escHtml(optionJson)}<\/script></div>`)
      i++; continue
    }

    // 表格占位符
    const tbMatch = trimmed.match(/^__TABLE_(\d+)__$/)
    if (tbMatch) {
      out.push(tables[parseInt(tbMatch[1])])
      i++; continue
    }

    // 分隔线
    if (/^(---|\*\*\*|___)\s*$/.test(trimmed)) {
      out.push('<hr class="md-hr">')
      // 跳过连续的分隔线，只保留一条
      while (i + 1 < lines.length && /^(---|\*\*\*|___)\s*$/.test(lines[i + 1].trim())) {
        i++
      }
      i++; continue
    }

    // 标题
    const hMatch = trimmed.match(/^(#{1,6})\s+(.+)$/)
    if (hMatch) {
      const level = hMatch[1].length
      out.push(`<h${level} class="md-h${level}">${processInline(hMatch[2])}</h${level}>`)
      i++; continue
    }

    // 无序列表
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

    // 有序列表
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

    // 引用块
    if (/^>\s?/.test(line)) {
      const items = []
      while (i < lines.length && /^>\s?/.test(lines[i])) {
        items.push(processInline(lines[i].replace(/^>\s?/, '')))
        i++
      }
      out.push('<blockquote class="md-quote">' + items.join('<br>') + '</blockquote>')
      continue
    }

    // 普通段落
    out.push('<p class="md-p">' + processInline(line) + '</p>')
    i++
  }

  // 5. 清理：孤立加粗行 / 短横线行 / 空段 / 多个连续空白
  let cleaned = out
    .map(s => s.trim())
    .filter(Boolean)
    // 去掉「整段只剩孤立符号 -、--、---、*、**、***、_、__ 之一」的废行
    .filter(s => {
      const text = s.replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').trim()
      // 整段是 - / * / _ 重复（含空白）
      if (/^[-*_]+$/.test(text)) return false
      // 整段是 1-2 个 - / * / _（前面可带点空白）
      if (/^[\s]*[-*_]{1,3}[\s]*$/.test(text)) return false
      // 整段是 # 标题前缀但没内容（如 "#"）
      if (/^#+\s*$/.test(text)) return false
      return true
    })
  // 二次清理：去掉空 p / 只剩 <br> 的 p
  cleaned = cleaned
    .map(s => s
      .replace(/<p[^>]*>\s*(<br\s*\/?>|\s)*\s*<\/p>/gi, '')
      .replace(/<p[^>]*>\s*<\/?strong>\s*<\/p>/gi, '')
      .replace(/<p[^>]*>\s*<\/?em>\s*<\/p>/gi, '')
    )
    .filter(Boolean)
  return cleaned.join('\n')
}

// Markdown 表格解析：识别 | 开头的连续行，并对 LLM 常见的"坏表格"做容错修复
//   - 容错 1：表头后跟随 1-2 行只含 `--` / `-` 的"伪分隔行" → 自动补成标准 `| --- | --- |`
//   - 容错 2：LLM 把多行数据塞到一行（流式拼接常见）→ 按表头列宽智能切分
function renderMarkdownTables(text, tables) {
  const lines = text.split('\n')
  const out = []
  let i = 0
  while (i < lines.length) {
    const trimmedNow = lines[i].trim()
    if (trimmedNow.startsWith('|') || isLikelySeparatorLine(trimmedNow)) {
      // 收集连续的"疑似表格行"（含 | 开头的 + 短横线行）
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

// 判断一行是否是"伪分隔行"（LLM 有时会写 `---` 或 `-` 作为分隔）
function isLikelySeparatorLine(t) {
  if (!t) return false
  // 整行只有 - 字符（可带空格）
  return /^-+$/.test(t.replace(/\s/g, '')) && t.length <= 50
}

function parseMarkdownTable(block) {
  if (block.length < 1) return null

  // 先把"伪分隔行"（纯 --- / -）单独抽出来
  const rawRows = []
  block.forEach((line, idx) => {
    const trimmed = line.trim()
    if (isLikelySeparatorLine(trimmed)) {
      // 跳过 - 真正进 row 解析时不要它
    } else if (trimmed.startsWith('|')) {
      // 正确格式：以 | 开头结尾
      if (trimmed.endsWith('|')) {
        rawRows.push(trimmed.slice(1, -1).split('|').map(c => c.trim()))
      } else {
        // 缺尾部 | 也容错
        rawRows.push(trimmed.slice(1).split('|').map(c => c.trim()))
      }
    }
  })

  if (rawRows.length < 1) return null

  // 查找标准分隔行
  let sepIdx = rawRows.findIndex(r => r.length && r.every(cell => /^:?-+-?:?$/.test(cell)))
  let headers, aligns, bodyRows

  if (sepIdx === -1) {
    // 没有标准分隔行：取第一行作表头，其余作数据
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

  // 过滤全空行
  bodyRows = bodyRows.filter(r => r.some(c => c && c.trim()))

  let html = '<table class="md-table"><thead><tr>'
  headers.forEach((h, idx) => {
    html += `<th style="text-align:${aligns[idx] || 'left'}">${processInline(h)}</th>`
  })
  html += '</tr></thead><tbody>'
  bodyRows.forEach(cells => {
    html += '<tr>'
    cells.forEach((c, idx) => {
      html += `<td style="text-align:${aligns[idx] || 'left'}">${processInline(c || '')}</td>`
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

  // 默认启用的数字人技能 ID
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
      // 流结束后自动折叠思考过程，避免冗长的中间步骤一直占着主视图
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

// 初始化/更新 Markdown 中的 ECharts 图表
const chartInstances = new Map()
function initCharts() {
  if (!messagesRef.value) return
  const chartDivs = messagesRef.value.querySelectorAll('.md-chart')
  chartDivs.forEach((div, idx) => {
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
})
</script>

<style scoped>
.hermes-chat-view {
  display: flex;
  height: 100%;
  background: #f5f7fa;
  overflow: hidden;
  min-height: 0;
}

/* 左侧会话列表面板 */
.conversation-panel {
  width: 280px;
  flex: 0 0 280px;
  height: 100%;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.conversation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-icon {
  font-size: 24px;
  color: #409eff;
}

.brand-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
}

.conversation-item:hover {
  background: #f5f7fa;
}

.conversation-item.active {
  background: #ecf5ff;
}

.conv-icon {
  font-size: 18px;
  color: #909399;
  flex-shrink: 0;
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-time {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.conv-actions {
  opacity: 0;
  transition: opacity 0.2s;
  color: #909399;
  cursor: pointer;
  flex-shrink: 0;
}

.conversation-item:hover .conv-actions {
  opacity: 1;
}

.conversation-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #909399;
  gap: 8px;
}

.conversation-empty .el-icon {
  font-size: 40px;
}

/* 右侧聊天面板 */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
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

.msg-bubble {
  padding: 10px 14px;
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
  table-layout: fixed;            /* 固定列宽算法：保证表头与数据列严格对齐 */
  border-collapse: collapse;      /* 合并边框，列边界竖线表头与数据严格对齐 */
  margin: 10px 0;
  font-size: 13px;
  border: 1px solid var(--el-color-primary-light-7, #d9ecff);
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}
.ai-bubble :deep(.md-table th),
.ai-bubble :deep(.md-table td) {
  border: 1px solid var(--el-color-primary-light-8, #e6f0fa);
  padding: 8px 12px;
  line-height: 1.5;
  vertical-align: middle;
  text-align: left;                /* 表头与数据列统一左对齐，列边界严格对齐 */
  word-break: break-word;
}
.ai-bubble :deep(.md-table th) {
  background: var(--el-color-primary-light-9, #ecf5ff);
  color: var(--el-color-primary, #409eff);
  font-weight: 600;
  font-size: 13px;
  white-space: nowrap;
}
.ai-bubble :deep(.md-table tbody tr:nth-child(even)) {
  background: #fafbfc;
}
.ai-bubble :deep(.md-table tbody tr:hover) {
  background: #f0f7ff;
}
.ai-bubble :deep(.md-table code) {
  background: rgba(64, 158, 255, 0.08);
  color: #409eff;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
}
.ai-bubble :deep(.md-p) {
  margin: 12px 0;
}
.ai-bubble :deep(.md-p:first-child) {
  margin-top: 0;
}
.ai-bubble :deep(.md-p:last-child) {
  margin-bottom: 0;
}
.ai-bubble :deep(.md-h1),
.ai-bubble :deep(.md-h2),
.ai-bubble :deep(.md-h3),
.ai-bubble :deep(.md-h4),
.ai-bubble :deep(.md-h5),
.ai-bubble :deep(.md-h6) {
  font-weight: 600;
  line-height: 1.4;
}
.ai-bubble :deep(.md-h1) { font-size: 18px; color: #303133; margin: 18px 0 10px 0; }
.ai-bubble :deep(.md-h2) { font-size: 16px; color: #303133; margin: 14px 0 8px 0; }
.ai-bubble :deep(.md-h3) { font-size: 15px; color: #606266; margin: 12px 0 6px 0; }
.ai-bubble :deep(.md-h4),
.ai-bubble :deep(.md-h5),
.ai-bubble :deep(.md-h6) { font-size: 14px; color: #606266; margin: 10px 0 6px 0; }
.ai-bubble :deep(.md-list) {
  margin: 12px 0;
  padding-left: 22px;
}
.ai-bubble :deep(.md-list li) {
  margin: 6px 0;
}
.ai-bubble :deep(.md-quote) {
  margin: 12px 0;
  padding: 10px 14px;
  border-left: 4px solid #409eff;
  background: #f5f7fa;
  border-radius: 4px;
  color: #606266;
}
.ai-bubble :deep(.md-hr) {
  border: none;
  border-top: 1px solid #e4e7ed;
  margin: 16px 0;
}
.ai-bubble :deep(.md-pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
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
.ai-bubble :deep(.md-link:hover) {
  text-decoration: underline;
}
.ai-bubble :deep(.md-img) {
  display: block;
  max-width: 100%;
  max-height: 360px;
  width: auto;
  height: auto;
  margin: 8px 0;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.ai-bubble :deep(.md-img:hover) {
  transform: scale(1.01);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}
/* 图片加载失败时优雅降级 */
.ai-bubble :deep(.md-img-broken) {
  display: inline-block;
  padding: 8px 12px;
  background: #fdf6ec;
  border: 1px dashed #e6a23c;
  border-radius: 4px;
  color: #b88230;
  font-size: 12px;
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
  max-height: 480px;
  overflow-y: auto;
  background: #fffaef;
  border-top: 1px solid #faecd8;
}
.thought-body :deep(.md-p) { margin: 8px 0; }
.thought-body :deep(.md-p:first-child) { margin-top: 0; }
.thought-body :deep(.md-p:last-child) { margin-bottom: 0; }
.thought-body :deep(.md-list) { margin: 8px 0; padding-left: 22px; }
.thought-body :deep(.md-list li) { margin: 4px 0; }
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
  padding: 12px 20px 16px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  margin-top: auto;
  flex-shrink: 0;
}
.agent-input :deep(.el-textarea__inner) {
  border-radius: 8px;
}
.send-btn {
  height: 56px;
  border-radius: 8px;
}

/* 图表渲染 */
.ai-bubble :deep(.md-chart) {
  width: 100%;
  height: 300px;
  margin: 12px 0;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}
</style>
