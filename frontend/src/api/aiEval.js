import request from '@/utils/api'

const BASE = '/ai-eval'

// 提示词版本
export function getPromptVersions(params) {
  return request.get(`${BASE}/prompt-versions/`, { params })
}
export function createPromptVersion(data) {
  return request.post(`${BASE}/prompt-versions/`, data)
}
export function activatePromptVersion(id) {
  return request.post(`${BASE}/prompt-versions/${id}/activate/`)
}

// 成本/调用日志
export function getCallLogs(params) {
  return request.get(`${BASE}/call-logs/`, { params })
}

// 评测数据集
export function getDatasets(params) {
  return request.get(`${BASE}/datasets/`, { params })
}
export function createDataset(data) {
  return request.post(`${BASE}/datasets/`, data)
}

// 评测用例
export function getCases(params) {
  return request.get(`${BASE}/cases/`, { params })
}
export function createCase(data) {
  return request.post(`${BASE}/cases/`, data)
}
export function deleteCase(id) {
  return request.delete(`${BASE}/cases/${id}/`)
}

// 评测运行
export function getRuns(params) {
  return request.get(`${BASE}/runs/`, { params })
}
export function createRun(data) {
  return request.post(`${BASE}/runs/`, data)
}
export function getRunResults(runId) {
  return request.get(`${BASE}/runs/${runId}/results/`)
}
export function rerunRun(id) {
  return request.post(`${BASE}/runs/${id}/rerun/`)
}

// 反馈
export function getFeedbacks(params) {
  return request.get(`${BASE}/feedbacks/`, { params })
}
export function createFeedback(data) {
  return request.post(`${BASE}/feedbacks/`, data)
}
export function convertFeedback(id, data) {
  return request.post(`${BASE}/feedbacks/${id}/convert_to_case/`, data)
}

// 效果看板
export function getEvalStats(params) {
  return request.get(`${BASE}/stats/`, { params })
}
