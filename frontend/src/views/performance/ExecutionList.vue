<template>
  <div class="execution-list">
    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- 单次执行记录 -->
      <el-tab-pane label="单次执行记录" name="single">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>执行记录</span>
              <el-button @click="loadData">刷新</el-button>
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
                <el-button size="small" type="primary" @click="goDetail(row.id)">详情</el-button>
                <el-button v-if="row.status === 'RUNNING' || row.status === 'QUEUED'" size="small" type="warning" @click="handleCancel(row.id)">取消</el-button>
                <el-button v-if="row.has_report" size="small" @click="goReport(row.id)">报告</el-button>
                <el-button size="small" type="danger" @click="handleDeleteExecution(row.id)">删除</el-button>
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
      </el-tab-pane>

      <!-- 批量执行记录 -->
      <el-tab-pane label="批量执行记录" name="batch">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>批量执行记录</span>
              <div>
                <el-button type="primary" @click="openBatchDialog">按项目执行</el-button>
                <el-button @click="loadBatchData">刷新</el-button>
              </div>
            </div>
          </template>

          <el-table :data="batchExecutions" v-loading="batchLoading" stripe>
            <el-table-column prop="batch_id" label="批次ID" width="200" />
            <el-table-column prop="name" label="批次名称" min-width="160" />
            <el-table-column prop="project_name" label="项目" width="140">
              <template #default="{ row }">{{ row.project_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="batchStatusType(row.status)" size="small">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="进度" width="120" align="center">
              <template #default="{ row }">
                {{ row.completed_scripts }}/{{ row.total_scripts }}
                <span v-if="row.failed_scripts > 0" style="color: #f56c6c;">({{ row.failed_scripts }}失败)</span>
              </template>
            </el-table-column>
            <el-table-column prop="thread_count" label="线程数" width="80" align="center" />
            <el-table-column prop="duration" label="持续(s)" width="90" align="center" />
            <el-table-column prop="created_at" label="创建时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" @click="goBatchDetail(row.id)">详情</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-pagination
            v-model:current-page="batchPage"
            :page-size="20"
            :total="batchTotal"
            layout="total, prev, pager, next"
            @current-change="loadBatchData"
            style="margin-top: 16px; justify-content: flex-end;"
          />
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 按项目执行 Dialog -->
    <el-dialog v-model="batchDialogVisible" title="按项目执行性能测试" width="800px" :close-on-click-modal="false">
      <el-form :model="batchForm" label-width="100px">
        <el-form-item label="批次名称">
          <el-input v-model="batchForm.name" placeholder="留空则自动生成" />
        </el-form-item>
        <el-form-item label="选择项目">
          <el-select v-model="batchForm.project" placeholder="选择项目（可选，用于筛选脚本）" clearable filterable style="width: 100%" @change="onProjectChange">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择脚本">
          <el-table :data="availableScripts" v-loading="scriptLoading" max-height="300" @selection-change="onScriptSelect" ref="scriptTableRef">
            <el-table-column type="selection" width="50" />
            <el-table-column prop="name" label="脚本名称" min-width="160" />
            <el-table-column prop="project_name" label="所属项目" width="140">
              <template #default="{ row }">{{ row.project_name || '通用' }}</template>
            </el-table-column>
            <el-table-column prop="script_type_display" label="模式" width="100" />
            <el-table-column prop="thread_count" label="默认线程" width="90" align="center" />
            <el-table-column prop="duration" label="默认持续(s)" width="100" align="center" />
          </el-table>
          <div v-if="availableScripts.length === 0 && !scriptLoading" style="text-align: center; padding: 20px; color: #909399;">
            {{ batchForm.project ? '该项目下暂无脚本' : '请先选择项目，或选择"通用"查看无项目关联的脚本' }}
          </div>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="线程数">
              <el-input-number v-model="batchForm.thread_count" :min="1" :max="1000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Ramp-Up(s)">
              <el-input-number v-model="batchForm.ramp_up" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="持续(s)">
              <el-input-number v-model="batchForm.duration" :min="1" :max="7200" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="实时报告">
          <el-switch v-model="batchForm.realtime_enabled" />
          <span style="margin-left: 8px; color: #909399; font-size: 12px;">需先在配置页启用 InfluxDB</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchCreating" :disabled="selectedScripts.length === 0" @click="handleCreateBatch">
          执行 ({{ selectedScripts.length }} 个脚本)
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getExecutions, cancelExecution, deleteExecution,
  getBatchExecutions, createBatchExecution,
  getScripts, getProjects,
} from '@/api/performance'

const router = useRouter()
const activeTab = ref('single')

// ===== 单次执行 =====
const executions = ref([])
const loading = ref(false)
const searchExecId = ref('')
const filterStatus = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

