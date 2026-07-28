<template>
  <div class="project-overview">
    <!-- 顶部：项目选择器 + 项目信息卡 -->
    <div class="header-row">
      <el-select
        v-model="selectedProjectId"
        placeholder="选择项目查看概览"
        filterable
        style="width: 320px"
        @change="onProjectChange"
      >
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <span v-if="overview?.project" class="project-tag">
        项目 ID: {{ overview.project.id }} · 描述: {{ overview.project.description || '—' }}
      </span>
    </div>

    <!-- 加载中 / 空态 -->
    <el-empty v-if="!selectedProjectId" description="请先选择项目" />
    <el-skeleton v-else-if="loading" :rows="8" animated />

    <template v-else-if="overview">
      <!-- 项目概览卡 -->
      <el-card class="hero-card" shadow="never">
        <div class="hero-title">
          <h2>📌 项目概览 · {{ overview.project.name }}</h2>
          <span class="hero-meta">
            <el-tag v-if="overview.test_types.functional_test.generation_tasks_done > 0" type="success" size="small">
              已生成 {{ overview.test_types.functional_test.generation_tasks_done }} 批用例
            </el-tag>
            <el-tag v-if="overview.knowledge_hub.kb_total > 0" type="warning" size="small">
              {{ overview.knowledge_hub.kb_published }} 个已发布 KB
            </el-tag>
            <el-tag v-if="overview.test_types.functional_test.coverage_pct > 0" type="info" size="small">
              覆盖率 {{ overview.test_types.functional_test.coverage_pct }}%
            </el-tag>
          </span>
        </div>
        <p class="hero-desc">{{ overview.project.description || '暂无项目描述' }}</p>
        <div class="hero-actions">
          <el-button type="primary" plain @click="router.push('/configuration/knowledge-hub/home')">🧠 知识中枢</el-button>
          <el-button @click="router.push('/ai-generation/kg-browse')">📊 知识图谱</el-button>
          <el-button @click="router.push('/ai-generation/testcases')">📋 测试用例</el-button>
          <el-button @click="router.push('/ai-generation/projects')">📁 项目管理</el-button>
        </div>
      </el-card>

      <!-- 第一排：6 个总览统计卡 -->
      <h3 class="section-title">📊 数据汇总</h3>
      <div class="stat-grid">
        <div class="stat-card" v-for="card in statCards" :key="card.key" @click="card.to && router.push(card.to)">
          <div class="stat-icon">{{ card.icon }}</div>
          <div class="stat-value">{{ card.value }}</div>
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-hint">{{ card.hint }}</div>
        </div>
      </div>

      <!-- 第二排：检索编排链路（前移到第2个位置） -->
      <h3 class="section-title">🔗 检索编排链路</h3>
      <el-card shadow="never" class="pipeline-card">
        <div class="pipeline">
          <div v-for="(step, idx) in pipelineSteps" :key="step.key" class="pipeline-step" :class="{ 'is-on': step.on, 'is-off': !step.on }">
            <div class="step-num">{{ idx + 1 }}</div>
            <div class="step-name">{{ step.name }}</div>
            <div class="step-status">{{ step.on ? '✓ 已配置' : '✗ 未配置' }}</div>
            <div v-if="idx < pipelineSteps.length - 1" class="step-arrow">→</div>
          </div>
        </div>
      </el-card>

      <!-- 第三排：按测试类型 6 卡独立展示（性能/评审 拆开） -->
      <h3 class="section-title">🧪 按测试类型拆分</h3>
      <div class="grid-note">
        💡 <b>通过率</b> = 已通过数 / 总数，适用于所有测试类型；<b>评分</b> 仅「用例评审」模块有实际数值（<code>TestCaseReview.score</code>，0-100 分），其余类型暂无统一评分字段。
      </div>
      <div class="test-type-grid">
        <el-card
          v-for="card in testTypeCards"
          :key="card.key"
          shadow="never"
          class="test-type-card"
          :class="['tt-' + card.key, card.allZero ? 'tt-empty' : '']"
        >
          <template #header>
            <div class="tt-header">
              <span class="tt-icon">{{ card.icon }}</span>
              <span class="tt-title">{{ card.title }}</span>
              <el-tag
                v-if="!card.allZero"
                :type="(card.rate ?? 0) >= 80 ? 'success' : ((card.rate ?? 0) >= 50 ? 'warning' : 'danger')"
                size="small"
                effect="plain"
              >
                {{ card.rateLabel || '通过率' }} {{ card.rate ?? 0 }}%
              </el-tag>
            </div>
          </template>
          <div v-if="card.allZero" class="tt-empty-tip">
            暂无该类型测试数据
            <div class="tt-empty-hint">{{ card.emptyHint }}</div>
          </div>
          <div v-else class="tt-body">
            <div v-for="item in card.items" :key="item.label" class="tt-row">
              <span class="tt-label">{{ item.label }}</span>
              <span class="tt-value" :class="{ 'is-high': item.highlight, 'is-score': item.isScore }">{{ item.value }}</span>
            </div>
            <div v-if="card.lastLabel" class="tt-last">
              <span class="tt-last-label">▸ {{ card.lastLabel }}</span>
              <span class="tt-last-time">{{ card.lastTime }}</span>
              <el-tag v-if="card.lastStatus" size="small" :type="card.lastStatusType" effect="plain">
                {{ card.lastStatus }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 第四排：AI 智能模式 -->
      <h3 class="section-title">🤖 AI 智能模式</h3>
      <div class="grid-note">
        💡 AI 用例生成按项目直接聚合；Dify 智能助手 / Hermes 数字人按 <b>项目成员</b>（ProjectMember）自动汇总其会话与消息数。
      </div>
      <div class="ai-grid">
        <el-card
          v-for="card in aiSmartCards"
          :key="card.key"
          shadow="never"
          class="ai-card"
          :class="['ai-' + card.key, card.allZero ? 'tt-empty' : '']"
        >
          <template #header>
            <div class="tt-header">
              <span class="tt-icon">{{ card.icon }}</span>
              <span class="tt-title">{{ card.title }}</span>
            </div>
          </template>
          <div v-if="card.allZero" class="tt-empty-tip">
            暂无该类型数据
            <div class="tt-empty-hint">{{ card.emptyHint }}</div>
          </div>
          <div v-else class="tt-body">
            <div v-for="item in card.items" :key="item.label" class="tt-row">
              <span class="tt-label">{{ item.label }}</span>
              <span class="tt-value" :class="{ 'is-high': item.highlight }">{{ item.value }}</span>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 第五排：知识图谱概览 + 知识中枢详情 -->
      <h3 class="section-title">🧠 知识图谱 & 知识中枢</h3>
      <div class="two-col">
        <el-card shadow="never">
          <template #header>
            <span>📊 知识图谱概览</span>
            <el-tag size="small" type="info" style="margin-left:8px">
              {{ overview.knowledge_graph.nodes }} 节点 / {{ overview.knowledge_graph.edges }} 边
            </el-tag>
          </template>
          <div v-if="!overview.knowledge_graph.node_by_type.length" class="empty-tip">
            该项目暂无图谱节点（先去图谱浏览页同步数据）
          </div>
          <div v-else>
            <div v-for="row in topNodeTypes" :key="row.entity_type" class="bar-row">
              <span class="bar-label">{{ entityTypeLabel(row.entity_type) }}</span>
              <el-progress
                :percentage="Math.round(row.count / maxNodeCount * 100)"
                :format="() => row.count"
                :stroke-width="14"
              />
            </div>
          </div>
        </el-card>

        <el-card shadow="never">
          <template #header><span>🧠 知识中枢</span></template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="本地 KB">{{ overview.knowledge_hub.kb_total }}</el-descriptions-item>
            <el-descriptions-item label="已发布">{{ overview.knowledge_hub.kb_published }}</el-descriptions-item>
            <el-descriptions-item label="文档">{{ overview.knowledge_hub.doc_total }}</el-descriptions-item>
            <el-descriptions-item label="已解析">{{ overview.knowledge_hub.doc_parsed }}</el-descriptions-item>
            <el-descriptions-item label="向量分块">{{ overview.knowledge_hub.chunk_total }}</el-descriptions-item>
            <el-descriptions-item label="外部数据源">{{ overview.knowledge_hub.source_total }}</el-descriptions-item>
            <el-descriptions-item label="KB 绑定">{{ overview.knowledge_hub.kb_bindings }}</el-descriptions-item>
            <el-descriptions-item label="文档共享">{{ overview.knowledge_hub.doc_bindings }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </div>

      <!-- 第六排：发布门禁（合并自质量门禁页，随项目切换） -->
      <template v-if="selectedProjectId">
        <h3 class="section-title">🚦 发布门禁</h3>
        <div class="grid-note">
          💡 <b>需求→缺陷闭环</b>的质量关卡：通过率 / 覆盖率 / 未关闭缺陷三维判定发布结论。可在此保存发布结论、登记缺陷。
        </div>

        <el-row :gutter="16">
          <!-- 发布门禁结论 -->
          <el-col :span="10">
            <el-card shadow="never" class="block">
              <template #header>
                <div class="card-head">
                  <span>发布门禁</span>
                  <el-button size="small" type="success" :loading="gateSaving" @click="saveGateConclusion">保存发布结论</el-button>
                </div>
              </template>
              <div v-if="gate" class="gate-body">
                <el-alert
                  :title="gateConclusionText"
                  :type="gateConclusionType"
                  :closable="false"
                  show-icon
                  class="conclusion"
                />
                <el-descriptions :column="2" border size="small" class="metrics">
                  <el-descriptions-item label="通过率">{{ gate.metrics.pass_rate }}%</el-descriptions-item>
                  <el-descriptions-item label="需求通过覆盖率">{{ gate.metrics.coverage_rate }}%</el-descriptions-item>
                  <el-descriptions-item label="关联覆盖率">{{ gate.metrics.linked_rate }}%</el-descriptions-item>
                  <el-descriptions-item label="执行覆盖率">{{ gate.metrics.executed_rate }}%</el-descriptions-item>
                  <el-descriptions-item label="未关闭缺陷">
                    {{ gate.metrics.open_defects }}
                    <span class="sev">
                      (S1:{{ gate.metrics.open_by_severity.S1 }}
                       S2:{{ gate.metrics.open_by_severity.S2 }}
                       S3:{{ gate.metrics.open_by_severity.S3 }}
                       S4:{{ gate.metrics.open_by_severity.S4 }})
                    </span>
                  </el-descriptions-item>
                  <el-descriptions-item label="阻塞">{{ gate.metrics.blocked }}</el-descriptions-item>
                </el-descriptions>
                <div class="reasons">
                  <div class="reasons-title">判定依据</div>
                  <ul>
                    <li v-for="(r, i) in gate.reasons" :key="i">{{ r }}</li>
                  </ul>
                </div>
              </div>
              <el-empty v-else :description="gateLoading ? '加载中…' : '暂无门禁数据'" />
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
                    <template #default="{ row }">{{ gateLevelText[row.requirement_level] || row.requirement_level }}</template>
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
        <el-card shadow="never" class="block">
          <template #header>
            <div class="card-head">
              <span>缺陷列表（{{ defects.length }}）</span>
              <el-button size="small" type="primary" @click="openGateDefect">新建缺陷</el-button>
            </div>
          </template>
          <el-table :data="defects" size="small" stripe>
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column label="严重程度" width="90" align="center">
              <template #default="{ row }"><el-tag :type="gateSevType[row.severity]" size="small">{{ gateSevText[row.severity] }}</el-tag></template>
            </el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }"><el-tag :type="gateStatusType[row.status]" size="small">{{ gateStatusText[row.status] }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="requirement" label="关联需求ID" width="110" align="center" />
            <el-table-column prop="created_at" label="创建时间" min-width="150" />
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button size="small" type="danger" plain @click="removeGateDefect(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 发布结论记录 -->
        <el-card shadow="never" class="block" v-if="gateConclusions.length">
          <template #header><span>发布结论记录</span></template>
          <el-table :data="gateConclusions" size="small" stripe>
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
        <el-dialog v-model="gateDialog" title="新建缺陷" width="520px">
          <el-form :model="gateForm" label-width="90px">
            <el-form-item label="标题" required>
              <el-input v-model="gateForm.title" placeholder="缺陷标题" />
            </el-form-item>
            <el-form-item label="严重程度">
              <el-select v-model="gateForm.severity" style="width: 100%">
                <el-option v-for="s in sevOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="gateForm.status" style="width: 100%">
                <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="关联需求">
              <el-select v-model="gateForm.requirement" filterable clearable placeholder="可选" style="width: 100%">
                <el-option v-for="r in gateRequirements" :key="r.id" :label="`${r.requirement_id} ${r.requirement_name}`" :value="r.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="gateForm.description" type="textarea" :rows="3" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="gateDialog = false">取消</el-button>
            <el-button type="primary" :loading="gateSubmitting" @click="submitGateDefect">提交</el-button>
          </template>
        </el-dialog>
      </template>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProjectOverview, unwrap } from '@/api/project-overview'
