<template>
  <div class="perf-dashboard-detail">
    <div class="dashboard-header">
      <div class="header-title">
        <h2>执行数据面板</h2>
        <div class="sub-title">
          <span>{{ execution?.script_name || '未选择脚本' }}</span>
          <el-tag v-if="execution" :type="statusType(execution.status)">{{ execution.status_display }}</el-tag>
          <span class="exec-id">{{ execution?.execution_id }}</span>
        </div>
      </div>
      <div class="header-controls">
        <el-select v-model="refreshInterval" style="width:100px" @change="onIntervalChange">
          <el-option label="5s" :value="5" />
          <el-option label="10s" :value="10" />
          <el-option label="30s" :value="30" />
          <el-option label="60s" :value="60" />
        </el-select>
        <el-switch v-model="autoRefresh" active-text="自动刷新" style="margin:0 12px" @change="onAutoChange" />
        <el-button @click="loadDashboard">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button @click="$router.push('/performance-testing/dashboard')">
          返回列表
        </el-button>
      </div>
    </div>

    <div v-if="!hasData" class="empty-state">
      <el-empty description="暂无该执行的数据看板">
        <el-button type="primary" @click="$router.push('/performance-testing/dashboard')">返回执行列表</el-button>
      </el-empty>
    </div>

    <template v-else>
      <!-- 指标卡片 -->
      <el-row :gutter="16" class="metric-cards">
        <el-col :span="3" v-for="(m, idx) in statCards" :key="idx">
          <el-card class="metric-card" shadow="never">
            <div class="metric-label">{{ m.label }}</div>
            <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 图表区 -->
      <el-row :gutter="16" class="chart-row">
        <el-col :span="12">
          <el-card class="chart-card" shadow="never">
            <div class="chart-title">响应时间</div>
            <v-chart class="chart" :option="responseTimeOption" autoresize />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card class="chart-card" shadow="never">
            <div class="chart-title">吞吐量</div>
            <v-chart class="chart" :option="throughputOption" autoresize />
          </el-card>
        </el-col>
      </el-row>
      <el-row :gutter="16" class="chart-row">
        <el-col :span="12">
          <el-card class="chart-card" shadow="never">
            <div class="chart-title">错误率</div>
            <v-chart class="chart" :option="errorRateOption" autoresize />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card class="chart-card" shadow="never">
            <div class="chart-title">活跃线程</div>
            <v-chart class="chart" :option="activeThreadsOption" autoresize />
          </el-card>
        </el-col>
      </el-row>

      <!-- 服务器/DB 监控（每个目标一个 card，每个指标一张折线图） -->
      <el-card v-if="monitoring.length" class="monitoring-card" shadow="never">
        <div class="chart-title">服务器 / 数据库监控</div>
        <div v-for="target in monitoring" :key="target.target_name" class="monitor-block">
          <div class="monitor-title">
            <span>{{ target.target_name }}</span>
            <el-tag size="small" type="info">{{ targetTypeLabel(target.target_type) }}</el-tag>
          </div>
          <el-row :gutter="16">
            <el-col :span="12" v-for="(m, mi) in target.metrics" :key="mi">
              <div class="monitor-chart-card">
                <div class="monitor-chart-title">{{ m.metric_label }}（{{ m.metric_unit }}）</div>
                <v-chart class="monitor-chart" :option="monitorChartOption(m)" autoresize />
              </div>
            </el-col>
          </el-row>
        </div>
      </el-card>
      <el-card v-else class="monitoring-card" shadow="never">
        <div class="chart-title">服务器 / 数据库监控</div>
        <div class="empty">未配置 Prometheus 监控目标，或执行期间无可用指标</div>
      </el-card>

      <!-- 事务明细 -->
      <el-card class="transaction-table" shadow="never">
        <div class="chart-title">事务明细</div>
        <el-table :data="metrics" border stripe>
          <el-table-column prop="sample_label" label="事务" min-width="180" show-overflow-tooltip />
          <el-table-column prop="sample_count" label="样本" width="100" />
          <el-table-column prop="error_count" label="失败" width="100" />
          <el-table-column prop="error_rate" label="错误率(%)" width="110">
            <template #default="{ row }">
              <span :style="{ color: row.error_rate > 0 ? '#f56c6c' : '#67c23a' }">{{ row.error_rate }}%</span>
            </template>
          </el-table-column>
          <el-table-column prop="throughput" label="吞吐/s" width="100" />
          <el-table-column prop="avg" label="平均(ms)" width="110" />
          <el-table-column prop="p95" label="P95(ms)" width="110" />
          <el-table-column prop="p99" label="P99(ms)" width="110" />
        </el-table>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { getDashboard } from '@/api/performance'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const route = useRoute()
