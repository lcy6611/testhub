<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">AI 定时任务</h1>
      <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon> 新建定时任务</el-button>
    </div>
    <div class="card-container">
      <el-table :data="tasks" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="任务名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="task_type_display" label="任务类型" width="120" />
        <el-table-column prop="trigger_type" label="触发类型" width="100">
          <template #default="{ row }">{{ row.trigger_type === 'CRON' ? 'Cron' : row.trigger_type === 'INTERVAL' ? '间隔' : '单次' }}</template>
        </el-table-column>
        <el-table-column prop="status_display" label="状态" width="90" />
        <el-table-column prop="execution_mode" label="执行模式" width="90" />
        <el-table-column prop="next_run_time" label="下次执行" width="165" :formatter="(row, col, val) => formatDt(val)" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="runNow(row)" :loading="row._running">立即执行</el-button>
            <el-button size="small" @click="editTask(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteTask(row)">删除</el-button>
            <el-button v-if="row.status === 'ACTIVE'" size="small" @click="pauseTask(row)">暂停</el-button>
            <el-button v-if="row.status === 'PAUSED'" size="small" @click="resumeTask(row)">恢复</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadTasks"
          @current-change="loadTasks"
        />
      </div>
    </div>
    <el-dialog v-model="showFormDialog" :title="editingId ? '编辑定时任务' : '新建定时任务'" width="560px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="110px">
        <el-form-item label="任务名称" prop="name"><el-input v-model="form.name" placeholder="请输入任务名称" /></el-form-item>
        <el-form-item label="关联项目" prop="project">
          <el-select v-model="form.project" placeholder="请选择项目" style="width: 100%" filterable @change="onFormProjectChange">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <div v-if="projects.length === 0" class="form-hint">暂无项目，请先在「AI 智能模式 → 项目管理」中创建项目</div>
        </el-form-item>
        <el-form-item label="任务类型" prop="task_type">
          <el-radio-group v-model="form.task_type" @change="onTaskTypeChange">
            <el-radio value="AI_SUITE">AI 套件执行</el-radio>
            <el-radio value="AI_CASE">AI 用例执行</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.task_type === 'AI_SUITE'" label="AI 套件" prop="ai_suite">
          <el-select v-model="form.ai_suite" placeholder="请先选择关联项目后再选择套件" style="width: 100%" clearable filterable :disabled="!form.project">
            <el-option v-for="s in aiSuites" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
          <div v-if="form.project && aiSuites.length === 0" class="form-hint">该项目下暂无 AI 套件，请先在「AI 套件管理」中创建</div>
        </el-form-item>
        <el-form-item v-if="form.task_type === 'AI_CASE'" label="AI 用例" prop="ai_case">
          <el-select v-model="form.ai_case" placeholder="请选择用例" style="width: 100%" clearable>
            <el-option v-for="c in aiCases" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发类型" prop="trigger_type">
          <el-radio-group v-model="form.trigger_type">
            <el-radio value="CRON">Cron</el-radio>
            <el-radio value="INTERVAL">间隔</el-radio>
            <el-radio value="ONCE">单次</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.trigger_type === 'CRON'" label="Cron 表达式"><el-input v-model="form.cron_expression" placeholder="如 0 9 * * *" /></el-form-item>
        <el-form-item v-if="form.trigger_type === 'INTERVAL'" label="间隔(秒)"><el-input-number v-model="form.interval_seconds" :min="60" /></el-form-item>
        <el-form-item v-if="form.trigger_type === 'ONCE'" label="执行时间"><el-date-picker v-model="form.execute_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择时间" style="width: 100%" /></el-form-item>
        <el-form-item label="执行模式">
          <el-select v-model="form.execution_mode" style="width: 100%">
            <el-option label="自动" value="auto" /><el-option label="文本" value="text" /><el-option label="视觉" value="vision" />
          </el-select>
        </el-form-item>
        <el-form-item label="无头模式"><el-switch v-model="form.headless" /></el-form-item>
        <el-form-item label="通知">
          <el-checkbox v-model="form.notify_on_success" @change="updateNotifyEmails">成功时通知</el-checkbox>
          <el-checkbox v-model="form.notify_on_failure" @change="updateNotifyEmails">失败时通知</el-checkbox>
        </el-form-item>
        <el-form-item v-if="form.notify_on_success || form.notify_on_failure" label="通知类型">
          <el-select v-model="form.notification_type" placeholder="请选择通知类型" style="width: 100%" @change="updateNotifyEmails">
            <el-option label="邮箱通知" value="email" />
            <el-option label="Webhook机器人" value="webhook" />
            <el-option label="两者都发送" value="both" />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="(form.notify_on_success || form.notify_on_failure) && (form.notification_type === 'email' || form.notification_type === 'both')"
          label="通知邮箱"
        >
          <div v-if="userEmail" class="auto-email">{{ userEmail }}（自动从个人设置获取）</div>
          <div v-else class="form-hint" style="color:#f56c6c;">个人邮箱未配置，请先在个人设置添加邮箱</div>
          <div class="form-hint">Webhook 需在通知配置中心勾选「AI测试」机器人</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFormDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getUiProjects,
  getAISuites,
  getAICases,
  getAIScheduledTasks,
  createAIScheduledTask,
  getAIScheduledTaskDetail,
  updateAIScheduledTask,
  deleteAIScheduledTask,
  pauseAIScheduledTask,
  resumeAIScheduledTask,
  runNowAIScheduledTask
} from '@/api/ui_automation'
import { useUserStore } from '@/stores/user'

