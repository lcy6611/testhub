<template>
  <div class="quality-gate">
    <!-- 项目选择 -->
    <el-card shadow="never" class="toolbar">
      <div class="toolbar-row">
        <span class="label">项目</span>
        <el-select
          v-model="projectId"
          filterable
          placeholder="选择项目"
          style="width: 280px"
          @change="onProjectChange"
        >
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadAll">刷新</el-button>
      </div>
    </el-card>

    <el-row :gutter="16" v-if="projectId">
      <!-- 质量门禁 -->
      <el-col :span="10">
        <el-card shadow="never" class="block">
          <template #header>
            <div class="card-head">
              <span>发布门禁</span>
              <el-button size="small" type="success" :loading="saving" @click="saveConclusion">保存发布结论</el-button>
            </div>
          </template>

          <div v-if="gate" class="gate-body">
            <el-alert
              :title="conclusionText"
              :type="conclusionType"
              :closable="false"
              show-icon
              class="conclusion"
            />
            <el-descriptions :column="2" border size="small" class="metrics">
              <el-descriptions-item label="通过率">
                {{ gate.metrics.pass_rate }}%
              </el-descriptions-item>
              <el-descriptions-item label="需求通过覆盖率">
                {{ gate.metrics.coverage_rate }}%
              </el-descriptions-item>
              <el-descriptions-item label="关联覆盖率">
                {{ gate.metrics.linked_rate }}%
              </el-descriptions-item>
              <el-descriptions-item label="执行覆盖率">
                {{ gate.metrics.executed_rate }}%
              </el-descriptions-item>
              <el-descriptions-item label="未关闭缺陷">
                {{ gate.metrics.open_defects }}
                <span class="sev">
                  (S1:{{ gate.metrics.open_by_severity.S1 }}
                   S2:{{ gate.metrics.open_by_severity.S2 }}
                   S3:{{ gate.metrics.open_by_severity.S3 }}
                   S4:{{ gate.metrics.open_by_severity.S4 }})
                </span>
              </el-descriptions-item>
              <el-descriptions-item label="阻塞">
                {{ gate.metrics.blocked }}
              </el-descriptions-item>
            </el-descriptions>
            <div class="reasons">
              <div class="reasons-title">判定依据</div>
              <ul>
                <li v-for="(r, i) in gate.reasons" :key="i">{{ r }}</li>
              </ul>
            </div>
          </div>
          <el-empty v-else description="请选择项目后刷新" />
        </el-card>
      </el-col>

      <!-- 需求三层覆盖率 -->
      <el-col :span="14">
        <el-card shadow="never" class="block">
          <template #header><span>需求三层覆盖率</span></template>
          <div v-if="coverage" class="coverage-body">
            <div class="rate-row">
              <span class="rate-label">关联用例</span>
              <el-progress :percentage="coverage.linked_rate" :stroke-width="14" />
              <span class="rate-num">{{ coverage.linked }}/{{ coverage.total_requirements }}</span>
            </div>
            <div class="rate-row">
              <span class="rate-label">已执行</span>
              <el-progress :percentage="coverage.executed_rate" :stroke-width="14" color="#e6a23c" />
              <span class="rate-num">{{ coverage.executed }}/{{ coverage.total_requirements }}</span>
            </div>
            <div class="rate-row">
              <span class="rate-label">已通过</span>
              <el-progress :percentage="coverage.passed_rate" :stroke-width="14" color="#67c23a" />
              <span class="rate-num">{{ coverage.passed }}/{{ coverage.total_requirements }}</span>
            </div>

            <el-table :data="coverage.items" size="small" max-height="320" class="cov-table">
              <el-table-column prop="requirement_name" label="需求" min-width="160" show-overflow-tooltip />
              <el-table-column label="级别" width="70">
                <template #default="{ row }">{{ levelText[row.requirement_level] || row.requirement_level }}</template>
              </el-table-column>
              <el-table-column label="关联" width="70" align="center">
                <template #default="{ row }"><el-tag :type="row.linked ? 'success' : 'info'" size="small">{{ row.linked ? '是' : '否' }}</el-tag></template>
              </el-table-column>
              <el-table-column label="执行" width="70" align="center">
                <template #default="{ row }"><el-tag :type="row.executed ? 'warning' : 'info'" size="small">{{ row.executed ? '是' : '否' }}</el-tag></template>
              </el-table-column>
              <el-table-column label="通过" width="70" align="center">
                <template #default="{ row }"><el-tag :type="row.passed ? 'success' : 'danger'" size="small">{{ row.passed ? '是' : '否' }}</el-tag></template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="暂无需求数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 缺陷列表 -->
    <el-card shadow="never" class="block" v-if="projectId">
      <template #header>
        <div class="card-head">
          <span>缺陷列表（{{ defects.length }}）</span>
          <el-button size="small" type="primary" @click="openCreate">新建缺陷</el-button>
        </div>
      </template>
      <el-table :data="defects" size="small" stripe>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column label="严重程度" width="90" align="center">
          <template #default="{ row }"><el-tag :type="sevType[row.severity]" size="small">{{ sevText[row.severity] }}</el-tag></template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }"><el-tag :type="statusType[row.status]" size="small">{{ statusText[row.status] }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="requirement" label="关联需求ID" width="110" align="center" />
        <el-table-column prop="created_at" label="创建时间" min-width="150" />
        <el-table-column label="操作" width="140" align="center">
          <template #default="{ row }">
            <el-button size="small" type="danger" plain @click="removeDefect(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 发布结论记录 -->
    <el-card shadow="never" class="block" v-if="projectId">
      <template #header><span>发布结论记录</span></template>
      <el-table :data="conclusions" size="small" stripe>
        <el-table-column label="结论" width="120" align="center">
          <template #default="{ row }"><el-tag :type="conclusionTag(row.conclusion)" size="small">{{ conclusionLabel(row.conclusion) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="metrics.pass_rate" label="通过率" width="90" align="center" />
        <el-table-column prop="metrics.coverage_rate" label="覆盖率" width="90" align="center" />
        <el-table-column prop="metrics.open_defects" label="未关闭缺陷" width="110" align="center" />
        <el-table-column prop="created_at" label="保存时间" min-width="150" />
        <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 新建缺陷弹窗 -->
    <el-dialog v-model="dialogVisible" title="新建缺陷" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="缺陷标题" />
        </el-form-item>
        <el-form-item label="严重程度">
          <el-select v-model="form.severity" style="width: 100%">
            <el-option v-for="s in sevOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联需求">
          <el-select v-model="form.requirement" filterable clearable placeholder="可选" style="width: 100%">
            <el-option v-for="r in requirements" :key="r.id" :label="`${r.requirement_id} ${r.requirement_name}`" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitDefect">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProjects } from '@/api/performance'
