<template>
  <div class="page-container defect-list-page">
    <div class="page-header">
      <h1 class="page-title">
        <el-icon class="title-icon"><Warning /></el-icon>
        问题管理
      </h1>
      <div class="header-actions">
        <el-button type="primary" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>
          新建 BUG
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-row :gutter="16" align="middle">
        <el-col :span="6">
          <el-select v-model="filterProject" placeholder="选择项目" clearable filterable @change="loadList">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filterStatus" placeholder="状态" clearable @change="loadList">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filterSeverity" placeholder="严重度" clearable @change="loadList">
            <el-option v-for="s in severityOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-col>
        <el-col :span="6">
          <el-input
            v-model="searchText"
            placeholder="搜索标题"
            clearable
            @input="debouncedLoad"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </el-col>
        <el-col :span="4">
          <el-button @click="resetFilter">重置</el-button>
        </el-col>
      </el-row>
    </div>

    <!-- 概览统计 -->
    <div class="stat-row" v-if="stats">
      <div class="stat-card stat-total">
        <div class="stat-n">{{ stats.total }}</div>
        <div class="stat-label">缺陷总数</div>
      </div>
      <div class="stat-card stat-open">
        <div class="stat-n">{{ stats.open }}</div>
        <div class="stat-label">待处理</div>
      </div>
      <div class="stat-card stat-s1">
        <div class="stat-n">{{ stats.s1 }}</div>
        <div class="stat-label">致命 S1</div>
      </div>
      <div class="stat-card stat-s2">
        <div class="stat-n">{{ stats.s2 }}</div>
        <div class="stat-label">严重 S2</div>
      </div>
      <div class="stat-card stat-resolved">
        <div class="stat-n">{{ stats.resolved }}</div>
        <div class="stat-label">已修复</div>
      </div>
    </div>

    <el-table
      :data="defectList"
      v-loading="loading"
      stripe
      :show-overflow-tooltip="true"
      style="width: 100%"
      empty-text="暂无缺陷"
    >
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="defect-expand">
            <div class="expand-row" v-if="row.description">
              <span class="lbl">描述：</span>
              <span class="val">{{ row.description }}</span>
            </div>
            <div class="expand-row" v-if="row.steps_to_reproduce">
              <span class="lbl">复现步骤：</span>
              <pre class="val steps">{{ row.steps_to_reproduce }}</pre>
            </div>
            <div class="expand-row" v-if="row.environment">
              <span class="lbl">环境：</span>
              <span class="val">{{ row.environment }}</span>
            </div>
            <div class="expand-row" v-if="row.attachments && row.attachments.length">
              <span class="lbl">附件：</span>
              <div class="att-list">
                <el-image
                  v-for="att in row.attachments.filter(a => a.kind === 'screenshot')"
                  :key="att.id"
                  :src="att.file_url"
                  :preview-src-list="row.attachments.filter(a => a.kind === 'screenshot').map(a => a.file_url)"
                  :initial-index="0"
                  fit="cover"
                  class="att-thumb"
                  :preview-teleported="true"
                />
                <a
                  v-for="att in row.attachments.filter(a => a.kind !== 'screenshot')"
                  :key="att.id"
                  :href="att.file_url"
                  target="_blank"
                  class="att-link"
                >
                  <el-icon><Document /></el-icon>
                  {{ att.original_name || '附件' }}
                </a>
              </div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="严重度" width="90">
        <template #default="{ row }">
          <el-tag :type="severityTagType(row.severity)" size="small">{{ row.severity_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="320">
        <template #default="{ row }">
          <el-link type="primary" underline="never" @click="openEditDialog(row)">
            {{ row.title }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="status_display" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" size="small">{{ row.status_display }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="project_name" label="所属项目" min-width="150" show-overflow-tooltip />
      <el-table-column label="来源" width="90">
        <template #default="{ row }">
          <span class="src-tag" :class="`src-${row.source}`">{{ row.source || 'manual' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="附件" width="70" align="center">
        <template #default="{ row }">
          <el-badge
            v-if="row.attachments && row.attachments.length"
            :value="row.attachments.length"
            type="info"
          />
          <span v-else class="muted">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="reported_by_name" label="报告人" width="100" />
      <el-table-column prop="created_at" label="创建时间" width="170">
        <template #default="{ row }">
          <span class="time-text">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-dropdown trigger="click" @command="(cmd) => handleRowCmd(cmd, row)">
            <el-button size="small" type="primary" link>
              操作<el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="detail">详情</el-dropdown-item>
                <el-dropdown-item command="in_progress">处理中</el-dropdown-item>
                <el-dropdown-item command="resolved">已修复</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination-wrap" v-if="total > pageSize">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="loadList"
        @size-change="loadList"
      />
    </div>

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑缺陷' : '新建 BUG'"
      width="780px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px" label-position="right">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" maxlength="300" show-word-limit placeholder="一句话描述问题" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所属项目" required>
              <el-select v-model="form.project" filterable placeholder="选择项目" style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="严重度">
              <el-select v-model="form.severity" style="width: 100%">
                <el-option v-for="s in severityOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="状态">
              <el-select v-model="form.status" style="width: 100%">
                <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="指派给">
              <el-select v-model="form.assigned_to" filterable clearable placeholder="选择处理人" style="width: 100%">
                <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="环境信息">
              <el-input v-model="form.environment" placeholder="如：Chrome 125 / Win11 / 测试服" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="详细描述" />
        </el-form-item>
        <el-form-item label="复现步骤">
          <el-input v-model="form.steps_to_reproduce" type="textarea" :rows="4" placeholder="1. 打开...\n2. 点击...\n3. 出现..." />
        </el-form-item>
        <el-form-item label="来源">
          <el-radio-group v-model="form.source">
            <el-radio value="manual">手动</el-radio>
            <el-radio value="execution">用例执行</el-radio>
            <el-radio value="performance">性能测试</el-radio>
            <el-radio value="hermes">数字人</el-radio>
            <el-radio value="ai">AI 分析</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="附件">
          <el-upload
            v-if="editing"
            :http-request="uploadAtt"
            :show-file-list="false"
            multiple
            accept="image/*,.log,.txt,.zip"
            :before-upload="beforeUpload"
          >
            <el-button type="primary" plain>
              <el-icon><Upload /></el-icon> 点击上传截图/日志
            </el-button>
            <template #tip>
              <div class="upload-tip">支持多文件；图片会展示缩略图，日志可下载</div>
            </template>
          </el-upload>
          <el-button v-else type="primary" plain @click="createDraftAndUpload">
            <el-icon><Upload /></el-icon> 先创建 BUG 后再上传附件
          </el-button>
          <template v-if="editing">
            <div class="att-grid" v-if="form.attachments && form.attachments.length">
              <div v-for="att in form.attachments" :key="att.id" class="att-card">
                <el-image
                  v-if="att.kind === 'screenshot'"
                  :src="att.file_url"
                  :preview-src-list="form.attachments.filter(a => a.kind === 'screenshot').map(a => a.file_url)"
                  :preview-teleported="true"
                  fit="cover"
                  class="att-card-img"
                />
                <a v-else :href="att.file_url" target="_blank" class="att-card-file">
                  <el-icon><Document /></el-icon>
                  <span>{{ att.original_name || '附件' }}</span>
                </a>
                <el-button
                  size="small"
                  type="danger"
                  link
                  class="att-del"
                  @click="removeAtt(att)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
                <div class="att-cap">{{ att.caption || att.original_name || '' }}</div>
              </div>
            </div>
          </template>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">
          {{ editing ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Warning, Plus, Search, Document, Upload, Delete, ArrowDown } from '@element-plus/icons-vue'
import {
  getDefects, getDefect, createDefect, patchDefect, deleteDefect,
  uploadDefectAttachment, deleteDefectAttachment
} from '@/api/defects'
import { getProjects } from '@/api/performance'
import request from '@/utils/api'

const route = useRoute()

const loading = ref(false)
const saving = ref(false)
const defectList = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const projects = ref([])
const users = ref([])

const filterProject = ref(null)
const filterStatus = ref(null)
const filterSeverity = ref(null)
const searchText = ref('')

const statusOptions = [
  { value: 'open', label: '待处理' },
  { value: 'in_progress', label: '处理中' },
  { value: 'resolved', label: '已修复' },
  { value: 'closed', label: '已关闭' },
  { value: 'reopened', label: '重新打开' }
]
const severityOptions = [
  { value: 'S1', label: '致命' },
  { value: 'S2', label: '严重' },
  { value: 'S3', label: '一般' },
  { value: 'S4', label: '轻微' }
]

const dialogVisible = ref(false)
const editing = ref(null)
const form = reactive({
  title: '',
  project: null,
  severity: 'S3',
  status: 'open',
  assigned_to: null,
  description: '',
  steps_to_reproduce: '',
  environment: '',
  source: 'manual',
  attachments: []
})

const stats = computed(() => {
  const all = defectList.value
  return {
    total: total.value,
    open: all.filter(d => d.status === 'open').length,
    s1: all.filter(d => d.severity === 'S1').length,
    s2: all.filter(d => d.severity === 'S2').length,
    resolved: all.filter(d => d.status === 'resolved').length
  }
})

let loadTimer = null
const debouncedLoad = () => {
  clearTimeout(loadTimer)
  loadTimer = setTimeout(() => { page.value = 1; loadList() }, 350)
}

const resetFilter = () => {
  filterProject.value = null
  filterStatus.value = null
  filterSeverity.value = null
  searchText.value = ''
  page.value = 1
  loadList()
}

const loadList = async () => {
  loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value
    }
    if (filterProject.value) params.project = filterProject.value
    if (filterStatus.value) params.status = filterStatus.value
    if (filterSeverity.value) params.severity = filterSeverity.value
    if (searchText.value) params.search = searchText.value
    const res = await getDefects(params)
    const data = res.data || res
    defectList.value = data.results || data || []
    total.value = data.count ?? defectList.value.length
  } catch (e) {
    ElMessage.error('加载缺陷列表失败：' + (e.message || ''))
  } finally {
    loading.value = false
  }
}

const loadProjects = async () => {
  try {
    const res = await getProjects({ page_size: 200 })
    const data = res.data || res
    projects.value = data.results || data || []
    if (!filterProject.value && projects.value.length) {
      filterProject.value = projects.value[0].id
      loadList()
    }
  } catch (e) {
    // ignore
  }
}

const loadUsers = async () => {
  try {
    const res = await request.get('/users/users/', { params: { page_size: 200 } })
    const data = res.data || res
    users.value = data.results || data || []
  } catch (e) {
    // ignore
  }
}

const openCreateDialog = () => {
  editing.value = null
  Object.assign(form, {
    title: '', project: filterProject.value || (projects.value[0]?.id ?? null),
    severity: 'S3', status: 'open', assigned_to: null,
    description: '', steps_to_reproduce: '', environment: '',
    source: 'manual', attachments: []
  })
  // 默认带入所选项目的默认环境
  applyProjectEnvironment(form.project)
  dialogVisible.value = true
}

// 从 projects 列表中查找 project 的默认环境并填入 form.environment
const applyProjectEnvironment = (projectId) => {
  if (!projectId) return
  const proj = projects.value.find(p => p.id === projectId)
  if (!proj) return
  const envs = proj.environments || []
  if (!envs.length) return
  // 优先 is_default=True，否则取第一个
  const def = envs.find(e => e.is_default) || envs[0]
  const parts = []
  if (def.name) parts.push(def.name)
  if (def.base_url) parts.push(def.base_url)
  if (parts.length) {
    form.environment = parts.join(' / ')
  }
}

// 新建时先创建草稿 BUG 再进入编辑态允许上传附件
const createDraftAndUpload = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请先填写标题，再上传附件')
    return
  }
  if (!form.project) {
    ElMessage.warning('请选择项目')
    return
  }
  saving.value = true
  try {
    const res = await createDefect({
      title: form.title,
      project: form.project,
      severity: form.severity,
      status: form.status,
      assigned_to: form.assigned_to || null,
      description: form.description,
      steps_to_reproduce: form.steps_to_reproduce,
      environment: form.environment,
      source: form.source
    })
    const created = res.data || res
    ElMessage.success('已创建 BUG #' + created.id + '，现在可上传附件')
    editing.value = created
    form.attachments = created.attachments || []
  } catch (e) {
    ElMessage.error('创建失败：' + (e.message || ''))
  } finally {
    saving.value = false
  }
}

const openEditDialog = async (row) => {
  try {
    const res = await getDefect(row.id)
    const d = res.data || res
    editing.value = d
    Object.assign(form, {
      title: d.title,
      project: d.project,
      severity: d.severity,
      status: d.status,
      assigned_to: d.assigned_to,
      description: d.description || '',
      steps_to_reproduce: d.steps_to_reproduce || '',
      environment: d.environment || '',
      source: d.source || 'manual',
      attachments: d.attachments || []
    })
    dialogVisible.value = true
  } catch (e) {
    ElMessage.error('加载详情失败：' + (e.message || ''))
  }
}

const submitForm = async () => {
  if (!form.title.trim()) return ElMessage.warning('请填写标题')
  if (!form.project) return ElMessage.warning('请选择项目')
  saving.value = true
  try {
    if (editing.value) {
      await patchDefect(editing.value.id, {
        title: form.title,
        project: form.project,
        severity: form.severity,
        status: form.status,
        assigned_to: form.assigned_to || null,
        description: form.description,
        steps_to_reproduce: form.steps_to_reproduce,
        environment: form.environment,
        source: form.source
      })
      ElMessage.success('已保存')
    } else {
      const res = await createDefect({
        title: form.title,
        project: form.project,
        severity: form.severity,
        status: form.status,
        assigned_to: form.assigned_to || null,
        description: form.description,
        steps_to_reproduce: form.steps_to_reproduce,
        environment: form.environment,
        source: form.source
      })
      const created = res.data || res
      ElMessage.success('已创建 BUG #' + created.id)
      editing.value = created
      form.attachments = created.attachments || []
    }
    dialogVisible.value = false
    loadList()
  } catch (e) {
    ElMessage.error('保存失败：' + (e.message || ''))
  } finally {
    saving.value = false
  }
}

const uploadAtt = async (options) => {
  const fd = new FormData()
  fd.append('file', options.file)
  const isImg = options.file.type.startsWith('image/')
  fd.append('kind', isImg ? 'screenshot' : 'log')
  try {
    const res = await uploadDefectAttachment(editing.value.id, fd)
    const att = res.data || res
    form.attachments = [...form.attachments, att]
    ElMessage.success('已上传')
    loadList()
  } catch (e) {
    ElMessage.error('上传失败：' + (e.message || ''))
  }
}

const beforeUpload = (file) => {
  const maxMB = 20
  if (file.size / 1024 / 1024 > maxMB) {
    ElMessage.error(`${file.name} 超过 ${maxMB}MB`)
    return false
  }
}

const removeAtt = async (att) => {
  try {
    await ElMessageBox.confirm('确认删除该附件？', '提示', { type: 'warning' })
    await deleteDefectAttachment(editing.value.id, att.id)
    form.attachments = form.attachments.filter(a => a.id !== att.id)
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败：' + (e.message || ''))
  }
}

const quickStatus = async (row, status) => {
  try {
    await patchDefect(row.id, { status })
    ElMessage.success('已更新')
    loadList()
  } catch (e) {
    ElMessage.error('更新失败：' + (e.message || ''))
  }
}

const confirmDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确认删除缺陷 #${row.id}「${row.title}」？`, '提示', { type: 'warning' })
    await deleteDefect(row.id)
    ElMessage.success('已删除')
    loadList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败：' + (e.message || ''))
  }
}

