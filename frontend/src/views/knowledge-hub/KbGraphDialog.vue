<!--
  知识库知识图谱弹窗（2026-07-23 创建 / 2026-07-24 v3.3 升级）
  - 显示 KB 关联项目的**完整业务图谱**（与「知识图谱浏览」同源）
  - 顶部项目下拉可切换（KB 多项目时）
  - 节点类型：Project + Requirement/TestCase/FunctionPoint + NativeKb/Doc + Code*
  - 支持点击节点看详情 / 重新同步
-->
<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    :title="dialogTitle"
    width="1100px"
    top="3vh"
    destroy-on-close
    @open="onOpen"
  >
    <div v-loading="loading" class="kg-dialog-body">
      <div class="kg-stats">
        <el-tag v-if="selectedProjectId" size="small" type="warning">
          📁 项目 #{{ selectedProjectId }}
        </el-tag>
        <el-tag size="small" type="success">{{ stats.nodes }} 节点</el-tag>
        <el-tag size="small" type="info">{{ stats.edges }} 边</el-tag>
        <el-tag v-if="kbName" size="small">KB: {{ kbName }}</el-tag>
        <span v-if="typeBreakdown" class="type-breakdown">
          <el-tag
            v-for="(c, t) in typeBreakdown"
            :key="t"
            size="small"
            :color="colorFor(t)"
            effect="dark"
            class="type-tag"
          >
            {{ t }} · {{ c }}
          </el-tag>
        </span>
        <el-button size="small" link type="primary" :loading="loading" @click="loadGraph(true)">
          🔄 重新生成图谱
        </el-button>
      </div>
      <el-select
        v-if="availableProjects.length > 1"
        v-model="selectedProjectId"
        size="small"
        placeholder="切换关联项目"
        style="width: 220px; margin-bottom: 8px"
        @change="onProjectChange"
      >
        <el-option
          v-for="p in availableProjects"
          :key="p.id"
          :label="p.name || `项目 #${p.id}`"
          :value="p.id"
        />
      </el-select>
      <div ref="chartRef" class="kg-chart" v-if="!errorMsg"></div>
      <el-empty v-if="errorMsg" :description="errorMsg" />
      <div v-if="selectedNode" class="kg-detail">
        <h4>节点详情</h4>
        <el-descriptions :column="1" size="small" border>
          <el-descriptions-item label="类型">{{ selectedNode.entity_type }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ selectedNode.label }}</el-descriptions-item>
          <el-descriptions-item v-if="selectedNode.ref_app" label="来源">
            {{ selectedNode.ref_app }}#{{ selectedNode.ref_id }}
          </el-descriptions-item>
          <el-descriptions-item v-if="selectedNode.dataset_id" label="数据集">
            {{ selectedNode.dataset_id }}
          </el-descriptions-item>
          <el-descriptions-item v-if="selectedNode.project_id" label="项目">
            #{{ selectedNode.project_id }}
          </el-descriptions-item>
          <el-descriptions-item v-if="Object.keys(selectedNode.properties || {}).length" label="属性">
            <pre class="props-pre">{{ JSON.stringify(selectedNode.properties, null, 2) }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getKbGraph } from '@/api/kb-hub'

