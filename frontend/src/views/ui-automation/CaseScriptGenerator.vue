<template>
  <div class="case-script-gen">
    <el-card shadow="never">
      <template #header><b>用例 → UI 自动化脚本生成</b></template>
      <el-form :model="form" label-width="120px">
        <el-form-item label="源用例" required>
          <el-select v-model="form.source_testcase_ids" multiple filterable remote
                     :remote-method="searchCases" :loading="searching"
                     placeholder="按标题搜索业务用例（支持多选）" style="max-width:560px">
            <el-option v-for="c in caseOptions" :key="c.id"
                       :label="`#${c.id} ${c.title}${c.project?.name ? ' · '+c.project.name : ''}`"
                       :value="c.id" />
          </el-select>
          <span class="tip">已选 {{ form.source_testcase_ids.length }} 条用例</span>
        </el-form-item>
        <el-form-item label="目标UI项目" required>
          <el-select v-model="form.ui_project_id" placeholder="选择 UI 项目" filterable style="max-width:320px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="被测系统地址" required>
          <el-input v-model="form.base_url" placeholder="https://example.com" style="max-width:420px" />
          <span class="tip">智能体将在此地址按用例操作并抓取元素</span>
        </el-form-item>
        <el-form-item label="失败自动重试">
          <el-input-number v-model="form.retry_limit" :min="0" :max="5" :step="1" />
          <span class="tip">生成失败后的自动重试次数（0=不重试，默认 1）</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="running" @click="onGenerate">生成脚本</el-button>
          <el-button v-if="running" type="danger" @click="onStop">停止</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="current" shadow="never" style="margin-top:16px">
      <template #header>
        <span>生成进度（#{{ current.id }} · {{ current.source_testcase_title }}）</span>
        <el-tag :type="statusType" style="margin-left:8px">{{ statusText }}</el-tag>
        <el-button v-if="current.status === 'failed'" size="small" type="warning"
                   style="margin-left:12px" :loading="retrying" @click="onRetry">重试</el-button>
      </template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="抓取元素">{{ current.elements_captured }}</el-descriptions-item>
        <el-descriptions-item label="步骤总数">{{ current.steps_total }}</el-descriptions-item>
        <el-descriptions-item label="验证通过">{{ current.steps_passed }}</el-descriptions-item>
        <el-descriptions-item label="已重试" :span="3" v-if="current.retry_count">
          {{ current.retry_count }} 次（上限 {{ current.retry_limit }}）
        </el-descriptions-item>
        <el-descriptions-item label="生成的UI用例" :span="3" v-if="current.generated_test_case_detail">
          <router-link :to="testCaseLink" class="suite-link">
            #{{ current.generated_test_case_detail.id }} {{ current.generated_test_case_detail.name }}
          </router-link>
          <span class="tip">（在「UI 自动化 → 用例管理」中可看步骤、调整定位器）</span>
        </el-descriptions-item>
        <el-descriptions-item label="关联套件" :span="3" v-if="current.suite_detail">
          <router-link :to="suiteLink" class="suite-link">
            #{{ current.suite_detail.id }} {{ current.suite_detail.name }}
          </router-link>
          <span class="tip">（已自动创建并触发执行）</span>
        </el-descriptions-item>
        <el-descriptions-item label="套件执行" :span="3" v-if="current.suite_execution_detail">
          <el-tag :type="execStatusType" size="small">{{ execStatusText }}</el-tag>
          <span class="kv">通过 <b>{{ current.suite_execution_detail.passed }}</b></span>
          <span class="kv">失败 <b>{{ current.suite_execution_detail.failed }}</b></span>
          <span class="kv">通过率 <b>{{ current.suite_execution_detail.pass_rate }}%</b></span>
          <span class="tip">（已用 Playwright 真实回放，可在「套件管理」查看报告）</span>
        </el-descriptions-item>
      </el-descriptions>
      <pre class="log">{{ current.progress_log }}</pre>
    </el-card>

    <el-card v-if="elements.length" shadow="never" style="margin-top:16px">
      <template #header><b>抓取到的元素 &amp; 验证状态</b></template>
      <el-table :data="elements" size="small" border>
        <el-table-column prop="step_order" label="步骤" width="60" />
        <el-table-column prop="action_type" label="动作" width="90" />
        <el-table-column prop="description" label="目标" />
        <el-table-column label="定位器">
          <template #default="{ row }">
            <span v-if="row.element">{{ row.element.locator_strategy }}: {{ row.element.locator_value }}</span>
            <span v-else class="muted">无（无元素步骤）</span>
          </template>
        </el-table-column>
        <el-table-column label="验证" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.element"
                    :type="row.element.validation_status === 'VALID' ? 'success' : (row.element.validation_status === 'INVALID' ? 'danger' : 'info')">
              {{ row.element.validation_status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getUiProjects, createCaseScriptGeneration, getCaseScriptGenerationDetail,
  stopCaseScriptGeneration, getCaseScriptGenerationElements,
  searchTestCases, retryCaseScriptGeneration,
} from '@/api/ui_automation'

const form = ref({ source_testcase_ids: [], ui_project_id: '', base_url: '', retry_limit: 1 })
const projects = ref([])
const caseOptions = ref([])
const searching = ref(false)
const current = ref(null)
const elements = ref([])
const running = ref(false)
const retrying = ref(false)
let timer = null
const route = useRoute()

const suiteLink = computed(() => {
  const q = {}
  if (current.value?.ui_project_detail?.id) q.projectId = current.value.ui_project_detail.id
  if (current.value?.suite_detail?.id) q.suiteId = current.value.suite_detail.id
  return { path: '/ui-automation/suites', query: q }
})
const testCaseLink = computed(() => {
  const q = {}
  if (current.value?.ui_project_detail?.id) q.projectId = current.value.ui_project_detail.id
  if (current.value?.generated_test_case_detail?.id) q.caseId = current.value.generated_test_case_detail.id
  return { path: '/ui-automation/test-cases', query: q }
})

const statusType = computed(() => {
  const m = { pending: 'info', running: 'warning', passed: 'success', partial: 'warning', failed: 'danger' }
  return m[current.value?.status] || 'info'
})
const statusText = computed(() => {
  const m = { pending: '等待中', running: '执行中', passed: '全部通过', partial: '部分通过', failed: '失败' }
  return m[current.value?.status] || current.value?.status
})
const execStatusType = computed(() => {
  const s = current.value?.suite_execution_detail?.status
  const m = { SUCCESS: 'success', FAILED: 'danger', RUNNING: 'warning', PENDING: 'info' }
  return m[s] || 'info'
})
const execStatusText = computed(() => {
  const s = current.value?.suite_execution_detail?.status
  const m = { SUCCESS: '执行成功', FAILED: '执行失败', RUNNING: '执行中', PENDING: '待执行' }
  return m[s] || s || '—'
})

async function loadProjects() {
  try {
    const r = await getUiProjects({ page_size: 200 })
    projects.value = r.data.results || r.data || []
  } catch (e) { /* ignore */ }
}

async function searchCases(query) {
  const q = (query || '').trim()
  searching.value = true
  try {
    const r = await searchTestCases({ search: q, page_size: 20 })
    caseOptions.value = r.data.results || r.data || []
  } catch (e) { /* ignore */ }
  finally { searching.value = false }
}

async function ensureCaseInOptions(caseId) {
  // 若 ?caseId 进来的用例不在当前 options 中，按 id 查一次塞进去
  if (caseOptions.value.some(c => c.id === caseId)) return
  try {
    const r = await searchTestCases({ search: '', page_size: 1 })
    // list 接口无按 id 查的字段；前端只通过 search 拿到全量
    // 兜底：清空 query 拉一次全量，再过滤到目标
    const all = r.data.results || r.data || []
    caseOptions.value = all
  } catch (e) { /* ignore */ }
}

async function onGenerate() {
  if (!form.value.source_testcase_ids.length || !form.value.ui_project_id || !form.value.base_url) {
    ElMessage.warning('请填全 源用例 / 目标UI项目 / 被测系统地址')
    return
  }
  try {
    const r = await createCaseScriptGeneration({
      source_testcase_ids: form.value.source_testcase_ids.map(Number),
      ui_project_id: form.value.ui_project_id,
      base_url: form.value.base_url,
      retry_limit: form.value.retry_limit,
    })
    const arr = r.data || []
    if (!arr.length) {
      ElMessage.warning('未创建任何任务')
      return
    }
    // 多任务时：轮询展示第一个，其他用户去列表页查；单任务同原行为
    current.value = arr[0]
    elements.value = []
    running.value = true
    poll()
    if (arr.length > 1) {
      ElMessage.success(`已批量创建 ${arr.length} 条生成任务（含本页面展示的第 1 条）`)
    }
  } catch (e) {
    ElMessage.error('生成触发失败：' + (e.response?.data?.detail || e.message))
  }
}

function poll() {
  if (timer) clearInterval(timer)
  timer = setInterval(async () => {
    if (!current.value) return
    try {
      const r = await getCaseScriptGenerationDetail(current.value.id)
      current.value = r.data
      if (r.data.status !== 'running' && r.data.status !== 'pending') {
        running.value = false
        clearInterval(timer)
        if (r.data.generated_test_case) {
          const e = await getCaseScriptGenerationElements(r.data.id)
          elements.value = e.data.elements || []
        }
        if (r.data.suite_detail) {
          const exec = r.data.suite_execution_detail
          const tcName = r.data.generated_test_case_detail?.name
          if (exec) {
            ElMessage.success(`✅ 已生成 UI 用例「${tcName}」并自动建套件「${r.data.suite_detail.name}」执行：通过率 ${exec.pass_rate}%`)
          } else {
            ElMessage.success(`✅ 已生成 UI 用例「${tcName}」并自动建套件「${r.data.suite_detail.name}」`)
          }
        } else if (r.data.generated_test_case_detail) {
          ElMessage.success(`✅ 已生成 UI 用例「${r.data.generated_test_case_detail.name}」`)
        } else if (r.data.status === 'passed' || r.data.status === 'partial') {
          ElMessage.success('生成完成')
        }
      }
    } catch (e) { /* ignore */ }
  }, 2500)
}

async function onStop() {
  if (!current.value) return
  await stopCaseScriptGeneration(current.value.id)
  ElMessage.info('已发送停止信号')
}

async function onRetry() {
  if (!current.value) return
  retrying.value = true
  try {
    await retryCaseScriptGeneration(current.value.id)
    ElMessage.success('已触发重试')
    running.value = true
    current.value.status = 'running'
    poll()
  } catch (e) {
    ElMessage.error('重试触发失败：' + (e.response?.data?.detail || e.message))
  } finally {
    retrying.value = false
  }
}

onUnmounted(() => { if (timer) clearInterval(timer) })
onMounted(() => {
  loadProjects()
  // 默认拉一页空搜索的列表，避免首次输入时空选项
  searchCases('')
  if (route.query.caseId) {
    const cid = Number(route.query.caseId)
    form.value.source_testcase_ids = [cid]
  }
})
</script>

<style scoped>
.log {
  background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px;
  max-height: 360px; overflow: auto; white-space: pre-wrap; font-size: 12px;
}
.tip { color: #999; margin-left: 8px; font-size: 12px; }
.muted { color: #999; }
.suite-link { color: #409eff; font-weight: 600; }
.kv { margin-left: 14px; color: #606266; font-size: 13px; }
</style>
