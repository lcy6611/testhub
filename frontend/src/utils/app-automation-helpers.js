// APP 自动化通用工具函数

// 执行状态 -> Element Plus Tag 类型
export function getExecutionStatusType(status) {
  if (!status) return 'info'
  const map = {
    pending: 'warning',
    running: 'warning',
    completed: 'success',
    success: 'success',
    failed: 'danger',
    error: 'danger',
    stopped: 'info',
    not_run: 'info'
  }
  return map[status] || 'info'
}

// 执行状态 -> 文本
export function getExecutionStatusText(status) {
  if (!status) return '未知'
  const map = {
    pending: '等待中',
    running: '执行中',
    completed: '已完成',
    success: '通过',
    failed: '失败',
    error: '执行异常',
    stopped: '已停止',
    not_run: '未执行'
  }
  return map[status] || status
}

// 组合 status + result，用于列表里的展示 Tag
export function getDisplayStatus(status, result) {
  // 先按 result 判断
  if (result === 'passed') return { type: 'success', text: '通过' }
  if (result === 'failed') return { type: 'danger', text: '失败' }
  if (result === 'skipped') return { type: 'warning', text: '跳过' }

  // 向后兼容只看 status 的场景
  if (status === 'not_run') return { type: 'info', text: '未执行' }
  if (status === 'pending') return { type: 'warning', text: '等待中' }
  if (status === 'running') return { type: 'warning', text: '执行中' }
  if (status === 'completed' || status === 'success') return { type: 'success', text: '已完成' }
  if (status === 'failed') return { type: 'danger', text: '失败' }
  if (status === 'error') return { type: 'danger', text: '执行异常' }
  if (status === 'stopped') return { type: 'info', text: '已停止' }

  return { type: 'info', text: status || '未知' }
}

// 设备状态 -> Element Plus Tag 类型
export function getDeviceStatusType(status) {
  if (!status) return 'info'
  const map = {
    online: 'success',
    available: 'success',
    locked: 'warning',
    offline: 'danger'
  }
  return map[status] || 'info'
}

// 设备状态 -> 文本
export function getDeviceStatusText(status) {
  if (!status) return '未知'
  const map = {
    online: '在线',
    available: '可用',
    locked: '已锁定',
    offline: '离线'
  }
  return map[status] || status
}

// 统一的日期时间格式化
export function formatDateTime(dateTime) {
  if (!dateTime) return '-'
  const d = new Date(dateTime)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 相对时间（用于“最近执行”之类）
export function formatRelativeTime(dateTime) {
  if (!dateTime) return '-'
  const d = new Date(dateTime)
  if (Number.isNaN(d.getTime())) return '-'
  const diff = Date.now() - d.getTime()

  const sec = Math.floor(diff / 1000)
  if (sec < 60) return `${sec}秒前`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}分钟前`
  const hour = Math.floor(min / 60)
  if (hour < 24) return `${hour}小时前`
  const day = Math.floor(hour / 24)
  if (day < 7) return `${day}天前`

  // 超过一周直接返回日期
  return d.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

