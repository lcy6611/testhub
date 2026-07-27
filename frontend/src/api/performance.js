import request from '@/utils/api'

// ==================== 项目列表（通用） ====================

export function getProjects(params) {
  return request({ url: '/projects/', method: 'get', params })
}

// ==================== 性能测试看板 ====================

export function getDashboard(params) {
  const query = {}
  if (typeof params === 'string' || typeof params === 'number') {
    query.execution_id = params
  } else if (params && typeof params === 'object') {
    if (params.execution_id) query.execution_id = params.execution_id
    if (params.id) query.id = params.id
  }
  return request({
    url: '/performance-testing/dashboard/',
    method: 'get',
    params: query
  })
}

// ==================== 脚本管理 ====================

export function getScripts(params) {
  return request({ url: '/performance-testing/scripts/', method: 'get', params })
}

export function getScript(id) {
  return request({ url: `/performance-testing/scripts/${id}/`, method: 'get' })
}

export function createScript(data) {
  return request({ url: '/performance-testing/scripts/', method: 'post', data })
}

export function updateScript(id, data) {
  return request({ url: `/performance-testing/scripts/${id}/`, method: 'patch', data })
}

export function deleteScript(id) {
  return request({ url: `/performance-testing/scripts/${id}/`, method: 'delete' })
}

export function executeScript(id, data) {
  return request({ url: `/performance-testing/scripts/${id}/execute/`, method: 'post', data })
}

export function getScriptExecutions(id, params) {
  return request({ url: `/performance-testing/scripts/${id}/executions/`, method: 'get', params })
}

export function checkJmx(id) {
  return request({ url: `/performance-testing/scripts/${id}/check_jmx/`, method: 'post' })
}

export function parseJmxToOnline(id) {
  return request({ url: `/performance-testing/scripts/${id}/parse-to-online/`, method: 'post' })
}

export function exportJmx(id) {
  return request({ url: `/performance-testing/scripts/${id}/export_jmx/`, method: 'get', responseType: 'blob' })
}

export function importJmx(data) {
  return request({ url: '/performance-testing/scripts/import_jmx/', method: 'post', data })
}

export function getLoadLimits() {
  return request({ url: '/performance-testing/scripts/load_limits/', method: 'get' })
}

export function uploadScriptCsvFiles(id, data) {
  return request({ url: `/performance-testing/scripts/${id}/upload-csv/`, method: 'post', data, headers: { 'Content-Type': 'multipart/form-data' } })
}

export function getScriptCsvFiles(id) {
  return request({ url: `/performance-testing/scripts/${id}/csv-files/`, method: 'get' })
}

export function deleteScriptCsvFile(id, data) {
  return request({ url: `/performance-testing/scripts/${id}/delete-csv/`, method: 'post', data })
}

// ==================== API 用例转压测 ====================

export function convertFromApi(data) {
  return request({ url: '/performance-testing/scripts/convert-from-api/', method: 'post', data })
}

// ==================== 执行记录 ====================

export function getExecutions(params) {
  return request({ url: '/performance-testing/executions/', method: 'get', params })
}

export function getExecution(id) {
  return request({ url: `/performance-testing/executions/${id}/`, method: 'get' })
}

export function cancelExecution(id) {
  return request({ url: `/performance-testing/executions/${id}/cancel/`, method: 'post' })
}

export function deleteExecution(id) {
  return request({ url: `/performance-testing/executions/${id}/`, method: 'delete' })
}

export function getExecutionSummary(id) {
  return request({ url: `/performance-testing/executions/${id}/summary/`, method: 'get' })
}

export function getExecutionMetrics(id) {
  return request({ url: `/performance-testing/executions/${id}/metrics/`, method: 'get' })
}

export function getRealtimeData(id, window = 60) {
  return request({ url: `/performance-testing/executions/${id}/realtime/`, method: 'get', params: { window } })
}

export function downloadJtl(id) {
  return request({ url: `/performance-testing/executions/${id}/jtl_download/`, method: 'get', responseType: 'blob' })
}

export function downloadJmx(id) {
  return request({ url: `/performance-testing/executions/${id}/jmx_download/`, method: 'get', responseType: 'blob' })
}

export function getExecutionReport(id) {
  // 返回 {html, size, execution_id} JSON；html 是完整 HTML 字符串
  return request({ url: `/performance-testing/executions/${id}/report/`, method: 'get' })
}

export function getExecutionMonitoring(id) {
  return request({ url: `/performance-testing/executions/${id}/monitoring/`, method: 'get' })
}

export function regenerateExecutionReport(id) {
  return request({ url: `/performance-testing/executions/${id}/regenerate_report/`, method: 'post' })
}

// ==================== 报告管理 ====================

export function getReports(params) {
  return request({ url: '/performance-testing/reports/', method: 'get', params })
}

export function getReport(id) {
  return request({ url: `/performance-testing/reports/${id}/`, method: 'get' })
}

// ==================== 定时任务 ====================

export function getScheduledTasks(params) {
  return request({ url: '/performance-testing/scheduled-tasks/', method: 'get', params })
}

export function createScheduledTask(data) {
  return request({ url: '/performance-testing/scheduled-tasks/', method: 'post', data })
}

export function updateScheduledTask(id, data) {
  return request({ url: `/performance-testing/scheduled-tasks/${id}/`, method: 'patch', data })
}

export function deleteScheduledTask(id) {
  return request({ url: `/performance-testing/scheduled-tasks/${id}/`, method: 'delete' })
}

// ==================== 性能测试配置 ====================

export function getPerformanceConfig() {
  return request({ url: '/performance-testing/config/', method: 'get' })
}

export function updatePerformanceConfig(data) {
  const id = data.id || 1
  return request({ url: `/performance-testing/config/${id}/`, method: 'patch', data })
}

export function testInfluxdbConnection(data) {
  return request({ url: '/performance-testing/config/test-influxdb/', method: 'post', data })
}

export function testPrometheusConnection(data) {
  return request({ url: '/performance-testing/config/test-prometheus/', method: 'post', data })
}

// ==================== 批量执行（按项目执行） ====================

export function getBatchExecutions(params) {
  return request({ url: '/performance-testing/batch-executions/', method: 'get', params })
}

export function getBatchExecution(id) {
  return request({ url: `/performance-testing/batch-executions/${id}/`, method: 'get' })
}

export function createBatchExecution(data) {
  return request({ url: '/performance-testing/batch-executions/', method: 'post', data })
}

export function getBatchSummary(id) {
  return request({ url: `/performance-testing/batch-executions/${id}/summary/`, method: 'get' })
}