// ===== 批量执行 =====
const batchExecutions = ref([])
const batchLoading = ref(false)
const batchPage = ref(1)
const batchTotal = ref(0)

// ===== 批量执行 Dialog =====
const batchDialogVisible = ref(false)
const batchCreating = ref(false)
const projectList = ref([])
const availableScripts = ref([])
const scriptLoading = ref(false)
const selectedScripts = ref([])
const scriptTableRef = ref(null)
const batchForm = ref({
  name: '',
  project: null,
  thread_count: 10,
  ramp_up: 5,
  duration: 60,
  realtime_enabled: false,
})

const formatTime = (val) => val ? new Date(val).toLocaleString('zh-CN', { hour12: false }) : ''

const statusType = (s) => ({
  QUEUED: 'info', RUNNING: 'warning', COMPLETED: 'success', FAILED: 'danger', CANCELLED: 'info',
}[s] || 'info')

const batchStatusType = (s) => ({
  QUEUED: 'info', RUNNING: 'warning', COMPLETED: 'success', FAILED: 'danger', PARTIAL: 'warning',
}[s] || 'info')

// ===== 数据加载 =====
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

const loadBatchData = async () => {
  batchLoading.value = true
  try {
    const res = await getBatchExecutions({ page: batchPage.value, page_size: 20 })
    batchExecutions.value = res.data?.results || []
    batchTotal.value = res.data?.count || 0
  } catch (e) {
    ElMessage.error('加载批量执行列表失败')
  } finally {
    batchLoading.value = false
  }
}

const onTabChange = (tab) => {
  if (tab === 'batch' && batchExecutions.value.length === 0) {
    loadBatchData()
  }
}

// ===== 导航 =====
const goDetail = (id) => router.push(`/performance-testing/executions/${id}`)
const goReport = (id) => router.push(`/performance-testing/executions/${id}?tab=report`)
const goBatchDetail = (id) => router.push(`/performance-testing/batch-executions/${id}`)

const handleCancel = async (id) => {
  try {
    await cancelExecution(id)
    ElMessage.success('已标记取消')
    loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '取消失败')
  }
}

const handleDeleteExecution = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该执行记录吗？关联的报告与介质文件也会一并删除，且不可恢复。', '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteExecution(id)
    ElMessage.success('执行记录已删除')
    loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

// ===== 批量执行 Dialog =====
const openBatchDialog = async () => {
  batchDialogVisible.value = true
  batchForm.value = {
    name: '',
    project: null,
    thread_count: 10,
    ramp_up: 5,
    duration: 60,
    realtime_enabled: false,
  }
  selectedScripts.value = []
  availableScripts.value = []

  // 加载项目列表
  try {
    const res = await getProjects({ page_size: 999 })
    projectList.value = res.data?.results || res.data || []
  } catch (e) {
    console.error('加载项目失败', e)
  }

  // 加载所有脚本
  await loadScripts()
}

const loadScripts = async () => {
  scriptLoading.value = true
  try {
    const params = { page_size: 999 }
    if (batchForm.value.project) {
      params.project = batchForm.value.project
    }
    const res = await getScripts(params)
    availableScripts.value = res.data?.results || res.data || []
  } catch (e) {
    ElMessage.error('加载脚本失败')
  } finally {
    scriptLoading.value = false
  }
}

const onProjectChange = () => {
  loadScripts()
}

const onScriptSelect = (selection) => {
  selectedScripts.value = selection
}

const handleCreateBatch = async () => {
  if (selectedScripts.value.length === 0) {
    ElMessage.warning('请至少选择一个脚本')
    return
  }
  batchCreating.value = true
  try {
    const data = {
      script_ids: selectedScripts.value.map(s => s.id),
      name: batchForm.value.name || undefined,
      project: batchForm.value.project || undefined,
      thread_count: batchForm.value.thread_count,
      ramp_up: batchForm.value.ramp_up,
      duration: batchForm.value.duration,
      realtime_enabled: batchForm.value.realtime_enabled,
    }
    const res = await createBatchExecution(data)
    ElMessage.success(`批量执行已创建，包含 ${data.script_ids.length} 个脚本`)
    batchDialogVisible.value = false
    activeTab.value = 'batch'
    loadBatchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建批量执行失败')
  } finally {
    batchCreating.value = false
  }
}

onMounted(() => {
  loadData()
  // 自动轮询（有执行中的任务时每5秒刷新）
  pollTimer = setInterval(() => {
    if (executions.value.some(e => e.status === 'QUEUED' || e.status === 'RUNNING')) {
      loadData()
    }
    if (activeTab.value === 'batch' && batchExecutions.value.some(b => b.status === 'QUEUED' || b.status === 'RUNNING')) {
      loadBatchData()
    }
  }, 5000)
})

let pollTimer = null
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; }
</style>
