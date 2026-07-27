<template>
  <div class="batch-detail">
    <!-- 头部信息 -->
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button text @click="$router.push('/performance-testing/executions')">
              <el-icon><ArrowLeft /></el-icon> 返回
            </el-button>
            <span class="batch-title">{{ batch.name || batch.batch_id }}</span>
            <el-tag :type="statusType(batch.status)" size="small">{{ batch.status_display }}</el-tag>
          </div>
          <div>
            <el-button v-if="batch.has_report" type="primary" @click="showReport = true">查看项目报告</el-button>
            <el-button @click="loadData">刷新</el-button>
          </div>
        </div>
      </template>

      <el-descriptions :column="4" border>
        <el-descriptions-item label="批次ID">{{ batch.batch_id }}</el-descriptions-item>
        <el-descriptions-item label="项目">{{ batch.project_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="创建者">{{ batch.created_by_name }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(batch.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="线程数">{{ batch.thread_count }}</el-descriptions-item>
        <el-descriptions-item label="Ramp-Up">{{ batch.ramp_up }}s</el-descriptions-item>
        <el-descriptions-item label="持续时间">{{ batch.duration }}s</el-descriptions-item>
        <el-descriptions-item label="完成时间">{{ formatTime(batch.completed_at) }}</el-descriptions-item>
      </el-descriptions>

      <!-- 进度条 -->
      <div class="progress-bar" v-if="batch.status === 'RUNNING' || batch.status === 'QUEUED'">
        <el-progress :percentage="progressPercent" :format="() => `${batch.completed_scripts}/${batch.total_scripts}`" />
      </div>
    </el-card>

    <!-- 汇总指标 -->
    <el-card class="summary-card" v-loading="loading">
      <template #header><span>项目汇总指标</span></template>
      <el-row :gutter="16" v-if="aggregate">
        <el-col :span="4" v-for="(item, idx) in summaryCards" :key="idx">
          <div class="metric-card">
            <div class="metric-label">{{ item.label }}</div>
            <div class="metric-value" :style="{ color: item.color }">{{ item.value }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 各执行记录对比表 -->
    <el-card>
      <template #header><span>执行记录明细</span></template>
      <el-table :data="batch.executions || []" stripe>
        <el-table-column prop="execution_id" label="执行ID" width="180" />
        <el-table-column prop="script_name" label="脚本" min-width="160" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="总样本" width="100" align="center">
          <template #default="{ row }">{{ getMetric(row.id, 'total_samples') }}</template>
        </el-table-column>
        <el-table-column label="错误率" width="90" align="center">
          <template #default="{ row }">
            <span :style="{ color: getMetric(row.id, 'error_rate') > 5 ? '#f56c6c' : '' }">
              {{ getMetric(row.id, 'error_rate') }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="平均RT(ms)" width="110" align="center">
          <template #default="{ row }">{{ getMetric(row.id, 'avg_response_time') }}</template>
        </el-table-column>
        <el-table-column label="P95(ms)" width="90" align="center">
          <template #default="{ row }">{{ getMetric(row.id, 'p95') }}</template>
        </el-table-column>
        <el-table-column label="吞吐量" width="100" align="center">
          <template #default="{ row }">{{ getMetric(row.id, 'throughput') }}</template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="170">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="$router.push(`/performance-testing/executions/${row.id}`)">详情</el-button>
            <el-button v-if="row.has_report" size="small" @click="$router.push(`/performance-testing/executions/${row.id}?tab=report`)">报告</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 错误信息 -->
    <el-card v-if="batch.error_message" class="error-card">
      <template #header><span style="color: #f56c6c;">错误信息</span></template>
      <el-alert type="error" :title="batch.error_message" :closable="false" show-icon />
    </el-card>

    <!-- 项目级报告弹窗 -->
    <el-dialog v-model="showReport" :title="`项目级报告 - ${batch.name || batch.batch_id}`" width="90%" top="5vh" destroy-on-close>
      <iframe v-if="batch.has_report" :src="reportUrl" class="batch-report-iframe" frameborder="0" />
      <el-empty v-else description="项目级报告尚未生成" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getBatchExecution, getBatchSummary } from '@/api/performance'

const route = useRoute()
const batchId = route.params.id

const batch = ref({})
const aggregate = ref(null)
const summaries = ref([])
const loading = ref(false)
const showReport = ref(false)
let pollTimer = null

const formatTime = (val) => val ? new Date(val).toLocaleString('zh-CN', { hour12: false }) : ''

const statusType = (s) => ({
  QUEUED: 'info', RUNNING: 'warning', COMPLETED: 'success', FAILED: 'danger', PARTIAL: 'warning',
}[s] || 'info')

const progressPercent = computed(() => {
  if (!batch.value.total_scripts) return 0
  return Math.round(batch.value.completed_scripts / batch.value.total_scripts * 100)
})

const summaryCards = computed(() => {
  const a = aggregate.value || {}
  return [
    { label: '执行总数', value: a.total_executions ?? 0, color: '#409eff' },
    { label: '成功', value: a.completed ?? 0, color: '#67c23a' },
    { label: '失败', value: a.failed ?? 0, color: '#f56c6c' },
    { label: '总样本数', value: a.total_samples ?? 0, color: '#409eff' },
    { label: '总错误数', value: a.total_errors ?? 0, color: '#f56c6c' },
    { label: '平均错误率', value: (a.error_rate ?? 0) + '%', color: a.error_rate > 5 ? '#f56c6c' : '#67c23a' },
    { label: '平均RT(ms)', value: a.avg_response_time ?? 0, color: '#e6a23c' },
    { label: '平均吞吐量', value: a.avg_throughput ?? 0, color: '#67c23a' },
    { label: '最大RT(ms)', value: a.max_response_time ?? 0, color: '#f56c6c' },
    { label: '平均P95(ms)', value: a.avg_p95 ?? 0, color: '#e6a23c' },
  ]
})

// 建立执行ID -> summary 映射
const summaryMap = computed(() => {
  const m = {}
  for (const s of summaries.value) {
    m[s.execution] = s
  }
  return m
})

const getMetric = (execId, field) => {
  const s = summaryMap.value[execId]
  if (!s) return '-'
  const val = s[field]
  if (val === undefined || val === null) return '-'
  return typeof val === 'number' ? Math.round(val * 100) / 100 : val
}

const reportUrl = computed(() => {
  const token = localStorage.getItem('access_token') || ''
  return `/api/performance-testing/batch-executions/${batchId}/report/?token=${encodeURIComponent(token)}`
})

const loadData = async () => {
  loading.value = true
  try {
    const [batchRes, summaryRes] = await Promise.all([
      getBatchExecution(batchId),
      getBatchSummary(batchId),
    ])
    batch.value = batchRes.data || {}
    aggregate.value = summaryRes.data?.aggregate || null
    summaries.value = summaryRes.data?.summaries || []
  } catch (e) {
    ElMessage.error('加载批次详情失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
  pollTimer = setInterval(() => {
    if (batch.value.status === 'QUEUED' || batch.value.status === 'RUNNING') {
      loadData()
    }
  }, 5000)
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.batch-detail { display: flex; flex-direction: column; gap: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.header-left { display: flex; align-items: center; gap: 12px; }
.batch-title { font-size: 16px; font-weight: 600; }
.progress-bar { margin-top: 16px; }
.metric-card {
  text-align: center; padding: 16px 8px;
  background: var(--el-bg-color-page); border-radius: 8px;
}
.metric-label { font-size: 12px; color: #909399; margin-bottom: 8px; }
.metric-value { font-size: 22px; font-weight: 700; }
.batch-report-iframe { width: 100%; height: 70vh; border: none; }
</style>
