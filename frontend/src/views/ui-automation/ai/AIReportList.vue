<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">测试报告</h1>
      <div class="actions">
        <el-select
          v-model="selectedProject"
          placeholder="选择项目"
          style="width: 220px; margin-right: 12px"
          clearable
          @change="refresh"
        >
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button type="primary" @click="refresh">
          <el-icon><Refresh /></el-icon>
          刷新报告
        </el-button>
      </div>
    </div>

    <div class="card-container">
      <el-empty v-if="!loading && reports.length === 0" description="暂无测试报告，请先执行套件或用例" />
      <el-table v-else :data="reports" v-loading="loading" style="width: 100%">
        <!-- 使用行号作为列表ID展示，避免套件运行ID(UUID)看起来异常 -->
        <el-table-column type="index" label="ID" width="80" />
        <el-table-column prop="suiteName" label="套件/任务名称" min-width="220" show-overflow-tooltip />
        <el-table-column prop="caseTotal" label="用例数" width="90" align="center" />
        <el-table-column prop="passed" label="通过数" width="90" align="center">
          <template #default="{ row }">
            <span style="color:#67c23a;font-weight:bold">{{ row.passed }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="failed" label="失败数" width="90" align="center">
          <template #default="{ row }">
            <span style="color:#f56c6c;font-weight:bold">{{ row.failed }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="executionMode" label="执行模式" width="110" align="center">
          <template #default="{ row }">
            {{ formatMode(row.executionMode) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="总耗时(秒)" width="120" align="center">
          <template #default="{ row }">{{ row.duration != null && row.duration !== '' ? Number(row.duration).toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间" width="180">
          <template #default="{ row }">{{ formatDate(null,null,row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="executed_by" label="执行者" width="120">
          <template #default="{ row }">{{ row.executedByName || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openSuiteReport(row)">
              <el-icon><Document /></el-icon>
              查看报告
            </el-button>
            <el-button link type="danger" size="small" @click="deleteSuiteReport(row)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="refresh"
          @current-change="refresh"
        />
      </div>
    </div>

    <!-- 套件级报告详情 -->
    <el-dialog v-model="showDetailDialog" title="AI 套件测试报告" width="80%" :close-on-click-modal="false">
      <div v-if="currentReport">
        <!-- 基本信息 -->
        <el-descriptions :column="2" border style="margin-bottom:16px">
          <el-descriptions-item label="报告ID">{{ currentReport.id }}</el-descriptions-item>
          <el-descriptions-item label="套件/任务">{{ currentReport.suiteName }}</el-descriptions-item>
          <el-descriptions-item label="执行状态">
            <el-tag :type="getStatusTag(currentReport.status)">{{ getStatusText(currentReport.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="执行模式">{{ formatMode(currentReport.executionMode) }}</el-descriptions-item>
          <el-descriptions-item label="用例总数">{{ currentReport.caseTotal }}</el-descriptions-item>
          <el-descriptions-item label="通过/失败">
            <span style="color:#67c23a;font-weight:bold">{{ currentReport.passed }}</span>
            /
            <span style="color:#f56c6c;font-weight:bold">{{ currentReport.failed }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="总耗时(秒)">{{ currentReport.duration ? currentReport.duration.toFixed(2) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="开始时间">{{ formatDate(null,null,currentReport.started_at) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 测试统计卡片，对齐 UI 自动化测试报告 -->
        <div class="statistics-section">
          <el-row :gutter="20">
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-label">总执行数</div>
                <div class="stat-value">{{ currentReport.caseTotal }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card success">
                <div class="stat-label">通过数</div>
                <div class="stat-value">{{ currentReport.passed }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card danger">
                <div class="stat-label">失败数</div>
                <div class="stat-value">{{ currentReport.failed }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card warning">
                <div class="stat-label">跳过数</div>
                <div class="stat-value">{{ currentReport.skipped }}</div>
              </div>
            </el-col>
          </el-row>

          <div class="pass-rate-wrapper">
            <span class="pass-rate-text">通过率: {{ currentReport.passRate }}%</span>
            <el-progress :percentage="currentReport.passRate" :color="getProgressColor(currentReport.passRate)" :stroke-width="18" />
          </div>
        </div>

        <h4 style="margin:16px 0 8px">用例执行明细</h4>
        <el-table :data="currentReport.executions || []" border>
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="case_name" label="用例名称" min-width="200" show-overflow-tooltip />
          <el-table-column prop="execution_mode" label="执行模式" width="110">
            <template #default="{ row }">{{ formatMode(row.execution_mode) }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="getStatusTag(row.status)">{{ getStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="duration" label="耗时(秒)" width="120">
            <template #default="{ row }">{{ row.duration ? row.duration.toFixed(2) : '-' }}</template>
          </el-table-column>
          <el-table-column prop="start_time" label="开始时间" width="180">
            <template #default="{ row }">{{ formatDate(null,null,row.start_time) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="openCaseReport(row)">查看详情</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="showDetailDialog = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 单条用例执行的详细报告（沿用 AIExecutionReport） -->
    <AIExecutionReport v-model="showReportDialog" :record-id="currentExecutionId" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Document, Delete } from '@element-plus/icons-vue'
import { getUiProjects, getAIExecutionRecordReportSummary, batchDeleteAIExecutionRecords } from '@/api/ui_automation'
import AIExecutionReport from './AIExecutionReport.vue'

const projects = ref([])
const selectedProject = ref(null)
const rawRecords = ref([])
const reports = ref([])
const loading = ref(false)
const total = ref(0)
const pagination = reactive({ currentPage: 1, pageSize: 20 })

const showReportDialog = ref(false)
const currentExecutionId = ref(null)
const showDetailDialog = ref(false)
const currentReport = ref(null)

function getStatusTag(status) {
  const map = { passed: 'success', failed: 'danger', running: 'warning', pending: 'info', stopped: 'info' }
  return map[status] || 'info'
}
function getStatusText(status) {
  const map = { passed: '成功', failed: '失败', running: '执行中', pending: '等待中', stopped: '已停止' }
  return map[status] || status
}
function formatDate(row, col, val) {
  if (!val) return '-'
  return new Date(val).toLocaleString('zh-CN')
}
function formatMode(mode) {
  if (mode === 'vision') return '视觉模型'
  if (mode === 'text') return '文本模型'
  if (mode === 'auto') return '自动'
  return mode || '-'
}

function getProgressColor(rate) {
  if (rate >= 80) return '#67c23a'
  if (rate >= 50) return '#e6a23c'
  if (rate > 0) return '#f56c6c'
  return '#909399'
}

// 将 report_summary 接口返回的 snake_case 转为前端使用的格式
function mapReportRow(row) {
  return {
    id: row.id,
    suiteId: row.suite_run_id ? null : row.id,
    suiteName: row.suite_name,
    caseTotal: row.case_total,
    passed: row.passed,
    failed: row.failed,
    skipped: row.skipped ?? Math.max(0, (row.case_total || 0) - (row.passed || 0) - (row.failed || 0)),
    passRate: row.pass_rate ?? 0,
    status: row.status,
    executionMode: row.execution_mode,
    duration: row.duration,
    started_at: row.started_at,
    executedByName: row.executed_by_name,
    executions: row.executions || [],
    execution_ids: row.execution_ids || [],
  }
}

async function loadProjects() {
  try {
    const res = await getUiProjects({ page_size: 500 })
    projects.value = res.data.results || res.data || []
  } catch (e) {
    console.error(e)
  }
}

async function refresh() {
  loading.value = true
  try {
    const params = { page: pagination.currentPage, page_size: pagination.pageSize }
    if (selectedProject.value) params.project = selectedProject.value
    const res = await getAIExecutionRecordReportSummary(params)
    const list = res.data.results || res.data || []
    reports.value = list.map(mapReportRow)
    total.value = res.data.count ?? reports.value.length
  } catch (e) {
    console.error(e)
    const msg = e.response?.data?.detail || e.response?.data?.error || '加载报告失败'
    ElMessage.error(typeof msg === 'string' ? msg : '加载报告失败')
  } finally {
    loading.value = false
  }
}

function openSuiteReport(row) {
  currentReport.value = row
  showDetailDialog.value = true
}

function openCaseReport(exec) {
  currentExecutionId.value = exec.id
  showReportDialog.value = true
}

async function deleteSuiteReport(row) {
  try {
    const ids = row.execution_ids?.length ? row.execution_ids : (row.executions || []).map(e => e.id)
    await ElMessageBox.confirm(`确定要删除此套件报告下的 ${ids.length} 条执行记录吗？此操作不可恢复。`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await batchDeleteAIExecutionRecords(ids)
    ElMessage.success('删除成功')
    refresh()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error('删除失败')
    }
  }
}

onMounted(async () => {
  await loadProjects()
  await refresh()
})
</script>

<style scoped>
.page-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { margin: 0; font-size: 24px; }
.card-container { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.pagination-container { margin-top: 16px; display: flex; justify-content: flex-end; }
.actions { display: flex; align-items: center; }

.statistics-section {
  margin-bottom: 20px;
}
.stat-card {
  background: #f5f7fa;
  border-radius: 6px;
  padding: 14px 18px;
  text-align: center;
}
.stat-card .stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}
.stat-card .stat-value {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}
.stat-card.success {
  background: #f0f9eb;
}
.stat-card.danger {
  background: #fef0f0;
}
.stat-card.warning {
  background: #fdf6ec;
}
.pass-rate-wrapper {
  margin-top: 16px;
}
.pass-rate-text {
  display: inline-block;
  margin-bottom: 6px;
  font-size: 14px;
  color: #606266;
}
</style>

