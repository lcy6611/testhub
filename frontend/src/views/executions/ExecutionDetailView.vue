<template>
  <div class="execution-detail">
    <!-- 美化的页面头部 -->
    <div class="page-header-card">
      <div class="header-content">
        <div class="title-section">
          <h1 class="page-title">{{ testPlan.name }}</h1>
          <el-tag v-if="testPlan.version" type="primary" size="large" class="version-tag">
            <el-icon><Stamp /></el-icon>
            {{ testPlan.version }}
          </el-tag>
        </div>
        
        <!-- 项目信息 -->
        <div class="project-info">
          <el-icon class="info-icon"><FolderOpened /></el-icon>
          <span v-if="testPlan.projects && testPlan.projects.length > 0">
            {{ testPlan.projects.join(', ') }}
          </span>
          <span v-else class="no-data">未关联项目</span>
        </div>
      </div>
    </div>

    <!-- 测试执行区域 -->
    <div v-if="testPlan.test_runs && testPlan.test_runs.length > 0">
      <div v-for="run in testPlan.test_runs" :key="run.id" class="test-run-card">
        <!-- 美化的运行头部 -->
        <div class="run-header">
          <div class="run-title-section">
            <h2 class="run-title">{{ run.name }}</h2>
            <el-tag :type="getRunStatusType(run.progress)" size="large" class="run-status-tag">
              {{ getRunStatusText(run.progress) }}
            </el-tag>
          </div>
          
          <!-- 美化的统计卡片 -->
          <div class="stats-cards">
            <div class="stat-card total">
              <el-icon class="stat-icon"><Document /></el-icon>
              <div class="stat-content">
                <div class="stat-value">{{ run.progress.total }}</div>
                <div class="stat-label">总计</div>
              </div>
            </div>
            <div class="stat-card passed">
              <el-icon class="stat-icon"><CircleCheck /></el-icon>
              <div class="stat-content">
                <div class="stat-value">{{ run.progress.passed }}</div>
                <div class="stat-label">通过</div>
              </div>
            </div>
            <div class="stat-card failed">
              <el-icon class="stat-icon"><CircleClose /></el-icon>
              <div class="stat-content">
                <div class="stat-value">{{ run.progress.failed }}</div>
                <div class="stat-label">失败</div>
              </div>
            </div>
            <div class="stat-card blocked">
              <el-icon class="stat-icon"><WarningFilled /></el-icon>
              <div class="stat-content">
                <div class="stat-value">{{ run.progress.blocked }}</div>
                <div class="stat-label">阻塞</div>
              </div>
            </div>
            <div class="stat-card untested">
              <el-icon class="stat-icon"><QuestionFilled /></el-icon>
              <div class="stat-content">
                <div class="stat-value">{{ run.progress.untested }}</div>
                <div class="stat-label">未测</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 进度条 -->
        <div class="progress-section">
          <el-progress 
            :percentage="run.progress.progress" 
            :stroke-width="12"
            :color="getProgressColor(run.progress.progress)"
            :show-text="true">
            <template #default="{ percentage }">
              <span class="progress-text">{{ percentage }}%</span>
            </template>
          </el-progress>
        </div>

        <!-- 批量操作按钮 -->
        <div v-if="selectedCases.length > 0" class="batch-actions">
          <el-button 
            type="danger" 
            :icon="Delete"
            @click="batchDeleteCases"
            :disabled="isDeleting">
            批量删除 ({{ selectedCases.length }})
          </el-button>
        </div>
        
        <!-- 优化的用例表格（支持步骤折叠） -->
        <el-table
          ref="tableRef"
          :data="paginatedCases(run.run_cases)"
          style="width: 100%"
          class="execution-table"
          @selection-change="handleSelectionChange"
          @expand-change="(row, expandedRows) => handleExpandChange(row, expandedRows, run.id)"
          :row-key="(row) => row.id"
          :expand-row-keys="run.expandedRowKeys || []">
          <el-table-column type="expand">
            <template #default="{ row: caseRow }">
              <div class="case-steps-panel">
                <div class="case-steps-header">
                  <span class="case-steps-title">
                    <el-icon><List /></el-icon>
                    步骤执行（联动至用例状态）
                  </span>
                  <el-tag v-if="caseRow._stepsLoaded" size="small" type="info">
                    {{ (caseRow.step_records || []).length }} 步
                  </el-tag>
                  <el-button
                    v-if="caseRow._stepsLoaded && (!caseRow.step_records || !caseRow.step_records.length)"
                    size="small"
                    type="primary"
                    plain
                    @click="initCaseSteps(caseRow, run.id)"
                  >
                    同步步骤
                  </el-button>
                </div>
                <div v-if="caseRow._stepsLoading" class="loading-text">同步步骤中…</div>
                <el-table
                  v-else-if="caseRow._stepsLoaded && caseRow.step_records && caseRow.step_records.length"
                  :data="caseRow.step_records"
                  size="small"
                  :show-overflow-tooltip="true"
                  class="steps-table"
                >
                  <el-table-column prop="step_number" label="#" width="55" />
                  <el-table-column label="操作" min-width="280">
                    <template #default="{ row: step }">
                      <span class="step-action">{{ step.action }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="预期" min-width="200" show-overflow-tooltip>
                    <template #default="{ row: step }">
                      <span class="step-expected">{{ step.expected }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="实际结果" min-width="180">
                    <template #default="{ row: step }">
                      <el-input
                        v-model="step.actual_result"
                        size="small"
                        placeholder="实际结果"
                        @blur="updateStep(caseRow, step, run.id)"
                      />
                    </template>
                  </el-table-column>
                  <el-table-column label="步骤状态" width="160">
                    <template #default="{ row: step }">
                      <el-select
                        v-model="step.status"
                        size="small"
                        @change="updateStep(caseRow, step, run.id)"
                        style="width: 100%"
                      >
                        <el-option label="未测试" value="untested" />
                        <el-option label="通过" value="passed" />
                        <el-option label="失败" value="failed" />
                        <el-option label="阻塞" value="blocked" />
                        <el-option label="重测" value="retest" />
                      </el-select>
                    </template>
                  </el-table-column>
                </el-table>
                <div v-else-if="caseRow._stepsLoaded" class="case-steps-empty">
                  <el-empty description="该用例暂无步骤，请在 TestCase 中补充" :image-size="60" />
                </div>
                <div v-else class="case-steps-empty">
                  <el-empty description="展开后将自动同步步骤" :image-size="60" />
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column type="selection" width="55" :reserve-selection="true" />
          <el-table-column
            type="index"
            label="序号"
            width="70"
            :index="getSerialNumber" />
          <el-table-column label="测试用例" min-width="280">
            <template #default="scope">
              <div class="case-title-cell">
                <el-popover
                  placement="top-start"
                  trigger="hover"
                  :width="320"
                  :show-after="200"
                  popper-class="case-preview-popover">
                  <template #reference>
                    <el-link type="primary" :underline="false" @click="scope.row._expanded = !scope.row._expanded; handleExpandChange(scope.row, [], null)">
                      {{ scope.row.testcase }}
                    </el-link>
                  </template>
                  <div class="case-preview">
                    <div class="case-preview__title">{{ scope.row.testcase }}</div>
                    <div class="case-preview__row">
                      <span class="case-preview__label">状态</span>
                      <el-tag :type="getStatusType(scope.row.status)" size="small">{{ getStatusText(scope.row.status) }}</el-tag>
                    </div>
                    <div class="case-preview__row">
                      <span class="case-preview__label">步骤</span>
                      <span>{{ (scope.row.step_records || []).length }} 步</span>
                    </div>
                    <div class="case-preview__row case-preview__row--remark">
                      <span class="case-preview__label">备注</span>
                      <span class="case-preview__remark">{{ scope.row.comments || '—' }}</span>
                    </div>
                  </div>
                </el-popover>
                <el-tag v-if="scope.row.step_records && scope.row.step_records.length" size="small" type="info">
                  {{ scope.row.step_records.length }} 步
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="执行状态" width="150">
            <template #default="scope">
              <el-select
                v-model="scope.row.status"
                @change="updateCaseStatus(scope.row)"
                size="small">
                <el-option label="未测试" value="untested" />
                <el-option label="通过" value="passed" />
                <el-option label="失败" value="failed" />
                <el-option label="阻塞" value="blocked" />
                <el-option label="重测" value="retest" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="250">
            <template #default="scope">
              <el-input
                v-model="scope.row.comments"
                placeholder="请输入备注"
                type="textarea"
                :rows="2"
                size="small"
                @blur="updateCaseDetails(scope.row)">
              </el-input>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="scope">
              <el-button
                size="small"
                type="primary"
                :icon="Clock"
                @click="viewCaseHistory(scope.row)">
                历史
              </el-button>
              <el-button
                size="small"
                :icon="View"
                @click="openCaseDrawer(scope.row)">
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页组件 -->
        <div v-if="run.run_cases && run.run_cases.length > 0" class="pagination-container">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="run.run_cases.length"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
            @size-change="handleSizeChange">
          </el-pagination>
        </div>
      </div>
    </div>

    <!-- 历史记录对话框 -->
    <el-dialog 
      title="执行历史记录" 
      v-model="historyDialogVisible" 
      width="80%">
      <el-table :data="currentCaseHistory" style="width: 100%">
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="comments" label="备注" show-overflow-tooltip />
        <el-table-column prop="executed_by.username" label="执行者" width="120" />
        <el-table-column prop="executed_at" label="执行时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.executed_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 用例执行详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      title="用例执行详情"
      direction="rtl"
      size="46%"
      :destroy-on-close="true">
      <template v-if="drawerCase">
        <el-descriptions :column="1" border class="drawer-desc">
          <el-descriptions-item label="测试用例">{{ drawerCase.testcase }}</el-descriptions-item>
          <el-descriptions-item label="执行状态">
            <el-tag :type="getStatusType(drawerCase.status)">{{ getStatusText(drawerCase.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="备注">{{ drawerCase.comments || '—' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="drawer-subtitle">执行步骤</h4>
        <el-table :data="drawerCase.step_records || []" size="small" border>
          <el-table-column prop="step_number" label="#" width="55" />
          <el-table-column prop="action" label="操作" min-width="280" show-overflow-tooltip />
          <el-table-column prop="expected" label="预期" min-width="200" show-overflow-tooltip />
          <el-table-column prop="actual_result" label="实际结果" min-width="180" show-overflow-tooltip />
          <el-table-column label="状态" width="100">
            <template #default="s">
              <el-tag :type="getStatusType(s.row.status)" size="small">{{ getStatusText(s.row.status) }}</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <h4 class="drawer-subtitle">执行历史</h4>
        <el-table :data="drawerHistory" size="small" border>
          <el-table-column label="状态" width="100">
            <template #default="s">
              <el-tag :type="getStatusType(s.row.status)">{{ getStatusText(s.row.status) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="comments" label="备注" show-overflow-tooltip />
          <el-table-column prop="executed_by.username" label="执行者" width="120" />
          <el-table-column label="执行时间" width="180">
            <template #default="s">{{ formatDate(s.row.executed_at) }}</template>
          </el-table-column>
        </el-table>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Delete, Clock, Document, CircleCheck, CircleClose,
  WarningFilled, QuestionFilled, Stamp, FolderOpened, List, View
} from '@element-plus/icons-vue'
import api from '@/utils/api'

const route = useRoute()
const testPlan = ref({})
const historyDialogVisible = ref(false)
const currentCaseHistory = ref([])
const drawerVisible = ref(false)
const drawerCase = ref(null)
const drawerHistory = ref([])

// 打开用例详情抽屉：确保步骤已加载并拉取历史
const openCaseDrawer = async (runCase) => {
  drawerCase.value = runCase
  if (!runCase._stepsLoaded) {
    await loadCaseSteps(runCase)
  }
  try {
    const res = await api.get(`/executions/run_cases/${runCase.id}/history/`)
    drawerHistory.value = res.data || []
  } catch (e) {
    drawerHistory.value = []
  }
  drawerVisible.value = true
}
const selectedCases = ref([])
const currentPage = ref(1)
const pageSize = ref(10)
const isDeleting = ref(false)
const tableRef = ref(null)

const fetchTestPlan = async () => {
  try {
    const planId = route.params.id
    const response = await api.get(`/executions/plans/${planId}/`)
    testPlan.value = response.data
    // 默认展开每个 run 的第一行，并预加载其步骤，方便用户直观看到「折叠+步骤」能力
    if (testPlan.value.test_runs && testPlan.value.test_runs.length) {
      for (const run of testPlan.value.test_runs) {
        run.expandedRowKeys = []
        if (run.run_cases && run.run_cases.length) {
          const first = run.run_cases[0]
          first._expanded = true
          run.expandedRowKeys.push(first.id)
          // 预拉一次步骤（即便没有步骤，也只是空列表；展开会自动 init-steps 兜底）
          loadCaseSteps(first)
        }
      }
    }
  } catch (error) {
    ElMessage.error('获取测试计划失败')
  }
}

// 加载某 run_case 的步骤
const loadCaseSteps = async (runCase) => {
  try {
    const res = await api.get(`/executions/run_cases/${runCase.id}/steps/`)
    runCase.step_records = res.data || []
    runCase._stepsLoaded = true
  } catch (e) {
    ElMessage.error('加载步骤失败：' + (e.message || ''))
    runCase._stepsLoaded = true
  }
}

// 初始化某 run_case 的步骤（从 TestCase 复制）
const initCaseSteps = async (runCase, runId) => {
  runCase._stepsLoading = true
  try {
    await api.post(`/executions/run_cases/${runCase.id}/init-steps/`)
    await loadCaseSteps(runCase)
    ElMessage.success('步骤已同步')
  } catch (e) {
    ElMessage.error('初始化失败：' + (e.message || ''))
  } finally {
    runCase._stepsLoading = false
  }
}

// 展开/收起某 case 时按需加载；若没步骤则自动从 TestCase 同步
const handleExpandChange = async (row, _expandedRows, _runId) => {
  if (row._expanded) {
    if (!row._stepsLoaded) {
      row._stepsLoading = true
      try {
        // 先尝试拉一次，如果列表为空且有 testcase id，则自动 init-steps 同步
        await loadCaseSteps(row)
        if ((!row.step_records || !row.step_records.length) && row.testcase_id) {
          await api.post(`/executions/run_cases/${row.id}/init-steps/`)
          await loadCaseSteps(row)
        }
      } finally {
        row._stepsLoading = false
      }
    }
  }
}

// 更新某步骤状态（自动联动 case 状态）
const updateStep = async (runCase, step, _runId) => {
  try {
    const res = await api.patch(`/executions/run_cases/${runCase.id}/steps/${step.step_number}/`, {
      status: step.status,
      actual_result: step.actual_result || ''
    })
    const payload = res.data || {}
    if (payload.run_case_status) {
      runCase.status = payload.run_case_status
    }
    // 静默成功，不打扰
  } catch (e) {
    ElMessage.error('步骤状态更新失败：' + (e.message || ''))
  }
}

const updateCaseStatus = async (runCase) => {
  try {
    await api.patch(`/executions/run_cases/${runCase.id}/update_status/`, {
      status: runCase.status,
      comments: runCase.comments || ''
    })
    await fetchTestPlan() // 刷新数据以更新进度和最后执行时间
    ElMessage.success('状态更新成功')
  } catch (error) {
    ElMessage.error('状态更新失败')
  }
}

const updateCaseDetails = async (runCase) => {
  try {
    await api.patch(`/executions/run_cases/${runCase.id}/update_status/`, {
      status: runCase.status,
      comments: runCase.comments || ''
    })
    ElMessage.success('详细信息更新成功')
  } catch (error) {
    ElMessage.error('详细信息更新失败')
  }
}

const viewCaseHistory = async (runCase) => {
  try {
    const response = await api.get(`/executions/run_cases/${runCase.id}/history/`)
    currentCaseHistory.value = response.data
    historyDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取历史记录失败')
  }
}

// 处理选择变化
const handleSelectionChange = (selection) => {
  selectedCases.value = selection
}

// 批量删除
const batchDeleteCases = async () => {
  if (selectedCases.value.length === 0) {
    ElMessage.warning('请先选择要删除的用例')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedCases.value.length} 个用例吗？此操作不可恢复。`,
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    isDeleting.value = true
    let successCount = 0
    let failCount = 0

    for (const runCase of selectedCases.value) {
      try {
        await api.delete(`/executions/run_cases/${runCase.id}/`)
        successCount++
      } catch (error) {
        console.error(`删除用例 ${runCase.id} 失败:`, error)
        failCount++
      }
    }

    if (successCount > 0) {
      ElMessage.success(`成功删除 ${successCount} 个用例${failCount > 0 ? `，${failCount} 个失败` : ''}`)
    } else {
      ElMessage.error('删除失败')
    }

    selectedCases.value = []
    await fetchTestPlan()

  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error('批量删除失败')
    }
  } finally {
    isDeleting.value = false
  }
}

// 分页相关
const paginatedCases = (cases) => {
  if (!cases) return []
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return cases.slice(start, end)
}

const getSerialNumber = (index) => {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

const handlePageChange = () => {
  selectedCases.value = []
  // 清空表格选择
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

const handleSizeChange = () => {
  currentPage.value = 1
  selectedCases.value = []
  // 清空表格选择
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const getProgressColor = (percentage) => {
  if (percentage < 30) return '#f56c6c'
  if (percentage < 70) return '#e6a23c'
  return '#67c23a'
}

const getRunStatusType = (progress) => {
  if (progress.progress === 100) return 'success'
  if (progress.failed > 0) return 'danger'
  if (progress.blocked > 0) return 'warning'
  return 'info'
}

const getRunStatusText = (progress) => {
  if (progress.progress === 100) return '已完成'
  if (progress.untested === progress.total) return '未开始'
  return '进行中'
}

const getStatusType = (status) => {
  const typeMap = {
    'untested': 'info',
    'passed': 'success',
    'failed': 'danger',
    'blocked': 'warning',
    'retest': 'primary'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    'untested': '未测试',
    'passed': '通过',
    'failed': '失败',
    'blocked': '阻塞',
    'retest': '重测'
  }
  return textMap[status] || status
}

onMounted(() => {
  fetchTestPlan()
})
</script>

<style scoped>
.execution-detail {
  padding: 24px;
  background: #f5f7fa;
  min-height: 100vh;
}

/* 美化的页面头部 */
.page-header-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 32px;
  margin-bottom: 24px;
  box-shadow: 0 8px 24px rgba(102, 126, 234, 0.25);
  color: white;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.title-section {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-title {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  color: white;
}

.version-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  backdrop-filter: blur(10px);
}

.project-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.9);
}

.info-icon {
  font-size: 18px;
}

.no-data {
  color: rgba(255, 255, 255, 0.6);
  font-style: italic;
}

/* 测试运行卡片 */
.test-run-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.run-header {
  margin-bottom: 24px;
}

.run-title-section {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.run-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.run-status-tag {
  font-weight: 600;
}

/* 美化的统计卡片 */
.stats-cards {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  transition: all 0.3s ease;
  cursor: default;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-card.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stat-card.passed {
  background: linear-gradient(135deg, #84fab0 0%, #8fd3f4 100%);
  color: #155724;
}

.stat-card.failed {
  background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
  color: #721c24;
}

.stat-card.blocked {
  background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
  color: #856404;
}

.stat-card.untested {
  background: linear-gradient(135deg, #e0e7ff 0%, #cfd9ff 100%);
  color: #383d41;
}

.stat-icon {
  font-size: 32px;
  opacity: 0.9;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
}

.stat-label {
  font-size: 12px;
  margin-top: 4px;
  opacity: 0.9;
}

/* 进度条区域 */
.progress-section {
  margin-bottom: 24px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.progress-text {
  font-weight: 600;
  font-size: 14px;
}

/* 批量操作 */
.batch-actions {
  margin-bottom: 16px;
  display: flex;
  justify-content: flex-end;
}

/* 表格样式 */
.execution-table {
  border-radius: 8px;
  overflow: hidden;
}

/* 分页 */
.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

/* 步骤折叠区 */
.case-steps-panel {
  padding: 12px 16px;
  background: #fafbfc;
  border-radius: 6px;
  margin: 4px 0;
}
.case-steps-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.case-steps-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
}
.steps-table {
  border-radius: 4px;
  overflow: hidden;
}
.step-action {
  color: #303133;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
}
.step-expected {
  color: #67c23a;
  font-size: 12px;
}
.case-steps-empty {
  text-align: center;
  padding: 12px 0;
}
.loading-text {
  color: #909399;
  font-size: 12px;
  padding: 8px;
}
.case-title-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 用例悬浮预览卡片 */
.case-preview {
  font-size: 13px;
}
.case-preview__title {
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
  word-break: break-all;
}
.case-preview__row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.case-preview__row--remark {
  align-items: flex-start;
}
.case-preview__label {
  color: #909399;
  flex: 0 0 36px;
}
.case-preview__remark {
  color: #606266;
  word-break: break-all;
  line-height: 1.5;
}

/* 抽屉内样式 */
.drawer-desc {
  margin-bottom: 16px;
}
.drawer-subtitle {
  margin: 20px 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  border-left: 3px solid #409eff;
  padding-left: 8px;
}
</style>
