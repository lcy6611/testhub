<template>
  <div class="case-script-records">
    <el-card shadow="never">
      <template #header>
        <div class="hd">
          <b>用例 → UI 脚本生成记录</b>
          <div class="filters">
            <el-select v-model="statusFilter" placeholder="全部状态" clearable style="width:160px" @change="load">
              <el-option v-for="s in statusOpts" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-button type="primary" plain @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="rows" v-loading="loading" border size="small">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="source_testcase_title" label="源用例" min-width="200" show-overflow-tooltip />
        <el-table-column label="UI项目" min-width="160">
          <template #default="{ row }">
            <router-link v-if="row.ui_project_detail" :to="`/ui-automation/projects`" class="lnk">#{{ row.ui_project_detail.id }} {{ row.ui_project_detail.name }}</router-link>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="elements_captured" label="元素" width="70" />
        <el-table-column prop="steps_total" label="步数" width="70" />
        <el-table-column prop="steps_passed" label="验证通过" width="90" />
        <el-table-column label="套件通过率" width="110">
          <template #default="{ row }">
            <span v-if="row.suite_execution_detail">{{ row.suite_execution_detail.pass_rate }}%</span>
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="重试" width="80">
          <template #default="{ row }">
            <span v-if="row.retry_count">{{ row.retry_count }}/{{ row.retry_limit }}</span>
            <span v-else class="muted">0/{{ row.retry_limit }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="340" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="goDetail(row.id)">详情</el-button>
            <el-button v-if="row.generated_test_case_detail" size="small" type="success" plain
                       @click="goTestCase(row)">打开用例</el-button>
            <el-button v-if="row.suite_detail" size="small" type="primary" plain
                       :loading="runningId === row.id"
                       @click="onRunSuite(row)">执行</el-button>
            <el-button v-if="row.suite_detail" size="small" plain
                       @click="goSuite(row)">套件</el-button>
            <el-button v-if="row.status === 'failed'" size="small" type="warning"
                       :loading="retryingId === row.id" @click="onRetry(row)">重试</el-button>
            <el-button v-if="row.status === 'running' || row.status === 'pending'" size="small" type="danger"
                       @click="onStop(row)">停止</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
                       layout="total, prev, pager, next" @current-change="load" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import {
  getCaseScriptGenerations, retryCaseScriptGeneration, stopCaseScriptGeneration,
  runTestSuite,
} from '@/api/ui_automation'

const router = useRouter()
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const retryingId = ref(null)
const runningId = ref(null)

const statusOpts = [
  { value: 'pending', label: '等待中' },
  { value: 'running', label: '执行中' },
  { value: 'passed', label: '全部通过' },
  { value: 'partial', label: '部分通过' },
  { value: 'failed', label: '失败' },
]

const statusType = (s) => ({ pending: 'info', running: 'warning', passed: 'success', partial: 'warning', failed: 'danger' }[s] || 'info')
const statusText = (s) => ({ pending: '等待中', running: '执行中', passed: '全部通过', partial: '部分通过', failed: '失败' }[s] || s)
const fmt = (d) => d ? dayjs(d).format('YYYY-MM-DD HH:mm') : '-'

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (statusFilter.value) params.status = statusFilter.value
    const r = await getCaseScriptGenerations(params)
    rows.value = r.data.results || r.data || []
    total.value = r.data.count || rows.value.length
  } catch (e) {
    ElMessage.error('加载生成记录失败：' + (e.message || ''))
  } finally {
    loading.value = false
  }
}

function goDetail(id) {
  router.push(`/ui-automation/generate-result/${id}`)
}
function goSuite(row) {
  const pid = row.ui_project_detail?.id || row.ui_project
  const sid = row.suite_detail?.id
  router.push({ path: '/ui-automation/suites', query: { ...(pid ? { projectId: pid } : {}), ...(sid ? { suiteId: sid } : {}) } })
}
function goTestCase(row) {
  const pid = row.ui_project_detail?.id || row.ui_project
  const cid = row.generated_test_case_detail?.id
  router.push({ path: '/ui-automation/test-cases', query: { ...(pid ? { projectId: pid } : {}), ...(cid ? { caseId: cid } : {}) } })
}
async function onRunSuite(row) {
  if (!row.suite_detail) return
  runningId.value = row.id
  try {
    await runTestSuite(row.suite_detail.id, { headless: true })
    ElMessage.success('已触发套件执行，进入套件列表查看进度')
    setTimeout(load, 1500)
  } catch (e) {
    ElMessage.error('执行失败：' + (e.response?.data?.detail || e.response?.data?.error || e.message))
  } finally {
    runningId.value = null
  }
}
async function onRetry(row) {
  retryingId.value = row.id
  try {
    await retryCaseScriptGeneration(row.id)
    ElMessage.success('已触发重试')
    load()
  } catch (e) {
    ElMessage.error('重试失败：' + (e.response?.data?.detail || e.message))
  } finally {
    retryingId.value = null
  }
}
async function onStop(row) {
  await stopCaseScriptGeneration(row.id)
  ElMessage.info('已发送停止信号')
  load()
}

onMounted(load)
</script>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
.filters { display: flex; gap: 10px; }
.lnk { color: #409eff; }
.muted { color: #999; }
.pager { margin-top: 16px; display: flex; justify-content: center; }
</style>