const router = useRouter()
const executionId = route.params.id

const execution = ref(null)
const summary = ref({})
const metrics = ref([])
const realtime = ref({ enabled: false, response_time_p95: [], throughput: [], errors: [], active_threads: [] })
const monitoring = ref([])
const autoRefresh = ref(false)
const refreshInterval = ref(5)
let timer = null

const TARGET_TYPE_LABELS = {
  app_server: '应用服务器',
  gateway: '网关',
  redis: 'Redis/缓存',
  db: '数据库',
  custom: '自定义微服务',
}
const targetTypeLabel = (t) => TARGET_TYPE_LABELS[t] || t || '-'

const monitorChartOption = (m) => {
  const times = (m.timeline || []).map(p => p.t + 's')
  const values = (m.timeline || []).map(p => p.v)
  return {
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    tooltip: { trigger: 'axis' },
    title: {
      text: `${m.metric_label} (${m.metric_unit})`,
      left: 'center',
      textStyle: { fontSize: 13, fontWeight: 'normal' },
    },
    xAxis: { type: 'category', boundaryGap: false, data: times },
    yAxis: { type: 'value', scale: true },
    series: [{
      name: m.metric_label,
      type: 'line',
      smooth: true,
      data: values,
      itemStyle: { color: '#409eff' },
      lineStyle: { width: 2 },
    }],
  }
}

const hasData = computed(() => !!execution.value)

function statusType(status) {
  const map = { QUEUED: 'info', RUNNING: 'primary', COMPLETED: 'success', FAILED: 'danger', CANCELLED: 'warning' }
  return map[status] || 'info'
}

function formatNumber(n, digits = 1) {
  if (n === undefined || n === null) return '-'
  const num = Number(n)
  if (Number.isNaN(num)) return '-'
  return Number.isInteger(num) ? num : num.toFixed(digits)
}

const statCards = computed(() => {
  const s = summary.value || {}
  return [
    { label: '样本', value: formatNumber(s.total_samples, 0), color: '#303133' },
    { label: '失败', value: formatNumber(s.error_count, 0), color: '#f56c6c' },
    { label: '错误率', value: `${formatNumber(s.error_rate, 1)}%`, color: '#f56c6c' },
    { label: '吞吐/s', value: formatNumber(s.throughput, 1), color: '#409eff' },
    { label: '平均(ms)', value: formatNumber(s.avg_response_time, 1), color: '#303133' },
    { label: 'P95(ms)', value: formatNumber(s.p95, 1), color: '#303133' },
    { label: 'P99(ms)', value: formatNumber(s.p99, 1), color: '#303133' },
    { label: '活跃线程', value: formatNumber(execution.value?.thread_count, 0), color: '#67c23a' },
  ]
})

function buildLineOption(title, seriesList) {
  return {
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 0, data: seriesList.map(s => s.name) },
    xAxis: { type: 'category', boundaryGap: false, data: seriesList[0]?.times || [] },
    yAxis: { type: 'value', scale: true },
    series: seriesList.map(s => ({
      name: s.name,
      type: 'line',
      smooth: true,
      data: s.values,
      itemStyle: { color: s.color },
      lineStyle: { width: 2 }
    }))
  }
}

function extractTimeSeries(data, key) {
  if (!data || !data.length) return { times: [], values: [] }
  const times = data.map(d => {
    const t = d.time || d.ts || d.timestamp || ''
    return t.split('T').pop()?.split('.')[0] || t
  })
  const values = data.map(d => Number(d.value || d[key] || 0))
  return { times, values }
}

const responseTimeOption = computed(() => {
  if (realtime.value.enabled && realtime.value.response_time_p95?.length) {
    const s = extractTimeSeries(realtime.value.response_time_p95)
    return buildLineOption('响应时间', [
      { name: 'P95', ...s, color: '#409eff' }
    ])
  }
  const timeline = metrics.value[0]?.timeline || []
  const times = timeline.map(t => t.time || t.t)
  const values = timeline.map(t => t.avg || t.mean)
  return buildLineOption('响应时间', [
    { name: '平均', times, values, color: '#409eff' },
  ])
})