import { getBusinessRequirements } from '@/api/requirement-analysis'
import {
  getDefects, createDefect, deleteDefect,
  getRequirementCoverage, getQualityGate, saveQualityGate, getReleaseConclusions
} from '@/api/defects'

const projects = ref([])
const projectId = ref(null)
const requirements = ref([])
const defects = ref([])
const coverage = ref(null)
const gate = ref(null)
const conclusions = ref([])
const loading = ref(false)
const saving = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const form = ref({ title: '', severity: 'S3', status: 'open', requirement: null, description: '' })

const sevOptions = [
  { value: 'S1', label: '致命' }, { value: 'S2', label: '严重' },
  { value: 'S3', label: '一般' }, { value: 'S4', label: '轻微' }
]
const statusOptions = [
  { value: 'open', label: '待处理' }, { value: 'in_progress', label: '处理中' },
  { value: 'resolved', label: '已修复' }, { value: 'closed', label: '已关闭' },
  { value: 'reopened', label: '重新打开' }
]
const sevText = { S1: '致命', S2: '严重', S3: '一般', S4: '轻微' }
const sevType = { S1: 'danger', S2: 'danger', S3: 'warning', S4: 'info' }
const statusText = { open: '待处理', in_progress: '处理中', resolved: '已修复', closed: '已关闭', reopened: '重新打开' }
const statusType = { open: 'info', in_progress: 'warning', resolved: 'success', closed: 'success', reopened: 'danger' }
const levelText = { high: '高', medium: '中', low: '低' }