import { getProjects } from '@/api/performance' // 复用现有项目列表 API
import { getBusinessRequirements } from '@/api/requirement-analysis'
import {
  getDefects, createDefect, deleteDefect,
  getRequirementCoverage, getQualityGate, saveQualityGate, getReleaseConclusions
} from '@/api/defects'

const router = useRouter()
const projects = ref([])
const selectedProjectId = ref(null)
const overview = ref(null)
const loading = ref(false)

// ===== 发布门禁（合并自质量门禁页）=====
const gate = ref(null)
const gateLoading = ref(false)
const coverage = ref(null)
const defects = ref([])
const gateConclusions = ref([])
const gateSaving = ref(false)
const gateSubmitting = ref(false)
const gateDialog = ref(false)
const gateRequirements = ref([])
const gateForm = ref({ title: '', severity: 'S3', status: 'open', requirement: null, description: '' })
const gateConclusionText = ref('')
const gateConclusionType = ref('info')

const sevOptions = [
  { value: 'S1', label: '致命' }, { value: 'S2', label: '严重' },
  { value: 'S3', label: '一般' }, { value: 'S4', label: '轻微' }
]
const statusOptions = [
  { value: 'open', label: '待处理' }, { value: 'in_progress', label: '处理中' },
  { value: 'resolved', label: '已修复' }, { value: 'closed', label: '已关闭' },
  { value: 'reopened', label: '重新打开' }
]
const gateSevText = { S1: '致命', S2: '严重', S3: '一般', S4: '轻微' }
const gateSevType = { S1: 'danger', S2: 'danger', S3: 'warning', S4: 'info' }
const gateStatusText = { open: '待处理', in_progress: '处理中', resolved: '已修复', closed: '已关闭', reopened: '重新打开' }
const gateStatusType = { open: 'info', in_progress: 'warning', resolved: 'success', closed: 'success', reopened: 'danger' }
const gateLevelText = { high: '高', medium: '中', low: '低' }
const conclusionLabel = (c) => ({ GO: '可发布', CONDITIONAL_GO: '有条件发布', NO_GO: '不可发布' }[c] || c)
const conclusionTag = (c) => ({ GO: 'success', CONDITIONAL_GO: 'warning', NO_GO: 'danger' }[c] || 'info')

