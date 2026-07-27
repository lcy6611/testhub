<template>
  <div class="kb-function-config">
    <div class="page-header">
      <h1>📦 知识库功能模块</h1>
      <p>将业务功能与 Dify 知识库文档关联，生成用例时可按功能自动带入参考文档。</p>
    </div>

    <div class="toolbar">
      <el-select
        v-model="selectedDifyConfigId"
        placeholder="Dify 配置"
        style="width: 220px"
        @change="onDifyConfigChange">
        <el-option
          v-for="cfg in difyConfigs"
          :key="cfg.id"
          :label="cfg.app_type || ('配置 #' + cfg.id)"
          :value="cfg.id" />
      </el-select>
      <el-select
        v-model="selectedDatasetId"
        placeholder="知识库"
        style="width: 280px"
        :disabled="!selectedDifyConfigId"
        @change="loadFunctions">
        <el-option
          v-for="kb in knowledgeBases"
          :key="kb.id"
          :label="kb.name"
          :value="kb.id" />
      </el-select>
      <el-button type="primary" :disabled="!selectedDatasetId" @click="openDialog()">
        新增功能模块
      </el-button>
      <el-button
        :disabled="!kgEnabled || kgSyncing"
        :loading="kgSyncing"
        @click="syncToKnowledgeGraph">
        同步到图谱
      </el-button>
    </div>
    <p v-if="kgEnabled === false" class="kg-disabled-hint">
      知识图谱已禁用，无法同步。可在环境变量中设置 KNOWLEDGE_GRAPH_ENABLED=true 后重启服务。
    </p>

    <div v-if="kgEnabled && selectedDatasetId" class="impact-section">
      <h3>文档变更影响分析</h3>
      <p class="impact-desc">修改或删除 KB 文档前，查看哪些 AI 生成任务与已采纳用例可能受影响。</p>
      <div class="impact-toolbar">
        <el-select
          v-model="impactDocumentId"
          placeholder="选择知识库文档"
          filterable
          clearable
          style="width: 360px">
          <el-option
            v-for="doc in kbDocuments"
            :key="doc.id"
            :label="doc.name || doc.id"
            :value="String(doc.id)" />
        </el-select>
        <el-button
          type="primary"
          :disabled="!impactDocumentId"
          :loading="impactLoading"
          @click="analyzeImpact">
          分析影响
        </el-button>
      </div>
      <p v-if="impactError" class="impact-error">{{ impactError }}</p>
      <p v-else-if="impactQueried && impactFlatRows.length === 0" class="impact-empty">
        未发现引用该文档的生成任务，或图谱中尚无相关数据。可先「同步到图谱」或重新生成/采纳用例后再试。
      </p>
      <el-table
        v-if="impactFlatRows.length > 0"
        v-loading="impactLoading"
        :data="impactFlatRows"
        stripe
        size="small"
        style="width: 100%; margin-top: 12px">
        <el-table-column label="生成任务" min-width="200">
          <template #default="{ row }">
            <router-link
              v-if="row.task?.ref_id"
              :to="{ name: 'TaskDetail', params: { taskId: row.task.ref_id } }"
              class="impact-link">
              {{ row.task.label || row.task.ref_id }}
            </router-link>
            <span v-else>{{ row.task?.label || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="已采纳用例" min-width="200">
          <template #default="{ row }">
            <router-link
              v-if="row.testCase?.ref_id"
              :to="{ name: 'TestCaseDetail', params: { id: row.testCase.ref_id } }"
              class="impact-link">
              {{ row.testCase.label || ('用例 #' + row.testCase.ref_id) }}
            </router-link>
            <span v-else class="impact-muted">（任务未采纳用例）</span>
          </template>
        </el-table-column>
      </el-table>
      <p v-if="impactCount > 0" class="impact-summary">
        共 {{ impactTaskCount }} 个生成任务，{{ impactCaseCount }} 条已采纳用例可能受影响
      </p>
    </div>

    <div v-if="kgEnabled" class="suggested-section">
      <h3>AI 建议待确认</h3>
      <p class="suggested-desc">
        图谱 AI 建议的 <code>maps_to</code> / <code>covers</code> 边需人工确认后才会生效（确认后变为 manual/system）。
      </p>
      <div class="suggested-toolbar">
        <el-button :loading="suggestedLoading" @click="loadSuggestedEdges">刷新</el-button>
        <el-button
          type="primary"
          :disabled="!selectedDatasetId || functions.length === 0"
          :loading="suggestGenerating"
          @click="generateMapsToSuggestions">
          生成 maps_to 建议
        </el-button>
      </div>
      <p v-if="suggestedError" class="func-cases-error">{{ suggestedError }}</p>
      <p v-else-if="!suggestedLoading && filteredSuggestedEdges.length === 0" class="func-cases-hint">
        暂无待确认建议。可点击「生成 maps_to 建议」基于当前知识库功能模块与业务需求自动匹配。
      </p>
      <el-table
        v-else
        v-loading="suggestedLoading"
        :data="filteredSuggestedEdges"
        stripe
        size="small"
        style="width: 100%; margin-top: 12px">
        <el-table-column label="关系" width="88">
          <template #default="{ row }">
            {{ getKgRelationLabel(row.relation_type) }}
          </template>
        </el-table-column>
        <el-table-column label="源" min-width="160">
          <template #default="{ row }">
            {{ row.src_node?.label || row.src }}
          </template>
        </el-table-column>
        <el-table-column label="目标" min-width="160">
          <template #default="{ row }">
            {{ row.dst_node?.label || row.dst }}
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="88">
          <template #default="{ row }">
            {{ formatConfidence(row.confidence) }}
          </template>
        </el-table-column>
        <el-table-column label="说明" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.meta?.reason || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :loading="suggestedActionId === row.id && suggestedActionType === 'confirm'"
              @click="confirmSuggestedEdge(row)">
              确认
            </el-button>
            <el-button
              link
              type="danger"
              :loading="suggestedActionId === row.id && suggestedActionType === 'reject'"
              @click="rejectSuggestedEdge(row)">
              拒绝
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-table v-loading="loading" :data="functions" stripe style="width: 100%; margin-top: 16px">
      <el-table-column prop="name" label="功能名称" min-width="140" />
      <el-table-column prop="code" label="编码" width="120" />
      <el-table-column label="绑定文档" min-width="200">
        <template #default="{ row }">
          <el-tag v-for="doc in (row.documents || []).slice(0, 3)" :key="doc.id" size="small" style="margin-right: 4px">
            {{ doc.dify_document_name || doc.dify_document_id }}
          </el-tag>
          <span v-if="(row.documents || []).length > 3">+{{ row.documents.length - 3 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="关联功能" width="100">
        <template #default="{ row }">
          {{ (row.outgoing_relations || []).length }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="kgEnabled"
            link
            type="primary"
            @click="openMapRequirementDialog(row)">
            映射需求
          </el-button>
          <el-button
            v-if="kgEnabled"
            link
            type="primary"
            @click="openFuncCasesDialog(row)">
            关联用例
          </el-button>
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button link type="danger" @click="removeFunction(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="funcCasesDialogVisible"
      :title="funcCasesTitle"
      width="640px">
      <p v-if="funcCasesLoading" class="func-cases-hint">正在查询关联用例…</p>
      <p v-else-if="funcCasesError" class="func-cases-error">{{ funcCasesError }}</p>
      <p v-else-if="funcCasesRows.length === 0" class="func-cases-hint">
        暂无已采纳用例引用该功能模块。请确认生成任务已选择此功能并已采纳用例，或先点击「同步到图谱」。
      </p>
      <el-table v-else :data="funcCasesRows" stripe size="small">
        <el-table-column label="已采纳用例" min-width="180">
          <template #default="{ row }">
            <router-link
              v-if="row.testCase?.ref_id"
              :to="{ name: 'TestCaseDetail', params: { id: row.testCase.ref_id } }"
              class="impact-link">
              {{ row.testCase.label || ('用例 #' + row.testCase.ref_id) }}
            </router-link>
            <span v-else class="impact-muted">（未采纳）</span>
          </template>
        </el-table-column>
        <el-table-column label="生成任务" min-width="180">
          <template #default="{ row }">
            <router-link
              v-if="row.task?.ref_id"
              :to="{ name: 'TaskDetail', params: { taskId: row.task.ref_id } }"
              class="impact-link">
              {{ row.task.label || row.task.ref_id }}
            </router-link>
            <span v-else>—</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="funcCasesDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="mapReqDialogVisible"
      :title="mapReqTitle"
      width="620px">
      <p class="map-req-desc">
        将结构化业务需求映射到本功能模块（图谱 <code>maps_to</code> 边），供混合检索与覆盖分析使用。
      </p>
      <p v-if="mapReqLoading" class="func-cases-hint">正在加载已映射需求…</p>
      <p v-else-if="mapReqError" class="func-cases-error">{{ mapReqError }}</p>
      <template v-else>
        <el-form class="map-req-form" label-width="88px" @submit.prevent>
          <el-form-item label="业务需求" required>
            <el-select
              v-model="mapReqSelectedId"
              filterable
              clearable
              placeholder="选择需求分析中的业务需求"
              style="width: 100%"
              :loading="mapReqReqsLoading">
              <el-option
                v-for="req in businessRequirements"
                :key="req.id"
                :label="formatBusinessRequirementLabel(req)"
                :value="req.id"
                :disabled="mapReqMappedIds.has(req.id)" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              :loading="mapReqSaving"
              :disabled="!mapReqSelectedId"
              @click="saveMapRequirement">
              添加映射
            </el-button>
          </el-form-item>
        </el-form>
        <p v-if="!mapReqReqsLoading && businessRequirements.length === 0" class="func-cases-hint">
          暂无结构化业务需求。请先在「需求分析」中上传文档并完成分析。
        </p>
        <div class="map-req-list">
          <p class="map-req-list-title">已映射需求</p>
          <p v-if="mapReqRows.length === 0" class="func-cases-hint">暂无需求映射。</p>
          <el-table v-else :data="mapReqRows" stripe size="small">
            <el-table-column label="业务需求" min-width="220">
              <template #default="{ row }">
                {{ row.label }}
              </template>
            </el-table-column>
            <el-table-column label="关系" width="90">
              <template #default>maps_to</template>
            </el-table-column>
          </el-table>
        </div>
      </template>
      <template #footer>
        <el-button @click="mapReqDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑功能模块' : '新增功能模块'" width="720px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="功能名称" required>
          <el-input v-model="form.name" placeholder="如：用户登录" />
        </el-form-item>
        <el-form-item label="功能编码">
          <el-input v-model="form.code" placeholder="可选，如 login" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="绑定文档">
          <el-select
            v-model="selectedDocIds"
            multiple
            filterable
            placeholder="选择 Dify 文档"
            style="width: 100%">
            <el-option
              v-for="doc in kbDocuments"
              :key="doc.id"
              :label="doc.name || doc.id"
              :value="String(doc.id)" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联功能">
          <el-select
            v-model="relatedFunctionIds"
            multiple
            filterable
            placeholder="选择相关功能（自动扩展参考文档）"
            style="width: 100%">
            <el-option
              v-for="fn in otherFunctions"
              :key="fn.id"
              :label="fn.name"
              :value="fn.id"
              :disabled="editingId === fn.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveFunction">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import {
  getDifyKnowledgeBases,
  getDifyKnowledgeBaseDocuments,
  getKbFunctions,
  createKbFunction,
  updateKbFunction,
  deleteKbFunction,
  getBusinessRequirements
} from '@/api/requirement-analysis'
import { getKgRelationLabel } from '@/utils/kgLabels'
import {
  getKgStatus,
  syncKgKbFunctions,
  getKgImpact,
  getKgSubgraph,
  getKgEdges,
  createKgEdge,
  getKgSuggestedEdges,
  suggestKgEdges,
  confirmKgSuggestedEdges,
  rejectKgSuggestedEdges
} from '@/api/knowledge-graph'

const difyConfigs = ref([])
const selectedDifyConfigId = ref('')
const knowledgeBases = ref([])
const selectedDatasetId = ref('')
const kbDocuments = ref([])
const functions = ref([])
const loading = ref(false)
const kgEnabled = ref(null)
const kgSyncing = ref(false)
const mapReqDialogVisible = ref(false)
const mapReqLoading = ref(false)
const mapReqError = ref('')
const mapReqEdges = ref([])
const mapReqTitle = ref('需求映射')
const mapReqFunc = ref(null)
const mapReqSelectedId = ref(null)
const mapReqSaving = ref(false)
const mapReqReqsLoading = ref(false)
const businessRequirements = ref([])
const suggestedEdges = ref([])
const suggestedLoading = ref(false)
const suggestedError = ref('')
const suggestGenerating = ref(false)
const suggestedActionId = ref(null)
const suggestedActionType = ref('')
const funcCasesDialogVisible = ref(false)
const funcCasesLoading = ref(false)
const funcCasesError = ref('')
const funcCasesRows = ref([])
const funcCasesTitle = ref('关联用例')
const impactDocumentId = ref('')
const impactLoading = ref(false)
const impactError = ref('')
const impactQueried = ref(false)
const impactResults = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const selectedDocIds = ref([])
const relatedFunctionIds = ref([])

const form = ref({
  name: '',
  code: '',
  description: '',
  is_active: true
})

const otherFunctions = computed(() =>
  functions.value.filter(fn => fn.id !== editingId.value)
)

const impactFlatRows = computed(() => {
  const rows = []
  for (const item of impactResults.value) {
    const task = item.generation_task
    const cases = item.test_cases || []
    if (cases.length === 0) {
      rows.push({ task, testCase: null })
    } else {
      for (const testCase of cases) {
        rows.push({ task, testCase })
      }
    }
  }
  return rows
})

const impactTaskCount = computed(() => impactResults.value.length)

const impactCaseCount = computed(() =>
  impactResults.value.reduce((sum, item) => sum + (item.test_cases || []).length, 0)
)

const impactCount = computed(() => impactFlatRows.value.length)

const filteredSuggestedEdges = computed(() => {
  if (!selectedDatasetId.value) {
    return suggestedEdges.value
  }
  const datasetId = selectedDatasetId.value
  return suggestedEdges.value.filter(edge => {
    if (edge.relation_type === 'maps_to') {
      const ds = edge.dst_node?.properties?.dify_dataset_id
      return !ds || String(ds) === String(datasetId)
    }
    if (edge.relation_type === 'covers' && edge.dst_node?.entity_type === 'KbFunction') {
      const ds = edge.dst_node?.properties?.dify_dataset_id
      return !ds || String(ds) === String(datasetId)
    }
    return true
  })
})

function formatConfidence(value) {
  if (value == null || value === '') return '—'
  const num = Number(value)
  if (Number.isNaN(num)) return '—'
  return num.toFixed(2)
}

async function loadSuggestedEdges() {
  if (!kgEnabled.value) return
  suggestedLoading.value = true
  suggestedError.value = ''
  try {
    const resp = await getKgSuggestedEdges({ limit: 100 })
    suggestedEdges.value = resp.data?.edges || []
  } catch (error) {
    suggestedEdges.value = []
    suggestedError.value = error.response?.data?.detail || '加载待确认建议失败'
  } finally {
    suggestedLoading.value = false
  }
}

async function generateMapsToSuggestions() {
  if (!selectedDatasetId.value || functions.value.length === 0) {
    ElMessage.warning('请先选择知识库并加载功能模块')
    return
  }
  suggestGenerating.value = true
  try {
    const resp = await suggestKgEdges({
      kb_function_ids: functions.value.map(fn => fn.id),
      dataset_id: selectedDatasetId.value,
      relation_types: ['maps_to'],
      min_confidence: 0.5,
      persist: true
    })
    const counts = resp.data?.persist?.count || {}
    const saved = (counts.created || 0) + (counts.updated || 0)
    ElMessage.success(saved > 0 ? `已生成 ${saved} 条待确认建议` : '未发现新的 maps_to 建议')
    await loadSuggestedEdges()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '生成建议失败')
  } finally {
    suggestGenerating.value = false
  }
}

async function confirmSuggestedEdge(row) {
  if (!row?.id) return
  suggestedActionId.value = row.id
  suggestedActionType.value = 'confirm'
  try {
    await confirmKgSuggestedEdges([row.id])
    ElMessage.success('已确认')
    await loadSuggestedEdges()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '确认失败')
  } finally {
    suggestedActionId.value = null
    suggestedActionType.value = ''
  }
}

async function rejectSuggestedEdge(row) {
  if (!row?.id) return
  try {
    await ElMessageBox.confirm('确定拒绝该 AI 建议？', '拒绝建议', { type: 'warning' })
  } catch {
    return
  }
  suggestedActionId.value = row.id
  suggestedActionType.value = 'reject'
  try {
    await rejectKgSuggestedEdges([row.id])
    ElMessage.success('已拒绝')
    await loadSuggestedEdges()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '拒绝失败')
  } finally {
    suggestedActionId.value = null
    suggestedActionType.value = ''
  }
}

const mapReqRows = computed(() =>
  (mapReqEdges.value || []).map(edge => ({
    label: edge.src_node?.label || edge.src || '—',
    entityKey: edge.src
  }))
)

const mapReqMappedIds = computed(() => {
  const ids = new Set()
  for (const edge of mapReqEdges.value || []) {
    const refId = edge.src_node?.ref_id
    if (refId != null && refId !== '') {
      ids.add(Number(refId))
      continue
    }
    const match = String(edge.src || '').match(/^biz_req:(\d+)$/)
    if (match) ids.add(Number(match[1]))
  }
  return ids
})

function formatBusinessRequirementLabel(req) {
  const parts = [req.requirement_id, req.requirement_name].filter(Boolean)
  const base = parts.join(' · ')
  return req.module ? `${base}（${req.module}）` : base
}

async function loadBusinessRequirements() {
  mapReqReqsLoading.value = true
  try {
    const resp = await getBusinessRequirements({ page_size: 500 })
    businessRequirements.value = resp.data?.results || resp.data || []
  } catch {
    businessRequirements.value = []
  } finally {
    mapReqReqsLoading.value = false
  }
}

async function reloadMapReqEdges(funcId) {
  try {
    const resp = await getKgEdges(`kb_func:${funcId}`, {
      direction: 'in',
      relation_type: 'maps_to',
      source: 'manual'
    })
    if (!resp.data?.entity) {
      mapReqError.value = resp.data?.detail || '图谱中尚无该功能模块，请先点击「同步到图谱」'
      mapReqEdges.value = []
      return false
    }
    mapReqEdges.value = resp.data.edges || []
    return true
  } catch (error) {
    if (error.response?.status === 404) {
      mapReqError.value = error.response?.data?.detail || '图谱中尚无该功能模块，请先点击「同步到图谱」'
      mapReqEdges.value = []
      return false
    }
    throw error
  }
}

async function saveMapRequirement() {
  if (!mapReqFunc.value?.id || !mapReqSelectedId.value) {
    ElMessage.warning('请选择业务需求')
    return
  }
  mapReqSaving.value = true
  try {
    await createKgEdge({
      business_requirement_id: mapReqSelectedId.value,
      kb_function_id: mapReqFunc.value.id
    })
    ElMessage.success('需求映射已保存')
    mapReqSelectedId.value = null
    await reloadMapReqEdges(mapReqFunc.value.id)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存映射失败')
  } finally {
    mapReqSaving.value = false
  }
}

async function openMapRequirementDialog(row) {
  mapReqFunc.value = row
  mapReqTitle.value = `需求映射 · ${row.name}`
  mapReqDialogVisible.value = true
  mapReqLoading.value = true
  mapReqError.value = ''
  mapReqEdges.value = []
  mapReqSelectedId.value = null
  try {
    await Promise.all([loadBusinessRequirements(), reloadMapReqEdges(row.id)])
  } catch (error) {
    mapReqError.value = error.response?.data?.detail || '加载需求映射失败'
  } finally {
    mapReqLoading.value = false
  }
}

function parseFuncRelatedCases(subgraph, funcId) {
  const entityKey = `kb_func:${funcId}`
  const nodes = subgraph?.nodes || []
  const edges = subgraph?.edges || []
  const nodeMap = Object.fromEntries(nodes.map(n => [n.entity_key, n]))

  const taskKeys = new Set()
  for (const edge of edges) {
    if (edge.dst === entityKey && edge.relation_type === 'used_reference') {
      taskKeys.add(edge.src)
    }
  }

  const rows = []
  const tasksWithCases = new Set()
  for (const edge of edges) {
    if (edge.relation_type !== 'provenance' || !taskKeys.has(edge.dst)) continue
    const testCase = nodeMap[edge.src]
    const task = nodeMap[edge.dst]
    if (testCase?.entity_type !== 'TestCase') continue
    tasksWithCases.add(edge.dst)
    rows.push({ testCase, task })
  }

  for (const taskKey of taskKeys) {
    if (tasksWithCases.has(taskKey)) continue
    rows.push({ testCase: null, task: nodeMap[taskKey] || { entity_key: taskKey } })
  }
  return rows
}

async function openFuncCasesDialog(row) {
  funcCasesTitle.value = `关联用例 · ${row.name}`
  funcCasesDialogVisible.value = true
  funcCasesLoading.value = true
  funcCasesError.value = ''
  funcCasesRows.value = []
  try {
    const entityKey = `kb_func:${row.id}`
    const resp = await getKgSubgraph(entityKey, { depth: 2, max_nodes: 100 })
    if (!resp.data?.root) {
      funcCasesError.value = resp.data?.detail || '图谱中尚无该功能模块，请先「同步到图谱」'
      return
    }
    funcCasesRows.value = parseFuncRelatedCases(resp.data, row.id)
  } catch (error) {
    funcCasesError.value = error.response?.data?.detail || '查询关联用例失败'
  } finally {
    funcCasesLoading.value = false
  }
}

async function loadDifyConfigs() {
  const response = await api.get('/assistant/config/dify/all/')
  difyConfigs.value = Array.isArray(response.data) ? response.data : []
  const active = difyConfigs.value.find(cfg => cfg.is_active)
  if (active) selectedDifyConfigId.value = active.id
}

async function onDifyConfigChange() {
  selectedDatasetId.value = ''
  knowledgeBases.value = []
  functions.value = []
  resetImpact()
  if (!selectedDifyConfigId.value) return
  const response = await getDifyKnowledgeBases({
    dify_config_id: selectedDifyConfigId.value,
    limit: 100
  })
  knowledgeBases.value = response.data?.data || []
}

async function loadKbDocuments() {
  if (!selectedDifyConfigId.value || !selectedDatasetId.value) return
  const response = await getDifyKnowledgeBaseDocuments({
    dify_config_id: selectedDifyConfigId.value,
    dataset_id: selectedDatasetId.value,
    limit: 200
  })
  kbDocuments.value = response.data?.data || []
}

async function loadFunctions() {
  if (!selectedDatasetId.value) {
    functions.value = []
    resetImpact()
    return
  }
  resetImpact()
  loading.value = true
  try {
    await loadKbDocuments()
    const response = await getKbFunctions({ dify_dataset_id: selectedDatasetId.value })
    functions.value = response.data?.results || response.data || []
  } catch (error) {
    functions.value = []
    ElMessage.error(error.response?.data?.detail || '加载功能模块失败')
  } finally {
    loading.value = false
  }
}

function openDialog(row) {
  editingId.value = row?.id || null
  form.value = {
    name: row?.name || '',
    code: row?.code || '',
    description: row?.description || '',
    is_active: row?.is_active !== false
  }
  selectedDocIds.value = (row?.documents || []).map(d => String(d.dify_document_id))
  relatedFunctionIds.value = (row?.outgoing_relations || []).map(r => r.to_function)
  dialogVisible.value = true
}

async function saveFunction() {
  if (!form.value.name.trim()) {
    ElMessage.error('请填写功能名称')
    return
  }
  if (!selectedDatasetId.value) {
    ElMessage.error('请先选择知识库')
    return
  }

  const docNameMap = {}
  for (const doc of kbDocuments.value) {
    docNameMap[String(doc.id)] = doc.name || String(doc.id)
  }

  const payload = {
    name: form.value.name.trim(),
    code: form.value.code.trim(),
    description: form.value.description.trim(),
    dify_dataset_id: selectedDatasetId.value,
    is_active: form.value.is_active,
    documents: selectedDocIds.value.map((docId, idx) => ({
      dify_document_id: docId,
      dify_document_name: docNameMap[docId] || docId,
      is_primary: idx === 0,
      sort_order: idx
    })),
    outgoing_relations: relatedFunctionIds.value.map(toId => ({
      to_function: toId,
      relation_type: 'related'
    }))
  }

  saving.value = true
  try {
    if (editingId.value) {
      await updateKbFunction(editingId.value, payload)
    } else {
      await createKbFunction(payload)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await loadFunctions()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function removeFunction(row) {
  try {
    await ElMessageBox.confirm(`确定删除功能模块「${row.name}」？`, '确认删除', { type: 'warning' })
    await deleteKbFunction(row.id)
    ElMessage.success('已删除')
    await loadFunctions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

async function loadKgStatus() {
  try {
    const response = await getKgStatus()
    kgEnabled.value = response.data?.enabled !== false
    if (kgEnabled.value) {
      await loadSuggestedEdges()
    }
  } catch {
    kgEnabled.value = false
  }
}

async function syncToKnowledgeGraph() {
  kgSyncing.value = true
  try {
    const response = await syncKgKbFunctions()
    const count = response.data?.synced ?? 0
    ElMessage.success(`已同步 ${count} 个功能模块到知识图谱`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '同步到图谱失败')
  } finally {
    kgSyncing.value = false
  }
}

function resetImpact() {
  impactDocumentId.value = ''
  impactResults.value = []
  impactError.value = ''
  impactQueried.value = false
}

async function analyzeImpact() {
  if (!selectedDatasetId.value || !impactDocumentId.value) return
  impactLoading.value = true
  impactError.value = ''
  impactQueried.value = false
  try {
    const response = await getKgImpact(selectedDatasetId.value, impactDocumentId.value)
    impactResults.value = response.data?.impacts || []
    impactQueried.value = true
  } catch (error) {
    impactResults.value = []
    impactQueried.value = true
    impactError.value = error.response?.data?.detail || '影响分析失败'
  } finally {
    impactLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadDifyConfigs(), loadKgStatus()])
  if (selectedDifyConfigId.value) {
    await onDifyConfigChange()
  }
})
</script>

<style scoped>
.kb-function-config { max-width: 1100px; }
.page-header h1 { margin: 0 0 8px; font-size: 1.4rem; color: #2c3e50; }
.page-header p { margin: 0 0 20px; color: #666; }
.toolbar { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
.kg-disabled-hint { margin: 8px 0 0; font-size: 13px; color: #94a3b8; }
.impact-section {
  margin-top: 20px;
  padding: 16px 20px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
}
.impact-section h3 {
  margin: 0 0 6px;
  font-size: 1.05rem;
  color: #1e293b;
}
.suggested-section {
  margin-top: 20px;
  padding: 16px 20px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
}
.suggested-section h3 {
  margin: 0 0 6px;
  font-size: 1.05rem;
  color: #92400e;
}
.suggested-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #78716c;
  line-height: 1.5;
}
.suggested-desc code {
  font-size: 12px;
  background: #fef3c7;
  padding: 1px 4px;
  border-radius: 3px;
}
.suggested-toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}
.impact-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
}
.impact-toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}
.impact-error { margin: 10px 0 0; font-size: 13px; color: #b91c1c; }
.impact-empty { margin: 10px 0 0; font-size: 13px; color: #64748b; line-height: 1.5; }
.impact-summary { margin: 10px 0 0; font-size: 12px; color: #94a3b8; }
.impact-link { color: #2563eb; text-decoration: none; }
.impact-link:hover { text-decoration: underline; }
.impact-muted { color: #94a3b8; font-size: 13px; }
.func-cases-hint { margin: 0; font-size: 13px; color: #64748b; line-height: 1.5; }
.func-cases-error { margin: 0; font-size: 13px; color: #b91c1c; }
.map-req-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.map-req-desc code {
  font-size: 12px;
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 3px;
}
.map-req-form {
  margin-bottom: 16px;
}
.map-req-list-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}
.map-req-list {
  margin-top: 4px;
}
</style>
