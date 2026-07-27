<template>
  <div class="kb-chat-layout">
    <div class="sidebar">
      <div class="sidebar-header">
        <el-button type="primary" class="new-chat-btn" :icon="Plus" @click="startNewChat">
          新对话
        </el-button>
        <p class="sidebar-hint">切换历史对话</p>
      </div>
      <div class="session-list">
        <div
          v-for="session in sessions"
          :key="session.session_id"
          :class="['session-item', { active: currentSession?.session_id === session.session_id }]"
          @click="switchSession(session)"
        >
          <span class="session-title">{{ session.title || '新对话' }}</span>
          <el-popconfirm title="确定删除？" @confirm="removeSession(session.session_id)">
            <template #reference>
              <el-icon class="delete-btn" @click.stop><Delete /></el-icon>
            </template>
          </el-popconfirm>
        </div>
        <div v-if="sessions.length === 0" class="session-empty">暂无对话，请先提问或新建</div>
      </div>
    </div>

    <div class="main-panel">
      <div class="config-bar">
        <el-select
          v-model="selectedDifyConfigId"
          placeholder="Dify 配置"
          size="small"
          style="width: 180px"
          @change="onDifyConfigChange"
        >
          <el-option
            v-for="cfg in kbReadyConfigs"
            :key="cfg.id"
            :label="cfg.app_type || `配置#${cfg.id}`"
            :value="cfg.id"
          />
        </el-select>

        <el-select
          v-model="selectedDatasetId"
          placeholder="知识库"
          size="small"
          style="width: 200px"
          :loading="loadingDatasets"
          @change="onDatasetChange"
        >
          <el-option
            v-for="ds in datasets"
            :key="ds.id"
            :label="ds.name || ds.id"
            :value="ds.id"
          />
        </el-select>

        <el-button size="small" @click="scopePanelVisible = !scopePanelVisible">
          检索范围 ({{ scopeButtonLabel }})
        </el-button>

        <div class="generate-area">
          <span class="selection-tip">勾选问答 + 可附截图</span>
          <el-button size="small" link type="primary" @click="selectAllMessages">全选</el-button>
          <el-button size="small" link @click="clearMessageSelection">清空</el-button>
          <span class="selection-count">已选 {{ selectedMessageCount }} 条</span>
          <el-upload
            :show-file-list="false"
            accept="image/*"
            multiple
            :disabled="uploadingImages || imageAttachments.length >= 12"
            :before-upload="handleImageBeforeUpload"
          >
            <el-button size="small" :loading="uploadingImages">
              上传截图 ({{ imageAttachments.length }}/12)
            </el-button>
          </el-upload>
          <el-button
            type="success"
            size="small"
            :disabled="!canGenerate || generatingCases"
            :loading="generatingCases"
            @click="handleGenerateTestcases"
          >
            一键生成用例
          </el-button>
        </div>
      </div>

      <KgRelationPanel
        v-if="currentSession?.session_id"
        ref="kgPanel"
        variant="embedded"
        :entity-key="kgChatEntityKey"
        title="🔗 关联图谱"
        mode="derived-incoming"
        disabled-hint="知识图谱未启用"
        empty-hint="暂无关联数据。在本页「一键生成用例」后，将自动关联生成任务与 KB 文档。" />

      <div v-if="scopePanelVisible" class="scope-panel">
        <el-radio-group v-model="retrievalScopeMode" class="scope-mode-group" @change="onScopeModeChange">
          <el-radio label="full">检索全库</el-radio>
          <el-radio label="documents">指定文档</el-radio>
        </el-radio-group>
        <div class="scope-tip">
          <template v-if="retrievalScopeMode === 'full'">
            全库模式：调用 Dify 检索 API（语义 → 关键词 → 全文，必要时扫描全部文档）。
            Embedding 在 Dify 知识库设置中配置。
          </template>
          <template v-else>
            指定文档：仅读取勾选文档正文（不调用 Embedding，适合规避限流）。
          </template>
        </div>
        <div v-if="retrievalScopeMode === 'documents'">
          <div v-if="loadingDocuments" class="scope-loading">加载文档...</div>
          <el-checkbox-group
            v-else
            v-model="selectedDocumentIds"
            class="doc-checkboxes"
            @change="onDocumentSelectionChange"
          >
            <el-checkbox v-for="doc in documents" :key="doc.id" :label="doc.id">
              {{ doc.name || doc.id }}
            </el-checkbox>
          </el-checkbox-group>
          <div v-if="!loadingDocuments && documents.length === 0" class="scope-loading">
            该知识库暂无文档
          </div>
        </div>

        <div v-if="selectedDatasetId" class="function-scope-section">
          <div class="scope-subtitle">关联功能模块（一键生成用例时带入绑定文档）</div>
          <div v-if="loadingKbFunctions" class="scope-loading">加载功能模块...</div>
          <el-checkbox-group
            v-else-if="kbFunctions.length > 0"
            v-model="selectedFunctionIds"
            class="doc-checkboxes"
          >
            <el-checkbox v-for="fn in kbFunctions" :key="fn.id" :label="fn.id">
              {{ fn.name }}
              <span class="fn-doc-count">（{{ (fn.documents || []).length }} 篇文档）</span>
            </el-checkbox>
          </el-checkbox-group>
          <div v-else class="scope-loading">
            暂无功能模块，可在
            <router-link to="/ai-generation/kb-functions">知识图谱 → 功能模块配置</router-link>
            维护
          </div>
        </div>
        <p v-if="kgExpandLoading" class="kg-expand-preview">正在预览图谱扩展…</p>
        <p v-else-if="kgExpandPreviewText" class="kg-expand-preview">🔗 {{ kgExpandPreviewText }}</p>
      </div>

      <div ref="messagesContainer" class="messages-area">
        <div v-if="messages.length === 0" class="empty-hint">
          <h2>知识库问答</h2>
          <p>基于 Dify 知识库检索 + 大模型回答。可先选知识库与检索范围，再提问。</p>
        </div>
        <div v-else class="messages-list">
          <div
            v-for="msg in messages"
            :key="msg._clientKey || msg.id || `${msg.role}-${msg.created_at}`"
            :class="['message-row', msg.role, { 'is-selected': isMessageSelected(msg) }]"
          >
            <el-checkbox
              v-if="!msg.isPending"
              class="msg-checkbox"
              :model-value="isMessageSelected(msg)"
              @change="(val) => toggleMessageSelection(msg, val)"
              @click.stop
            />
            <div class="bubble" :class="{ 'is-error': msg.isError }">
              <div class="content" v-html="formatContent(msg.content, msg.role)"></div>
              <div v-if="msg.isPending" class="pending">
                <el-icon class="is-loading"><Loading /></el-icon> 检索并生成中...
              </div>
              <div
                v-if="getMessageSources(msg).length || getRetrievalWarnings(msg).length"
                class="sources"
              >
                <div class="sources-title">参考文档</div>
                <div v-if="getRetrievalWarnings(msg).length" class="retrieval-warnings">
                  <div v-for="(w, wi) in getRetrievalWarnings(msg)" :key="wi">{{ w }}</div>
                </div>
                <div
                  v-for="(src, si) in getMessageSources(msg)"
                  :key="`${src.document_id || src.document_name}-${si}`"
                  class="source-card"
                >
                  <div class="source-head">
                    <span class="source-name">{{ src.document_name || src.document_id || '未知文档' }}</span>
                    <span v-if="formatSourceScore(src.score)" class="source-score">
                      {{ formatSourceScore(src.score) }}
                    </span>
                  </div>
                  <div v-if="src.snippet" class="source-snippet">{{ src.snippet }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="imageAttachments.length" class="attachment-bar">
        <span class="attachment-label">生成用例参考截图（请标注用途）：</span>
        <div class="attachment-list attachment-list-detailed">
          <div v-for="(item, idx) in imageAttachments" :key="idx" class="attachment-item-detailed">
            <img :src="item.previewUrl" :alt="item.name" class="attachment-thumb-sm" />
            <div class="attachment-meta">
              <el-select v-model="item.role" size="small" style="width: 140px" @change="onImageRoleChange(item)">
                <el-option label="页面样式参考" value="ui_layout" />
                <el-option label="操作步骤参考" value="operation_step" />
              </el-select>
              <el-input
                v-model="item.caption"
                size="small"
                :placeholder="item.role === 'operation_step' ? '步骤说明' : '界面说明'"
                style="width: 140px"
              />
              <el-input-number
                v-if="item.role === 'operation_step'"
                v-model="item.step_index"
                size="small"
                :min="1"
                controls-position="right"
                style="width: 88px"
              />
            </div>
            <el-icon class="attachment-remove" @click="removeAttachment(idx)"><Delete /></el-icon>
          </div>
        </div>
        <span class="attachment-tip">截图非需求正文；需视觉 writer 模型</span>
      </div>

      <div class="input-bar">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="2"
          placeholder="输入问题，Enter 发送..."
          resize="none"
          :disabled="sending"
          @keydown.enter.exact.prevent="sendMessage"
        />
        <el-button type="primary" :disabled="!canSend" :loading="sending" @click="sendMessage">
          发送
        </el-button>
      </div>
    </div>

    <el-dialog v-model="generateDialogVisible" title="用例生成已启动" width="420px">
      <p>任务 ID：<code>{{ lastTaskId }}</code></p>
      <p v-if="kgExpandPreviewText" class="graph-expansion-hint dialog-hint">
        🔗 {{ kgExpandPreviewText }}
      </p>
      <p>可在「AI生成用例记录」中查看进度与结果。</p>
      <template #footer>
        <el-button @click="generateDialogVisible = false">留在此页</el-button>
        <el-button type="primary" @click="goToTaskDetail">查看任务</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Delete, Loading } from '@element-plus/icons-vue'
