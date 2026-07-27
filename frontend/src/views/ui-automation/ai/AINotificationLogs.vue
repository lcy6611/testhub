<template>
  <div class="notification-logs-container">
    <div class="page-actions">
      <el-row :gutter="20" class="filter-row">
        <el-col :span="6">
          <el-input
            v-model="searchForm.taskName"
            placeholder="搜索任务名称"
            clearable
            @clear="handleSearch"
            @keyup.enter="handleSearch"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-col>
        <el-col :span="6">
          <el-date-picker
            v-model="searchForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            @change="handleSearch"
          />
        </el-col>
        <el-col :span="6">
          <el-select v-model="searchForm.status" placeholder="通知状态" clearable @change="handleSearch">
            <el-option label="全部状态" value="" />
            <el-option label="发送成功" value="success" />
            <el-option label="发送失败" value="failed" />
            <el-option label="待发送" value="pending" />
            <el-option label="发送中" value="sending" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="handleSearch"><el-icon><Search /></el-icon> 搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-col>
      </el-row>
    </div>

    <div class="logs-table-container">
      <el-table :data="logs" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="task_name" label="任务名称" min-width="150" show-overflow-tooltip />
        <el-table-column prop="task_type_display" label="任务类型" min-width="120">
          <template #default="{ row }">
            <el-tag type="info" size="small">{{ row.task_type_display || '未记录' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="actual_notification_type_display" label="通知类型" min-width="140">
          <template #default="{ row }">
            <el-tag
              :type="getNotificationTypeTagType(row.actual_notification_type_display)"
              :style="getNotificationTypeTagStyle(row.actual_notification_type_display)"
              effect="light"
              size="small"
            >
              {{ row.actual_notification_type_display || row.notification_type_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="通知时间" min-width="180">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" min-width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status_display)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="120">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadLogs"
          @current-change="loadLogs"
        />
      </div>
    </div>

    <!-- 详情弹窗：与 UI 自动化通知详情样式一致 -->
    <el-dialog
      v-model="showDetailDialog"
      title="通知详情"
      width="600px"
      :before-close="handleDetailClose"
    >
      <el-form v-if="selectedLog" label-position="top" class="notification-detail-form">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="任务名称">
              <span>{{ selectedLog.task_name }}</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="任务类型">
              <span>{{ selectedLog.task_type_display || '未记录' }}</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="通知类型">
              <el-tag
                :type="getNotificationTypeTagType(selectedLog.actual_notification_type_display)"
                :style="getNotificationTypeTagStyle(selectedLog.actual_notification_type_display)"
                effect="light"
              >
                {{ selectedLog.actual_notification_type_display || selectedLog.notification_type_display }}
              </el-tag>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-tag :type="getStatusTagType(selectedLog.status_display)">
                {{ selectedLog.status_display }}
              </el-tag>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="通知时间">
              <span>{{ formatDate(selectedLog.created_at) }}</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发送时间">
              <span>{{ formatDate(selectedLog.sent_at || selectedLog.created_at) }}</span>
            </el-form-item>
          </el-col>
          <el-col :span="24" v-if="selectedLog.webhook_bot_info && (selectedLog.webhook_bot_info.bot_type || selectedLog.webhook_bot_info.type || selectedLog.webhook_bot_info.name)">
            <el-form-item label="Webhook机器人">
              <div class="webhook-info">
                <el-tag class="webhook-tag" size="small" type="info">
                  {{ formatWebhookBotLabel(selectedLog.webhook_bot_info) }}
                </el-tag>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="通知内容">
              <div class="notification-content">
                <div v-if="parsedNotificationContent && parsedNotificationContent.length" class="notification-content-parsed">
                  <div v-for="(item, index) in parsedNotificationContent" :key="index" class="content-item">
                    <span class="content-label">{{ item.label }}:</span>
                    <span class="content-value">{{ item.value }}</span>
                  </div>
                </div>
                <div v-else class="notification-content-raw">
                  <pre>{{ selectedLog.notification_content || '-' }}</pre>
                </div>
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="24" v-if="selectedLog.error_message">
            <el-form-item label="错误信息">
              <div class="error-message">
                <el-alert :title="selectedLog.error_message" type="error" show-icon :closable="false" />
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showDetailDialog = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { getAINotificationLogs, getAINotificationLogDetail } from '@/api/ui_automation'

const logs = ref([])
const loading = ref(false)
const total = ref(0)
const searchForm = reactive({
  taskName: '',
  dateRange: [],
  status: ''
})
const pagination = reactive({ currentPage: 1, pageSize: 10 })
const showDetailDialog = ref(false)
const selectedLog = ref(null)

function getStatusTagType(status) {
  const map = { '发送成功': 'success', success: 'success', '发送失败': 'danger', failed: 'danger', '待发送': 'info', pending: 'info', '发送中': 'warning', sending: 'warning', '已取消': 'info', cancelled: 'info' }
  return map[status] || 'info'
}

function getNotificationTypeTagType(display) {
  if (!display) return 'info'
  if (display.includes('邮箱')) return 'info'
  if (display.includes('飞书')) return 'primary'
  if (display.includes('企微')) return 'success'
  if (display.includes('钉钉')) return 'warning'
  return 'info'
}

function getNotificationTypeTagStyle(display) {
  if (!display || !display.includes('邮箱')) return {}
  return { backgroundColor: '#FFF7E6', borderColor: '#FFE4B3', color: '#B88200' }
}

function formatWebhookBotLabel(bot) {
  if (!bot) return 'Webhook机器人'
  const t = bot.type || bot.bot_type || ''
  const name = bot.name || bot.bot_name || ''
  const map = { wechat: '企微机器人', feishu: '飞书机器人', dingtalk: '钉钉机器人' }
  const label = map[t] || 'Webhook机器人'
  return name ? `${label}（${name}）` : label
}

function formatDate(val) {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN')
}

const parsedNotificationContent = computed(() => {
  if (!selectedLog.value || !selectedLog.value.notification_content) return null
  const content = selectedLog.value.notification_content
  try {
    const json = JSON.parse(content)
    let text = ''
    if (json.msgtype === 'markdown' && json.markdown) {
      text = json.markdown.text || json.markdown.content || ''
    } else if (json.msg_type === 'interactive' && json.card && json.card.elements && json.card.elements[0] && json.card.elements[0].text) {
      text = json.card.elements[0].text.content || ''
    }
    if (text) {
      const result = []
      text.split('\n').filter(l => l.trim()).forEach(line => {
        if (line.includes('**') || !line.trim()) return
        const idx = line.indexOf(':')
        if (idx > 0) {
          const label = line.substring(0, idx).trim()
          const value = line.substring(idx + 1).trim()
          if (label && value) result.push({ label, value })
        }
      })
      return result.length ? result : null
    }
  } catch (_) {}
  try {
    const result = []
    content.split('\n').filter(l => l.trim()).forEach(line => {
      const idx = line.indexOf(':')
      if (idx > 0) {
        const label = line.substring(0, idx).trim()
        const value = line.substring(idx + 1).trim()
        if (label && value && !value.includes("'results':") && !value.includes('"results":')) result.push({ label, value })
      }
    })
    return result.length ? result : null
  } catch (_) {}
  return null
})

async function loadLogs() {
  loading.value = true
  try {
    const params = { page: pagination.currentPage, page_size: pagination.pageSize }
    if (searchForm.taskName) params.search = searchForm.taskName
    if (searchForm.dateRange && searchForm.dateRange.length === 2) {
      params.start_date = searchForm.dateRange[0]
      params.end_date = searchForm.dateRange[1]
    }
    if (searchForm.status) params.status = searchForm.status
    const res = await getAINotificationLogs(params)
    logs.value = res.data.results || res.data || []
    total.value = res.data.count ?? logs.value.length
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.currentPage = 1
  loadLogs()
}

function handleReset() {
  searchForm.taskName = ''
  searchForm.dateRange = []
  searchForm.status = ''
  pagination.currentPage = 1
  loadLogs()
}

function handleDetailClose(done) {
  selectedLog.value = null
  done()
}

async function viewDetail(row) {
  try {
    const res = await getAINotificationLogDetail(row.id)
    selectedLog.value = res.data
    showDetailDialog.value = true
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => loadLogs())
</script>

<style scoped>
.notification-logs-container {
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}
.page-actions { margin-bottom: 20px; padding: 20px; background: #f8f9fa; border-radius: 6px; }
.filter-row { display: flex; align-items: center; gap: 15px; }
.logs-table-container { margin-top: 20px; }
.pagination-container { margin-top: 20px; display: flex; justify-content: flex-end; }

.notification-detail-form :deep(.el-form-item) {
  margin-bottom: 18px;
}
.notification-content {
  width: 100%;
}
.notification-content-parsed {
  background: #ffffff;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.content-item {
  display: flex;
  align-items: flex-start;
  padding: 12px 0;
  border-bottom: 1px solid #f0f2f5;
}
.content-item:last-child { border-bottom: none; padding-bottom: 0; }
.content-item:first-child { padding-top: 0; }
.content-label {
  font-weight: 600;
  color: #606266;
  min-width: 100px;
  flex-shrink: 0;
  margin-right: 16px;
  font-size: 14px;
  line-height: 1.8;
}
.content-value {
  color: #303133;
  flex: 1;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.8;
}
.notification-content-raw pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
  max-height: 400px;
  overflow-y: auto;
}
.notification-content-raw pre::-webkit-scrollbar { width: 6px; height: 6px; }
.notification-content-raw pre::-webkit-scrollbar-thumb { background: #c0c4cc; border-radius: 3px; }
.notification-content-raw pre::-webkit-scrollbar-thumb:hover { background: #a8abb2; }
.webhook-info { display: flex; flex-wrap: wrap; gap: 8px; }
.webhook-tag { margin: 0; }
.error-message { margin-top: 8px; }
.dialog-footer { display: flex; justify-content: flex-end; gap: 10px; }
</style>