echarts.use([GraphChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  kbId: { type: [Number, String], default: null },
  kbName: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const errorMsg = ref('')
const chartRef = ref(null)
const graphData = ref({ nodes: [], edges: [] })
const availableProjects = ref([])
const selectedProjectId = ref(null)
const stats = computed(() => ({
  nodes: graphData.value?.nodes?.length || 0,
  edges: graphData.value?.edges?.length || 0,
}))
const typeBreakdown = computed(() => {
  const map = {}
  for (const n of (graphData.value?.nodes || [])) {
    const t = n.entity_type || 'unknown'
    map[t] = (map[t] || 0) + 1
  }
  return Object.keys(map).length > 1 ? map : null
})
const selectedNode = ref(null)
const dialogTitle = computed(() => {
  const base = `知识图谱 · ${props.kbName || ('KB#' + props.kbId)}`
  return selectedProjectId.value ? `${base} · 项目级完整图谱` : base
})
let chartInstance = null

const COLORS = {
  Project: '#e6a23c',
  RequirementDocument: '#f56c6c',
  BusinessRequirement: '#a461e0',
  FunctionPoint: '#909399',
  TestCase: '#13c2c2',
  TestCaseGenerationTask: '#ff9a8b',
  NativeKb: '#409eff',
  NativeKbDocument: '#67c23a',
  KbDocument: '#67c23a',
  KbFunction: '#5470c6',
  CodeFile: '#ffd666',
  CodeClass: '#ffc53d',
  CodeModule: '#ff7a45',
  CodeFunction: '#bae637',
  ApiRequest: '#5cdbd3',
  UiPage: '#b37feb',
  default: '#909399',
}

function colorFor(entityType) {
  return COLORS[entityType] || COLORS.default
}

function disposeChart() {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
}

function renderChart() {
  if (!chartRef.value) return
  disposeChart()
  chartInstance = echarts.init(chartRef.value)
  const nodes = (graphData.value.nodes || []).map(n => ({
    id: n.entity_key,
    name: n.label || n.entity_key,
    symbolSize: n.entity_type === 'NativeKb' || n.entity_type === 'Project' ? 42
              : n.entity_type === 'NativeKbDocument' ? 22
              : n.entity_type === 'BusinessRequirement' || n.entity_type === 'RequirementDocument' ? 24
              : n.entity_type === 'FunctionPoint' ? 18
              : n.entity_type === 'TestCase' ? 16
              : n.entity_type === 'CodeClass' || n.entity_type === 'CodeModule' ? 14
              : 12,
    itemStyle: { color: colorFor(n.entity_type) },
    category: n.entity_type,
    value: n,
    label: {
      show: ['NativeKb', 'Project', 'BusinessRequirement', 'RequirementDocument', 'FunctionPoint'].includes(n.entity_type),
      fontSize: 10,
    },
  }))
  // edges: dedupe by (src,dst,relation) and pick srcKey/dstKey
  const keyMap = new Map(nodes.map(n => [n.id, n.id]))
  const edges = (graphData.value.edges || [])
    .filter(e => keyMap.has(e.src) && keyMap.has(e.dst))
    .map(e => ({
      source: e.src,
      target: e.dst,
      label: { show: false },
      lineStyle: { width: 1.0, color: '#c0c4cc', curveness: 0.05 },
    }))
  const categories = Array.from(new Set(nodes.map(n => n.category))).map(name => ({ name }))

  chartInstance.setOption({
    tooltip: {
      formatter: (p) => {
        if (p.dataType === 'node') {
          return `<b>${p.data.value.label || p.data.name}</b><br>类型: ${p.data.value.entity_type}`
        }
        return ''
      },
    },
    legend: [{ data: categories.map(c => c.name), top: 0, type: 'scroll', textStyle: { fontSize: 11 } }],
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      data: nodes,
      links: edges,
      categories,
      force: { repulsion: 120, edgeLength: 60, gravity: 0.05 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 2 } },
      lineStyle: { opacity: 0.4 },
      animationDurationUpdate: 600,
    }],
  })
  chartInstance.on('click', (params) => {
    if (params.dataType === 'node') selectedNode.value = params.data.value
  })
  window.addEventListener('resize', resizeChart)
}

function resizeChart() {
  chartInstance?.resize()
}

async function loadGraph(force = false) {
  if (!props.kbId) { errorMsg.value = '缺少 kb_id'; return }
  loading.value = true
  errorMsg.value = ''
  try {
    const params = {}
    if (force) params.force = 1
    if (selectedProjectId.value) params.project_id = selectedProjectId.value
    const { data } = await getKbGraph(props.kbId, params)
    if (data.project_ids && data.project_ids.length) {
      availableProjects.value = data.project_ids.map(id => ({ id, name: `项目 #${id}` }))
      // 自动选第一个项目（如果还没选）
      if (!selectedProjectId.value) {
        selectedProjectId.value = data.project_ids[0]
      }
    } else {
      availableProjects.value = []
      selectedProjectId.value = null
    }
    if (!data.nodes || !data.nodes.length) {
      errorMsg.value = '该知识库暂无图谱数据，请先在文档管理上传并入库文档'
      graphData.value = { nodes: [], edges: [] }
      return
    }
    graphData.value = data
    await nextTick()
    renderChart()
  } catch (e) {
    console.error(e)
    errorMsg.value = '加载图谱失败：' + (e?.response?.data?.detail || e?.message || '未知错误')
  } finally {
    loading.value = false
  }
}

async function onProjectChange(pid) {
  selectedProjectId.value = pid
  await loadGraph()
}

function onOpen() {
  selectedNode.value = null
  loadGraph()
}

watch(() => props.kbId, (val) => {
  if (val && props.modelValue) loadGraph()
})

watch(() => props.modelValue, (val) => {
  if (!val) {
    selectedNode.value = null
    disposeChart()
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  disposeChart()
})
</script>

<style scoped>
.kg-dialog-body { padding: 4px; }
.kg-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.type-breakdown {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-left: 8px;
}
.type-tag {
  font-size: 10px !important;
  padding: 0 4px;
  height: 18px;
  line-height: 18px;
}
.kg-chart {
  width: 100%;
  height: 600px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 8px;
  border: 1px solid #ebeef5;
}
.kg-detail {
  margin-top: 16px;
  padding: 12px;
  background: #fafbfc;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
.kg-detail h4 { margin: 0 0 8px; font-size: 14px; color: #303133; }
.props-pre {
  margin: 0;
  font-size: 12px;
  background: #fff;
  padding: 8px;
  border-radius: 4px;
  max-height: 200px;
  overflow: auto;
  font-family: 'Fira Code', 'Monaco', monospace;
}
</style>