const tasks = ref([])
const loading = ref(false)
const saving = ref(false)
const total = ref(0)
const pagination = reactive({ currentPage: 1, pageSize: 20 })
const showFormDialog = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const projects = ref([])
const aiSuites = ref([])
const aiCases = ref([])
const userStore = useUserStore()
const userEmail = computed(() => userStore.user?.email || '')
const form = reactive({
  name: '', project: null, task_type: 'AI_SUITE', ai_suite: null, ai_case: null,
  trigger_type: 'CRON', cron_expression: '', interval_seconds: 3600, execute_at: null,
  execution_mode: 'text', headless: false,
  notify_on_success: false, notify_on_failure: false,
  notification_type: '',
  notify_emails: []
})
const formRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  project: [{ required: true, message: '请选择项目', trigger: 'change' }]
}

const formatDt = (row, col, val) => val ? new Date(val).toLocaleString('zh-CN') : '-'

async function loadTasks() {
  loading.value = true
  try {
    const res = await getAIScheduledTasks({ page: pagination.currentPage, page_size: pagination.pageSize })
    tasks.value = res.data.results || res.data || []
    total.value = res.data.count ?? tasks.value.length
  } catch (e) {
    const msg = e.response?.data?.detail || e.response?.data?.error || '加载任务列表失败'
    ElMessage.error(typeof msg === 'string' ? msg : '加载任务列表失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  try {
    const res = await getUiProjects({ page_size: 500 })
    projects.value = res.data.results || res.data || []
  } catch (e) {
    projects.value = []
  }
}

async function loadSuitesForProject(projectId) {
  if (!projectId) { aiSuites.value = []; return }
  try {
    const res = await getAISuites({ project: Number(projectId), page_size: 500 })
    aiSuites.value = res.data.results || res.data || []
  } catch (e) {
    console.error('加载 AI 套件失败', e)
    aiSuites.value = []
  }
}

async function loadCasesForProject(projectId) {
  if (!projectId) { aiCases.value = []; return }
  try {
    const res = await getAICases({ project: projectId, page_size: 500 })
    aiCases.value = res.data.results || res.data || []
  } catch (e) {
    aiCases.value = []
  }
}

function onFormProjectChange() {
  form.ai_suite = null
  form.ai_case = null
  loadSuitesForProject(form.project)
  loadCasesForProject(form.project)
}

function onTaskTypeChange() {
  form.ai_suite = null
  form.ai_case = null
}

function updateNotifyEmails() {
  if ((form.notify_on_success || form.notify_on_failure) && (form.notification_type === 'email' || form.notification_type === 'both')) {
    form.notify_emails = userEmail.value ? [userEmail.value] : []
  } else {
    form.notify_emails = []
  }
}

function resetForm() {
  editingId.value = null
  form.name = ''
  form.project = null
  form.task_type = 'AI_SUITE'
  form.ai_suite = null
  form.ai_case = null
  form.trigger_type = 'CRON'
  form.cron_expression = ''
  form.interval_seconds = 3600
  form.execute_at = null
  form.execution_mode = 'text'
  form.headless = false
  form.notify_on_success = false
  form.notify_on_failure = false
  form.notification_type = ''
  form.notify_emails = []
}

function openCreate() {
  resetForm()
  loadProjects()
  showFormDialog.value = true
}

async function editTask(row) {
  editingId.value = row.id
  try {
    const res = await getAIScheduledTaskDetail(row.id)
    const d = res.data
    form.name = d.name
    form.project = d.project
    form.task_type = d.task_type
    form.ai_suite = d.ai_suite
    form.ai_case = d.ai_case
    form.trigger_type = d.trigger_type
    form.cron_expression = d.cron_expression || ''
    form.interval_seconds = d.interval_seconds || 3600
    form.execute_at = d.execute_at || null
    form.execution_mode = d.execution_mode || 'text'
    form.headless = d.headless || false
    form.notify_on_success = d.notify_on_success || false
    form.notify_on_failure = d.notify_on_failure || false
    form.notification_type = d.notification_type || ''
    form.notify_emails = d.notify_emails || (userEmail.value ? [userEmail.value] : [])
    updateNotifyEmails()
    loadSuitesForProject(d.project)
    loadCasesForProject(d.project)
    showFormDialog.value = true
  } catch (e) {
    ElMessage.error('加载任务详情失败')
    console.error(e)
  }
}

async function submitForm() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  if (form.task_type === 'AI_SUITE' && !form.ai_suite) {
    ElMessage.warning('请选择 AI 套件')
    return
  }
  if (form.task_type === 'AI_CASE' && !form.ai_case) {
    ElMessage.warning('请选择 AI 用例')
    return
  }
  updateNotifyEmails()
  if ((form.notify_on_success || form.notify_on_failure) && (form.notification_type === 'email' || form.notification_type === 'both') && (!form.notify_emails || form.notify_emails.length === 0)) {
    ElMessage.warning('个人邮箱未配置，请先在个人设置添加邮箱')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name,
      project: form.project,
      task_type: form.task_type,
      ai_suite: form.task_type === 'AI_SUITE' ? form.ai_suite : null,
      ai_case: form.task_type === 'AI_CASE' ? form.ai_case : null,
      trigger_type: form.trigger_type,
      cron_expression: form.cron_expression || '',
      interval_seconds: form.interval_seconds || null,
      execute_at: form.execute_at || null,
      execution_mode: form.execution_mode,
      headless: form.headless,
      notify_on_success: form.notify_on_success,
      notify_on_failure: form.notify_on_failure,
      notification_type: (form.notify_on_success || form.notify_on_failure) ? (form.notification_type || 'webhook') : '',
      notify_emails: (form.notify_on_success || form.notify_on_failure) && (form.notification_type === 'email' || form.notification_type === 'both')
        ? (form.notify_emails || [])
        : []
    }
    if (editingId.value) {
      await updateAIScheduledTask(editingId.value, payload)
      ElMessage.success('更新成功')
    } else {
      await createAIScheduledTask(payload)
      ElMessage.success('创建成功')
    }
    showFormDialog.value = false
    loadTasks()
  } catch (e) {
    const data = e.response?.data
    let msg = '保存失败'
    if (data) {
      if (typeof data.detail === 'string') msg = data.detail
      else if (data.detail && typeof data.detail === 'object') msg = Object.entries(data.detail).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : v}`).join('；')
      else if (data.error) msg = data.error
      else if (data.cron_expression) msg = Array.isArray(data.cron_expression) ? data.cron_expression.join(' ') : data.cron_expression
    }
    ElMessage.error(msg)
    console.error('保存定时任务失败', data || e)
  } finally {
    saving.value = false
  }
}

async function deleteTask(row) {
  try {
    await ElMessageBox.confirm('确定要删除该定时任务吗？', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
    await deleteAIScheduledTask(row.id)
    ElMessage.success('删除成功')
    loadTasks()
  } catch (e) {
    if (e !== 'cancel') { ElMessage.error('删除失败'); console.error(e) }
  }
}

async function pauseTask(row) {
  try {
    await pauseAIScheduledTask(row.id)
    ElMessage.success('已暂停')
    loadTasks()
  } catch (e) {
    ElMessage.error('操作失败')
    console.error(e)
  }
}

async function resumeTask(row) {
  try {
    await resumeAIScheduledTask(row.id)
    ElMessage.success('已恢复')
    loadTasks()
  } catch (e) {
    ElMessage.error('操作失败')
    console.error(e)
  }
}

async function runNow(row) {
  row._running = true
  try {
    await runNowAIScheduledTask(row.id)
    ElMessage.success('已触发立即执行')
    loadTasks()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '执行失败')
    console.error(e)
  } finally {
    row._running = false
  }
}

onMounted(() => {
  loadProjects()
  loadTasks()
})
</script>

<style scoped>
.page-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { margin: 0; font-size: 24px; }
.card-container { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.pagination-container { margin-top: 16px; display: flex; justify-content: flex-end; }
.form-hint { font-size: 12px; color: #909399; margin-top: 4px; }
</style>
