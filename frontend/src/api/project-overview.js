import request from '@/utils/api'

const BASE = '/kg'

/**
 * 项目概览聚合数据：按 project_id 返回 8 大维度统计
 * 后端端点：GET /api/kg/project-overview/?project_id=X
 * @param {number|string} projectId
 */
export function getProjectOverview(projectId) {
  return request({
    url: `${BASE}/project-overview/`,
    method: 'get',
    params: { project_id: projectId },
  })
}

/** response 拦截器返回完整 axios response，调用方需取 .data */
export function unwrap(res) { return res?.data || res }