function normalizeGate(list) {
  if (Array.isArray(list)) return list
  if (list && Array.isArray(list.results)) return list.results
  return []
}

function resetGate() {
  gate.value = null
  coverage.value = null
  defects.value = []
  gateConclusions.value = []
  gateConclusionText.value = ''
  gateConclusionType.value = 'info'
}

async function loadGateRequirements() {
  if (!selectedProjectId.value) return
  try {
    const res = await getBusinessRequirements({ project: selectedProjectId.value })
    gateRequirements.value = normalizeGate(res.data || res)
  } catch (e) { /* 忽略 */ }
}

async function loadGateData() {
  if (!selectedProjectId.value) { resetGate(); return }
  gateLoading.value = true
  try {
    const [cov, g, def, rel] = await Promise.all([
      getRequirementCoverage({ project: selectedProjectId.value }),
      getQualityGate({ project: selectedProjectId.value }),
      getDefects({ project: selectedProjectId.value }),
      getReleaseConclusions({ project: selectedProjectId.value }),
    ])
    coverage.value = cov?.data || cov
    gate.value = g?.data || g
    if (gate.value) {
      gateConclusionText.value = conclusionLabel(gate.value.conclusion)
      gateConclusionType.value = conclusionTag(gate.value.conclusion)
    }
    defects.value = normalizeGate(def?.data || def)
    gateConclusions.value = normalizeGate(rel?.data || rel)
  } catch (e) {
    ElMessage.error('加载发布门禁数据失败：' + (e.message || e))
  } finally {
    gateLoading.value = false
  }
}

