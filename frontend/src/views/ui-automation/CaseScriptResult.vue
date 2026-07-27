<template>
  <div class="case-script-result" v-if="gen">
    <el-card shadow="never">
      <template #header>
        <div class="hd">
          <span>生成结果 #{{ gen.id }} · {{ gen.source_testcase_title }}</span>
          <div>
            <el-tag :type="statusType(gen.status)">{{ statusText(gen.status) }}</el-tag>
            <el-button v-if="gen.status === 'failed'" size="small" type="warning"
                       style="margin-left:10px" :loading="retrying" @click="onRetry">重试</el-button>
            <el-button v-if="gen.suite_detail" size="small" type="success"
                       style="margin-left:10px" :loading="runningSuite" @click="onRunSuite">执行套件</el-button>
            <el-button size="small" @click="goBack">返回列表</el-button>
          </div>
        </div>
      </template>

      <el-descriptions :column="4" border size="small">
        <el-descriptions-item label="源用例">
          <router-link :to="`/ai-generation/testcases/${gen.source_testcase_id}`" class="lnk">#{{ gen.source_testcase_id }} {{ gen.source_testcase_title }}</router-link>
        </el-descriptions-item>
        <el-descriptions-item label="UI项目">
          <span v-if="gen.ui_project_detail">#{{ gen.ui_project_detail.id }} {{ gen.ui_project_detail.name }}</span>
          <span v-else class="muted">-</span>
        </el-descriptions-item>
        <el-descriptions-item label="被测地址">{{ gen.base_url }}</el-descriptions-item>
        <el-descriptions-item label="重试">{{ gen.retry_count }}/{{ gen.retry_limit }}</el-descriptions-item>

        <el-descriptions-item label="抓取元素">{{ gen.elements_captured }}</el-descriptions-item>
        <el-descriptions-item label="步骤总数">{{ gen.steps_total }}</el-descriptions-item>
        <el-descriptions-item label="验证通过">{{ gen.steps_passed }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ fmt(gen.created_at) }}</el-descriptions-item>

        <el-descriptions-item label="关联套件" :span="2" v-if="gen.suite_detail">
          <router-link :to="suiteLink" class="lnk">#{{ gen.suite_detail.id }} {{ gen.suite_detail.name }}</router-link>
          <el-button size="small" type="success" plain style="margin-left:10px"
                     :loading="runningSuite" @click="onRunSuite">执行</el-button>
        </el-descriptions-item>
        <el-descriptions-item label="套件执行" :span="2" v-if="gen.suite_execution_detail">
          <el-tag :type="execType(gen.suite_execution_detail.status)" size="small">{{ execText(gen.suite_execution_detail.status) }}</el-tag>
          <span class="kv">通过 <b>{{ gen.suite_execution_detail.passed }}</b></span>
          <span class="kv">失败 <b>{{ gen.suite_execution_detail.failed }}</b></span>
          <span class="kv">通过率 <b>{{ gen.suite_execution_detail.pass_rate }}%</b></span>
        </el-descriptions-item>
      </el-descriptions>

      <el-alert v-if="gen.error_message" type="error" :closable="false" show-icon
                :title="'错误信息'" style="margin-top:12px">
        <pre class="err">{{ gen.error_message }}</pre>
      </el-alert>
    </el-card>

    <el-card v-if="elements.length" shadow="never" style="margin-top:16px">
      <template #header><b>抓取到的元素 &amp; 验证状态</b></template>
      <el-table :data="elements" size="small" border>
        <el-table-column prop="step_order" label="步骤" width="60" />
        <el-table-column prop="action_type" label="动作" width="90" />
        <el-table-column prop="description" label="目标" />
        <el-table-column label="定位器">
          <template #default="{ row }">
            <span v-if="row.element">{{ row.element.locator_strategy }}: {{ row.element.locator_value }}</span>
            <span v-else class="muted">无（无元素步骤）</span>
          </template>
        </el-table-column>
        <el-table-column label="验证" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.element"
                    :type="row.element.validation_status === 'VALID' ? 'success' : (row.element.validation_status === 'INVALID' ? 'danger' : 'info')">
              {{ row.element.validation_status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="gen.generated_test_case_detail" shadow="never" style="margin-top:16px">
      <template #header>
        <div class="hd-row">
          <b>生成的 UI 用例</b>
          <el-button size="small" type="primary" plain @click="goTestCase">在用例管理中打开</el-button>
        </div>
      </template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="用例ID">#{{ gen.generated_test_case_detail.id }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ gen.generated_test_case_detail.name }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ gen.generated_test_case_detail.status }}</el-descriptions-item>
        <el-descriptions-item label="所属UI项目">#{{ gen.generated_test_case_detail.project_id }}</el-descriptions-item>
        <el-descriptions-item label="套件关联" :span="2">
          <span v-if="gen.suite_detail">已纳入套件：#{{ gen.suite_detail.id }} {{ gen.suite_detail.name }}</span>
          <span v-else class="muted">-</span>
        </el-descriptions-item>
      </el-descriptions>
      <p class="hint">说明：生成的脚本本质是 UI 用例（UiTestCase）。在「UI 自动化 → 用例管理」中可看步骤、配定位器、手工调整；套件通过「添加用例」纳入，套件执行时走 Playwright 真跑 UiTestCase。</p>
    </el-card>

    <el-card shadow="never" style="margin-top:16px" v-if="gen.playwright_code">
      <template #header>
        <div class="hd-row">
          <b>Playwright 代码（仅参考）</b>
          <el-button size="small" @click="copyCode" type="primary" plain>复制代码</el-button>
        </div>
      </template>
      <pre class="code">{{ gen.playwright_code }}</pre>
      <p class="hint">说明：此代码由生成器拼装，便于人工查看/复制；执行以 UI 用例步骤为准（TestExecutor 走 UiTestCase 真实回放）。</p>
    </el-card>

    <el-card shadow="never" style="margin-top:16px">
      <template #header><b>进度日志</b></template>
      <pre class="log">{{ gen.progress_log || '（暂无日志）' }}</pre>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import {
  getCaseScriptGenerationDetail, getCaseScriptGenerationElements,
  retryCaseScriptGeneration, runTestSuite,
} from '@/api/ui_automation'

const route = useRoute()
const router = useRouter()
const gen = ref(null)
const elements = ref([])
const retrying = ref(false)
const runningSuite = ref(false)
let timer = null

const suiteLink = computed(() => {
  const q = {}
  if (gen.value?.ui_project_detail?.id) q.projectId = gen.value.ui_project_detail.id
  if (gen.value?.suite_detail?.id) q.suiteId = gen.value.suite_detail.id
  return { path: '/ui-automation/suites', query: q }
})

const statusType = (s) => ({ pending: 'info', running: 'warning', passed: 'success', partial: 'warning', failed: 'danger' }[s] || 'info')
const statusText = (s) => ({ pending: '等待中', running: '执行中', passed: '全部通过', partial: '部分通过', failed: '失败' }[s] || s)
const execType = (s) => ({ SUCCESS: 'success', FAILED: 'danger', RUNNING: 'warning', PENDING: 'info' }[s] || 'info')
const execText = (s) => ({ SUCCESS: '执行成功', FAILED: '执行失败', RUNNING: '执行中', PENDING: '待执行' }[s] || s)
const fmt = (d) => d ? dayjs(d).format('YYYY-MM-DD HH:mm') : '-'

async function load() {
  const id = route.params.id
  try {
    const r = await getCaseScriptGenerationDetail(id)
    gen.value = r.data
    if (r.data.generated_test_case) {
      try {
        const e = await getCaseScriptGenerationElements(id)
        elements.value = e.data.elements || []
      } catch (e) { /* ignore */ }
    }
    if (r.data.status === 'running' || r.data.status === 'pending') {
      startPoll()
    } else if (timer) {
      clearInterval(timer)
    }
  } catch (e) {
    ElMessage.error('加载失败：' + (e.message || ''))
  }
}

function startPoll() {
  if (timer) clearInterval(timer)
  timer = setInterval(load, 2500)
}

async function onRetry() {
  if (!gen.value) return
  retrying.value = true
  try {
    await retryCaseScriptGeneration(gen.value.id)
    ElMessage.success('已触发重试')
    gen.value.status = 'running'
    startPoll()
  } catch (e) {
    ElMessage.error('重试失败：' + (e.response?.data?.detail || e.message))
  } finally {
    retrying.value = false
  }
}

function goBack() {
  router.push('/ui-automation/generate-records')
}

function goTestCase() {
  const q = {}
  if (gen.value?.ui_project_detail?.id) q.projectId = gen.value.ui_project_detail.id
  if (gen.value?.generated_test_case_detail?.id) q.caseId = gen.value.generated_test_case_detail.id
  router.push({ path: '/ui-automation/test-cases', query: q })
}

async function onRunSuite() {
  if (!gen.value?.suite_detail) return
  runningSuite.value = true
  try {
    await runTestSuite(gen.value.suite_detail.id, { headless: true })
    ElMessage.success('已触发套件执行，正在自动刷新结果')
    startPoll()
    setTimeout(load, 1500)
  } catch (e) {
    ElMessage.error('执行失败：' + (e.response?.data?.detail || e.response?.data?.error || e.message))
  } finally {
    runningSuite.value = false
  }
}

async function copyCode() {
  const code = gen.value?.playwright_code || ''
  if (!code) return
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success('已复制到剪贴板')
  } catch (e) {
    // 兜底：textarea 选中复制
    try {
      const ta = document.createElement('textarea')
      ta.value = code
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      ElMessage.success('已复制到剪贴板')
    } catch (e2) {
      ElMessage.error('复制失败：' + (e.message || ''))
    }
  }
}

onMounted(load)
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.hd { display: flex; align-items: center; justify-content: space-between; }
.hd-row { display: flex; align-items: center; justify-content: space-between; }
.lnk { color: #409eff; font-weight: 600; }
.muted { color: #999; }
.kv { margin-left: 14px; color: #606266; font-size: 13px; }
.log { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; max-height: 360px; overflow: auto; white-space: pre-wrap; font-size: 12px; }
.code { background: #1e1e1e; color: #9cdcfe; padding: 12px; border-radius: 6px; max-height: 420px; overflow: auto; white-space: pre-wrap; font-size: 12px; font-family: Consolas, monospace; }
.err { background: transparent; color: #f56c6c; white-space: pre-wrap; margin: 0; font-size: 12px; }
.hint { color: #909399; font-size: 12px; margin: 12px 0 0; line-height: 1.6; }
</style>
