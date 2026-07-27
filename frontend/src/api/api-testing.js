import request from '@/utils/api'

// 仪表盘相关API
export function getDashboardStats() {
  return request({
    url: '/api-testing/dashboard/stats/',
    method: 'get'
  })
}

// 获取定时任务列表
export function getScheduledTasks(params) {
  return request({
    url: '/api-testing/scheduled-tasks/',
    method: 'get',
    params
  })
}

// 创建定时任务
export function createScheduledTask(data) {
  return request({
    url: '/api-testing/scheduled-tasks/',
    method: 'post',
    data
  })
}

// 更新定时任务
export function updateScheduledTask(id, data) {
  return request({
    url: `/api-testing/scheduled-tasks/${id}/`,
    method: 'patch',
    data
  })
}

// 删除定时任务
export function deleteScheduledTask(id) {
  return request({
    url: `/api-testing/scheduled-tasks/${id}/`,
    method: 'delete'
  })
}

// 立即执行定时任务
export function runScheduledTask(id) {
  return request({
    url: `/api-testing/scheduled-tasks/${id}/run_now/`,
    method: 'post'
  })
}

// 获取执行日志
export function getExecutionLogs(taskId, params = {}) {
  return request({
    url: `/api-testing/scheduled-tasks/${taskId}/execution_logs/`,
    method: 'get',
    params
  })
}

// 获取测试套件列表
export function getTestSuites(params) {
  return request({
    url: '/api-testing/test-suites/',
    method: 'get',
    params
  })
}

// 获取API请求列表
export function getApiRequests(params) {
  return request({
    url: '/api-testing/requests/',
    method: 'get',
    params
  })
}

// 获取单个API请求详情
export function getApiRequest(id) {
  return request({
    url: `/api-testing/requests/${id}/`,
    method: 'get'
  })
}

// 创建API请求（脚本）
export function createApiRequest(data) {
  return request({
    url: '/api-testing/requests/',
    method: 'post',
    data
  })
}

// 更新API请求（脚本）
export function updateApiRequest(id, data) {
  return request({
    url: `/api-testing/requests/${id}/`,
    method: 'patch',
    data
  })
}

// 删除API请求（脚本）
export function deleteApiRequest(id) {
  return request({
    url: `/api-testing/requests/${id}/`,
    method: 'delete'
  })
}

// 管理脚本关联的项目（多对多复用）
export function manageApiRequestProjects(id, data) {
  return request({
    url: `/api-testing/requests/${id}/projects/`,
    method: 'post',
    data
  })
}

// 创建API集合（目录）
export function createApiCollection(data) {
  return request({
    url: '/api-testing/collections/',
    method: 'post',
    data
  })
}

// 更新API集合（重命名/改父级/改项目）
export function updateApiCollection(id, data) {
  return request({
    url: `/api-testing/collections/${id}/`,
    method: 'patch',
    data
  })
}

// 删除API集合（注意：后端会级联删除子集合与请求，请先确认）
export function deleteApiCollection(id) {
  return request({
    url: `/api-testing/collections/${id}/`,
    method: 'delete'
  })
}

// 获取环境列表
export function getEnvironments(params) {
  return request({
    url: '/api-testing/environments/',
    method: 'get',
    params
  })
}

// 获取项目列表
export function getApiProjects(params) {
  return request({
    url: '/api-testing/projects/',
    method: 'get',
    params
  })
}

// 获取集合列表
export function getApiCollections(params) {
  return request({
    url: '/api-testing/collections/',
    method: 'get',
    params
  })
}

// 执行测试套件
export function executeTestSuite(id, data) {
  return request({
    url: `/api-testing/test-suites/${id}/execute/`,
    method: 'post',
    data
  })
}

// 执行API请求
export function executeApiRequest(id, data) {
  return request({
    url: `/api-testing/api-requests/${id}/execute/`,
    method: 'post',
    data
  })
}

// 获取执行结果
export function getExecutionResult(id) {
  return request({
    url: `/api-testing/executions/${id}/`,
    method: 'get'
  })
}

// 获取请求历史
export function getRequestHistory(params) {
  return request({
    url: '/api-testing/histories/',
    method: 'get',
    params
  })
}

// 删除请求历史
export function deleteRequestHistory(id) {
  return request({
    url: `/api-testing/histories/${id}/`,
    method: 'delete'
  })
}

// 批量删除请求历史
export function batchDeleteRequestHistory(ids) {
  return request({
    url: '/api-testing/histories/batch-delete/',
    method: 'post',
    data: { ids }
  })
}

// 获取用户列表
export function getUsers(params) {
  return request({
    url: '/api-testing/users/',
    method: 'get',
    params
  })
}
// 获取操作日志
export function getOperationLogs(params) {
  return request({
    url: '/api-testing/operation-logs/',
    method: 'get',
    params
  })
}
