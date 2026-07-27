<template>
  <div ref="chartRef" class="kg-graph-chart" :style="{ height: `${height}px` }" />
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { getKgEntityTypeLabel, getKgRelationLabel } from '@/utils/kgLabels'

const props = defineProps({
  graphData: {
    type: Object,
    default: () => ({ nodes: [], edges: [], root: null })
  },
  height: {
    type: Number,
    default: 520
  },
  colorByCommunity: {
    type: Boolean,
    default: false
  }
})

const chartRef = ref(null)
let chartInstance = null

const TYPE_COLORS = {
  Project: '#6366f1',
  TestCase: '#22c55e',
  TestCaseGenerationTask: '#3b82f6',
  KbFunction: '#f59e0b',
  KbDocument: '#14b8a6',
  BusinessRequirement: '#a855f7',
  KbChatSession: '#ec4899',
  RequirementDocument: '#64748b',
  FunctionPoint: '#ef4444',
  ApiRequest: '#0ea5e9',
  UiPageObject: '#8b5cf6',
  CodeFile: '#334155',
  CodeClass: '#64748b',
  CodeFunction: '#94a3b8',
  CodeModule: '#a3a3a3',
}

const COMMUNITY_COLORS = [
  '#6366f1', '#22c55e', '#f59e0b', '#14b8a6', '#a855f7', '#ec4899',
  '#0ea5e9', '#ef4444', '#84cc16', '#f97316'
]

function confidenceLabel(level) {
  if (level === 'EXTRACTED') return '字面提取'
  if (level === 'INFERRED') return '推断'
  if (level === 'AMBIGUOUS') return '歧义'
  return ''
}

function buildOption(data) {
  const nodes = data?.nodes || []
  const edges = data?.edges || []
  const rootKey = data?.root?.entity_key
  const byCommunity = props.colorByCommunity

  const categories = []
  const categoryIndex = {}
  for (const node of nodes) {
    const cid = node.properties?.community_id
    const group = byCommunity
      ? (cid != null ? `社区 ${cid}` : '未分类')
      : (node.entity_type || 'Other')
    if (categoryIndex[group] == null) {
      categoryIndex[group] = categories.length
      categories.push({
        name: group,
        itemStyle: {
          color: byCommunity
            ? COMMUNITY_COLORS[categories.length % COMMUNITY_COLORS.length]
            : (TYPE_COLORS[node.entity_type] || '#94a3b8')
        }
      })
    }
  }

  const chartNodes = nodes.map(node => {
    const cid = node.properties?.community_id
    const group = byCommunity
      ? (cid != null ? `社区 ${cid}` : '未分类')
      : (node.entity_type || 'Other')
    return {
      id: node.entity_key,
      name: (node.label || node.entity_key).slice(0, 40),
      category: categoryIndex[group] ?? 0,
      symbolSize: node.entity_key === rootKey ? 52 : 34,
      value: node.entity_type,
    }
  })

  const chartLinks = edges.map(edge => ({
    source: edge.src,
    target: edge.dst,
    relation_type: edge.relation_type,
    confidence_level: edge.confidence_level,
    edgeSource: edge.source,
    label: {
      show: edges.length <= 40,
      formatter: getKgRelationLabel(edge.relation_type),
      fontSize: 10,
      color: '#64748b'
    },
    lineStyle: {
      curveness: 0.12,
      type: edge.confidence_level === 'AMBIGUOUS' ? 'dashed' : 'solid'
    }
  }))

  return {
    tooltip: {
      trigger: 'item',
      formatter(params) {
        if (params.dataType === 'edge') {
          const d = params.data
          const levelText = confidenceLabel(d.confidence_level)
          return [
            getKgRelationLabel(d.relation_type),
            `${d.source} → ${d.target}`,
            levelText ? `置信度：${levelText}` : '',
            d.edgeSource ? `来源：${d.edgeSource}` : ''
          ].filter(Boolean).join('<br/>')
        }
        const node = nodes.find(n => n.entity_key === params.data.id)
        if (!node) return params.data.name
        const lines = [
          `<strong>${node.label || node.entity_key}</strong>`,
          getKgEntityTypeLabel(node.entity_type),
          node.entity_key
        ]
        if (node.properties?.community_id != null) {
          lines.push(`社区：${node.properties.community_id}`)
        }
        return lines.join('<br/>')
      }
    },
    legend: categories.length > 1 ? [{ data: categories.map(c => c.name), bottom: 0, type: 'scroll' }] : undefined,
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        data: chartNodes,
        links: chartLinks,
        categories,
        label: {
          show: true,
          position: 'right',
          fontSize: 11,
          formatter: '{b}'
        },
        force: {
          repulsion: Math.max(140, chartNodes.length * 8),
          edgeLength: [70, 160],
          gravity: 0.08
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 2 }
        },
        lineStyle: {
          color: '#cbd5e1',
          width: 1.2,
          opacity: 0.85
        }
      }
    ]
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  const nodes = props.graphData?.nodes || []
  if (nodes.length === 0) {
    chartInstance.clear()
    return
  }
  chartInstance.setOption(buildOption(props.graphData), true)
}

function handleResize() {
  chartInstance?.resize()
}

watch(
  () => props.graphData,
  () => renderChart(),
  { deep: true }
)

watch(
  () => props.colorByCommunity,
  () => renderChart()
)

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})

defineExpose({ resize: handleResize })
</script>

<style scoped>
.kg-graph-chart {
  width: 100%;
  min-height: 320px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}
</style>
