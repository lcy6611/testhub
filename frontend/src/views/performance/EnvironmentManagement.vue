<template>
  <div class="env-management" v-loading="loading">
    <el-card shadow="never" class="card">
      <div class="card-header">
        <div>
          <div class="card-title">压测环境</div>
          <div class="card-sub">一套 base_url / 全局请求头 / 变量，供同一脚本在 dev / staging / prod 间复跑；执行时显式选择才生效</div>
        </div>
        <el-button type="primary" @click="openCreate">新建环境</el-button>
      </div>

      <el-table :data="environments" stripe v-loading="listLoading">
        <el-table-column prop="name" label="环境名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="作用域" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.scope === 'GLOBAL' ? 'warning' : 'info'">{{ row.scope_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="关联项目" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.project_name || '—' }}</template>
        </el-table-column>
        <el-table-column prop="base_url" label="基础地址" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.base_url || '—' }}</template>
        </el-table-column>
        <el-table-column label="变量" width="80" align="center">
          <template #default="{ row }">{{ (row.variables || []).length }}</template>
        </el-table-column>
        <el-table-column label="激活" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_active" type="success" size="small">已激活</el-tag>
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_by_name" label="创建人" width="110" />
        <el-table-column label="操作" width="190" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="!row.is_active" link type="success" size="small" @click="handleActivate(row)">激活</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!listLoading && !environments.length" description="暂无环境，先新建一个" :image-size="80" />
    </el-card>

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑环境' : '新建环境'" width="680px">
      <el-form label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="环境名称" required>
              <el-input v-model="form.name" placeholder="如：预发环境" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="作用域">
              <el-radio-group v-model="form.scope">
                <el-radio-button label="PROJECT">项目环境</el-radio-button>
                <el-radio-button label="GLOBAL">全局环境</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="form.scope === 'PROJECT'" label="关联项目" required>
          <el-select v-model="form.project" placeholder="选择项目" filterable style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="基础地址">
          <el-input v-model="form.base_url" placeholder="如：https://api.example.com（可带路径前缀 /v1）" />
        </el-form-item>
        <el-form-item label="校验 SSL">
          <el-switch v-model="form.verify_ssl" />
        </el-form-item>

        <el-form-item label="全局请求头">
          <div class="kv-list">
            <div v-for="(h, i) in headerRows" :key="'h' + i" class="kv-row">
              <el-input v-model="h.name" placeholder="Header 名" style="width: 200px" />
              <el-input v-model="h.value" placeholder="值" style="flex: 1" />
              <el-button link type="danger" @click="headerRows.splice(i, 1)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button link size="small" @click="headerRows.push({ name: '', value: '' })">
              <el-icon><Plus /></el-icon>添加请求头
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="环境变量">
          <div class="kv-list">
            <div v-for="(v, i) in variableRows" :key="'v' + i" class="kv-row">
              <el-input v-model="v.name" placeholder="变量名（同名覆盖脚本变量）" style="width: 240px" />
              <el-input v-model="v.value" placeholder="值" style="flex: 1" />
              <el-button link type="danger" @click="variableRows.splice(i, 1)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button link size="small" @click="variableRows.push({ name: '', value: '' })">
              <el-icon><Plus /></el-icon>添加变量
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import {
  getEnvironments,
  createEnvironment,
  updateEnvironment,
  deleteEnvironment,
  setActiveEnvironment,
  getProjects,
} from '@/api/performance'

const loading = ref(true)
const listLoading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const environments = ref([])
const projects = ref([])

const form = reactive({
  id: null,
  name: '',
  scope: 'PROJECT',
  project: null,
  base_url: '',
  verify_ssl: false,
})
const headerRows = ref([])
const variableRows = ref([])

const loadList = async () => {
  listLoading.value = true
  try {
    const res = await getEnvironments({ page_size: 200 })
    environments.value = res.data?.results || res.data || []
  } catch (e) {
    environments.value = []
  } finally {
    listLoading.value = false
  }
}

const resetForm = () => {
  Object.assign(form, { id: null, name: '', scope: 'PROJECT', project: null, base_url: '', verify_ssl: false })
  headerRows.value = []
  variableRows.value = []
}

const openCreate = () => {
  resetForm()
  dialogVisible.value = true
}

const openEdit = (row) => {
  resetForm()
  Object.assign(form, {
    id: row.id,
    name: row.name,
    scope: row.scope,
    project: row.project || null,
    base_url: row.base_url || '',
    verify_ssl: !!row.verify_ssl,
  })
  headerRows.value = Object.entries(row.headers || {}).map(([name, value]) => ({ name, value }))
  variableRows.value = (row.variables || []).map((v) => ({ name: v.name, value: v.value }))
  dialogVisible.value = true
}

const handleSave = async () => {
  if (!form.name.trim()) return ElMessage.warning('请输入环境名称')
  if (form.scope === 'PROJECT' && !form.project) return ElMessage.warning('项目环境必须选择关联项目')

  const headers = {}
  for (const row of headerRows.value) {
    if ((row.name || '').trim()) headers[row.name.trim()] = row.value
  }
  const variables = variableRows.value
    .filter((v) => (v.name || '').trim())
    .map((v) => ({ name: v.name.trim(), value: v.value }))

  const payload = {
    name: form.name.trim(),
    scope: form.scope,
    project: form.scope === 'PROJECT' ? form.project : null,
    base_url: form.base_url || '',
    verify_ssl: form.verify_ssl,
    headers,
    variables,
  }
  saving.value = true
  try {
    if (form.id) {
      await updateEnvironment(form.id, payload)
      ElMessage.success('环境已更新')
    } else {
      await createEnvironment(payload)
      ElMessage.success('环境已创建')
    }
    dialogVisible.value = false
    await loadList()
  } catch (e) {
    const d = e?.response?.data
    ElMessage.error(d?.project?.[0] || d?.name?.[0] || d?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const handleActivate = async (row) => {
  try {
    await setActiveEnvironment(row.id)
    ElMessage.success(`「${row.name}」已激活`)
    await loadList()
  } catch (e) {
    ElMessage.error('激活失败')
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定删除环境「${row.name}」吗？`, '提示', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await deleteEnvironment(row.id)
      ElMessage.success('已删除')
      await loadList()
    } catch (e) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

onMounted(async () => {
  try {
    const res = await getProjects({ page_size: 200 })
    projects.value = res.data?.results || res.data || []
  } catch (e) {
    projects.value = []
  }
  await loadList()
  loading.value = false
})
</script>

<style scoped>
.card { margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.card-title { font-size: 15px; font-weight: 600; color: #303133; }
.card-sub { font-size: 12px; color: #909399; margin-top: 4px; }
.kv-list { width: 100%; }
.kv-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }
</style>