import api from '@/utils/api'
import {
  getKbChatSessions,
  createKbChatSession,
  deleteKbChatSession,
  getKbChatMessages,
  streamKbChatMessage,
  getDifyKnowledgeBases,
  getDifyKnowledgeBaseDocuments
} from '@/api/kb-chat'
import { getKbFunctions } from '@/api/requirement-analysis'
import { getKgExpandRefs } from '@/api/knowledge-graph'
import { formatGraphExpansionHint } from '@/utils/kgLabels'
import KgRelationPanel from '@/components/kg/KgRelationPanel.vue'

const router = useRouter()

const sessions = ref([])
const currentSession = ref(null)
const messages = ref([])
const selectedMessageKeys = ref(new Set())
const inputMessage = ref('')
const sending = ref(false)
const generatingCases = ref(false)
const generateDialogVisible = ref(false)
const lastTaskId = ref('')

const difyConfigs = ref([])
const selectedDifyConfigId = ref(null)
const datasets = ref([])
const selectedDatasetId = ref('')
const documents = ref([])
const selectedDocumentIds = ref([])
const kbFunctions = ref([])
const selectedFunctionIds = ref([])
const loadingKbFunctions = ref(false)
const retrievalScopeMode = ref('full')
const loadingDatasets = ref(false)
const loadingDocuments = ref(false)
const scopePanelVisible = ref(false)
const messagesContainer = ref(null)
const imageAttachments = ref([])
const uploadingImages = ref(false)
const kgPanel = ref(null)
const kgExpandPreview = ref(null)
const kgExpandLoading = ref(false)
let kgExpandTimer = null

