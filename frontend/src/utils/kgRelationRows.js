import { getKgEntityTypeLabel, getKgRelationLabel } from '@/utils/kgLabels'

/** 根据图谱节点类型解析 Vue Router 跳转 */
export function resolveKgNodeLink(node) {
  if (!node?.entity_type || !node?.ref_id) return null
  if (node.entity_type === 'TestCaseGenerationTask') {
    return { name: 'TaskDetail', params: { taskId: node.ref_id } }
  }
  if (node.entity_type === 'TestCase') {
    return { name: 'TestCaseDetail', params: { id: node.ref_id } }
  }
  return null
}

export function buildKgRelationRow(edge, { nodeMap, prefix = '', neighbor = 'dst' }) {
  const nodeKey = neighbor === 'dst' ? edge.dst : edge.src
  const node = nodeMap[nodeKey] || {}
  const lastExecution = node.properties?.last_execution || null
  return {
    prefix,
    relationLabel: getKgRelationLabel(edge.relation_type),
    entityTypeLabel: getKgEntityTypeLabel(node.entity_type),
    label: node.label || nodeKey,
    linkTo: resolveKgNodeLink(node),
    entityType: node.entity_type,
    lastExecution,
    lastExecutionHint: formatKgLastExecution(lastExecution, node.entity_type)
  }
}

function formatIsoTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 格式化图谱节点 properties.last_execution 为展示文案 */
export function formatKgLastExecution(lastExecution, entityType) {
  if (!lastExecution || typeof lastExecution !== 'object') return ''

  const parts = []
  if (lastExecution.passed === true) {
    parts.push('通过')
  } else if (lastExecution.passed === false) {
    parts.push('失败')
  }

  const time = lastExecution.executed_at || lastExecution.finished_at
  const timeText = formatIsoTime(time)
  if (timeText) parts.push(timeText)

  if (entityType === 'ApiRequest') {
    if (lastExecution.status_code != null) parts.push(`HTTP ${lastExecution.status_code}`)
    if (lastExecution.response_time_ms != null) {
      parts.push(`${Math.round(lastExecution.response_time_ms)}ms`)
    }
  } else if (entityType === 'UiPageObject') {
    if (lastExecution.execution_time_sec != null) {
      parts.push(`${Number(lastExecution.execution_time_sec).toFixed(1)}s`)
    }
  }

  return parts.join(' · ')
}

function buildNodeMap(subgraph) {
  const nodeMap = {}
  for (const node of subgraph?.nodes || []) {
    nodeMap[node.entity_key] = node
  }
  return nodeMap
}

/**
 * @param {'outgoing'|'provenance-chain'|'derived-incoming'} mode
 */
export function buildKgDisplayRows(subgraph, rootKey, mode = 'outgoing') {
  const edges = subgraph?.edges || []
  if (!rootKey || !edges.length) return []

  const nodeMap = buildNodeMap(subgraph)

  if (mode === 'outgoing') {
    return edges
      .filter(e => e.src === rootKey)
      .map(e => buildKgRelationRow(e, { nodeMap }))
  }

  if (mode === 'provenance-chain') {
    const rows = []
    for (const edge of edges.filter(e => e.src === rootKey)) {
      rows.push(buildKgRelationRow(edge, { nodeMap }))
    }
    const taskEdge = edges.find(e => e.src === rootKey && e.relation_type === 'provenance')
    const taskKey = taskEdge?.dst
    if (taskKey) {
      for (const edge of edges.filter(e => e.src === taskKey)) {
        rows.push(buildKgRelationRow(edge, { nodeMap, prefix: '经生成任务' }))
      }
    }
    return rows
  }

  if (mode === 'testcase-detail') {
    const coversRows = []
    const automatesRows = []
    const directRows = []
    for (const edge of edges.filter(e => e.src === rootKey)) {
      const row = buildKgRelationRow(edge, { nodeMap })
      if (edge.relation_type === 'covers') {
        coversRows.push({ ...row, rowVariant: 'covers' })
      } else if (edge.relation_type === 'automates') {
        automatesRows.push({ ...row, rowVariant: 'automates' })
      } else if (edge.relation_type !== 'belongs_to') {
        directRows.push(row)
      }
    }
    const taskEdge = edges.find(e => e.src === rootKey && e.relation_type === 'provenance')
    const taskKey = taskEdge?.dst
    const taskRows = []
    if (taskKey) {
      for (const edge of edges.filter(e => e.src === taskKey)) {
        taskRows.push(buildKgRelationRow(edge, { nodeMap, prefix: '经生成任务' }))
      }
    }
    return [...coversRows, ...automatesRows, ...directRows, ...taskRows]
  }

  if (mode === 'derived-incoming') {
    const rows = []
    const taskKeys = new Set()
    for (const edge of edges) {
      if (edge.dst !== rootKey) continue
      if (edge.relation_type === 'derived_from') {
        taskKeys.add(edge.src)
      }
      const isOutgoing = edge.src === rootKey
      rows.push(
        buildKgRelationRow(edge, {
          nodeMap,
          neighbor: isOutgoing ? 'dst' : 'src'
        })
      )
    }
    for (const taskKey of taskKeys) {
      for (const edge of edges.filter(e => e.src === taskKey)) {
        rows.push(buildKgRelationRow(edge, { nodeMap, prefix: '经生成任务' }))
      }
    }
    return rows
  }

  return []
}

/** 用例详情：分组展示 covers / 来源 / 任务引用 */
export function buildKgTestCaseSections(subgraph, rootKey) {
  const edges = subgraph?.edges || []
  if (!rootKey || !edges.length) {
    return []
  }

  const nodeMap = buildNodeMap(subgraph)
  const coversRows = []
  const automatesRows = []
  const sourceRows = []

  for (const edge of edges.filter(e => e.src === rootKey)) {
    const row = buildKgRelationRow(edge, { nodeMap })
    if (edge.relation_type === 'covers') {
      coversRows.push({ ...row, rowVariant: 'covers' })
    } else if (edge.relation_type === 'automates') {
      automatesRows.push({ ...row, rowVariant: 'automates' })
    } else if (edge.relation_type !== 'belongs_to') {
      sourceRows.push(row)
    }
  }

  const taskEdge = edges.find(e => e.src === rootKey && e.relation_type === 'provenance')
  const taskKey = taskEdge?.dst
  const taskRows = []
  if (taskKey) {
    for (const edge of edges.filter(e => e.src === taskKey)) {
      taskRows.push(buildKgRelationRow(edge, { nodeMap, prefix: '经生成任务' }))
    }
  }

  const sections = []
  if (coversRows.length) {
    sections.push({ key: 'covers', title: '覆盖范围', rows: coversRows })
  }
  if (automatesRows.length) {
    sections.push({ key: 'automates', title: '自动化关联', rows: automatesRows })
  }
  if (sourceRows.length) {
    sections.push({ key: 'source', title: '来源', rows: sourceRows })
  }
  if (taskRows.length) {
    sections.push({ key: 'task', title: '生成任务引用', rows: taskRows })
  }
  return sections
}