// 操作列下拉菜单命令分发
const handleRowCmd = (cmd, row) => {
  if (cmd === 'detail') {
    openEditDialog(row)
  } else if (cmd === 'in_progress') {
    quickStatus(row, 'in_progress')
  } else if (cmd === 'resolved') {
    quickStatus(row, 'resolved')
  } else if (cmd === 'delete') {
    confirmDelete(row)
  }
}

// 监听项目变化，自动带入默认环境（编辑/新建均生效）
watch(() => form.project, (newId, oldId) => {
  if (newId && newId !== oldId) {
    applyProjectEnvironment(newId)
  }
})

const severityTagType = (s) => ({ S1: 'danger', S2: 'warning', S3: 'info', S4: '' })[s] || ''
const statusTagType = (s) => ({
  open: 'danger', in_progress: 'warning', resolved: 'success', closed: 'info', reopened: 'warning'
})[s] || ''

const formatTime = (t) => {
  if (!t) return ''
  const d = new Date(t)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(() => {
  loadProjects()
  loadUsers()
  loadList()
  // 从其他模块携带 query 预填：performance / hermes / execution 等
  if (route.query.preset_title) {
    Object.assign(form, {
      title: String(route.query.preset_title),
      description: route.query.preset_description ? String(route.query.preset_description) : '',
      severity: route.query.preset_severity ? String(route.query.preset_severity) : 'S3',
      source: route.query.preset_source ? String(route.query.preset_source) : 'manual',
      project: filterProject.value || (projects.value[0]?.id ?? null)
    })
    dialogVisible.value = true
  }
})
</script>

<style scoped>
.defect-list-page {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.title-icon {
  color: #f56c6c;
  font-size: 22px;
}
.filter-bar {
  background: #fafafa;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}
.stat-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  padding: 16px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #ebeef5;
  text-align: center;
  transition: all 0.2s;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.stat-n {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
}
.stat-label {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}
.stat-total .stat-n { color: #409eff; }
.stat-open .stat-n { color: #f56c6c; }
.stat-s1 .stat-n { color: #f56c6c; }
.stat-s2 .stat-n { color: #e6a23c; }
.stat-resolved .stat-n { color: #67c23a; }
.defect-expand {
  padding: 8px 24px;
  background: #fafbfc;
  border-radius: 4px;
  margin: 4px 0;
}
.expand-row {
  display: flex;
  gap: 8px;
  margin: 6px 0;
  font-size: 13px;
}
.expand-row .lbl {
  color: #909399;
  min-width: 80px;
  flex-shrink: 0;
}
.expand-row .val {
  color: #303133;
  flex: 1;
}
.expand-row .steps {
  background: #f4f4f5;
  padding: 8px;
  border-radius: 4px;
  white-space: pre-wrap;
  margin: 0;
  font-family: inherit;
  font-size: 12px;
}
.att-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  flex: 1;
}
.att-thumb {
  width: 80px;
  height: 80px;
  border-radius: 4px;
  border: 1px solid #ebeef5;
}
.att-link {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: #f4f4f5;
  border-radius: 4px;
  font-size: 12px;
  text-decoration: none;
  color: #606266;
}
.src-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 11px;
  background: #f4f4f5;
  color: #909399;
}
.src-performance { background: #ecf5ff; color: #409eff; }
.src-execution { background: #fdf6ec; color: #e6a23c; }
.src-hermes { background: #f0f9eb; color: #67c23a; }
.src-ai { background: #f4ecfc; color: #8e44ad; }
.muted { color: #c0c4cc; }
.time-text { font-size: 12px; color: #606266; }
.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.upload-tip {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.att-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  margin-top: 12px;
  width: 100%;
}
.att-card {
  position: relative;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 6px;
  background: #fafafa;
  min-height: 100px;
}
.att-card-img {
  width: 100%;
  height: 100px;
  object-fit: cover;
  border-radius: 4px;
}
.att-card-file {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 100px;
  padding: 8px;
  text-decoration: none;
  color: #606266;
  font-size: 12px;
  word-break: break-all;
}
.att-del {
  position: absolute;
  top: 4px;
  right: 4px;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 50%;
}
.att-cap {
  margin-top: 4px;
  font-size: 11px;
  color: #909399;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