const conclusionLabel = (c) => ({ GO: '可发布', CONDITIONAL_GO: '有条件发布', NO_GO: '不可发布' }[c] || c)
const conclusionTag = (c) => ({ GO: 'success', CONDITIONAL_GO: 'warning', NO_GO: 'danger' }[c] || 'info')
const conclusionText = ref('')
const conclusionType = ref('info')
const computedConclusion = () => {
  if (!gate.value) return
  conclusionText.value = conclusionLabel(gate.value.conclusion)
  conclusionType.value = conclusionTag(gate.value.conclusion)
}

function normalize(list) {
  if (Array.isArray(list)) return list
  if (list && Array.isArray(list.results)) return list.results
  return []
}

async function loadProjects() {
  try {
    const data = await getProjects()
    projects.value = normalize(data)
    if (!projectId.value && projects.value.length) {
      projectId.value = projects.value[0].id
    }
  } catch (e) {
    ElMessage.error('加载项目列表失败：' + (e?.response?.data?.detail || e?.message || e))
  }
}

async function loadAll() {
  if (!projectId.value) return
  loading.value = true
  try {
    const [cov, g, def, rel] = await Promise.all([
      getRequirementCoverage({ project: projectId.value }),
      getQualityGate({ project: projectId.value }),
      getDefects({ project: projectId.value }),
      getReleaseConclusions({ project: projectId.value })
    ])
    coverage.value = cov
    gate.value = g
    computedConclusion()
    defects.value = normalize(def)
    conclusions.value = normalize(rel)
  } catch (e) {
    ElMessage.error('加载失败：' + (e.message || e))
  } finally {
    loading.value = false
  }
}

async function loadRequirements() {
  if (!projectId.value) return
  try {
    const data = await getBusinessRequirements({ project: projectId.value })
    requirements.value = normalize(data)
  } catch (e) { /* 忽略 */ }
}

function onProjectChange() {
  coverage.value = null
  gate.value = null
  defects.value = []
  conclusions.value = []
  loadRequirements()
  loadAll()
}

async function saveConclusion() {
  if (!projectId.value || !gate.value) return
  saving.value = true
  try {
    await saveQualityGate({ project: projectId.value, conclusion: gate.value.conclusion })
    ElMessage.success('发布结论已保存')
    const rel = await getReleaseConclusions({ project: projectId.value })
    conclusions.value = normalize(rel)
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || e))
  } finally {
    saving.value = false
  }
}

function openCreate() {
  form.value = { title: '', severity: 'S3', status: 'open', requirement: null, description: '' }
  loadRequirements()
  dialogVisible.value = true
}

async function submitDefect() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请填写缺陷标题')
    return
  }
  submitting.value = true
  try {
    await createDefect({
      project: projectId.value,
      title: form.value.title,
      severity: form.value.severity,
      status: form.value.status,
      requirement: form.value.requirement || null,
      description: form.value.description
    })
    ElMessage.success('缺陷已创建')
    dialogVisible.value = false
    loadAll()
  } catch (e) {
    ElMessage.error('创建失败：' + (e.message || e))
  } finally {
    submitting.value = false
  }
}

async function removeDefect(row) {
  try {
    await ElMessageBox.confirm(`确认删除缺陷「${row.title}」？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await deleteDefect(row.id)
    ElMessage.success('已删除')
    loadAll()
  } catch (e) {
    ElMessage.error('删除失败：' + (e.message || e))
  }
}

onMounted(async () => {
  await loadProjects()
  if (projectId.value) {
    loadRequirements()
    loadAll()
  }
})
</script>

<style scoped>
.quality-gate { display: flex; flex-direction: column; gap: 16px; }
.toolbar .toolbar-row { display: flex; align-items: center; gap: 12px; }
.toolbar .label { color: var(--app-text, #303133); font-weight: 600; }
.block { margin-bottom: 0; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.conclusion { margin-bottom: 14px; }
.metrics { margin-bottom: 12px; }
.sev { color: #909399; font-size: 12px; margin-left: 4px; }
.reasons-title { font-weight: 600; margin: 8px 0 4px; }
.reasons ul { margin: 0; padding-left: 18px; color: #606266; font-size: 13px; }
.reasons li { margin: 2px 0; }
.rate-row { display: flex; align-items: center; gap: 12px; margin: 10px 0; }
.rate-label { width: 70px; color: #606266; font-size: 13px; }
.rate-num { width: 70px; text-align: right; color: #909399; font-size: 13px; }
.cov-table { margin-top: 12px; }
</style>
