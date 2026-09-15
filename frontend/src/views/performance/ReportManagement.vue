<template>
  <div class="perf-report-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>报告管理</span>
        </div>
      </template>

      <el-table :data="reports" v-loading="loading" stripe border>
        <el-table-column prop="execution_id" label="执行ID" width="180" />
        <el-table-column prop="script_name" label="脚本" min-width="160" />
        <el-table-column prop="status_display" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="thread_count" label="线程数" width="90" align="center" />
        <el-table-column prop="duration" label="持续(s)" width="100" align="center" />
        <el-table-column prop="created_at" label="生成时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" :disabled="!row.has_report" @click="viewReport(row.id)">HTML报告</el-button>
            <el-button size="small" :disabled="!row.has_jtl" @click="handleDownloadJtl(row.id)">JTL</el-button>
            <el-button size="small" type="danger" @click="handleDeleteReport(row.id)">删除</el-button>
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

    <el-dialog v-model="reportVisible" title="HTML 报告" width="90%" top="5vh">
      <iframe v-if="reportHtml" :srcdoc="reportHtml" class="report-iframe" frameborder="0" />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getReports, getExecutionReport, deleteExecution } from '@/api/performance'

const reports = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const reportVisible = ref(false)
const reportHtml = ref('')

const formatTime = (val) => val ? new Date(val).toLocaleString('zh-CN', { hour12: false }) : '-'
const statusType = (s) => ({ QUEUED: 'info', RUNNING: 'warning', COMPLETED: 'success', FAILED: 'danger', CANCELLED: 'info' }[s] || 'info')

async function loadData() {
  loading.value = true
  try {
    const res = await getReports({ page: page.value, page_size: pageSize.value })
    reports.value = res.data?.results || res.data || []
    total.value = res.data?.count || reports.value.length
  } catch (e) {
    ElMessage.error('加载报告失败')
  } finally {
    loading.value = false
  }
}

async function viewReport(id) {
  try {
    const res = await getExecutionReport(id)
    reportHtml.value = res.data?.html || '<p>报告内容为空</p>'
    reportVisible.value = true
  } catch (e) {
    ElMessage.error('加载报告失败')
  }
}

// 大文件（JTL 十几 MB）走浏览器原生下载 + ?token= 认证，避免 axios 超时 / 大 Blob 失败
function handleDownloadJtl(id) {
  const token = localStorage.getItem('access_token') || ''
  const a = document.createElement('a')
  a.href = `/api/performance-testing/executions/${id}/jtl_download/?token=${encodeURIComponent(token)}`
  a.download = `${id}.jtl`
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

async function handleDeleteReport(id) {
  try {
    await ElMessageBox.confirm('确定删除该报告吗？其对应的执行记录与介质文件也会一并删除，且不可恢复。', '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteExecution(id)
    ElMessage.success('报告已删除')
    loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.report-iframe { width: 100%; height: 70vh; border: none; }
</style>
