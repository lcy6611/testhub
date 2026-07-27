import api from '@/utils/api'

/** 获取知识图谱子图（以 entity_key 为根） */
export function getKgSubgraph(entityKey, params = {}) {
  return api.get('/kg/subgraph/', {
    params: {
      entity: entityKey,
      depth: params.depth ?? 2,
      max_nodes: params.max_nodes ?? 100
    }
  })
}

/** 项目级图谱（力导向图数据） */
export function getKgProjectGraph(projectId, params = {}) {
  const p = {
    project_id: projectId,
    depth: params.depth ?? 2,
    max_nodes: params.maxNodes ?? 300
  }
  if (params.datasetId) {
    p.dataset_id = params.datasetId
  }
  return api.get('/kg/project-graph/', { params: p })
}

/** 项目覆盖度报告 */
export function getKgCoverageReport(projectId, params = {}) {
  return api.get('/kg/coverage-report/', {
    params: {
      project_id: projectId,
      limit: params.limit ?? 100
    }
  })
}
/** 知识图谱是否启用 */
export function getKgStatus(entityKey) {
  return api.get('/kg/status/', {
    params: entityKey ? { entity: entityKey } : {}
  })
}

/** 将知识库功能模块同步到知识图谱 */
export function syncKgKbFunctions(params = {}) {
  const data = {}
  if (params.projectId) data.project_id = params.projectId
  if (params.datasetId) data.dataset_id = params.datasetId
  return api.post('/kg/sync-kb-functions/', data)
}

/** 将 API 测试接口同步到知识图谱 */
export function syncKgApiRequests(params = {}) {
  const data = {}
  if (params.projectId) data.project_id = params.projectId
  return api.post('/kg/sync-api-requests/', data)
}

/** 将 UI 页面对象同步到知识图谱 */
export function syncKgUiPages(params = {}) {
  const data = {}
  if (params.projectId) data.project_id = params.projectId
  return api.post('/kg/sync-ui-pages/', data)
}

/** 导出图谱 JSON（Neo4j 导入预备格式） */
export function exportKgGraph(params = {}) {
  return api.get('/kg/export/', {
    params: {
      project_id: params.projectId,
      max_nodes: params.maxNodes ?? 5000,
      max_edges: params.maxEdges ?? 10000
    }
  })
}

/** KB 文档变更影响：追溯到引用该文档的生成任务与已采纳用例 */
export function getKgImpact(datasetId, documentId) {
  return api.get('/kg/impact/', {
    params: {
      dataset_id: datasetId,
      document_id: documentId
    }
  })
}

/** 预览图谱扩展后的功能模块与 KB 文档 */
export function getKgExpandRefs({ datasetId, functionIds = [], documentIds = [], depth = 2 }) {
  const params = { dataset_id: datasetId, depth }
  if (functionIds.length > 0) {
    params.function_ids = functionIds.join(',')
  }
  if (documentIds.length > 0) {
    params.document_ids = documentIds.join(',')
  }
  return api.get('/kg/expand-refs/', { params })
}

/** 手动创建图谱边（maps_to：需求 → 功能模块） */
export function createKgEdge(data) {
  return api.post('/kg/edges/', data)
}

/** 列出实体关联边（默认 manual） */
export function getKgEdges(entityKey, params = {}) {
  return api.get('/kg/edges/', {
    params: {
      entity: entityKey,
      direction: params.direction ?? 'both',
      source: params.source ?? 'manual',
      relation_type: params.relation_type,
      limit: params.limit ?? 100
    }
  })
}

/** 建议 maps_to / covers 边（可选 persist 写入 ai_suggested） */
export function suggestKgEdges(data) {
  return api.post('/kg/suggest-edges/', data)
}

/** 待确认 AI 建议边列表 */
export function getKgSuggestedEdges(params = {}) {
  return api.get('/kg/suggested-edges/', { params })
}

/** 持久化 AI 建议边 */
export function persistKgSuggestedEdges(data) {
  return api.post('/kg/suggested-edges/', data)
}

