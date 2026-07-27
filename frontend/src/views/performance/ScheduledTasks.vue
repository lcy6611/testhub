<template>
  <div class="perf-scheduled-tasks">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>定时任务</span>
          <el-button type="primary" @click="openDialog()">
            <el-icon><Plus /></el-icon>新建任务
          </el-button>
        </div>
      </template>

      <el-table :data="tasks" v-loading="loading" stripe border>
        <el-table-column prop="name" label="任务名称" min-width="180" />
        <el-table-column prop="script_name" label="关联脚本" min-width="160" />
        <el-table-column prop="cron" label="Cron 表达式" width="150" />
        <el-table-column prop="status_display" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'enabled' ? 'success' : 'info'" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="thread_count" label="线程数" width="90" align="center" />
        <el-table-column prop="duration" label="持续(s)" width="100" align="center" />
        <el-table-column prop="updated_at" label="更新时间" width="170">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openDialog(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑定时任务' : '新建定时任务'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="任务名称" required>
          <el-input v-model="form.name" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="关联脚本" required>
          <el-select v-model="form.script" placeholder="选择脚本" style="width:100%" filterable>
            <el-option v-for="s in scripts" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Cron 表达式" required>
          <el-input v-model="form.cron" placeholder="例如：0 2 * * *" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio value="enabled">启用</el-radio>
            <el-radio value="disabled">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="线程数">
              <el-input-number v-model="form.thread_count" :min="1" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Ramp-Up">
              <el-input-number v-model="form.ramp_up" :min="0" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="持续(s)">
              <el-input-number v-model="form.duration" :min="1" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="实时报告">
          <el-switch v-model="form.realtime_enabled" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getScheduledTasks, createScheduledTask, updateScheduledTask, deleteScheduledTask,
  getScripts
} from '@/api/performance'

const tasks = ref([])
const scripts = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const isEdit = ref(false)
const currentId = ref(null)

const form = reactive({
  name: '',
  script: null,
  cron: '',
  status: 'enabled',
  thread_count: 10,
  ramp_up: 5,
  duration: 60,
  realtime_enabled: false,
  description: ''
})

const formatTime = (val) => val ? new Date(val).toLocaleString('zh-CN', { hour12: false }) : '-'

async function loadData() {
  loading.value = true
  try {
    const [tasksRes, scriptsRes] = await Promise.all([getScheduledTasks(), getScripts()])
    tasks.value = tasksRes.data?.results || tasksRes.data || []
    scripts.value = scriptsRes.data?.results || scriptsRes.data || []
  } catch (e) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

function openDialog(row = null) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  Object.assign(form, {
    name: row?.name || '',
    script: row?.script || null,
    cron: row?.cron || '',
    status: row?.status || 'enabled',
    thread_count: row?.thread_count || 10,
    ramp_up: row?.ramp_up || 5,
    duration: row?.duration || 60,
    realtime_enabled: row?.realtime_enabled || false,
    description: row?.description || ''
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!form.name || !form.script || !form.cron) {
    ElMessage.warning('请填写必填项')
    return
  }
  submitting.value = true
  try {
    if (isEdit.value) {
      await updateScheduledTask(currentId.value, form)
    } else {
      await createScheduledTask(form)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await loadData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || JSON.stringify(e.response?.data) || '保存失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该定时任务吗？', '删除确认', { type: 'warning' })
    await deleteScheduledTask(row.id)
    ElMessage.success('删除成功')
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
