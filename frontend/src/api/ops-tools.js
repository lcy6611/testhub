import request from '@/utils/api'

export function getEnvironments(params) {
  return request.get('/ops-tools/environments/', { params })
}

export function createEnvironment(data) {
  return request.post('/ops-tools/environments/', data)
}

export function updateEnvironment(id, data) {
  return request.put(`/ops-tools/environments/${id}/`, data)
}

export function deleteEnvironment(id) {
  return request.delete(`/ops-tools/environments/${id}/`)
}

export function connectEnvironment(id) {
  return request.post(`/ops-tools/environments/${id}/connect/`)
}

export function getEnvironmentDatabases(id) {
  return request.get(`/ops-tools/environments/${id}/databases/`)
}

export function getText2SQLRecords(params) {
  return request.get('/ops-tools/text2sql/', { params })
}

export function createText2SQLRecord(data) {
  return request.post('/ops-tools/text2sql/', data)
}

// Text2SQL 三个动作都可能要等 LLM/DB 较长耗时，60s 兜底
const LONG_TIMEOUT = 60 * 1000

export function generateSQL(id, data) {
  return request.post(`/ops-tools/text2sql/${id}/generate/`, data, { timeout: LONG_TIMEOUT })
}

export function validateSQL(id, data) {
  return request.post(`/ops-tools/text2sql/${id}/validate/`, data, { timeout: LONG_TIMEOUT })
}

export function executeSQL(id, data) {
  return request.post(`/ops-tools/text2sql/${id}/execute/`, data, { timeout: LONG_TIMEOUT })
}

export function listLogDirs(data) {
  return request.post('/ops-tools/logs/list-dirs/', data)
}

export function readLog(data) {
  return request.post('/ops-tools/logs/read/', data)
}

export function getFileTransfers(params) {
  return request.get('/ops-tools/files/', { params })
}

export function uploadFile(data) {
  return request.post('/ops-tools/files/upload/', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function downloadFile(id) {
  return request.get(`/ops-tools/files/${id}/download/`, { responseType: 'blob' })
}
