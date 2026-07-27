<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">用例详情</h1>
      <div>
        <el-button @click="$router.back()">返回</el-button>
        <el-button type="primary" @click="editTestCase">编辑</el-button>
        <el-button type="success" @click="goGenerateUI">生成UI脚本</el-button>
      </div>
    </div>
    
    <div class="card-container" v-if="testcase">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="用例标题" :span="2">{{ testcase.title }}</el-descriptions-item>
        <el-descriptions-item label="优先级">
          <el-tag :class="`priority-tag ${testcase.priority}`">{{ getPriorityText(testcase.priority) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusType(testcase.status)">{{ getStatusText(testcase.status) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="测试类型">{{ getTypeText(testcase.test_type) }}</el-descriptions-item>
        <el-descriptions-item label="归属项目">{{ testcase.project?.name || '未关联项目' }}</el-descriptions-item>
        <el-descriptions-item label="关联版本" :span="2">
          <div v-if="testcase.versions && testcase.versions.length > 0" class="version-tags">
            <el-tag 
              v-for="version in testcase.versions" 
              :key="version.id" 
              size="small" 
              :type="version.is_baseline ? 'warning' : 'info'"
              class="version-tag"
            >
              {{ version.name }}
            </el-tag>
          </div>
          <span v-else class="no-version">未关联版本</span>
        </el-descriptions-item>
        <el-descriptions-item label="作者">{{ testcase.author?.username }}</el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">{{ formatDate(testcase.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="用例描述" :span="2">{{ testcase.description || '暂无描述' }}</el-descriptions-item>
        <el-descriptions-item label="前置条件" :span="2">{{ testcase.preconditions || '无' }}</el-descriptions-item>
        <el-descriptions-item label="操作步骤" :span="2">
          <div class="steps-content">{{ testcase.steps || '无' }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="预期结果" :span="2">{{ testcase.expected_result }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div v-if="testcase" class="kg-automates-bar">
      <el-button size="small" type="primary" plain @click="openAutomatesDialog">
        关联自动化
      </el-button>
      <span class="kg-automates-hint">将用例关联到 API 接口或 UI 页面对象</span>
    </div>

    <KgRelationPanel
      v-if="testcase"
      ref="kgPanel"
      :entity-key="kgCaseEntityKey"
      title="🔗 来源与覆盖"
      mode="testcase-detail"
      empty-hint="暂无图谱数据。从 AI 生成任务一键采纳后，将自动建立溯源与 covers 覆盖边（功能模块 / 映射需求）。" />

    <!-- 套件反向绑定业务用例：展示由本用例自动生成的 UI 套件（含执行结果） -->
    <el-card v-if="testcase" class="ui-suite-card" shadow="never" style="margin-top:16px">
      <template #header>
        <span>🔗 关联 UI 自动化套件</span>
        <span class="hint">（由本用例「生成UI脚本」自动创建，可在此直接查看对应自动化套件）</span>
      </template>
      <el-table v-if="linkedGenerations.length" :data="linkedGenerations" size="small" border>
        <el-table-column prop="id" label="生成任务" width="90" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="UI 套件" min-width="220">
          <template #default="{ row }">
            <router-link v-if="row.suite_detail" :to="`/ui-automation/generate-result/${row.id}`" class="lnk">
              #{{ row.suite_detail.id }} {{ row.suite_detail.name }}
            </router-link>
            <span v-else class="muted">未生成套件</span>
          </template>
        </el-table-column>
        <el-table-column prop="elements_captured" label="元素" width="70" />
        <el-table-column label="套件通过率" width="110">
          <template #default="{ row }">
            <span v-if="row.suite_execution_detail">{{ row.suite_execution_detail.pass_rate }}%</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/ui-automation/generate-result/${row.id}`)">查看结果</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-else-if="linkedLoaded" class="muted" style="padding:8px 0">
        暂无由本用例生成的 UI 自动化套件。点击右上角「生成UI脚本」即可自动创建。
      </div>
      <div v-else class="muted" style="padding:8px 0">加载中…</div>
    </el-card>

    <el-dialog
      v-model="automatesDialogVisible"
      title="关联自动化"
      width="520px"
      destroy-on-close
      @closed="resetAutomatesDialog">
      <el-form label-width="100px">
        <el-form-item label="目标类型">
          <el-radio-group v-model="automatesTargetType">
            <el-radio value="api">API 接口</el-radio>
            <el-radio value="ui">UI 页面</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="automatesTargetType === 'api' ? 'API 接口' : 'UI 页面'">
          <el-select
            v-model="automatesSelectedId"
            filterable
            placeholder="请选择"
            style="width: 100%"
            :loading="automatesOptionsLoading">
            <el-option
              v-for="item in automatesOptions"
              :key="item.id"
              :label="item.label"
              :value="item.id" />
          </el-select>
        </el-form-item>
        <p v-if="automatesLoadError" class="automates-error">{{ automatesLoadError }}</p>
      </el-form>
      <template #footer>
        <el-button @click="automatesDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="automatesSaving"
          :disabled="!automatesSelectedId"
          @click="saveAutomatesLink">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import dayjs from 'dayjs'
import KgRelationPanel from '@/components/kg/KgRelationPanel.vue'
import { createKgEdge } from '@/api/knowledge-graph'
import { getApiRequests } from '@/api/api-testing'
import { getPageObjects, getCaseScriptGenerationsByTestcase } from '@/api/ui_automation'

const route = useRoute()
const router = useRouter()
function goGenerateUI() {
  const id = route.params.id
  if (!id) { ElMessage.warning('用例ID缺失'); return }
  router.push({ path: '/ui-automation/generate-from-case', query: { caseId: id } })
}
const testcase = ref(null)
const kgPanel = ref(null)

// 套件反向绑定：按业务用例查询其关联的 UI 脚本生成任务
const linkedGenerations = ref([])
const linkedLoaded = ref(false)

const statusType = (s) => ({ pending: 'info', running: 'warning', passed: 'success', partial: 'warning', failed: 'danger' }[s] || 'info')
const statusText = (s) => ({ pending: '等待中', running: '执行中', passed: '全部通过', partial: '部分通过', failed: '失败' }[s] || s)

async function loadLinkedGenerations() {
  if (!route.params.id) return
  linkedLoaded.value = false
  try {
    const r = await getCaseScriptGenerationsByTestcase(route.params.id)
    linkedGenerations.value = r.data.generations || []
  } catch (e) {
    linkedGenerations.value = []
  } finally {
    linkedLoaded.value = true
  }
}

const automatesDialogVisible = ref(false)
const automatesTargetType = ref('api')
const automatesSelectedId = ref(null)
const automatesOptions = ref([])
const automatesOptionsLoading = ref(false)
const automatesLoadError = ref('')
const automatesSaving = ref(false)

const kgCaseEntityKey = computed(() =>
  route.params.id ? `tc:${route.params.id}` : ''
)

const fetchTestCase = async () => {
  try {
    const response = await api.get(`/testcases/${route.params.id}/`)
    testcase.value = response.data
    await kgPanel.value?.refresh?.()
  } catch (error) {
    ElMessage.error('获取用例详情失败')
  }
}

async function loadAutomatesOptions() {
  automatesOptionsLoading.value = true
  automatesLoadError.value = ''
  automatesOptions.value = []
  try {
    if (automatesTargetType.value === 'api') {
      const resp = await getApiRequests({ page_size: 200 })
      const list = resp.data?.results || resp.data || []
      automatesOptions.value = list.map(item => ({
        id: item.id,
        label: `${item.method || 'GET'} ${item.name}`
      }))
      if (!list.length) {
        automatesLoadError.value = '暂无 API 接口，请先在 API 测试模块创建，或在知识图谱浏览页同步到图谱。'
      }
    } else {
      const resp = await getPageObjects({ page_size: 200 })
      const list = resp.data?.results || resp.data || []
      automatesOptions.value = list.map(item => ({
        id: item.id,
        label: item.name
      }))
      if (!list.length) {
        automatesLoadError.value = '暂无 UI 页面对象，请先在 UI 自动化模块创建，或在知识图谱浏览页同步到图谱。'
      }
    }
  } catch {
    automatesLoadError.value = '加载选项失败'
  } finally {
    automatesOptionsLoading.value = false
  }
}

function resetAutomatesDialog() {
  automatesSelectedId.value = null
  automatesLoadError.value = ''
  automatesOptions.value = []
}

async function openAutomatesDialog() {
  automatesDialogVisible.value = true
  automatesTargetType.value = 'api'
  resetAutomatesDialog()
  await loadAutomatesOptions()
}

async function saveAutomatesLink() {
  if (!testcase.value?.id || !automatesSelectedId.value) return
  automatesSaving.value = true
  try {
    const payload = {
      test_case_id: testcase.value.id,
      relation_type: 'automates'
    }
    if (automatesTargetType.value === 'api') {
      payload.api_request_id = automatesSelectedId.value
    } else {
      payload.ui_page_id = automatesSelectedId.value
    }
    await createKgEdge(payload)
    ElMessage.success('自动化关联已保存')
    automatesDialogVisible.value = false
    await kgPanel.value?.refresh?.()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存关联失败')
  } finally {
    automatesSaving.value = false
  }
}

watch(automatesTargetType, () => {
  if (automatesDialogVisible.value) {
    automatesSelectedId.value = null
    loadAutomatesOptions()
  }
})

const editTestCase = () => {
  router.push(`/ai-generation/testcases/${route.params.id}/edit`)
}

const getPriorityText = (priority) => {
  const textMap = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '紧急'
  }
  return textMap[priority] || priority
}

const getStatusType = (status) => {
  const typeMap = {
    draft: 'info',
    active: 'success',
    deprecated: 'warning'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    draft: '草稿',
    active: '激活',
    deprecated: '废弃'
  }
  return textMap[status] || status
}

const getTypeText = (type) => {
  const textMap = {
    functional: '功能测试',
    integration: '集成测试',
    api: 'API测试',
    ui: 'UI测试',
    performance: '性能测试',
    security: '安全测试'
  }
  return textMap[type] || '-'
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm')
}

onMounted(() => {
  fetchTestCase()
  loadLinkedGenerations()
})
</script>

<style lang="scss" scoped>
.priority-tag {
  &.low { color: #67c23a; }
  &.medium { color: #e6a23c; }
  &.high { color: #f56c6c; }
  &.critical { color: #f56c6c; font-weight: bold; }
}

.version-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  
  .version-tag {
    margin: 0;
  }
}

.no-version {
  color: #909399;
  font-size: 14px;
  font-style: italic;
}

.steps-content {
  white-space: pre-wrap;
  line-height: 1.6;
  color: #303133;
  font-family: inherit;
}

.kg-automates-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 20px;
  margin-bottom: 8px;
}

.kg-automates-hint {
  font-size: 13px;
  color: #64748b;
}

.ui-suite-card {
  .hint {
    font-size: 13px;
    color: #64748b;
    margin-left: 8px;
  }
  .lnk {
    color: #409eff;
    font-weight: 600;
  }
  .muted {
    color: #999;
  }
}

.automates-error {
  margin: 0;
  font-size: 13px;
  color: #b91c1c;
}
</style>