async function saveGateConclusion() {
  if (!selectedProjectId.value || !gate.value) return
  gateSaving.value = true
  try {
    await saveQualityGate({ project: selectedProjectId.value, conclusion: gate.value.conclusion })
    ElMessage.success('发布结论已保存')
    const rel = await getReleaseConclusions({ project: selectedProjectId.value })
    gateConclusions.value = normalizeGate(rel?.data || rel)
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || e))
  } finally {
    gateSaving.value = false
  }
}

function openGateDefect() {
  gateForm.value = { title: '', severity: 'S3', status: 'open', requirement: null, description: '' }
  loadGateRequirements()
  gateDialog.value = true
}

async function submitGateDefect() {
  if (!gateForm.value.title.trim()) {
    ElMessage.warning('请填写缺陷标题')
    return
  }
  gateSubmitting.value = true
  try {
    await createDefect({
      project: selectedProjectId.value,
      title: gateForm.value.title,
      severity: gateForm.value.severity,
      status: gateForm.value.status,
      requirement: gateForm.value.requirement || null,
      description: gateForm.value.description,
    })
    ElMessage.success('缺陷已创建')
    gateDialog.value = false
    loadGateData()
  } catch (e) {
    ElMessage.error('创建失败：' + (e.message || e))
  } finally {
    gateSubmitting.value = false
  }
}

