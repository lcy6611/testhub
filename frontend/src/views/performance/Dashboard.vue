<template>
  <div class="perf-dashboard-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据看板 — 执行记录</span>
          <div class="header-actions">
            <el-button @click="loadData">
              <el-icon><Refresh /></el-icon>刷新
            </el-button>
            <el-button type="primary" @click="$router.push('/performance-testing/scripts')">新建执行</el-button>
          </div>
        </div>
      </template>

      <div class="filter-bar">
        <el-input v-model="searchExecId" placeholder="执行ID" clearable style="width: 200px" @keyup.enter="loadData" />
        <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 140px" @change="loadData">
          <el-option label="排队中" value="QUEUED" />
          <el-option label="执行中" value="RUNNING" />
          <el-option label="已完成" value="COMPLETED" />
          <el-option label="失败" value="FAILED" />
          <el-option label="已取消" value="CANCELLED" />
        </el-select>
        <el-button @click="loadData">搜索</el-button>
      </div>

      <el-table :data="executions" v-loading="loading" stripe>
        <el-table-column prop="execution_id" label="执行ID" width="180" />
        <el-table-column prop="script_name" label="脚本" min-width="160" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="thread_count" label="线程数" width="80" align="center" />
        <el-table-column prop="duration" label="持续(s)" width="90" align="center" />
        <el-table-column label="实时" width="70" align="center">
          <template #default="{ row }">
            <el-tag :type="row.realtime_enabled ? 'success' : 'info'" size="small">{{ row.realtime_enabled ? '开' : '关' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="170">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="completed_at" label="完成时间" width="170">
          <template #default="{ row }">{{ formatTime(row.completed_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="goDashboard(row.id)">数据面板</el-button>
            <el-button size="small" @click="goDetail(row.id)">执行详情</el-button>
            <el-button size="small" type="danger" plain @click="openReportDefect(row)">提 BUG</el-button>
            <el-button v-if="row.status === 'RUNNING' || row.status === 'QUEUED'" size="small" type="warning" @click="handleCancel(row.id)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { getExecutions, cancelExecution } from '@/api/performance'

const openReportDefect = (row) => {
  // 性能测试"提 BUG"：携带执行上下文跳到问题管理页，用户选项目后保存（避免无 project 必填）
  const title = `[性能测试] ${row.script_name || row.execution_id} 异常`
  const desc = `执行ID：${row.execution_id}\n脚本：${row.script_name || ''}\n线程：${row.thread_count || 0}\n持续：${row.duration || 0}s\n状态：${row.status_display || row.status}\n开始：${row.started_at || '-'}\n完成：${row.completed_at || '-'}`
  router.push({
    path: '/defects',
    query: {
      preset_title: title,
      preset_description: desc,
      preset_source: 'performance',
      preset_severity: 'S2'
    }
  })
}

const router = useRouter()
const executions = ref([])
const loading = ref(false)
const searchExecId = ref('')
const filterStatus = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
let pollTimer = null

const formatTime = (val) => val ? new Date(val).toLocaleString('zh-CN', { hour12: false }) : ''

const statusType = (s) => ({
  QUEUED: 'info', RUNNING: 'warning', COMPLETED: 'success', FAILED: 'danger', CANCELLED: 'info',
}[s] || 'info')

const loadData = async () => {
  loading.value = true
  try {
    const res = await getExecutions({ search: searchExecId.value, status: filterStatus.value, page: page.value, page_size: pageSize.value })
    executions.value = res.data?.results || res.data || []
    total.value = res.data?.count || executions.value.length
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const goDashboard = (id) => router.push(`/performance-testing/dashboard/${id}`)
const goDetail = (id) => router.push(`/performance-testing/executions/${id}`)

const handleCancel = async (id) => {
  try {
    await cancelExecution(id)
    ElMessage.success('已标记取消')
    loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '取消失败')
  }
}

onMounted(() => {
  loadData()
  // 自动轮询（有执行中的任务时每5秒刷新）
  pollTimer = setInterval(() => {
    if (executions.value.some(e => e.status === 'QUEUED' || e.status === 'RUNNING')) {
      loadData()
    }
  }, 5000)
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.perf-dashboard-list {
  padding: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>