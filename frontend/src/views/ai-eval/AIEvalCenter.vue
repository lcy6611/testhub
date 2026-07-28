<template>
  <div class="ai-eval-center">
    <div class="header-bar">
      <div class="title">
        <el-icon><DataBoard /></el-icon>
        <span>AI 评测与反馈闭环</span>
      </div>
      <div class="filters">
        <el-select v-model="projectId" placeholder="全部项目" clearable size="default" style="width: 200px" @change="onFilterChange">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="eval-tabs">
      <!-- 效果看板 -->
      <el-tab-pane label="效果看板" name="dashboard">
        <div class="dash-toolbar">
          <el-radio-group v-model="days" @change="loadStats">
            <el-radio-button :value="7">近7天</el-radio-button>
            <el-radio-button :value="30">近30天</el-radio-button>
            <el-radio-button :value="90">近90天</el-radio-button>
          </el-radio-group>
          <el-button @click="loadStats" :icon="Refresh">刷新</el-button>
        </div>

        <div class="stat-cards" v-loading="statsLoading">
          <el-card shadow="never" header="总调用次数"><div class="stat-n">{{ stats.totals.calls || 0 }}</div></el-card>
          <el-card shadow="never" header="总 Tokens"><div class="stat-n">{{ stats.totals.total_tokens || 0 }}</div></el-card>
          <el-card shadow="never" header="估算成本(元)"><div class="stat-n">{{ Number(stats.totals.cost || 0).toFixed(4) }}</div></el-card>
          <el-card shadow="never" header="平均耗时(ms)"><div class="stat-n">{{ stats.totals.avg_latency_ms || 0 }}</div></el-card>
          <el-card shadow="never" header="成功率"><div class="stat-n">{{ Number(stats.totals.success_rate || 0).toFixed(1) }}%</div></el-card>
        </div>

        <el-row :gutter="16" style="margin-top: 16px">
          <el-col :span="12">
            <el-card shadow="never" header="按模块用量">
              <el-table :data="stats.by_module" size="small" max-height="320">
                <el-table-column prop="module" label="模块" />
                <el-table-column prop="calls" label="调用" width="90" />
                <el-table-column prop="tokens" label="Tokens" width="120" />
                <el-table-column label="成本(元)" width="110">
                  <template #default="{ row }">{{ (row.cost || 0).toFixed(4) }}</template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never" header="按日趋势">
              <el-table :data="stats.by_day" size="small" max-height="320">
                <el-table-column prop="day" label="日期" width="130" />
                <el-table-column prop="calls" label="调用" width="90" />
                <el-table-column prop="tokens" label="Tokens" width="120" />
                <el-table-column label="成本(元)" width="110">
                  <template #default="{ row }">{{ (row.cost || 0).toFixed(4) }}</template>
                </el-table-column>
              </el-table>
            </el-card>
          </el-col>
        </el-row>

        <el-card shadow="never" header="最近一次评测汇总" style="margin-top: 16px" v-if="stats.latest_eval && stats.latest_eval.total">
          <el-descriptions :column="4" border size="small">
            <el-descriptions-item label="用例数">{{ stats.latest_eval.total }}</el-descriptions-item>
            <el-descriptions-item label="已判分">{{ stats.latest_eval.scored }}</el-descriptions-item>
            <el-descriptions-item label="通过率">{{ (stats.latest_eval.pass_rate * 100).toFixed(1) }}%</el-descriptions-item>
            <el-descriptions-item label="平均分">{{ stats.latest_eval.avg_score }}</el-descriptions-item>
            <el-descriptions-item label="评测Tokens">{{ stats.latest_eval.total_tokens }}</el-descriptions-item>
            <el-descriptions-item label="评测成本(元)">{{ (stats.latest_eval.total_cost || 0).toFixed(4) }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
        <el-empty v-else description="暂无评测数据" style="margin-top: 16px" />
      </el-tab-pane>

      <!-- Prompt 版本 -->
      <el-tab-pane label="Prompt 版本" name="prompts">
        <div class="toolbar">
          <el-button type="primary" @click="openPromptDialog" :icon="Plus">新建版本</el-button>
        </div>
        <el-table :data="promptList" v-loading="promptLoading" size="small" border :show-overflow-tooltip="true">
          <el-table-column prop="key" label="标识" width="140" />
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="category" label="类别" width="100" />
          <el-table-column prop="version" label="版本" width="80" />
          <el-table-column label="启用" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_active" type="success" size="small">是</el-tag>
              <el-tag v-else type="info" size="small">否</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170" />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button v-if="!row.is_active" size="small" type="primary" @click="activatePrompt(row)">启用</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="promptDialog" title="新建提示词版本" width="680px">
          <el-form :model="promptForm" label-width="90px">
            <el-form-item label="标识"><el-input v-model="promptForm.key" placeholder="如 writer / reviewer / general" /></el-form-item>
            <el-form-item label="名称"><el-input v-model="promptForm.name" /></el-form-item>
            <el-form-item label="类别">
              <el-select v-model="promptForm.category" style="width: 100%">
                <el-option label="用例编写" value="writer" />
                <el-option label="用例评审" value="reviewer" />
                <el-option label="通用" value="general" />
                <el-option label="自定义" value="custom" />
              </el-select>
            </el-form-item>
            <el-form-item label="内容">
              <el-input v-model="promptForm.content" type="textarea" :rows="8" />
            </el-form-item>
            <el-form-item label="变更说明"><el-input v-model="promptForm.change_note" type="textarea" :rows="2" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="promptDialog = false">取消</el-button>
            <el-button type="primary" @click="submitPrompt">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- 评测数据集 -->
      <el-tab-pane label="评测数据集" name="datasets">
        <el-row :gutter="16">
          <el-col :span="9">
            <div class="toolbar">
              <el-button type="primary" @click="openDatasetDialog" :icon="Plus">新建数据集</el-button>
            </div>
            <el-table :data="datasetList" v-loading="datasetLoading" size="small" highlight-current-row @current-change="onDatasetSelect" border>
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="case_count" label="用例" width="70" />
              <el-table-column prop="created_at" label="创建" width="120" />
            </el-table>
          </el-col>
          <el-col :span="15">
            <div class="toolbar" v-if="selectedDataset">
              <span class="ds-name">用例：{{ selectedDataset.name }}</span>
              <el-button type="primary" size="small" @click="openCaseDialog" :icon="Plus">添加用例</el-button>
            </div>
            <el-empty v-if="!selectedDataset" description="请选择左侧数据集" />
            <el-table v-else :data="caseList" v-loading="caseLoading" size="small" border>
              <el-table-column prop="name" label="名称" width="180" />
              <el-table-column prop="input_text" label="输入" show-overflow-tooltip />
              <el-table-column prop="criteria" label="判分标准" show-overflow-tooltip />
              <el-table-column label="操作" width="80">
                <template #default="{ row }">
                  <el-button size="small" type="danger" @click="removeCase(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-col>
        </el-row>

        <el-dialog v-model="datasetDialog" title="新建评测数据集" width="520px">
          <el-form :model="datasetForm" label-width="80px">
            <el-form-item label="名称"><el-input v-model="datasetForm.name" /></el-form-item>
            <el-form-item label="说明"><el-input v-model="datasetForm.description" type="textarea" :rows="3" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="datasetDialog = false">取消</el-button>
            <el-button type="primary" @click="submitDataset">保存</el-button>
          </template>
        </el-dialog>

        <el-dialog v-model="caseDialog" title="添加评测用例" width="640px">
          <el-form :model="caseForm" label-width="90px">
            <el-form-item label="名称"><el-input v-model="caseForm.name" /></el-form-item>
            <el-form-item label="输入内容"><el-input v-model="caseForm.input_text" type="textarea" :rows="5" /></el-form-item>
            <el-form-item label="期望输出"><el-input v-model="caseForm.expected_output" type="textarea" :rows="3" /></el-form-item>
            <el-form-item label="判分标准"><el-input v-model="caseForm.criteria" type="textarea" :rows="3" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="caseDialog = false">取消</el-button>
            <el-button type="primary" @click="submitCase">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- 评测运行 -->
      <el-tab-pane label="评测运行" name="runs">
        <div class="toolbar">
          <el-button type="primary" @click="openRunDialog" :icon="VideoPlay">发起评测</el-button>
          <el-button @click="loadRuns" :icon="Refresh">刷新</el-button>
        </div>
        <el-table :data="runList" v-loading="runLoading" size="small" border :show-overflow-tooltip="true">
          <el-table-column prop="dataset_name" label="数据集" width="180" show-overflow-tooltip />
          <el-table-column prop="model_config_name" label="模型" width="180" show-overflow-tooltip />
          <el-table-column prop="prompt_version_label" label="提示词版本" width="140" show-overflow-tooltip />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="runTagType(row.status)" size="small">{{ runStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="通过率" width="90">
            <template #default="{ row }">
              {{ row.summary_json && row.summary_json.pass_rate != null ? (row.summary_json.pass_rate * 100).toFixed(1) + '%' : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="平均分" width="80">
            <template #default="{ row }">{{ row.summary_json && row.summary_json.avg_score != null ? row.summary_json.avg_score : '-' }}</template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="170" show-overflow-tooltip />
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openResults(row)">查看结果</el-button>
              <el-button size="small" type="warning" @click="rerun(row)" :disabled="row.status === 'running'">重跑</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="runDialog" title="发起评测运行" width="520px">
          <el-form :model="runForm" label-width="100px">
            <el-form-item label="数据集">
              <el-select v-model="runForm.dataset" style="width: 100%" @change="onRunDatasetChange">
                <el-option v-for="d in datasetList" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="评测模型">
              <el-select v-model="runForm.model_config" style="width: 100%" placeholder="选择 AI 模型配置">
                <el-option v-for="m in modelConfigs" :key="m.id" :label="`${m.name} (${m.model_name})`" :value="m.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="提示词版本">
              <el-select v-model="runForm.prompt_version" style="width: 100%" clearable placeholder="可选">
                <el-option v-for="p in promptList" :key="p.id" :label="`${p.key} v${p.version}`" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="runDialog = false">取消</el-button>
            <el-button type="primary" @click="submitRun">开始</el-button>
          </template>
        </el-dialog>

        <el-dialog v-model="resultDialog" title="评测结果" width="900px">
          <el-alert v-if="currentRun" :title="`状态：${runStatusText(currentRun.status)}`" :type="runTagType(currentRun.status) === 'danger' ? 'error' : 'info'" :closable="false" style="margin-bottom: 12px" />
          <el-alert v-if="currentRun && currentRun.status === 'failed' && currentRun.error" :title="`失败原因：${currentRun.error}`" type="error" :closable="false" style="margin-bottom: 12px" />
          <el-table :data="resultList" v-loading="resultLoading" size="small" border :show-overflow-tooltip="true">
            <el-table-column prop="case_name" label="用例" width="200" show-overflow-tooltip />
            <el-table-column label="得分" width="70">
              <template #default="{ row }">{{ row.score != null ? row.score : '-' }}</template>
            </el-table-column>
            <el-table-column label="通过" width="70">
              <template #default="{ row }">
                <el-tag v-if="row.passed === true" type="success" size="small">通过</el-tag>
                <el-tag v-else-if="row.passed === false" type="danger" size="small">未过</el-tag>
                <el-tag v-else type="info" size="small">待判</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="模型输出" min-width="220">
              <template #default="{ row }">
                <span class="cell-clip" :title="row.output">{{ truncate(row.output, 80) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="判分说明" min-width="180">
              <template #default="{ row }">
                <span class="cell-clip" :title="row.judge_note">{{ truncate(row.judge_note, 60) }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-dialog>
      </el-tab-pane>

      <!-- 反馈记录 -->
      <el-tab-pane label="反馈记录" name="feedbacks">
        <el-table :data="feedbackList" v-loading="feedbackLoading" size="small" border :show-overflow-tooltip="true">
          <el-table-column prop="module" label="来源模块" width="160" />
          <el-table-column label="评价" width="90">
            <template #default="{ row }">
              <el-tag :type="row.rating === 'positive' ? 'success' : row.rating === 'negative' ? 'danger' : 'info'" size="small">
                {{ row.rating === 'positive' ? '赞' : row.rating === 'negative' ? '踩' : '中性' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="comment" label="反馈内容" show-overflow-tooltip />
          <el-table-column prop="correction" label="修正内容" show-overflow-tooltip />
          <el-table-column prop="created_at" label="时间" width="170" />
          <el-table-column label="操作" width="110">
            <template #default="{ row }">
              <el-button v-if="!row.converted_to_case" size="small" type="primary" @click="openConvert(row)">转评测用例</el-button>
              <el-tag v-else type="success" size="small">已转</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="convertDialog" title="转为评测用例" width="420px">
          <el-form label-width="90px">
            <el-form-item label="目标数据集">
              <el-select v-model="convertForm.dataset_id" style="width: 100%" placeholder="选择数据集">
                <el-option v-for="d in datasetList" :key="d.id" :label="d.name" :value="d.id" />
              </el-select>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="convertDialog = false">取消</el-button>
            <el-button type="primary" @click="submitConvert">转换</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DataBoard, Plus, Refresh, VideoPlay } from '@element-plus/icons-vue'
import {
  getPromptVersions, createPromptVersion, activatePromptVersion,
  getDatasets, createDataset, getCases, createCase, deleteCase,
  getRuns, createRun, getRunResults, rerunRun,
  getFeedbacks, convertFeedback, getEvalStats,
} from '@/api/aiEval'
import { getProjects } from '@/api/performance'
import request from '@/utils/api'

const activeTab = ref('dashboard')
const projectId = ref(null)
const days = ref(30)
const projects = ref([])

// 后端分页响应统一转数组，兼容 [{...}] / {results: [...]} / 其他
function normalize(list) {
  if (Array.isArray(list)) return list
  if (list && Array.isArray(list.results)) return list.results
  return []
}

// 看板
const stats = reactive({ totals: { calls: 0, total_tokens: 0, cost: 0, avg_latency_ms: 0, success_rate: 0 }, by_module: [], by_day: [], latest_eval: {} })
const statsLoading = ref(false)
async function loadStats() {
  statsLoading.value = true
  try {
    const params = { days: days.value }
    if (projectId.value) params.project_id = projectId.value
    const res = await getEvalStats(params)
    const data = res?.data || res
    if (data && typeof data === 'object') {
      const t = data.totals || {}
      stats.totals = {
        calls: Number(t.calls || 0),
        total_tokens: Number(t.total_tokens || 0),
        cost: Number(t.cost || 0),
        avg_latency_ms: Number(t.avg_latency_ms || 0),
        success_rate: Number(t.success_rate || 0),
      }
      stats.by_module = Array.isArray(data.by_module) ? data.by_module : []
      stats.by_day = Array.isArray(data.by_day) ? data.by_day : []
      stats.latest_eval = (data.latest_eval && typeof data.latest_eval === 'object') ? data.latest_eval : {}
    }
  } catch (e) {
    ElMessage.error('加载看板失败')
  } finally {
    statsLoading.value = false
  }
}

// Prompt 版本
const promptList = ref([])
const promptLoading = ref(false)
const promptDialog = ref(false)
const promptForm = reactive({ key: '', name: '', category: 'general', content: '', change_note: '' })
async function loadPrompts() {
  promptLoading.value = true
  try {
    const res = await getPromptVersions()
    promptList.value = normalize(res.data || res)
  } finally { promptLoading.value = false }
}
function openPromptDialog() {
  Object.assign(promptForm, { key: '', name: '', category: 'general', content: '', change_note: '' })
  promptDialog.value = true
}
async function submitPrompt() {
  if (!promptForm.key || !promptForm.name || !promptForm.content) {
    ElMessage.warning('标识/名称/内容必填')
    return
  }
  await createPromptVersion({ ...promptForm })
  ElMessage.success('已保存新版本')
  promptDialog.value = false
  loadPrompts()
}
async function activatePrompt(row) {
  await activatePromptVersion(row.id)
  ElMessage.success('已启用该版本')
  loadPrompts()
}

// 数据集 / 用例
const datasetList = ref([])
const datasetLoading = ref(false)
const selectedDataset = ref(null)
const caseList = ref([])
const caseLoading = ref(false)
const datasetDialog = ref(false)
const datasetForm = reactive({ name: '', description: '' })
const caseDialog = ref(false)
const caseForm = reactive({ name: '', input_text: '', expected_output: '', criteria: '' })

async function loadDatasets() {
  datasetLoading.value = true
  try {
    const res = await getDatasets()
    datasetList.value = normalize(res.data || res)
  } finally { datasetLoading.value = false }
}
function openDatasetDialog() {
  Object.assign(datasetForm, { name: '', description: '' })
  datasetDialog.value = true
}
async function submitDataset() {
  if (!datasetForm.name) { ElMessage.warning('名称必填'); return }
  await createDataset({ ...datasetForm })
  ElMessage.success('数据集已创建')
  datasetDialog.value = false
  loadDatasets()
}
function onDatasetSelect(row) {
  selectedDataset.value = row
  if (row) loadCases(row.id)
}
async function loadCases(datasetId) {
  caseLoading.value = true
  try {
    const res = await getCases({ dataset_id: datasetId })
    caseList.value = normalize(res.data || res)
  } finally { caseLoading.value = false }
}
function openCaseDialog() {
  Object.assign(caseForm, { name: '', input_text: '', expected_output: '', criteria: '' })
  caseDialog.value = true
}
async function submitCase() {
  if (!selectedDataset.value) return
  if (!caseForm.name || !caseForm.input_text) { ElMessage.warning('名称/输入必填'); return }
  await createCase({ dataset: selectedDataset.value.id, ...caseForm })
  ElMessage.success('用例已添加')
  caseDialog.value = false
  loadCases(selectedDataset.value.id)
  loadDatasets()
}
async function removeCase(row) {
  await ElMessageBox.confirm('确认删除该用例？', '提示', { type: 'warning' })
  await deleteCase(row.id)
  ElMessage.success('已删除')
  loadCases(selectedDataset.value.id)
  loadDatasets()
}

// 评测运行
const runList = ref([])
const runLoading = ref(false)
const runDialog = ref(false)
const runForm = reactive({ dataset: null, model_config: null, prompt_version: null })
const modelConfigs = ref([])
const resultDialog = ref(false)
const resultList = ref([])
const resultLoading = ref(false)
const currentRun = ref(null)
let pollTimer = null

async function loadModelConfigs() {
  try {
    const res = await request.get('/requirement-analysis/ai-models/')
    modelConfigs.value = normalize(res.data || res)
  } catch (e) { /* ignore */ }
}
async function loadRuns() {
  runLoading.value = true
  try {
    const res = await getRuns()
    runList.value = normalize(res.data || res)
  } finally { runLoading.value = false }
}
function openRunDialog() {
  Object.assign(runForm, { dataset: null, model_config: null, prompt_version: null })
  runDialog.value = true
}
function onRunDatasetChange() { /* noop */ }
async function submitRun() {
  if (!runForm.dataset || !runForm.model_config) {
    ElMessage.warning('请选择数据集与评测模型')
    return
  }
  await createRun({ ...runForm })
  ElMessage.success('评测已启动（后台运行）')
  runDialog.value = false
  loadRuns()
}
function runStatusText(s) {
  return { pending: '待运行', running: '运行中', completed: '已完成', failed: '失败' }[s] || s
}
function runTagType(s) {
  return { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }[s] || 'info'
}
function truncate(text, n) {
  if (text == null) return '-'
  const s = String(text)
  return s.length > n ? s.slice(0, n) + '…' : s
}
async function openResults(run) {
  currentRun.value = run
  resultDialog.value = true
  resultLoading.value = true
  await fetchResults(run)
  if (run.status === 'running') startPoll(run)
}
async function fetchResults(run) {
  try {
    const res = await getRunResults(run.id)
    resultList.value = normalize(res.data || res)
    // 同步最新运行状态
    const updated = runList.value.find(r => r.id === run.id)
    if (updated) {
      const detail = await getRuns()
      const fresh = normalize(detail.data || detail).find(r => r.id === run.id)
      if (fresh) { currentRun.value = fresh; Object.assign(run, fresh) }
    }
  } finally { resultLoading.value = false }
}
function startPoll(run) {
  stopPoll()
  pollTimer = setInterval(async () => {
    const res = await getRuns()
    const list = normalize(res.data || res)
    const fresh = list.find(r => r.id === run.id)
    if (fresh) {
      Object.assign(run, fresh)
      currentRun.value = fresh
      if (fresh.status !== 'running') {
        await fetchResults(run)
        stopPoll()
      }
    }
  }, 2500)
}
function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
async function rerun(row) {
  await rerunRun(row.id)
  ElMessage.success('已重新启动')
  loadRuns()
  if (resultDialog.value && currentRun.value && currentRun.value.id === row.id) startPoll(row)
}

// 反馈
const feedbackList = ref([])
const feedbackLoading = ref(false)
const convertDialog = ref(false)
const convertForm = reactive({ dataset_id: null })
const convertTarget = ref(null)
async function loadFeedbacks() {
  feedbackLoading.value = true
  try {
    const res = await getFeedbacks()
    feedbackList.value = normalize(res.data || res)
  } finally { feedbackLoading.value = false }
}
function openConvert(row) {
  convertTarget.value = row
  convertForm.dataset_id = datasetList.value[0]?.id || null
  convertDialog.value = true
}
async function submitConvert() {
  if (!convertForm.dataset_id) { ElMessage.warning('请选择目标数据集'); return }
  await convertFeedback(convertTarget.value.id, { dataset_id: convertForm.dataset_id })
  ElMessage.success('已转为评测用例')
  convertDialog.value = false
  loadFeedbacks()
}

function onFilterChange() { loadStats() }

onMounted(async () => {
  try {
    const res = await getProjects()
    projects.value = normalize(res.data || res)
  } catch (e) { /* ignore */ }
  loadStats()
  loadPrompts()
  loadDatasets()
  loadRuns()
  loadFeedbacks()
  loadModelConfigs()
})
onBeforeUnmount(() => stopPoll())
</script>

<style scoped>
.ai-eval-center { padding: 16px 20px; }
.header-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.header-bar .title { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 600; }
.stat-cards { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.stat-cards .stat-n { font-size: 22px; font-weight: 700; color: #303133; line-height: 1.4; }
.stat-cards .el-card__header { font-size: 13px; color: #909399; font-weight: 500; }
.cell-clip { display: inline-block; max-width: 100%; vertical-align: middle; line-height: 1.4; }
.dash-toolbar, .toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.ds-name { font-weight: 600; margin-right: 12px; }
</style>