const kgChatEntityKey = computed(() =>
  currentSession.value?.session_id ? `kb_chat:${currentSession.value.session_id}` : ''
)

const kgExpandPreviewText = computed(() => {
  const preview = kgExpandPreview.value
  if (!preview) return ''
  const fnCount = (preview.function_ids || []).length
  const docCount = (preview.document_ids || []).length
  const parts = []
  if (fnCount > 0) parts.push(`${fnCount} 个功能模块`)
  if (docCount > 0) parts.push(`${docCount} 份文档`)
  if (!parts.length) return ''
  let text = `生成时将参考 ${parts.join('、')}`
  if (preview.expanded) {
    const hint = formatGraphExpansionHint({
      graph_summary: preview.graph_summary,
      graph_expansion: preview.meta
    })
    if (hint) text += `（${hint}）`
  }
  if (preview.prompt_summary_chars > 0) {
    text += `；Prompt 将注入图谱摘要 ${preview.prompt_summary_chars} 字（≤2048）`
  }
  return text
})

async function refreshKgExpandPreview() {
  if (!selectedDatasetId.value) {
    kgExpandPreview.value = null
    return
  }
  const fnIds = selectedFunctionIds.value || []
  const docIds = retrievalScopeMode.value === 'documents' ? (selectedDocumentIds.value || []) : []
  if (fnIds.length === 0 && docIds.length === 0) {
    kgExpandPreview.value = null
    return
  }
  kgExpandLoading.value = true
  try {
    const resp = await getKgExpandRefs({
      datasetId: selectedDatasetId.value,
      functionIds: fnIds,
      documentIds: docIds,
      depth: 2
    })
    kgExpandPreview.value = resp.data
  } catch {
    kgExpandPreview.value = null
  } finally {
    kgExpandLoading.value = false
  }
}

function scheduleKgExpandPreview() {
  if (kgExpandTimer) clearTimeout(kgExpandTimer)
  kgExpandTimer = setTimeout(() => refreshKgExpandPreview(), 400)
}

watch(
  [selectedDatasetId, selectedFunctionIds, selectedDocumentIds, retrievalScopeMode],
  scheduleKgExpandPreview,
  { deep: true }
)

onBeforeUnmount(() => {
  if (kgExpandTimer) clearTimeout(kgExpandTimer)
})

const reindexOperationSteps = () => {
  let step = 1
  for (const item of imageAttachments.value) {
    if (item.role === 'operation_step') {
      item.step_index = step
      step += 1
    }
  }
}

const onImageRoleChange = (item) => {
  if (item.role === 'operation_step' && !item.step_index) {
    item.step_index = imageAttachments.value.filter(a => a.role === 'operation_step').length
  }
  reindexOperationSteps()
}

const buildImageAttachmentsPayload = () =>
  imageAttachments.value.map((item) => {
    const entry = { url: item.url, role: item.role || 'ui_layout' }
    if ((item.caption || '').trim()) entry.caption = item.caption.trim()
    if (entry.role === 'operation_step') entry.step_index = item.step_index || 1
    return entry
  })

