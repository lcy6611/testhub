import request from '@/utils/api'

const BASE = '/requirement-analysis/kb-hub'

// ==================== 知识中枢配置 ====================

export function getKbHubConfig() {
  return request({ url: `${BASE}/config/`, method: 'get' })
}

export function updateKbHubConfig(data) {
  return request({ url: `${BASE}/config/`, method: 'patch', data })
}

export function switchEngine(engine) {
  return request({ url: `${BASE}/config/switch-engine/`, method: 'post', data: { engine } })
}

export function testRetrieval(query, kbId) {
  return request({ url: `${BASE}/config/test-retrieval/`, method: 'post', data: { query, kb_id: kbId } })
}

export function getKbHubKnowledgeBases(keyword = '') {
  return request({ url: `${BASE}/config/knowledge-bases/`, method: 'get', params: { keyword } })
}

// ==================== 自建知识库 ====================

export function getNativeKbs(params) {
  return request({ url: `${BASE}/native-kbs/`, method: 'get', params })
}

export function createNativeKb(data) {
  return request({ url: `${BASE}/native-kbs/`, method: 'post', data })
}

export function updateNativeKb(id, data) {
  return request({ url: `${BASE}/native-kbs/${id}/`, method: 'patch', data })
}

export function deleteNativeKb(id) {
  return request({ url: `${BASE}/native-kbs/${id}/`, method: 'delete' })
}

export function publishNativeKb(id) {
  return request({ url: `${BASE}/native-kbs/${id}/publish/`, method: 'post' })
}

export function unpublishNativeKb(id) {
  return request({ url: `${BASE}/native-kbs/${id}/unpublish/`, method: 'post' })
}

export function getNativeKbDocuments(kbId) {
  return request({ url: `${BASE}/native-kbs/${kbId}/documents/`, method: 'get' })
}

export function getNativeKbAllDocuments(params = {}) {
  return request({ url: `${BASE}/native-docs/all/`, method: 'get', params })
}

// ==================== 文档管理 ====================

export function uploadNativeDoc(formData) {
  return request({ url: `${BASE}/native-docs/`, method: 'post', data: formData, headers: { 'Content-Type': 'multipart/form-data' } })
}

export function updateNativeDoc(id, data) {
  return request({ url: `${BASE}/native-docs/${id}/`, method: 'patch', data })
}

export function deleteNativeDoc(id) {
  return request({ url: `${BASE}/native-docs/${id}/`, method: 'delete' })
}

export function ingestNativeDoc(id) {
  return request({ url: `${BASE}/native-docs/${id}/ingest/`, method: 'post' })
}

export function reindexNativeDoc(id) {
  return request({ url: `${BASE}/native-docs/${id}/reindex/`, method: 'post' })
}

export function clearNativeDocChunks(id) {
  return request({ url: `${BASE}/native-docs/${id}/chunks/`, method: 'delete' })
}

// ==================== Dify 配置列表（引擎切换下拉用） ====================

export function getDifyConfigs() {
  return request({ url: '/assistant/config/dify/', method: 'get' })
}

// ==================== 外部知识源（飞书等） ====================

export function getKbSources(params) {
  return request({ url: `${BASE}/kb-sources/`, method: 'get', params })
}

export function createKbSource(data) {
  return request({ url: `${BASE}/kb-sources/`, method: 'post', data })
}

export function deleteKbSource(id) {
  return request({ url: `${BASE}/kb-sources/${id}/`, method: 'delete' })
}

export function syncKbSource(id) {
  // 同步可能拉取大量文档，放宽超时到 5 分钟
  return request({ url: `${BASE}/kb-sources/${id}/sync/`, method: 'post', timeout: 300000 })
}

// ==================== 项目-Dify 知识库绑定 ====================

export function getDifyBindings(project, params = {}) {
  return request({ url: `${BASE}/dify-kb-bindings/`, method: 'get', params: { project, ...params } })
}

export function bindDifyKb(data) {
  return request({ url: `${BASE}/dify-kb-bindings/`, method: 'post', data })
}

export function unbindDifyKb(id) {
  return request({ url: `${BASE}/dify-kb-bindings/${id}/`, method: 'delete' })
}

export function getDifyAvailableDatasets(project, keyword = '') {
  return request({
    url: `${BASE}/dify-kb-bindings/available-datasets/`,
    method: 'get',
    params: { project, keyword },
  })
}

// ==================== 项目级 KB 自动判定（AI 用例生成用） ====================

export function getProjectKbs(projectId) {
  return request({
    url: `${BASE}/config/project-kbs/`,
    method: 'get',
    params: { project_id: projectId },
  })
}

export function getKbHubOverview() {
  return request({
    url: `${BASE}/config/overview/`,
    method: 'get',
  })
}

// ==================== KB 知识图谱（自动生成） ====================

export function getKbGraph(kbId, params = {}) {
  return request({
    url: `/kg/kb-graph/`,
    method: 'get',
    params: { kb_id: kbId, ...params },
  })
}

export function syncAllNativeKbsToKg() {
  return request({ url: `/kg/sync-native-kbs/`, method: 'post' })
}