async function removeGateDefect(row) {
  try {
    await ElMessageBox.confirm(`确认删除缺陷「${row.title}」？`, '提示', { type: 'warning' })
  } catch { return }
  try {
    await deleteDefect(row.id)
    ElMessage.success('已删除')
    loadGateData()
  } catch (e) {
    ElMessage.error('删除失败：' + (e.message || e))
  }
}

const ENTITY_TYPE_LABEL = {
  Project: '项目',
  RequirementDocument: '需求文档',
  BusinessRequirement: '业务需求',
  FunctionPoint: '功能点',
  TestCase: '测试用例',
  TestCaseGenerationTask: '生成任务',
  KbFunction: 'KB 功能',
  KbDocument: 'KB 文档',
  NativeKb: '本地 KB',
  NativeKbDocument: 'KB 文档',
  CodeFile: '代码文件',
  CodeModule: '代码模块',
  CodeClass: '代码类',
  CodeFunction: '代码函数',
  ApiRequest: 'API 接口',
  UiPage: 'UI 页面',
}
function entityTypeLabel(t) { return ENTITY_TYPE_LABEL[t] || t }

function formatTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch (e) {
    return iso
  }
}

const STATUS_TYPE_MAP = {
  // API
  COMPLETED: 'success', PENDING: 'info', RUNNING: 'warning', FAILED: 'danger', CANCELLED: 'info',
  // UI
  SUCCESS: 'success', ABORTED: 'info',
  // APP
  PASSED: 'success', SKIPPED: 'info', ERROR: 'danger', STOPPED: 'info',
  // Performance
  completed: 'success', running: 'warning', failed: 'danger',
}
function statusType(s) { return STATUS_TYPE_MAP[s] || 'info' }

const onProjectChange = async () => {
  if (!selectedProjectId.value) { overview.value = null; resetGate(); return }
  loading.value = true
  try {
    overview.value = unwrap(await getProjectOverview(selectedProjectId.value))
  } catch (e) {
    ElMessage.error('加载项目概览失败')
    overview.value = null
  } finally {
    loading.value = false
  }
  // 门禁数据随项目切换并行加载（独立 try，不影响概览渲染）
  loadGateData()
}

// 6 个总览统计卡
const statCards = computed(() => {
  const o = overview.value
  if (!o) return []
  const ft = o.test_types.functional_test
  return [
    { key: 'kb', icon: '📚', label: '本地 KB', value: o.knowledge_hub.kb_total, hint: `${o.knowledge_hub.kb_published} 已发布`, to: '/configuration/knowledge-hub/kbs' },
    { key: 'doc', icon: '📄', label: '知识库文档', value: o.knowledge_hub.doc_total, hint: `${o.knowledge_hub.doc_parsed} 已解析`, to: '/configuration/knowledge-hub/documents' },
    { key: 'biz_req', icon: '🎯', label: '业务需求', value: ft.business_requirements, hint: `${ft.requirement_documents} 份文档`, to: '/ai-generation/requirement-analysis' },
    { key: 'tc', icon: '🧪', label: '测试用例', value: ft.testcases, hint: `${ft.generation_tasks_done} 批已生成`, to: '/ai-generation/testcases' },
    { key: 'kg', icon: '🕸️', label: '图谱节点', value: o.knowledge_graph.nodes, hint: `${o.knowledge_graph.edges} 条边`, to: '/ai-generation/kg-browse' },
    { key: 'api', icon: '🔌', label: 'API 接口', value: o.test_types.api_automation.api_requests, hint: `${o.test_types.ui_automation.ui_pages} UI 页面`, to: '/api-testing/interfaces' },
  ]
})