const kbReadyConfigs = computed(() =>
  difyConfigs.value.filter(cfg => cfg.has_dataset_api_key)
)

const selectedDatasetName = computed(() => {
  const ds = datasets.value.find(d => d.id === selectedDatasetId.value)
  return ds?.name || ''
})

const scopeButtonLabel = computed(() => {
  const fnCount = selectedFunctionIds.value.length
  if (retrievalScopeMode.value === 'full') {
    return fnCount > 0 ? `全库 · ${fnCount} 功能` : '全库'
  }
  const n = selectedDocumentIds.value.length
  if (n > 0 && fnCount > 0) return `${n} 篇 · ${fnCount} 功能`
  if (n > 0) return `${n} 篇`
  if (fnCount > 0) return `${fnCount} 功能`
  return '未选文档'
})

const effectiveDocumentIds = computed(() => {
  if (retrievalScopeMode.value === 'full') return []
  return selectedDocumentIds.value
})

const buildKbPayload = () => ({
  kb_scope_mode: retrievalScopeMode.value,
  kb_document_ids: effectiveDocumentIds.value,
  kb_top_k: 5
})

const canSend = computed(() => {
  return (
    !!inputMessage.value.trim() &&
    !sending.value &&
    !!selectedDifyConfigId.value &&
    !!selectedDatasetId.value
  )
})

const canGenerate = computed(() => {
  const selected = messages.value.filter(m => !m.isPending && isMessageSelected(m))
  return selected.some(m => m.role === 'user' && (m.content || '').trim())
})

const selectedMessageCount = computed(() => {
  return messages.value.filter(m => !m.isPending && isMessageSelected(m)).length
})

const getMessageKey = (msg) => {
  if (msg?.id) return `id:${msg.id}`
  if (msg?._clientKey) return `ck:${msg._clientKey}`
  return `${msg.role}-${msg.created_at || ''}`
}

const isMessageSelected = (msg) => selectedMessageKeys.value.has(getMessageKey(msg))

const syncMessageSelection = (list) => {
  const keys = list
    .filter(m => !m.isPending && (m.content || '').trim())
    .map(getMessageKey)
  selectedMessageKeys.value = new Set(keys)
}

const selectAllMessages = () => {
  syncMessageSelection(messages.value)
}

const clearMessageSelection = () => {
  selectedMessageKeys.value = new Set()
}

const toggleMessageSelection = (msg, checked) => {
  const key = getMessageKey(msg)
  const next = new Set(selectedMessageKeys.value)
  if (checked) next.add(key)
  else next.delete(key)
  selectedMessageKeys.value = next
}

const buildRequirementFromSelectedMessages = () => {
  const selected = messages.value.filter(m => !m.isPending && isMessageSelected(m))
  if (!selected.some(m => m.role === 'user' && (m.content || '').trim())) {
    return ''
  }
  const lines = [
    `【来源】知识库对话 — ${selectedDatasetName.value || selectedDatasetId.value || '知识库'}`,
    ''
  ]
  for (const msg of selected) {
    if (!(msg.content || '').trim()) continue
    const roleLabel = msg.role === 'user' ? '用户' : '助手'
    lines.push(`${roleLabel}：${msg.content.trim()}`)
  }
  lines.push(
    '',
    '请根据以上知识库对话内容，生成完整、结构化、可执行的测试用例。',
    '须覆盖对话中讨论的功能点、业务规则与边界条件。'
  )
  return lines.join('\n')
}

const deriveGenerationTitle = () => {
  const firstUser = messages.value.find(
    m => !m.isPending && isMessageSelected(m) && m.role === 'user' && (m.content || '').trim()
  )
  const raw = (firstUser?.content || currentSession.value?.title || '知识库对话生成用例').trim()
  return raw.length > 30 ? `${raw.slice(0, 30)}...` : raw
}

const handleImageBeforeUpload = async (file) => {
  if (imageAttachments.value.length >= 12) {
    ElMessage.warning('最多上传 12 张截图')
    return false
  }
  if (!file.type?.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return false
  }
  uploadingImages.value = true
  try {
    const fd = new FormData()
    fd.append('files', file)
    const resp = await api.post('/requirement-analysis/testcase-generation/upload-images/', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    const url = (resp.data?.image_data_urls || [])[0]
    if (!url) {
      ElMessage.error('图片解析失败')
      return false
    }
    imageAttachments.value.push({
      url,
      role: 'ui_layout',
      caption: '',
      step_index: null,
      previewUrl: URL.createObjectURL(file),
      name: file.name
    })
    ElMessage.success('截图已添加，请标注用途（页面样式 / 操作步骤）')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '上传截图失败')
  } finally {
    uploadingImages.value = false
  }
  return false
}