const throughputOption = computed(() => {
  if (realtime.value.enabled && realtime.value.throughput?.length) {
    const s = extractTimeSeries(realtime.value.throughput)
    return buildLineOption('吞吐量', [
      { name: '吞吐/s', ...s, color: '#67c23a' }
    ])
  }
  const timeline = metrics.value[0]?.timeline || []
  const times = timeline.map(t => t.time || t.t)
  const values = timeline.map(t => t.throughput || t.tps || (t.count ? +(t.count / 10).toFixed(2) : 0))
  return buildLineOption('吞吐量', [
    { name: '吞吐/s', times, values, color: '#67c23a' },
  ])
})

const errorRateOption = computed(() => {
  if (realtime.value.enabled && realtime.value.errors?.length) {
    const s = extractTimeSeries(realtime.value.errors)
    return buildLineOption('错误率', [
      { name: '错误数', ...s, color: '#f56c6c' }
    ])
  }
  const timeline = metrics.value[0]?.timeline || []
  const times = timeline.map(t => t.time || t.t)
  const values = timeline.map(t => {
    if (t.error_rate || t.errorRate) return t.error_rate || t.errorRate
    if (t.error_count && t.count) return +(t.error_count / t.count * 100).toFixed(2)
    return 0
  })
  return buildLineOption('错误率', [
    { name: '错误率(%)', times, values, color: '#f56c6c' },
  ])
})

const activeThreadsOption = computed(() => {
  if (realtime.value.enabled && realtime.value.active_threads?.length) {
    const s = extractTimeSeries(realtime.value.active_threads)
    return buildLineOption('活跃线程', [
      { name: '活跃线程', ...s, color: '#e6a23c' }
    ])
  }
  const t = execution.value?.thread_count || 0
  return buildLineOption('活跃线程', [
    { name: '活跃线程', times: ['00:00'], values: [t], color: '#e6a23c' }
  ])
})

async function loadDashboard() {
  if (!executionId) return
  try {
    const res = await getDashboard({ id: executionId, execution_id: executionId })
    const data = res.data || {}
    execution.value = data.execution || null
    summary.value = data.summary || {}
    metrics.value = data.metrics || []
    realtime.value = data.realtime || { enabled: false, response_time_p95: [], throughput: [], errors: [], active_threads: [] }
    monitoring.value = data.monitoring || []
    // 如果执行已结束且正在自动刷新，停止轮询
    if (execution.value?.status !== 'RUNNING' && timer) {
      stopTimer()
    }
  } catch (e) {
    if (e.response?.status !== 404) {
      ElMessage.error('加载看板数据失败')
    }
  }
}

function startTimer() {
  stopTimer()
  timer = setInterval(() => loadDashboard(), refreshInterval.value * 1000)
}

function stopTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function onAutoChange(v) {
  if (v) startTimer()
  else stopTimer()
}

function onIntervalChange() {
  if (autoRefresh.value) startTimer()
}

onMounted(async () => {
  await loadDashboard()
  // 运行中自动开启轮询，和实时监控保持一致
  if (execution.value?.status === 'RUNNING') {
    autoRefresh.value = true
    startTimer()
  }
})

onUnmounted(() => {
  stopTimer()
})
</script>

<style scoped>
.perf-dashboard-detail {
  padding: 16px;
  background: #f5f7fa;
  min-height: calc(100vh - 60px);
}
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.header-title h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}
.sub-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  font-size: 13px;
  color: #606266;
}
.exec-id {
  font-family: monospace;
  color: #909399;
}
.header-controls {
  display: flex;
  align-items: center;
}
.metric-cards {
  margin-bottom: 16px;
}
.metric-card {
  text-align: center;
  padding: 12px 0;
}
.metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.metric-value {
  font-size: 22px;
  font-weight: 600;
}
.chart-row {
  margin-bottom: 16px;
}
.chart-card {
  padding: 12px;
}
.chart-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
}
.chart {
  height: 240px;
}
.transaction-table {
  padding: 12px;
}
.monitoring-card {
  margin-bottom: 16px;
  padding: 12px;
}
.monitor-block { margin-bottom: 12px; }
.monitor-title { font-size: 14px; font-weight: 600; color: #303133; margin: 12px 0 8px; display: flex; align-items: center; gap: 8px; }
.monitor-chart-card { background: #fff; border-radius: 8px; border: 1px solid #ebeef5; padding: 10px; margin-bottom: 12px; }
.monitor-chart-title { font-size: 13px; font-weight: 600; color: #303133; text-align: center; margin-bottom: 4px; }
.monitor-chart { height: 220px; }
.empty-state {
  padding: 60px 0;
  text-align: center;
}
</style>