// 按测试类型 6 卡（性能/评审 拆开）
const testTypeCards = computed(() => {
  const tt = overview.value?.test_types
  if (!tt) return []

  // 工具：把 items 全为 0 的卡标记为 allZero（功能/性能/评审除外）
  const makeCard = (cfg) => {
    const allZero = cfg.items.every(i => i.value === 0) && !cfg.alwaysShow
    return { ...cfg, allZero }
  }

  const ft = tt.functional_test
  const api = tt.api_automation
  const ui = tt.ui_automation
  const app = tt.app_automation
  const perf = tt.performance
  const rev = tt.review
  const revScore = rev.avg_score != null ? rev.avg_score : rev.checklist_pass_rate

  return [
    makeCard({
      key: 'functional', icon: '📋', title: '功能测试', alwaysShow: true,
      rate: ft.pass_rate,
      rateLabel: '通过率',
      items: [
        { label: '需求文档', value: ft.requirement_documents },
        { label: '业务需求', value: ft.business_requirements, highlight: ft.business_requirements > 0 },
        { label: '测试用例', value: ft.testcases, highlight: ft.testcases > 0 },
        { label: '已执行用例', value: ft.testcases_executed, highlight: ft.testcases_executed > 0 },
        { label: '已通过用例', value: ft.testcases_passed, highlight: ft.testcases_passed > 0 },
        { label: '需求覆盖率', value: `${ft.coverage_pct}%`, highlight: ft.coverage_pct > 0 },
      ],
    }),
    makeCard({
      key: 'api', icon: '🔌', title: '接口自动化',
      rate: api.pass_rate,
      emptyHint: '需先在「接口测试」创建 ApiProject 并把脚本关联到此项目',
      items: [
        { label: '接口脚本', value: api.api_requests, highlight: api.api_requests > 0 },
        { label: '接口集合', value: api.api_collections },
        { label: '测试套件', value: api.api_test_suites },
        { label: '执行总数', value: api.executions_total },
        { label: '已通过', value: api.executions_passed },
      ],
      lastLabel: '最近执行',
      lastTime: formatTime(api.last_execution?.created_at),
      lastStatus: api.last_execution?.status || null,
    }),
    makeCard({
      key: 'ui', icon: '🖥️', title: 'UI 自动化',
      rate: ui.pass_rate,
      emptyHint: '需先在「UI 自动化」创建 UiProject 并把脚本关联到此项目',
      items: [
        { label: '页面对象', value: ui.ui_pages },
        { label: '测试脚本', value: ui.ui_scripts, highlight: ui.ui_scripts > 0 },
        { label: '测试套件', value: ui.ui_test_suites },
        { label: '执行总数', value: ui.executions_total },
        { label: '已通过', value: ui.executions_passed },
      ],
      lastLabel: '最近执行',
      lastTime: formatTime(ui.last_execution?.created_at),
      lastStatus: ui.last_execution?.status || null,
    }),
    makeCard({
      key: 'app', icon: '📱', title: 'APP 自动化',
      rate: app.pass_rate,
      emptyHint: '需先在「APP 自动化」创建 AppProject 并把脚本关联到此项目',
      items: [
        { label: '应用包', value: app.app_packages },
        { label: '测试套件', value: app.app_test_suites },
        { label: '测试用例', value: app.app_test_cases, highlight: app.app_test_cases > 0 },
        { label: '执行总数', value: app.executions_total },
        { label: '已通过', value: app.executions_passed },
      ],
      lastLabel: '最近执行',
      lastTime: formatTime(app.last_execution?.created_at),
      lastStatus: app.last_execution?.status || null,
    }),
    makeCard({
      key: 'performance', icon: '🚀', title: '性能测试', alwaysShow: true,
      rate: perf.performance_pass_rate,
      rateLabel: '通过率',
      items: [
        { label: '性能脚本', value: perf.performance_scripts, highlight: perf.performance_scripts > 0 },
        { label: '性能执行', value: perf.performance_executions_total },
        { label: '已通过', value: perf.performance_passed },
      ],
      lastLabel: '最近性能',
      lastTime: formatTime(perf.last_performance?.created_at),
      lastStatus: perf.last_performance?.status || null,
    }),
    makeCard({
      key: 'review', icon: '⭐', title: '用例评审', alwaysShow: true,
      rate: revScore,
      rateLabel: '评分',
      items: [
        { label: '评审总数', value: rev.review_total, highlight: rev.review_total > 0 },
        { label: '已通过评审', value: rev.review_approved },
        { label: '评审通过率', value: `${rev.review_approval_rate}%` },
        { label: '检查项总数', value: rev.checklist_total },
        { label: '检查项通过', value: rev.checklist_passed },
        { label: rev.avg_score != null ? '评审评分(实际)' : '检查通过率(评分)', value: `${revScore}%`, isScore: true, highlight: revScore > 0 },
      ],
      lastLabel: '最近评审',
      lastTime: rev.last_review?.title ? `${rev.last_review.title} · ${formatTime(rev.last_review.created_at)}` : '—',
      lastStatus: rev.last_review?.status || null,
    }),
  ]
})

