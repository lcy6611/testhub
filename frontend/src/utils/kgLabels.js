/** 知识图谱关系类型 → 中文标签 */
export const KG_REL_LABELS = {
  belongs_to: '归属',
  derived_from: '来源于',
  used_reference: '引用参考',
  provenance: '溯源',
  covers: '覆盖',
  maps_to: '映射',
  references: '参考文档',
  depends_on: '依赖',
  related: '相关',
  impacts: '影响',
  automates: '自动化',
  contains: '包含',
  similar_to: '相似',
}

/** 知识图谱实体类型 → 中文标签 */
export const KG_TYPE_LABELS = {
  Project: '项目',
  RequirementDocument: '需求文档',
  TestCaseGenerationTask: '生成任务',
  TestCase: '测试用例',
  KbFunction: '功能模块',
  KbDocument: 'KB 文档',
  KbDataset: '知识库',
  BusinessRequirement: '业务需求',
  KbChatSession: 'KB 对话',
  ApiRequest: 'API 接口',
  UiPageObject: 'UI 页面',
  FunctionPoint: '功能点',
}

export function getKgRelationLabel(relationType) {
  return KG_REL_LABELS[relationType] || relationType
}

export function getKgEntityTypeLabel(entityType) {
  return KG_TYPE_LABELS[entityType] || entityType || '—'
}

/** 从 kb_context_meta 提取图谱扩展提示文案 */
export function formatGraphExpansionHint(kbContextMeta) {
  const meta = kbContextMeta || {}
  const parts = []
  if (meta.graph_summary) parts.push(String(meta.graph_summary))
  const exp = meta.graph_expansion || {}
  const fnCount = (exp.added_function_ids || []).length
  const docCount = (exp.added_document_ids || []).length
  if (fnCount > 0) parts.push(`扩展 ${fnCount} 个关联功能模块`)
  if (docCount > 0) parts.push(`扩展 ${docCount} 份参考文档`)
  if (meta.graph_prompt_summary_chars > 0) {
    parts.push(`已注入图谱摘要 ${meta.graph_prompt_summary_chars} 字`)
  }
  return parts.join('；')
}
