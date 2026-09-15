<template>
  <div class="execution-detail" v-loading="loading">
    <!-- 顶部状态卡 -->
    <el-card v-if="execution" class="status-card">
      <div class="status-bar">
        <div class="status-left">
          <el-tag :type="statusType(execution.status)" size="large">{{ execution.status_display }}</el-tag>
          <span class="exec-id">{{ execution.execution_id }}</span>
          <span class="script-name">{{ execution.script_name }}</span>
        </div>
        <div class="status-right">
          <el-button v-if="execution.has_jtl" size="small" @click="handleDownload('jtl')">下载 JTL</el-button>
          <el-button v-if="execution.jmx_path" size="small" @click="handleDownload('jmx')">下载 JMX</el-button>
          <el-button @click="$router.push('/performance-testing/executions')">返回列表</el-button>
        </div>
      </div>
      <el-row :gutter="20" class="meta-row">
        <el-col :span="4"><div class="meta"><span class="label">线程数</span><span class="value">{{ execution.thread_count }}</span></div></el-col>
        <el-col :span="4"><div class="meta"><span class="label">Ramp-Up</span><span class="value">{{ execution.ramp_up }}s</span></div></el-col>
        <el-col :span="4"><div class="meta"><span class="label">持续</span><span class="value">{{ execution.duration }}s</span></div></el-col>
        <el-col :span="6"><div class="meta"><span class="label">开始</span><span class="value">{{ formatTime(execution.started_at) }}</span></div></el-col>
        <el-col :span="6"><div class="meta"><span class="label">完成</span><span class="value">{{ formatTime(execution.completed_at) }}</span></div></el-col>
      </el-row>
      <el-alert v-if="execution.error_message" :title="execution.error_message" type="warning" :closable="false" show-icon style="margin-top: 12px" />
    </el-card>

    <!-- Tabs -->
    <el-card style="margin-top: 16px" v-if="execution">
      <el-tabs v-model="activeTab" @tab-change="onTabChange">
        <!-- 汇总概览 -->
        <el-tab-pane label="汇总概览" name="summary">
          <div v-if="summary" class="summary-grid">
            <div class="stat-card" v-for="item in summaryCards" :key="item.label">
              <div class="stat-label">{{ item.label }}</div>
              <div class="stat-value" :style="{ color: item.color }">{{ item.value }}</div>
            </div>
          </div>
          <el-empty v-else description="汇总数据尚未生成" />

          <!-- 验收判定：SLA 阈值判定 + 验收目标判定（脚本未配置时均为「未评估」） -->
          <div class="verdict-block" v-if="execution">
            <div class="verdict-head">
              <span class="verdict-title">验收判定</span>
              <el-tag :type="verdictType(execution.sla_result)" size="small">
                SLA：{{ execution.sla_result_display || '未评估' }}
              </el-tag>
              <el-tag :type="verdictType(execution.verdict)" size="small" style="margin-left: 8px">
                验收目标：{{ execution.verdict_display || '未评估' }}
              </el-tag>
            </div>
            <el-table :data="judgeRows" size="small" stripe v-if="judgeRows.length" style="margin-top: 10px">
              <el-table-column prop="scope" label="范围" min-width="140" show-overflow-tooltip />
              <el-table-column prop="source" label="来源" width="100" align="center" />
              <el-table-column prop="metric" label="指标" min-width="140" />
              <el-table-column prop="comparator" label="比较" width="70" align="center" />
              <el-table-column prop="target" label="阈值/目标" width="110" align="center" />
              <el-table-column prop="actual" label="实际" width="110" align="center" />
              <el-table-column prop="unit" label="单位" width="80" align="center" />
              <el-table-column label="结果" width="90" align="center">
                <template #default="{ row }">
                  <el-tag :type="row.passed ? 'success' : 'danger'" size="small">
                    {{ row.passed ? '通过' : '未通过' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="该脚本未配置 SLA 阈值 / 验收目标，本次未评估" :image-size="60" />
          </div>
        </el-tab-pane>

        <!-- 结构化指标 -->
        <el-tab-pane label="结构化指标" name="metrics">
          <el-table :data="metrics" stripe v-if="metrics.length">
            <el-table-column prop="sample_label" label="请求名称" min-width="200" />
            <el-table-column prop="sample_count" label="样本数" width="90" align="center" sortable />
            <el-table-column prop="avg" label="平均(ms)" width="100" align="center" sortable />
            <el-table-column prop="min" label="最小(ms)" width="100" align="center" />
            <el-table-column prop="max" label="最大(ms)" width="100" align="center" />
            <el-table-column prop="p90" label="P90(ms)" width="100" align="center" sortable />
            <el-table-column prop="p95" label="P95(ms)" width="100" align="center" sortable />
            <el-table-column prop="p99" label="P99(ms)" width="100" align="center" />
            <el-table-column prop="throughput" label="吞吐量(req/s)" width="120" align="center" sortable />
            <el-table-column prop="error_rate" label="错误率(%)" width="100" align="center" sortable>
              <template #default="{ row }">
                <span :style="{ color: row.error_rate > 5 ? '#f56c6c' : '' }">{{ row.error_rate }}</span>
              </template>
            </el-table-column>
            <el-table-column label="时间线" width="100" align="center">
              <template #default="{ row }">
                <el-button size="small" text @click="showTimeline(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="暂无指标数据" />
        </el-tab-pane>

        <!-- 实时监控 -->
        <el-tab-pane name="realtime">
          <template #label>
            实时监控 <el-tag v-if="execution.status === 'RUNNING'" type="warning" size="small" style="margin-left:4px">LIVE</el-tag>
          </template>
          <div v-if="realtimeData?.enabled">
            <div class="realtime-grid">
              <div class="rt-card" v-for="item in realtimeCards" :key="item.label">
                <div class="rt-label">{{ item.label }}</div>
                <div class="rt-value">{{ item.value }}</div>
              </div>
            </div>
            <div class="realtime-charts">
              <el-row :gutter="16">
                <el-col :span="12" v-for="(opt, idx) in realtimeChartOptions" :key="idx">
                  <div class="rt-chart-card">
                    <v-chart class="rt-chart" :option="opt" autoresize />
                  </div>
                </el-col>
              </el-row>
            </div>
          </div>
          <el-alert v-else type="info" :closable="false" show-icon title="暂无实时数据" description="执行完成后才能查看实时指标，或检查 JTL 文件是否存在。" />
        </el-tab-pane>

        <!-- 服务器/数据库监控 -->
        <el-tab-pane label="服务器/DB 监控" name="monitoring">
          <div v-if="monitoringTargets.length">
            <div v-for="target in monitoringTargets" :key="target.target_name" class="monitor-block">
              <h3 class="monitor-title">
                {{ target.target_name }}
                <el-tag size="small" type="info">{{ targetTypeLabel(target.target_type) }}</el-tag>
              </h3>
              <el-table :data="target.metrics" stripe size="small" style="margin-bottom: 12px">
                <el-table-column prop="metric_label" label="指标" min-width="140" />
                <el-table-column prop="metric_unit" label="单位" width="70" align="center" />
                <el-table-column prop="avg_value" label="平均" width="90" align="center" sortable />
                <el-table-column prop="max_value" label="最大" width="90" align="center" sortable />
                <el-table-column prop="peak_value" label="峰值" width="90" align="center" sortable />
              </el-table>
              <el-row :gutter="16">
                <el-col :span="12" v-for="(m, mi) in target.metrics" :key="mi">
                  <div class="monitor-chart-card">
                    <div class="monitor-chart-title">{{ m.metric_label }}（{{ m.metric_unit }}）</div>
                    <v-chart class="monitor-chart" :option="monitorChartOption(m)" autoresize />
                  </div>
                </el-col>
              </el-row>
            </div>
          </div>
          <el-empty v-else description="未采集到监控数据（未配置 Prometheus 或执行期间无指标）" />
        </el-tab-pane>

        <!-- JMeter 日志 -->
        <el-tab-pane label="JMeter 日志" name="log">
          <el-input type="textarea" :model-value="execution.jmeter_log" :rows="20" readonly style="font-family: monospace; font-size: 12px" />
        </el-tab-pane>

        <!-- HTML 报告 -->
        <el-tab-pane label="HTML 报告" name="report" :disabled="!execution.has_report">
          <div v-if="execution.has_report && reportHtml" class="report-actions">
            <el-button size="small" type="primary" :loading="regenerating" @click="handleRegenerateReport">
              重新生成报告
            </el-button>
            <el-button size="small" :loading="reportLoading" @click="refreshReport">刷新</el-button>
            <span style="color: #909399; font-size: 12px; margin-left: 8px;">旧版报告可能显示空白图表，点击重新生成</span>
          </div>
          <iframe v-if="execution.has_report && reportHtml" :srcdoc="reportHtml" class="report-iframe" frameborder="0" :key="reportKey" />
          <el-empty v-else description="HTML 报告尚未生成" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 时间线弹窗 -->
    <el-dialog v-model="timelineDialogVisible" :title="`时间线 - ${currentMetric?.sample_label}`" width="700px">
      <div v-if="currentMetric?.timeline?.length" class="timeline-chart">
        <div v-for="(point, idx) in currentMetric.timeline" :key="idx" class="timeline-bar-group">
          <div class="timeline-bar" :style="{ height: barHeight(point.p95) + 'px', background: point.error_count > 0 ? '#f56c6c' : '#409eff' }" :title="`t=${point.t}s avg=${point.avg}ms p95=${point.p95}ms count=${point.count} errors=${point.error_count}`" />
          <div class="timeline-label">{{ point.t }}s</div>
        </div>
      </div>
      <el-empty v-else description="无时间线数据" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { getExecution, getExecutionSummary, getExecutionMetrics, getRealtimeData, regenerateExecutionReport, getExecutionReport, getExecutionMonitoring } from '@/api/performance'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const route = useRoute()
const loading = ref(true)
const execution = ref(null)
const summary = ref(null)
const metrics = ref([])
const realtimeData = ref(null)
const activeTab = ref(route.query.tab || 'summary')
const reportKey = ref(0)
const regenerating = ref(false)
const autoRegenTried = ref(false)  // 防止自动重生成循环
const reportHtml = ref('')
const reportLoading = ref(false)
const monitoringTargets = ref([])
const monitoringLoaded = ref(false)

const timelineDialogVisible = ref(false)
const currentMetric = ref(null)

let pollTimer = null

const formatTime = (val) => val ? new Date(val).toLocaleString('zh-CN', { hour12: false }) : '-'
const statusType = (s) => ({ QUEUED: 'info', RUNNING: 'warning', COMPLETED: 'success', FAILED: 'danger', CANCELLED: 'info' }[s] || 'info')
const verdictType = (v) => ({ PASSED: 'success', FAILED: 'danger', NOT_EVALUATED: 'info' }[v] || 'info')

// 验收判定明细：把 SLA 逐项判定 + 验收目标明细拍平成一张表
const judgeRows = computed(() => {
  const ex = execution.value
  if (!ex) return []
  const unitOf = (label) => {
    const s = String(label || '')
    if (s.includes('ms')) return 'ms'
    if (s.includes('%')) return '%'
    return 'req/s'
  }
  const rows = []
  for (const d of ex.sla_detail || []) {
    rows.push({
      scope: '(整体)',
      source: 'SLA',
      metric: d.label,
      comparator: d.comparator || '',
      target: d.threshold,
      actual: d.actual,
      unit: unitOf(d.label),
      passed: !!d.passed,
    })
  }
  for (const d of ex.verdict_details || []) {
    rows.push({
      scope: d.step,
      source: '验收目标',
      metric: d.metric,
      comparator: d.metric === 'TPS' ? '≥' : '≤',
      target: d.target,
      actual: d.actual,
      unit: d.unit,
      passed: d.result === 'PASS',
    })
  }
  return rows
})

const summaryCards = computed(() => {
  if (!summary.value) return []
  const s = summary.value
  return [
    { label: '总样本数', value: s.total_samples, color: '#409eff' },
    { label: '错误数', value: s.error_count, color: s.error_count > 0 ? '#f56c6c' : '#67c23a' },
    { label: '错误率(%)', value: s.error_rate, color: s.error_rate > 5 ? '#f56c6c' : '#67c23a' },
    { label: '平均响应(ms)', value: s.avg_response_time, color: '#409eff' },
    { label: '最小响应(ms)', value: s.min_response_time, color: '#67c23a' },
    { label: '最大响应(ms)', value: s.max_response_time, color: '#e6a23c' },
    { label: 'P90(ms)', value: s.p90, color: '#409eff' },
    { label: 'P95(ms)', value: s.p95, color: '#e6a23c' },
    { label: 'P99(ms)', value: s.p99, color: '#f56c6c' },
    { label: '吞吐量(req/s)', value: s.throughput, color: '#409eff' },
    { label: '接收(MB)', value: (s.data_received / 1048576).toFixed(2), color: '#909399' },
    { label: '发送(MB)', value: (s.data_sent / 1048576).toFixed(2), color: '#909399' },
  ]
})

const realtimeCards = computed(() => {
  if (!realtimeData.value?.enabled) return []
  const d = realtimeData.value
  const lastVal = (arr) => arr.length ? arr[arr.length - 1].value.toFixed(2) : '-'
  return [
    { label: 'P95 响应(ms)', value: lastVal(d.response_time_p95) },
    { label: '吞吐量(req/s)', value: lastVal(d.throughput) },
    { label: '错误数(5s)', value: lastVal(d.errors) },
    { label: '活跃线程', value: lastVal(d.active_threads) },
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
  const times = data.map(d => d.time || d.ts || d.timestamp || '')
  const values = data.map(d => Number(d.value || d[key] || 0))
  return { times, values }
}

const realtimeChartOptions = computed(() => {
  const d = realtimeData.value
  if (!d?.enabled) return []
  const opts = []
  const rt = extractTimeSeries(d.response_time_p95)
  const tps = extractTimeSeries(d.throughput)
  const errs = extractTimeSeries(d.errors)
  const threads = extractTimeSeries(d.active_threads)
  opts.push(buildLineOption('P95 响应时间(ms)', [{ name: 'P95', ...rt, color: '#409eff' }]))
  opts.push(buildLineOption('吞吐量(req/s)', [{ name: '吞吐/s', ...tps, color: '#67c23a' }]))
  opts.push(buildLineOption('错误数(5s)', [{ name: '错误数', ...errs, color: '#f56c6c' }]))
  opts.push(buildLineOption('活跃线程', [{ name: '活跃线程', ...threads, color: '#e6a23c' }]))
  return opts
})

const showTimeline = (row) => {
  currentMetric.value = row
  timelineDialogVisible.value = true
}

const maxP95 = computed(() => {
  if (!currentMetric.value?.timeline?.length) return 1
  return Math.max(...currentMetric.value.timeline.map(p => p.p95), 1)
})

const barHeight = (p95) => Math.max(4, (p95 / maxP95.value) * 200)

const handleRegenerateReport = async () => {
  regenerating.value = true
  try {
    await regenerateExecutionReport(route.params.id)
    ElMessage.success('报告已重新生成')
    reportKey.value += 1
    await loadReportHtml()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重新生成报告失败')
  } finally {
    regenerating.value = false
  }
}

const refreshReport = async () => {
  reportKey.value += 1
  await loadReportHtml()
}

const loadReportHtml = async () => {
  if (!execution.value?.has_report) return
  reportLoading.value = true
  try {
    const res = await getExecutionReport(route.params.id)
    reportHtml.value = res.data?.html || '<p>报告内容为空</p>'
  } catch (e) {
    // 报告文件缺失（jtl 被清理 / 历史执行 / 旧版报告损坏）→ 自动重生成一次
    if (!autoRegenTried.value) {
      autoRegenTried.value = true
      ElMessage.warning('报告文件缺失，正在自动重新生成…')
      await handleRegenerateReport()
    } else {
      ElMessage.error('加载报告失败，请检查 JTL 文件或后端日志')
      reportHtml.value = '<p>报告加载失败，请点击"重新生成报告"重试</p>'
    }
  } finally {
    reportLoading.value = false
  }
}

const onTabChange = (tab) => {
  if (tab === 'report' && execution.value?.has_report && !reportHtml.value && !reportLoading.value) {
    loadReportHtml()
  }
  if (tab === 'monitoring') {
    loadMonitoring()
    // 执行中启动监控轮询（15s 一次，与后端采集频率对齐）
    if (execution.value && (execution.value.status === 'QUEUED' || execution.value.status === 'RUNNING')) {
      startMonitoringPoll()
    }
  }
}

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

const loadMonitoring = async (silent = false) => {
  try {
    const res = await getExecutionMonitoring(route.params.id)
    monitoringTargets.value = res.data.targets || []
    monitoringLoaded.value = true
  } catch (e) {
    if (!silent) monitoringTargets.value = []
  }
}

// 监控独立轮询（执行期间才跑，状态变非 RUNNING 自动停）
let monitoringTimer = null
const startMonitoringPoll = () => {
  if (monitoringTimer) return
  monitoringTimer = setInterval(async () => {
    if (!execution.value || (execution.value.status !== 'QUEUED' && execution.value.status !== 'RUNNING')) {
      stopMonitoringPoll()
      return
    }
    await loadMonitoring(true)
  }, 15000)
}
const stopMonitoringPoll = () => {
  if (monitoringTimer) {
    clearInterval(monitoringTimer)
    monitoringTimer = null
  }
}

// 结果文件走浏览器原生下载（?token= 认证），不再用 axios 拉 blob：
// JTL 动辄十几 MB，axios 超时 10s、内存里再拼一次 Blob，容易在下载器/内嵌 webview 里失败。
const handleDownload = (type) => {
  const token = localStorage.getItem('access_token') || ''
  const path = type === 'jtl' ? 'jtl_download' : 'jmx_download'
  const filename = `${execution.value?.execution_id || route.params.id}.${type === 'jtl' ? 'jtl' : 'jmx'}`
  const url = `/api/performance-testing/executions/${route.params.id}/${path}/?token=${encodeURIComponent(token)}`
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

const loadAll = async () => {
  loading.value = true
  try {
    const [execRes, metricsRes] = await Promise.all([
      getExecution(route.params.id),
      getExecutionMetrics(route.params.id),
    ])
    execution.value = execRes.data
    metrics.value = metricsRes.data || []
    // 汇总只有在 COMPLETED 时才有
    if (execRes.data.status === 'COMPLETED') {
      try {
        const sumRes = await getExecutionSummary(route.params.id)
        summary.value = sumRes.data
      } catch (e) { /* 可能还没生成 */ }
    }
    // 实时数据：运行中始终刷新，未启用 InfluxDB 时回退到 JTL 实时解析
    if (execRes.data.status === 'RUNNING' || execRes.data.status === 'COMPLETED') {
      try {
        const rtRes = await getRealtimeData(route.params.id, 60)
        realtimeData.value = rtRes.data
      } catch (e) { /* 忽略 */ }
    }
    // 如果当前打开的是 HTML 报告 tab，提前加载报告内容
    if (activeTab.value === 'report' && execRes.data.has_report) {
      loadReportHtml()
    }
  } catch (e) {
    ElMessage.error('加载执行详情失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAll()
  // 如果还在执行中，每5秒轮询
  pollTimer = setInterval(async () => {
    if (execution.value && (execution.value.status === 'QUEUED' || execution.value.status === 'RUNNING')) {
      await loadAll()
    }
  }, 5000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  stopMonitoringPoll()
})
</script>

<style scoped>
.status-card .status-bar { display: flex; justify-content: space-between; align-items: center; }
.status-left { display: flex; align-items: center; gap: 12px; }
.exec-id { color: #909399; font-size: 13px; font-family: monospace; }
.script-name { font-weight: 600; }
.meta-row { margin-top: 16px; }
.meta { display: flex; flex-direction: column; gap: 4px; }
.meta .label { font-size: 12px; color: #909399; }
.meta .value { font-size: 14px; font-weight: 500; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 16px; }
.stat-card { background: #f5f7fa; border-radius: 8px; padding: 16px; text-align: center; }
.stat-label { font-size: 13px; color: #606266; margin-bottom: 8px; }
.stat-value { font-size: 24px; font-weight: 700; }
.realtime-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
.rt-card { background: #f0f9ff; border: 1px solid #d0e8ff; border-radius: 8px; padding: 20px; text-align: center; }
.rt-label { font-size: 14px; color: #606266; margin-bottom: 8px; }
.rt-value { font-size: 28px; font-weight: 700; color: #409eff; }
.realtime-charts { margin-top: 16px; }
.rt-chart-card { background: #fff; border-radius: 8px; border: 1px solid #ebeef5; padding: 12px; margin-bottom: 16px; }
.rt-chart { height: 260px; }
.report-actions { margin-bottom: 12px; }
.report-iframe { width: 100%; height: 600px; border: none; }
.timeline-chart { display: flex; align-items: flex-end; gap: 2px; height: 240px; padding: 20px 0; overflow-x: auto; }
.timeline-bar-group { display: flex; flex-direction: column; align-items: center; flex-shrink: 0; width: 20px; }
.timeline-bar { width: 16px; border-radius: 2px 2px 0 0; transition: height 0.3s; }
.timeline-label { font-size: 9px; color: #909399; margin-top: 4px; }
.monitor-block { margin-bottom: 24px; }
.monitor-title { font-size: 15px; font-weight: 600; color: #303133; margin: 8px 0 12px; display: flex; align-items: center; gap: 8px; }
.monitor-chart-card { background: #fff; border-radius: 8px; border: 1px solid #ebeef5; padding: 12px; margin-bottom: 16px; }
.monitor-chart-title { font-size: 13px; font-weight: 600; color: #303133; text-align: center; margin-bottom: 4px; }
.monitor-chart { height: 220px; }
.verdict-block { margin-top: 20px; border-top: 1px solid #ebeef5; padding-top: 16px; }
.verdict-head { display: flex; align-items: center; gap: 8px; }
.verdict-title { font-size: 15px; font-weight: 600; color: #303133; margin-right: 8px; }
</style>