/** 确认 AI 建议边 */
export function confirmKgSuggestedEdges(edgeIds) {
  return api.post('/kg/suggested-edges/confirm/', { edge_ids: edgeIds })
}

/** 拒绝 AI 建议边 */
export function rejectKgSuggestedEdges(edgeIds) {
  return api.post('/kg/suggested-edges/reject/', { edge_ids: edgeIds })
}

/** 层次3：AI 抽取文档功能点写入图谱 */
export function extractFunctionPoints(data) {
  return api.post('/kg/extract-function-points/', data, { timeout: 5 * 60 * 1000 })
}

/** 层次3：跨文档功能点语义匹配 */
export function crossDocRelations(data) {
  return api.post('/kg/cross-doc-relations/', data, { timeout: 5 * 60 * 1000 })
}

/** 同步项目的业务需求(及需求文档)到图谱节点 */
export function syncKgRequirements(params = {}) {
  const data = {}
  if (params.projectId) data.project_id = params.projectId
  return api.post('/kg/sync-requirements/', data)
}

/** 同步项目的测试用例到图谱节点，并自动建立 covers 覆盖边 */
export function syncKgTestCases(params = {}) {
  const data = { auto_cover: params.autoCover ?? true }
  if (params.projectId) data.project_id = params.projectId
  return api.post('/kg/sync-testcases/', data)
}

/** 同步项目的 AI 生成任务到图谱节点(溯源边) */
export function syncKgGenerationTasks(params = {}) {
  const data = {}
  if (params.projectId) data.project_id = params.projectId
  return api.post('/kg/sync-generation-tasks/', data)
}

/** 同步自建知识中枢（NativeKb + NativeKbDocument）到图谱节点 */
export function syncKgNativeKbs(params = {}) {
  const data = {}
  if (params.projectId) data.project_id = params.projectId
  if (params.status) data.status = params.status
  return api.post('/kg/sync-native-kbs/', data)
}

/** 列出自建知识中枢（用于知识源下拉） */
export function listNativeKbs(params = {}) {
  return api.get('/requirement-analysis/kb-hub/native-kbs/', { params })
}

/** 为已同步的测试用例自动建立 covers 覆盖边 */
export function autoCoverKg(params = {}) {
  const data = {}
  if (params.projectId) data.project_id = params.projectId
  return api.post('/kg/auto-cover/', data)
}

/** 直接对项目的业务需求调 LLM 抽取功能点写入图谱（不依赖 Dify） */
export function extractFunctionPointsFromRequirements(params = {}) {
  const data = {}
  if (params.projectId) data.project_id = params.projectId
  return api.post('/kg/extract-function-points-from-requirements/', data, { timeout: 5 * 60 * 1000 })
}

/** 基于知识图谱的 AI 推荐执行 */
export function recommendExecution(params = {}) {
  return api.post('/kg/recommend-execution/', {
    project_id: params.projectId
  }, { timeout: 2 * 60 * 1000 })
}

/** 层次4：本地代码解析（tree-sitter），把目录代码结构入谱（零 LLM 成本） */
export function parseCode(data = {}) {
  return api.post('/kg/parse-code/', {
    path: data.path || '/app',
    project_id: data.projectId,
    max_files: data.maxFiles ?? 200
  })
}

/** 层次5：图聚类（Louvain 社区发现），community_id 写回实体 properties */
export function clusterKg(data = {}) {
  return api.post('/kg/cluster/', {
    project_id: data.projectId,
    resolution: data.resolution ?? 1.0
  })
}

/** 导出图谱（export_format: json/mermaid/svg/html） */
export function exportKgGraphFormatted(params = {}) {
  return api.get('/kg/export/', {
    params: {
      project_id: params.projectId,
      max_nodes: params.maxNodes ?? 5000,
      max_edges: params.maxEdges ?? 10000,
      export_format: params.format ?? 'json'
    },
    responseType: params.format && params.format !== 'json' ? 'blob' : 'json'
  })
}