const removeAttachment = (idx) => {
  const item = imageAttachments.value[idx]
  if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl)
  imageAttachments.value.splice(idx, 1)
  reindexOperationSteps()
}

const formatContent = (text, role = 'user') => {
  if (!text) return ''
  let content = text
  if (role === 'assistant') {
    content = content.replace(/\n*引用来源[：:].*$/s, '').trim()
  }
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

const getMessageSources = (msg) => {
  const sources = msg?.retrieval_meta?.sources
  if (!Array.isArray(sources)) return []
  return sources.filter(src => typeof src.score !== 'number' || src.score >= 0.18)
}

const formatSourceScore = (score) => {
  if (typeof score !== 'number') return ''
  const pct = score <= 1 ? score * 100 : score
  return `相关度 ${pct.toFixed(1)}%`
}

const getRetrievalWarnings = (msg) => {
  const warnings = msg?.retrieval_meta?.warnings
  if (!Array.isArray(warnings) || warnings.length === 0) return []
  // 有参考文档时不展示内部降级提示
  if (getMessageSources(msg).length > 0) return []
  return warnings
}

let scopePersistTimer = null
const schedulePersistSession = () => {
  if (!currentSession.value?.session_id) return
  clearTimeout(scopePersistTimer)
  scopePersistTimer = setTimeout(() => {
    persistSessionSettings()
  }, 300)
}

const onScopeModeChange = (mode) => {
  if (mode === 'full') {
    selectedDocumentIds.value = []
  } else if (selectedDocumentIds.value.length === 0 && documents.value.length > 0) {
    selectedDocumentIds.value = [documents.value[0].id]
  }
  schedulePersistSession()
}

const onDocumentSelectionChange = () => {
  if (selectedDocumentIds.value.length > 0) {
    retrievalScopeMode.value = 'documents'
  }
  schedulePersistSession()
}

const scrollToBottom = async () => {
  await nextTick()
  const el = messagesContainer.value
  if (el) el.scrollTop = el.scrollHeight
}

const loadDifyConfigs = async () => {
  try {
    const resp = await api.get('/assistant/config/dify/all/')
    const list = Array.isArray(resp.data) ? resp.data : []
    difyConfigs.value = list
    const ready = list.filter(c => c.has_dataset_api_key)
    if (ready.length) {
      selectedDifyConfigId.value = (ready.find(c => c.is_active) || ready[0]).id
      await loadDatasets()
    }
  } catch (e) {
    console.error(e)
  }
}

const loadDatasets = async () => {
  if (!selectedDifyConfigId.value) return
  loadingDatasets.value = true
  try {
    const resp = await getDifyKnowledgeBases({ dify_config_id: selectedDifyConfigId.value })
    datasets.value = resp.data?.data || []
    if (datasets.value.length && !selectedDatasetId.value) {
      selectedDatasetId.value = datasets.value[0].id
      await loadDocuments()
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载知识库失败')
  } finally {
    loadingDatasets.value = false
  }
}

const loadDocuments = async () => {
  if (!selectedDifyConfigId.value || !selectedDatasetId.value) {
    documents.value = []
    kbFunctions.value = []
    return
  }
  loadingDocuments.value = true
  try {
    const resp = await getDifyKnowledgeBaseDocuments({
      dify_config_id: selectedDifyConfigId.value,
      dataset_id: selectedDatasetId.value
    })
    documents.value = resp.data?.data || []
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '加载文档失败')
  } finally {
    loadingDocuments.value = false
  }
  await loadKbFunctions()
}

const loadKbFunctions = async () => {
  if (!selectedDatasetId.value) {
    kbFunctions.value = []
    return
  }
  loadingKbFunctions.value = true
  try {
    const resp = await getKbFunctions({
      dify_dataset_id: selectedDatasetId.value,
      is_active: 'true'
    })
    kbFunctions.value = resp.data?.results || resp.data || []
    const validIds = new Set(kbFunctions.value.map(fn => fn.id))
    selectedFunctionIds.value = selectedFunctionIds.value.filter(id => validIds.has(id))
  } catch (e) {
    console.error(e)
    kbFunctions.value = []
  } finally {
    loadingKbFunctions.value = false
  }
}

const onDifyConfigChange = async () => {
  selectedDatasetId.value = ''
  selectedDocumentIds.value = []
  selectedFunctionIds.value = []
  retrievalScopeMode.value = 'full'
  await loadDatasets()
}

const onDatasetChange = async () => {
  selectedDocumentIds.value = []
  selectedFunctionIds.value = []
  retrievalScopeMode.value = 'full'
  await loadDocuments()
  if (currentSession.value?.session_id) {
    await persistSessionSettings()
  }
}

const persistSessionSettings = async () => {
  if (!currentSession.value?.session_id) return
  const sessionId = currentSession.value.session_id
  try {
    const resp = await api.patch(
      `/requirement-analysis/kb-chat/sessions/${sessionId}/`,
      {
        dify_config: selectedDifyConfigId.value,
        dify_dataset_id: selectedDatasetId.value,
        dify_dataset_name: selectedDatasetName.value,
        kb_scope_mode: retrievalScopeMode.value,
        kb_document_ids: effectiveDocumentIds.value,
        kb_top_k: 5
      }
    )
    currentSession.value = {
      ...currentSession.value,
      ...resp.data,
      session_id: resp.data.session_id || sessionId
    }
    const idx = sessions.value.findIndex(s => s.session_id === sessionId)
    if (idx >= 0) {
      sessions.value[idx] = { ...sessions.value[idx], ...currentSession.value }
    }
  } catch (e) {
    console.error(e)
  }
}

const loadSessions = async () => {
  try {
    const resp = await getKbChatSessions()
    const data = resp.data
    sessions.value = Array.isArray(data) ? data : (data?.results || [])
  } catch (e) {
    console.error(e)
  }
}

const loadMessages = async (sessionId) => {
  try {
    const resp = await getKbChatMessages(sessionId)
    messages.value = resp.data || []
    syncMessageSelection(messages.value)
    await scrollToBottom()
  } catch (e) {
    console.error(e)
  }
}

const startNewChat = async () => {
  if (!selectedDifyConfigId.value || !selectedDatasetId.value) {
    ElMessage.warning('请先选择 Dify 配置与知识库')
    return null
  }
  try {
    const resp = await createKbChatSession({
      title: '新对话',
      dify_config: selectedDifyConfigId.value,
      dify_dataset_id: selectedDatasetId.value,
      dify_dataset_name: selectedDatasetName.value,
      kb_scope_mode: 'full',
      kb_document_ids: [],
      kb_top_k: 5
    })
    currentSession.value = resp.data
    retrievalScopeMode.value = 'full'
    selectedDocumentIds.value = []
    messages.value = []
    sessions.value.unshift(resp.data)
    return resp.data.session_id
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建会话失败')
    return null
  }
}

const ensureSessionForSend = async () => {
  if (currentSession.value?.session_id) {
    const sessionId = currentSession.value.session_id
    await persistSessionSettings()
    return sessionId
  }
  return startNewChat()
}

const createClientKey = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

const markAssistantError = (err) => {
  const last = messages.value[messages.value.length - 1]
  if (last?.isPending) {
    last.isPending = false
    last.isError = true
    last.content = last.content || `回复失败：${err?.message || '未知错误'}`
  }
}

const replaceTempMessages = (payload, fallbackUserText) => {
  if (messages.value.length >= 2 && messages.value[messages.value.length - 1]?.isPending) {
    messages.value.splice(-2, 2)
  }
  if (payload?.user_message) {
    messages.value.push({ ...payload.user_message, _clientKey: createClientKey() })
  } else if (fallbackUserText) {
    messages.value.push({ role: 'user', content: fallbackUserText, _clientKey: createClientKey() })
  }
  if (payload?.assistant_message) {
    messages.value.push({ ...payload.assistant_message, _clientKey: createClientKey() })
  }
  syncMessageSelection(messages.value)
}

const updateSessionTitle = (text) => {
  if (!currentSession.value?.session_id || !text) return
  const title = text.length > 20 ? `${text.slice(0, 20)}...` : text
  if (!currentSession.value.title || currentSession.value.title === '新对话') {
    currentSession.value.title = title
    const idx = sessions.value.findIndex(s => s.session_id === currentSession.value.session_id)
    if (idx >= 0) {
      sessions.value[idx] = { ...sessions.value[idx], title }
    }
  }
}

const switchSession = async (session) => {
  currentSession.value = session
  selectedDifyConfigId.value = session.dify_config || selectedDifyConfigId.value
  selectedDatasetId.value = session.dify_dataset_id || ''
  retrievalScopeMode.value = session.kb_scope_mode || (
    (session.kb_document_ids?.length > 0) ? 'documents' : 'full'
  )
  selectedDocumentIds.value = retrievalScopeMode.value === 'documents'
    ? [...(session.kb_document_ids || [])]
    : []
  if (selectedDifyConfigId.value) await loadDatasets()
  if (selectedDatasetId.value) await loadDocuments()
  await loadMessages(session.session_id)
  await kgPanel.value?.refresh?.()
}

const removeSession = async (sessionId) => {
  try {
    await deleteKbChatSession(sessionId)
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
    if (currentSession.value?.session_id === sessionId) {
      currentSession.value = null
      messages.value = []
    }
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text || sending.value) return
  if (!selectedDifyConfigId.value || !selectedDatasetId.value) {
    ElMessage.warning('请先选择 Dify 配置与知识库')
    return
  }
  if (retrievalScopeMode.value === 'documents' && effectiveDocumentIds.value.length === 0) {
    ElMessage.warning('「指定文档」模式下请至少勾选一篇文档')
    return
  }

  const sessionId = await ensureSessionForSend()
  if (!sessionId) return

  sending.value = true
  inputMessage.value = ''

  const userTemp = { role: 'user', content: text, _clientKey: createClientKey() }
  const aiTemp = { role: 'assistant', content: '', isPending: true, _clientKey: createClientKey() }
  messages.value.push(userTemp, aiTemp)
  await scrollToBottom()

  try {
    await streamKbChatMessage(
      {
        session_id: sessionId,
        message: text,
        dify_config_id: selectedDifyConfigId.value,
        dify_dataset_id: selectedDatasetId.value,
        dify_dataset_name: selectedDatasetName.value,
        ...buildKbPayload()
      },
      {
        onChunk: (chunk) => {
          const last = messages.value[messages.value.length - 1]
          if (last?.isPending) {
            last.content += chunk
          }
          scrollToBottom()
        },
        onDone: (payload) => {
          replaceTempMessages(payload, text)
          updateSessionTitle(text)
        },
        onError: (err) => {
          markAssistantError(err)
          ElMessage.error(err.message || '发送失败')
        }
      }
    )
  } catch (e) {
    if (messages.value[messages.value.length - 1]?.isPending) {
      markAssistantError(e)
      if (!messages.value[messages.value.length - 1]?.content?.startsWith('回复失败')) {
        ElMessage.error(e?.message || '发送失败')
      }
    }
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

const handleGenerateTestcases = async () => {
  const requirementText = buildRequirementFromSelectedMessages()
  if (!requirementText) {
    ElMessage.warning('请至少勾选一条用户消息（及其相关助手回复）')
    return
  }
  if (!selectedDifyConfigId.value || !selectedDatasetId.value) {
    ElMessage.warning('请先选择 Dify 配置与知识库')
    return
  }

  generatingCases.value = true
  try {
    const sessionId = await ensureSessionForSend()
    if (!sessionId) return

    const requestData = {
      title: deriveGenerationTitle(),
      requirement_text: requirementText,
      output_mode: 'stream',
      dify_config_id: selectedDifyConfigId.value,
      dify_dataset_id: selectedDatasetId.value,
      dify_dataset_name: selectedDatasetName.value,
      kb_top_k: 5,
      kb_chat_session_id: sessionId
    }
    if (retrievalScopeMode.value === 'documents' && effectiveDocumentIds.value.length > 0) {
      requestData.kb_document_ids = effectiveDocumentIds.value
    }
    if (selectedFunctionIds.value.length > 0) {
      requestData.kb_function_ids = [...selectedFunctionIds.value]
    }
    if (
      (requestData.kb_document_ids && requestData.kb_document_ids.length > 0)
      || (requestData.kb_function_ids && requestData.kb_function_ids.length > 0)
    ) {
      requestData.kb_reference_mode = 'documents'
    }
    const imagePayload = buildImageAttachmentsPayload()
    if (imagePayload.length > 0) {
      requestData.image_attachments = imagePayload
    }

    const resp = await api.post('/requirement-analysis/testcase-generation/generate/', requestData)
    lastTaskId.value = resp.data.task_id
    generateDialogVisible.value = true
    await kgPanel.value?.refresh?.()
    ElMessage.success('用例生成任务已启动，流程与 AI 用例生成一致')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '启动生成失败')
  } finally {
    generatingCases.value = false
  }
}

const goToTaskDetail = () => {
  generateDialogVisible.value = false
  if (lastTaskId.value) {
    router.push(`/ai-generation/task-detail/${lastTaskId.value}`)
  }
}

onMounted(async () => {
  await loadDifyConfigs()
  await loadSessions()
  if (!currentSession.value && sessions.value.length > 0) {
    await switchSession(sessions.value[0])
  }
})
</script>

<style scoped lang="scss">
.kb-chat-layout {
  display: flex;
  height: calc(100vh - 64px - 40px);
  margin: -20px;
  width: calc(100% + 40px);
  background: #f5f7fa;
  overflow: hidden;
}

.sidebar {
  width: 240px;
  background: #001529;
  color: rgba(255, 255, 255, 0.75);
  display: flex;
  flex-direction: column;

  .sidebar-header {
    padding: 16px;
    .new-chat-btn { width: 100%; }
    .sidebar-hint {
      margin: 10px 0 0;
      font-size: 11px;
      line-height: 1.4;
      color: rgba(255, 255, 255, 0.45);
    }
  }

  .session-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 8px 16px;
  }

  .session-empty {
    padding: 12px;
    font-size: 12px;
    color: rgba(255, 255, 255, 0.45);
    text-align: center;
  }

  .session-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-radius: 6px;
    cursor: pointer;
    margin-bottom: 4px;

    &:hover, &.active {
      background: rgba(255, 255, 255, 0.08);
    }

    &.active .session-title {
      color: #fff;
      font-weight: 600;
    }

    .session-title {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-size: 13px;
    }

    .delete-btn {
      flex-shrink: 0;
      opacity: 0.5;
      &:hover { opacity: 1; color: #ff7875; }
    }
  }
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.config-bar {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;

  .generate-area {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
    flex-wrap: wrap;
  }

  .selection-tip {
    font-size: 12px;
    color: #909399;
  }

  .selection-count {
    font-size: 12px;
    color: #606266;
    min-width: 64px;
  }
}

.kg-expand-preview {
  margin: 10px 0 0;
  padding: 8px 12px;
  font-size: 12px;
  color: #1e40af;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  line-height: 1.5;
}
.dialog-hint {
  margin: 10px 0;
}

.scope-panel {
  flex-shrink: 0;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  padding: 12px 16px;
  max-height: 220px;
  overflow-y: auto;

  .scope-mode-group {
    margin-bottom: 10px;
  }

  .scope-tip {
    font-size: 12px;
    color: #909399;
    margin-bottom: 8px;
  }

  .doc-checkboxes {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 16px;
  }

  .function-scope-section {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px dashed #ebeef5;
  }

  .scope-subtitle {
    font-size: 12px;
    color: #606266;
    margin-bottom: 8px;
  }

  .fn-doc-count {
    color: #909399;
    font-size: 12px;
  }
}

.messages-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
}

.messages-list {
  display: flex;
  flex-direction: column;
}

.empty-hint {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #909399;
  h2 { color: #303133; margin-bottom: 8px; }
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 16px;

  &.user { justify-content: flex-end; }
  &.assistant { justify-content: flex-start; }

  &.is-selected .bubble {
    box-shadow: 0 0 0 1px #b3d8ff;
  }

  .msg-checkbox {
    flex-shrink: 0;
    margin-top: 12px;
  }

  &.user .msg-checkbox {
    order: 2;
    margin-top: 12px;
  }

  .bubble {
    max-width: 78%;
    padding: 12px 16px;
    border-radius: 12px;
    line-height: 1.6;
    font-size: 14px;
  }

  &.user .bubble {
    background: #409eff;
    color: #fff;
  }

  &.assistant .bubble {
    background: #fff;
    border: 1px solid #e4e7ed;
    color: #303133;

    &.is-error {
      border-color: #fbc4c4;
      background: #fef0f0;
      color: #f56c6c;
    }
  }

  .pending {
    margin-top: 8px;
    font-size: 12px;
    color: #909399;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .sources {
    margin-top: 12px;
    padding-top: 10px;
    border-top: 1px dashed #e4e7ed;

    .sources-title {
      font-size: 12px;
      color: #909399;
      margin-bottom: 8px;
    }

    .retrieval-warnings {
      font-size: 12px;
      color: #e6a23c;
      margin-bottom: 8px;
      line-height: 1.5;
    }

    .source-card {
      background: #f5f7fa;
      border-radius: 8px;
      padding: 8px 10px;
      margin-bottom: 6px;

      &:last-child { margin-bottom: 0; }
    }

    .source-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 4px;
    }

    .source-name {
      font-size: 13px;
      font-weight: 600;
      color: #303133;
    }

    .source-score {
      font-size: 12px;
      color: #409eff;
      white-space: nowrap;
    }

    .source-snippet {
      font-size: 12px;
      color: #606266;
      line-height: 1.5;
    }
  }
}

.attachment-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  background: #fafafa;
  border-top: 1px solid #ebeef5;
  flex-wrap: wrap;

  .attachment-label {
    font-size: 12px;
    color: #606266;
    flex-shrink: 0;
  }

  .attachment-tip {
    font-size: 11px;
    color: #909399;
    margin-left: auto;
  }

  .attachment-list {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .attachment-list-detailed {
    flex: 1;
    align-items: flex-start;
  }

  .attachment-item-detailed {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border: 1px solid #dcdfe6;
    border-radius: 6px;
    background: #fff;
  }

  .attachment-thumb-sm {
    width: 56px;
    height: 40px;
    object-fit: cover;
    border-radius: 4px;
    flex-shrink: 0;
  }

  .attachment-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }

  .attachment-item {
    position: relative;
    width: 72px;
    height: 48px;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    overflow: hidden;

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .attachment-remove {
      position: absolute;
      top: 2px;
      right: 2px;
      background: rgba(0, 0, 0, 0.45);
      color: #fff;
      border-radius: 50%;
      padding: 2px;
      cursor: pointer;
    }
  }
}

.input-bar {
  flex-shrink: 0;
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  background: #fff;
  border-top: 1px solid #ebeef5;
  align-items: flex-end;

  .el-textarea { flex: 1; }
}
</style>
