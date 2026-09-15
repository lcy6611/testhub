<template>
  <div class="page-container stats-page" v-loading="loading">
    <div class="page-header">
      <h1 class="page-title"><el-icon><DataAnalysis /></el-icon> 缺陷统计</h1>
      <div class="header-actions">
        <el-select v-model="filterProject" placeholder="项目" clearable filterable @change="load" style="width:180px">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button @click="$router.push('/defects')"><el-icon><List /></el-icon> 列表</el-button>
        <el-button @click="$router.push('/defects/kanban')"><el-icon><Grid /></el-icon> 看板</el-button>
      </div>
    </div>

    <div class="stat-cards" v-if="stats">
      <div class="stat-card"><div class="n">{{ stats.total }}</div><div class="l">缺陷总数</div></div>
      <div class="stat-card s-open"><div class="n">{{ openCount }}</div><div class="l">未关闭</div></div>
      <div class="stat-card s-resolved"><div class="n">{{ resolvedCount }}</div><div class="l">已修复/待验证</div></div>
      <div class="stat-card s-closed"><div class="n">{{ closedCount }}</div><div class="l">已关闭</div></div>
    </div>

    <el-row :gutter="16" v-if="!loading">
      <el-col :span="8">
        <el-card shadow="never"><template #header>状态分布</template><div ref="statusChart" class="chart"></div></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never"><template #header>优先级分布</template><div ref="priorityChart" class="chart"></div></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never"><template #header>类型分布</template><div ref="typeChart" class="chart"></div></el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px" v-if="!loading">
      <el-col :span="14">
        <el-card shadow="never"><template #header>趋势（新建 / 关闭 / 解决）</template><div ref="trendChart" class="chart-lg"></div></el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never"><template #header>处理人分布</template><div ref="assigneeChart" class="chart-lg"></div></el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { DataAnalysis, List, Grid } from '@element-plus/icons-vue'
import { getDefectStats } from '@/api/defects'
import request from '@/utils/api'

const loading = ref(false)
const stats = ref(null)
const projects = ref([])
const filterProject = ref(null)

const statusChart = ref(null)
const priorityChart = ref(null)
const typeChart = ref(null)
const trendChart = ref(null)
const assigneeChart = ref(null)
let charts = []

const statusLabelMap = {
  new: '新建', open: '待处理', in_progress: '处理中', resolved: '已修复',
  fixed: '待验证', closed: '已关闭', rejected: '已驳回', reopened: '重新打开'
}
const priorityLabelMap = { P0: 'P0', P1: 'P1', P2: 'P2', P3: 'P3' }
const typeLabelMap = {
  functional: '功能', ui: '界面', compatibility: '兼容', performance: '性能',
  security: '安全', data: '数据', other: '其他'
}

const openCount = ref(0)
const resolvedCount = ref(0)
const closedCount = ref(0)

const load = async () => {
  loading.value = true
  try {
    const params = {}
    if (filterProject.value) params.project = filterProject.value
    const res = await getDefectStats(params)
    const data = res.data || res
    stats.value = data
    openCount.value = (data.by_status || []).filter(s => !['closed', 'rejected'].includes(s.value)).reduce((a, b) => a + b.count, 0)
    resolvedCount.value = (data.by_status || []).filter(s => ['resolved', 'fixed'].includes(s.value)).reduce((a, b) => a + b.count, 0)
    closedCount.value = (data.by_status || []).filter(s => s.value === 'closed').reduce((a, b) => a + b.count, 0)
    await nextTick()
    renderCharts(data)
  } catch (e) {
    console.error(e)
  } finally { loading.value = false }
}

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/', { params: { page_size: 200 } })
    const data = res.data || res
    projects.value = data.results || data || []
    if (projects.value.length) { filterProject.value = projects.value[0].id; load() }
  } catch (e) {}
}

const basePie = (el, dataArr, labelMap) => {
  const chart = echarts.init(el)
  charts.push(chart)
  chart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll' },
    series: [{
      type: 'pie', radius: '55%', center: ['50%', '45%'],
      data: dataArr.map(d => ({ name: labelMap[d.value] || d.value, value: d.count })),
      label: { formatter: '{b}: {c}' }
    }]
  })
}

const renderCharts = (data) => {
  charts.forEach(c => c.dispose()); charts = []
  if (statusChart.value) basePie(statusChart.value, data.by_status || [], statusLabelMap)
  if (priorityChart.value) basePie(priorityChart.value, data.by_priority || [], priorityLabelMap)
  if (typeChart.value) basePie(typeChart.value, data.by_type || [], typeLabelMap)

  if (trendChart.value) {
    const tc = echarts.init(trendChart.value); charts.push(tc)
    const trend = data.trend || []
    tc.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['新建', '关闭', '解决'], bottom: 0 },
      grid: { left: 40, right: 20, top: 20, bottom: 40 },
      xAxis: { type: 'category', data: trend.map(t => t.date) },
      yAxis: { type: 'value' },
      series: [
        { name: '新建', type: 'line', smooth: true, data: trend.map(t => t.created), areaStyle: {} },
        { name: '关闭', type: 'line', smooth: true, data: trend.map(t => t.closed) },
        { name: '解决', type: 'line', smooth: true, data: trend.map(t => t.resolved) },
      ]
    })
  }

  if (assigneeChart.value) {
    const ac = echarts.init(assigneeChart.value); charts.push(ac)
    const arr = data.by_assignee || []
    ac.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 80, right: 20, top: 20, bottom: 20 },
      xAxis: { type: 'value' },
      yAxis: { type: 'category', data: arr.map(a => a.username).reverse() },
      series: [{ type: 'bar', data: arr.map(a => a.count).reverse() }]
    })
  }
}

const onResize = () => charts.forEach(c => c.resize())
onMounted(() => { loadProjects(); window.addEventListener('resize', onResize) })
onUnmounted(() => { charts.forEach(c => c.dispose()); window.removeEventListener('resize', onResize) })
</script>

<style scoped>
.stats-page { padding: 20px; }
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.page-title { display:flex; align-items:center; gap:8px; margin:0; font-size:20px; font-weight:600; }
.header-actions { display:flex; gap:8px; }
.stat-cards { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px; }
.stat-card { padding:16px; border-radius:8px; background:#fff; border:1px solid #ebeef5; text-align:center; }
.stat-card .n { font-size:28px; font-weight:700; }
.stat-card .l { margin-top:6px; font-size:12px; color:#909399; }
.s-open .n { color:#f56c6c; }
.s-resolved .n { color:#67c23a; }
.s-closed .n { color:#909399; }
.chart { height:280px; }
.chart-lg { height:320px; }
</style>
