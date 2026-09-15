<template>
  <div class="comparison-report" v-loading="loading">
    <!-- 生成区 -->
    <el-card shadow="never" class="card">
      <div class="card-header">
        <div class="card-title">生成多轮对照报告</div>
        <div class="card-sub">选择同一脚本的 2~5 次执行横向对照，可选让 AI 给出稳定性 / 劣化 / 瓶颈结论</div>
      </div>
      <el-form label-width="90px">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="脚本">
              <el-select
                v-model="form.script"
                placeholder="选择脚本"
                filterable
                style="width: 100%"
                @change="onScriptChange"
              >
                <el-option v-for="s in scripts" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="对比执行">
              <el-select
                v-model="form.execution_ids"
                multiple
                filterable
                :multiple-limit="5"
                placeholder="选择 2~5 次执行（按选择顺序对照）"
                style="width: 100%"
              >
                <el-option v-for="e in executions" :key="e.id" :label="execLabel(e)" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="基准执行">
              <el-select
                v-model="form.reference_execution_id"
                clearable
                placeholder="默认第一条"
                style="width: 100%"
              >
                <el-option v-for="e in selectedExecutions" :key="e.id" :label="execLabel(e)" :value="e.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="报告标题">
              <el-input v-model="form.title" placeholder="留空自动生成" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="AI 分析">
              <div class="gen-actions">
                <el-switch v-model="form.with_ai" />
                <el-button type="primary" :loading="generating" @click="handleGenerate">生成报告</el-button>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 报告列表 -->
    <el-card shadow="never" class="card">
      <div class="card-header"><div class="card-title">对照报告列表</div></div>
      <el-table :data="reports" stripe v-loading="listLoading">
        <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip />
        <el-table-column prop="script_name" label="脚本" min-width="160" show-overflow-tooltip />
        <el-table-column label="轮次" width="80" align="center">
          <template #default="{ row }">{{ (row.execution_ids || []).length }}</template>
        </el-table-column>
        <el-table-column label="AI 分析" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.ai_analysis ? 'success' : 'info'" size="small">{{ row.ai_analysis ? '有' : '无' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="110" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDetail(row)">查看</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!listLoading && !reports.length" description="暂无对照报告" :image-size="80" />
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" :title="detail?.title || '对照报告'" size="72%">
      <div v-if="detail && detail.snapshot" class="detail-body">
        <div class="section-title">指标矩阵（相对基准执行的变化）</div>
        <el-table :data="matrixRows" size="small" stripe border>
          <el-table-column prop="label" label="指标" width="150" fixed />
          <el-table-column
            v-for="(ex, i) in detail.snapshot.executions || []"
            :key="i"
            :label="shortNo(ex.execution_id) + (ex.is_reference ? ' (基准)' : '')"
            min-width="150"
            align="center"
          >
            <template #default="{ row }">
              <div>{{ fmt(row.values[i]) }}</div>
              <div v-if="!ex.is_reference && row.deltas[i] !== null && row.deltas[i] !== undefined"
                   class="delta" :style="{ color: deltaColor(row.key, row.deltas[i]) }">
                {{ row.deltas[i] > 0 ? '+' : '' }}{{ row.deltas[i] }}%
              </div>
            </template>
          </el-table-column>
        </el-table>

        <template v-if="(detail.snapshot.step_comparison || []).length">
          <div class="section-title" style="margin-top: 20px">接口级对比（TPS / 平均ms / P95ms / 错误率%）</div>
          <el-table :data="stepTableRows" size="small" stripe border>
            <el-table-column prop="step_name" label="请求名" min-width="180" fixed show-overflow-tooltip />
            <el-table-column
              v-for="(ex, i) in detail.snapshot.executions || []"
              :key="i"
              :label="shortNo(ex.execution_id)"
              min-width="190"
              align="center"
            >
              <template #default="{ row }">{{ row.cells[i] }}</template>
            </el-table-column>
          </el-table>
        </template>

        <div class="section-title" style="margin-top: 20px">AI 对照分析</div>
        <div v-if="detail.ai_analysis" class="md-body" v-html="renderMd(detail.ai_analysis)"></div>
        <el-empty v-else description="该报告生成时未开启 AI 分析" :image-size="60" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import {
  getScripts,
  getExecutions,
  getComparisonReports,
  createComparisonReport,
  deleteComparisonReport,
} from '@/api/performance'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`
      } catch (e) { /* 忽略高亮异常 */ }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  },
})

const loading = ref(true)
const listLoading = ref(false)
const generating = ref(false)
const scripts = ref([])
const executions = ref([])
const reports = ref([])
const detailVisible = ref(false)
const detail = ref(null)

const form = reactive({
  script: null,
  execution_ids: [],
  reference_execution_id: null,
  title: '',
  with_ai: true,
})

const selectedExecutions = computed(() =>
  form.execution_ids
    .map((id) => executions.value.find((e) => e.id === id))
    .filter(Boolean)
)

const matrixRows = computed(() => {
  const snap = detail.value?.snapshot
  if (!snap) return []
  const keys = snap.metric_keys || []
  const labels = snap.metric_labels || {}
  const execs = snap.executions || []
  return keys.map((k) => ({
    key: k,
    label: labels[k] || k,
    values: execs.map((e) => (e.summary || {})[k]),
    deltas: execs.map((e) => (e.delta_pct || {})[k]),
  }))
})

const stepTableRows = computed(() => {
  const rows = detail.value?.snapshot?.step_comparison || []
  return rows.map((r) => ({
    step_name: r.step_name,
    cells: (r.values || []).map((v) =>
      `${fmt(v.throughput)} / ${fmt(v.avg)} / ${fmt(v.p95)} / ${fmt(v.error_rate)}`
    ),
  }))
})

const fmt = (v) => (v === null || v === undefined ? '—' : (typeof v === 'number' ? Number(v.toFixed(2)) : v))
const shortNo = (no) => (no ? String(no).replace(/^PERF_/, '') : '-')
const formatTime = (v) => (v ? new Date(v).toLocaleString('zh-CN', { hour12: false }) : '-')
const renderMd = (text) => md.render(text || '')

// 越大越好的指标：上涨不算劣化
const HIGHER_BETTER = ['throughput', 'total_samples']
const deltaColor = (key, delta) => {
  const bad = HIGHER_BETTER.includes(key) ? delta < 0 : delta > 0
  return bad ? '#f56c6c' : '#67c23a'
}

const execLabel = (e) => {
  const t = e.created_at ? new Date(e.created_at).toLocaleString('zh-CN', { hour12: false }) : ''
  return `${shortNo(e.execution_id)} · ${e.status_display || e.status} · ${t}`
}

const loadReports = async () => {
  listLoading.value = true
  try {
    const res = await getComparisonReports({ page_size: 100 })
    reports.value = res.data?.results || res.data || []
  } catch (e) {
    reports.value = []
  } finally {
    listLoading.value = false
  }
}

const onScriptChange = async () => {
  form.execution_ids = []
  form.reference_execution_id = null
  executions.value = []
  if (!form.script) return
  try {
    const res = await getExecutions({ script: form.script, status: 'COMPLETED', page_size: 200 })
    executions.value = res.data?.results || res.data || []
  } catch (e) {
    executions.value = []
  }
}

const handleGenerate = async () => {
  if (!form.script) return ElMessage.warning('请先选择脚本')
  if (form.execution_ids.length < 2) return ElMessage.warning('请至少选择 2 次执行')
  generating.value = true
  try {
    const res = await createComparisonReport({
      title: form.title || undefined,
      execution_ids: form.execution_ids,
      reference_execution_id: form.reference_execution_id || undefined,
      with_ai: form.with_ai,
    })
    ElMessage.success('对照报告已生成')
    detail.value = res.data
    detailVisible.value = true
    await loadReports()
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || '生成对照报告失败')
  } finally {
    generating.value = false
  }
}

const openDetail = (row) => {
  detail.value = row
  detailVisible.value = true
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除对照报告「${row.title}」吗？`, '提示', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteComparisonReport(row.id)
      ElMessage.success('已删除')
      await loadReports()
    } catch (e) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

onMounted(async () => {
  try {
    const res = await getScripts({ page_size: 200 })
    scripts.value = res.data?.results || res.data || []
  } catch (e) {
    scripts.value = []
  }
  await loadReports()
  loading.value = false
})
</script>

<style scoped>
.comparison-report { padding: 0; }
.card { margin-bottom: 16px; }
.card-header { margin-bottom: 12px; }
.card-title { font-size: 15px; font-weight: 600; color: #303133; }
.card-sub { font-size: 12px; color: #909399; margin-top: 4px; }
.gen-actions { display: flex; align-items: center; gap: 12px; }
.section-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 10px; }
.delta { font-size: 12px; margin-top: 2px; }
.md-body { font-size: 13px; line-height: 1.7; color: #303133; }
.md-body :deep(h1), .md-body :deep(h2), .md-body :deep(h3) { font-size: 15px; margin: 14px 0 8px; }
.md-body :deep(pre) { background: #f6f8fa; padding: 10px; border-radius: 6px; overflow-x: auto; }
.md-body :deep(table) { border-collapse: collapse; }
.md-body :deep(th), .md-body :deep(td) { border: 1px solid #ebeef5; padding: 6px 10px; }
</style>
