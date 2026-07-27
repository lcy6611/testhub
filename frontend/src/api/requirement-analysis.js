/**
 * 需求分析 / AI 用例生成模块相关 API（与上游 URL 风格一致：/requirement-analysis/xxx）
 */
import request from '@/utils/api'

export function getGenerationConfigs(params) {
  return request({
    url: '/requirement-analysis/generation-config/',
    method: 'get',
    params
  })
}

export function getGenerationConfigDetail(id) {
  return request({
    url: `/requirement-analysis/generation-config/${id}/`,
    method: 'get'
  })
}

export function createGenerationConfig(data) {
  return request({
    url: '/requirement-analysis/generation-config/',
    method: 'post',
    data
  })
}

export function updateGenerationConfig(id, data) {
  return request({
    url: `/requirement-analysis/generation-config/${id}/`,
    method: 'put',
    data
  })
}

export function deleteGenerationConfig(id) {
  return request({
    url: `/requirement-analysis/generation-config/${id}/`,
    method: 'delete'
  })
}

export function getActiveGenerationConfig() {
  return request({
    url: '/requirement-analysis/generation-config/active/',
    method: 'get'
  })
}

export function getDifyKnowledgeBases(params) {
  return request({
    url: '/requirement-analysis/dify-knowledge-bases/',
    method: 'get',
    params
  })
}

export function getDifyKnowledgeBaseDocuments(params) {
  return request({
    url: '/requirement-analysis/dify-knowledge-bases/documents/',
    method: 'get',
    params
  })
}

export function previewKbReference(data) {
  return request({
    url: '/requirement-analysis/dify-knowledge-bases/preview-reference/',
    method: 'post',
    data
  })
}

export function getKbFunctions(params) {
  return request({
    url: '/requirement-analysis/kb-functions/',
    method: 'get',
    params
  })
}

export function createKbFunction(data) {
  return request({
    url: '/requirement-analysis/kb-functions/',
    method: 'post',
    data
  })
}

export function updateKbFunction(id, data) {
  return request({
    url: `/requirement-analysis/kb-functions/${id}/`,
    method: 'put',
    data
  })
}

export function deleteKbFunction(id) {
  return request({
    url: `/requirement-analysis/kb-functions/${id}/`,
    method: 'delete'
  })
}

/** 结构化业务需求列表（需求分析产出） */
export function getBusinessRequirements(params = {}) {
  return request({
    url: '/requirement-analysis/requirements/',
    method: 'get',
    params: {
      page_size: params.page_size ?? 500,
      ...params
    }
  })
}

// ==================== Skill 技能包 ====================

export function getSkills(params = {}) {
  return request({
    url: '/requirement-analysis/skills/',
    method: 'get',
    params
  })
}

export function uploadSkillTemplate(id, file) {
  const fd = new FormData()
  fd.append('file', file)
  return request({
    url: `/requirement-analysis/skills/${id}/upload-template/`,
    method: 'post',
    data: fd,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function deleteSkillTemplate(id) {
  return request({
    url: `/requirement-analysis/skills/${id}/delete-template/`,
    method: 'post'
  })
}

export function exportSkillPackage(id) {
  return request({
    url: `/requirement-analysis/skills/${id}/export-package/`,
    method: 'get',
    responseType: 'blob'
  })
}

export function importSkillPackage(file) {
  const fd = new FormData()
  fd.append('file', file)
  return request({
    url: `/requirement-analysis/skills/import-package/`,
    method: 'post',
    data: fd,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function addSkillArtifact(skillId, data, file) {
  const fd = new FormData()
  fd.append('path', data.path)
  fd.append('artifact_type', data.artifact_type)
  if (data.text_content !== undefined && data.text_content !== null) {
    fd.append('text_content', data.text_content)
  }
  if (file) {
    fd.append('file', file)
  }
  return request({
    url: `/requirement-analysis/skills/${skillId}/add-artifact/`,
    method: 'post',
    data: fd,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function removeSkillArtifact(skillId, payload) {
  return request({
    url: `/requirement-analysis/skills/${skillId}/remove-artifact/`,
    method: 'post',
    data: payload
  })
}

// ==================== 生成任务 / 多格式导出 ====================

export function exportTaskResult(taskId, format = 'excel') {
  return request({
    url: `/requirement-analysis/testcase-generation/${taskId}/export/`,
    method: 'get',
    params: { format },
    responseType: 'blob'
  })
}

// ==================== 通用 Skill 执行 ====================

export function runSkill(skillId, inputText, extra = {}) {
  return request({
    url: `/requirement-analysis/skills/run/`,
    method: 'post',
    data: { skill_id: skillId, input_text: inputText, ...extra },
    timeout: 120000,
  })
}

export function saveSkillCase(data) {
  return request({
    url: `/requirement-analysis/skills/save/`,
    method: 'post',
    data
  })
}