// AI 智能模式 3 卡
const aiSmartCards = computed(() => {
  const ai = overview.value?.test_types?.ai_smart
  if (!ai) return []

  const makeCard = (cfg) => {
    const allZero = cfg.items.every(i => i.value === 0) && !cfg.alwaysShow
    return { ...cfg, allZero }
  }

  return [
    makeCard({
      key: 'gen', icon: '✨', title: 'AI 用例生成', alwaysShow: true,
      rate: ai.generation_pass_rate,
      rateLabel: '成功率',
      emptyHint: '去「AI 用例生成」上传需求文档 → 自动抽取业务需求 → 一键生成测试用例',
      items: [
        { label: '生成任务', value: ai.generation_tasks, highlight: ai.generation_tasks > 0 },
        { label: '已完成', value: ai.generation_tasks_done },
      ],
    }),
    makeCard({
      key: 'dify', icon: '💬', title: 'Dify 智能助手',
      emptyHint: '去「数字员工」/ Dify 智能助手发起对话，会话与消息会自动按项目成员汇总',
      items: [
        { label: '助手会话', value: ai.dify_sessions, highlight: ai.dify_sessions > 0 },
        { label: '聊天消息', value: ai.dify_messages },
      ],
    }),
    makeCard({
      key: 'hermes', icon: '🤖', title: 'Hermes 数字人',
      emptyHint: '去「Hermes 数字人」发起对话，会按项目成员汇总会话/消息数',
      items: [
        { label: '数字人会话', value: ai.hermes_conversations, highlight: ai.hermes_conversations > 0 },
        { label: '数字人消息', value: ai.hermes_messages },
      ],
    }),
  ]
})

// 检索链路 5 步
const pipelineSteps = computed(() => {
  const p = overview.value?.retrieval_pipeline || {}
  return [
    { key: 'acl', name: 'ACL 过滤', on: p.acl },
    { key: 'recall', name: 'Hybrid Recall', on: p.recall },
    { key: 'fusion', name: 'RRF 融合', on: true },
    { key: 'rerank', name: 'Rerank', on: p.rerank },
    { key: 'context', name: 'Context Bundle', on: p.context },
  ]
})

// 节点类型分布 top 6
const topNodeTypes = computed(() => {
  const list = overview.value?.knowledge_graph?.node_by_type || []
  return list.slice(0, 6)
})
const maxNodeCount = computed(() => {
  const list = overview.value?.knowledge_graph?.node_by_type || []
  return list.length ? list[0].count : 1
})

onMounted(async () => {
  try {
    const res = await getProjects()
    const body = res?.data || res
    projects.value = body?.results || body?.data || (Array.isArray(body) ? body : [])
  } catch (e) {
    ElMessage.error('加载项目列表失败')
  }
  if (projects.value.length === 1) {
    selectedProjectId.value = projects.value[0].id
    await onProjectChange()
  }
})

watch(selectedProjectId, () => onProjectChange())
</script>

<style scoped>
.project-overview { padding: 24px; max-width: 1400px; margin: 0 auto; }

