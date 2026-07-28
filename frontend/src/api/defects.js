import request from '@/utils/api'

// 缺陷
export function getDefects(params) {
  return request.get('/defects/defects/', { params })
}
export function getDefect(id) {
  return request.get(`/defects/defects/${id}/`)
}
export function createDefect(data) {
  return request.post('/defects/defects/', data)
}
export function updateDefect(id, data) {
  return request.put(`/defects/defects/${id}/`, data)
}
export function patchDefect(id, data) {
  return request.patch(`/defects/defects/${id}/`, data)
}
export function deleteDefect(id) {
  return request.delete(`/defects/defects/${id}/`)
}

// 缺陷附件
export function uploadDefectAttachment(defectId, formData) {
  return request.post(`/defects/defects/${defectId}/attachments/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
export function deleteDefectAttachment(defectId, attId) {
  return request.delete(`/defects/defects/${defectId}/attachments/${attId}/`)
}

// 需求三层覆盖率
export function getRequirementCoverage(params) {
  return request.get('/defects/requirement-coverage/', { params })
}

// 质量门禁（GET 评估 / POST 保存发布结论）
export function getQualityGate(params) {
  return request.get('/defects/quality-gate/', { params })
}
export function saveQualityGate(data) {
  return request.post('/defects/quality-gate/', data)
}

// 发布结论记录
export function getReleaseConclusions(params) {
  return request.get('/defects/release-conclusions/', { params })
}