.header-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.project-tag { color: #909399; font-size: 13px; }

.hero-card { margin-bottom: 16px; }
.hero-title { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }
.hero-title h2 { margin: 0; font-size: 20px; }
.hero-meta { display: flex; gap: 6px; flex-wrap: wrap; }
.hero-desc { color: #606266; margin: 12px 0; line-height: 1.6; }
.hero-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.section-title { margin: 20px 0 12px; font-size: 16px; color: #303133; }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
  margin-bottom: 8px;
}
.stat-card {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.08); border-color: #409eff; }
.stat-icon { font-size: 24px; margin-bottom: 4px; }
.stat-value { font-size: 26px; font-weight: bold; color: #303133; line-height: 1.2; }
.stat-label { color: #303133; font-size: 13px; margin-top: 4px; }
.stat-hint { color: #909399; font-size: 11px; margin-top: 4px; }

/* 按测试类型 5 卡网格 */
.test-type-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
  margin-bottom: 8px;
}
.test-type-card {
  transition: all 0.2s;
}
.test-type-card :deep(.el-card__header) {
  padding: 12px 16px;
}
.tt-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tt-icon { font-size: 18px; }
.tt-title { font-size: 14px; font-weight: 600; color: #303133; flex: 1; }

.tt-body { padding: 4px 0; }
.tt-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  border-bottom: 1px dashed #f0f0f0;
  font-size: 13px;
}
.tt-row:last-child { border-bottom: none; }
.tt-label { color: #606266; }
.tt-value {
  color: #303133;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.tt-value.is-high {
  color: #409eff;
  font-weight: 600;
}
.tt-last {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #ebeef5;
  font-size: 12px;
  color: #606266;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.tt-last-label { color: #909399; }
.tt-last-time { color: #303133; }

.tt-empty-tip {
  text-align: center;
  color: #c0c4cc;
  padding: 24px 8px;
  font-size: 13px;
}
.tt-empty-hint {
  margin-top: 6px;
  font-size: 11px;
  color: #c0c4cc;
  line-height: 1.5;
}
.test-type-card.tt-empty { opacity: 0.78; }
.test-type-card.tt-empty :deep(.el-card__body) { padding: 0; }

/* 各测试类型主题色（左 border） */
.tt-functional :deep(.el-card__body) { border-left: 3px solid #409eff; padding-left: 12px; }
.tt-api :deep(.el-card__body) { border-left: 3px solid #67c23a; padding-left: 12px; }
.tt-ui :deep(.el-card__body) { border-left: 3px solid #e6a23c; padding-left: 12px; }
.tt-app :deep(.el-card__body) { border-left: 3px solid #f56c6c; padding-left: 12px; }
.tt-performance :deep(.el-card__body) { border-left: 3px solid #909399; padding-left: 12px; }
.tt-review :deep(.el-card__body) { border-left: 3px solid #c456f3; padding-left: 12px; }

/* 区块说明条 */
.grid-note {
  font-size: 12px;
  color: #606266;
  background: #f4f7fb;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 12px;
  line-height: 1.6;
}
.grid-note code {
  background: #eaedf2;
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 11px;
  color: #9254de;
}
.grid-note b { color: #303133; }

/* AI 智能模式卡网格 */
.ai-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
  margin-bottom: 8px;
}
.ai-card { transition: all 0.2s; }
.ai-card :deep(.el-card__header) { padding: 12px 16px; }
.ai-gen :deep(.el-card__body) { border-left: 3px solid #9254de; padding-left: 12px; }
.ai-dify :deep(.el-card__body) { border-left: 3px solid #36cfc9; padding-left: 12px; }
.ai-hermes :deep(.el-card__body) { border-left: 3px solid #ff85c0; padding-left: 12px; }
.ai-card.tt-empty { opacity: 0.78; }
.ai-card.tt-empty :deep(.el-card__body) { padding: 0; }

/* 评分高亮（评审卡检查通过率） */
.tt-value.is-score {
  color: #c456f3;
  font-weight: 700;
  font-size: 14px;
}

.pipeline-card { margin-bottom: 16px; }
.pipeline {
  display: flex;
  align-items: stretch;
  gap: 0;
  overflow-x: auto;
  padding: 8px 0;
}
.pipeline-step {
  flex: 1;
  min-width: 130px;
  padding: 16px 12px;
  border-radius: 8px;
  position: relative;
  text-align: center;
  margin: 0 4px;
}
.pipeline-step.is-on { background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border: 1px solid #409eff33; }
.pipeline-step.is-off { background: #fef2f2; border: 1px solid #fca5a533; }
.step-num {
  width: 24px; height: 24px; line-height: 24px;
  border-radius: 50%; margin: 0 auto 8px;
  font-size: 12px; font-weight: bold;
}
.is-on .step-num { background: #409eff; color: #fff; }
.is-off .step-num { background: #f56c6c; color: #fff; }
.step-name { font-size: 13px; font-weight: 500; margin-bottom: 4px; }
.step-status { font-size: 11px; }
.is-on .step-status { color: #67c23a; }
.is-off .step-status { color: #f56c6c; }
.step-arrow {
  position: absolute;
  right: -8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 18px;
  color: #c0c4cc;
  z-index: 1;
}

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
@media (max-width: 980px) {
  .two-col { grid-template-columns: 1fr; }
}

.bar-row { display: flex; align-items: center; gap: 8px; margin: 8px 0; }
.bar-label { width: 100px; font-size: 12px; color: #606266; }
.empty-tip { color: #909399; text-align: center; padding: 24px 0; font-size: 13px; }

/* ===== 发布门禁（合并自质量门禁页）===== */
.block { margin-bottom: 16px; }
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