<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">AI 项目管理</h1>
      <el-button type="primary" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        新建项目
      </el-button>
    </div>
    <div class="card-container">
      <div class="filter-bar">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-input v-model="searchText" placeholder="搜索项目名称" clearable @input="handleSearch">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
          </el-col>
          <el-col :span="4">
            <el-select v-model="statusFilter" placeholder="状态筛选" clearable @change="handleFilter">
              <el-option label="未开始" value="NOT_STARTED" />
              <el-option label="进行中" value="IN_PROGRESS" />
              <el-option label="已结束" value="COMPLETED" />
            </el-select>
          </el-col>
        </el-row>
      </div>
      <el-table :data="projects" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="项目名称" min-width="200">
          <template #default="{ row }">
            <el-link @click="goToDetail(row.id)" type="primary">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="280" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="base_url" label="基础URL" min-width="180" show-overflow-tooltip />
        <el-table-column prop="owner.username" label="负责人" width="100" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="goToCases(row.id)">用例</el-button>
            <el-button size="small" @click="goToSuites(row.id)">套件</el-button>
            <el-button size="small" @click="editProject(row)"><el-icon><Edit /></el-icon> 编辑</el-button>
            <el-button size="small" type="danger" @click="deleteProject(row.id)"><el-icon><Delete /></el-icon> 删除</el-button>
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
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>
    <el-dialog v-model="showCreateDialog" title="新建项目" width="500px">
      <el-form ref="createFormRef" :model="createForm" :rules="formRules" label-width="80px">
        <el-form-item label="项目名称" prop="name"><el-input v-model="createForm.name" placeholder="请输入项目名称" /></el-form-item>
        <el-form-item label="项目描述" prop="description"><el-input v-model="createForm.description" type="textarea" placeholder="请输入项目描述" /></el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="createForm.status" placeholder="请选择"><el-option label="未开始" value="NOT_STARTED" /><el-option label="进行中" value="IN_PROGRESS" /><el-option label="已结束" value="COMPLETED" /></el-select>
        </el-form-item>
        <el-form-item label="基础URL" prop="base_url"><el-input v-model="createForm.base_url" placeholder="请输入基础URL" /></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="createForm.start_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="createForm.end_date" type="date" placeholder="选择日期" value-format="YYYY-MM-DD" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showEditDialog" title="编辑项目" width="500px">
      <el-form ref="editFormRef" :model="editForm" :rules="formRules" label-width="80px">
        <el-form-item label="项目名称" prop="name"><el-input v-model="editForm.name" placeholder="请输入项目名称" /></el-form-item>
        <el-form-item label="项目描述"><el-input v-model="editForm.description" type="textarea" placeholder="请输入项目描述" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="editForm.status"><el-option label="未开始" value="NOT_STARTED" /><el-option label="进行中" value="IN_PROGRESS" /><el-option label="已结束" value="COMPLETED" /></el-select></el-form-item>
        <el-form-item label="基础URL"><el-input v-model="editForm.base_url" placeholder="请输入基础URL" /></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="editForm.start_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="editForm.end_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleEdit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Edit, Delete } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getUiProjects, createUiProject, updateUiProject, deleteUiProject } from '@/api/ui_automation'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const projects = ref([])
const loading = ref(false)
const total = ref(0)
const pagination = reactive({ currentPage: 1, pageSize: 10 })
const searchText = ref('')
const statusFilter = ref('')
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const createFormRef = ref(null)
const editFormRef = ref(null)
const currentEditId = ref(null)
const createForm = reactive({ name: '', description: '', status: 'IN_PROGRESS', base_url: '', start_date: null, end_date: null })
const editForm = reactive({ name: '', description: '', status: 'IN_PROGRESS', base_url: '', start_date: null, end_date: null })
const formRules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }, { min: 2, max: 200, message: '长度 2-200 字符', trigger: 'blur' }],
  base_url: [{ required: true, message: '请输入基础URL', trigger: 'blur' }, { type: 'url', message: '请输入有效URL', trigger: 'blur' }]
}

const formatDate = (row, col, val) => val ? new Date(val).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' }) : ''
const getStatusType = (s) => ({ NOT_STARTED: 'warning', IN_PROGRESS: 'primary', COMPLETED: 'success' }[s] || 'default')
const getStatusText = (s) => ({ NOT_STARTED: '未开始', IN_PROGRESS: '进行中', COMPLETED: '已结束' }[s] || s)

const loadProjects = async () => {
  loading.value = true
  try {
    const params = { page: pagination.currentPage, page_size: pagination.pageSize }
    if (searchText.value) params.search = searchText.value
    if (statusFilter.value) params.status = statusFilter.value
    const res = await getUiProjects(params)
    projects.value = res.data.results || res.data
    total.value = res.data.count ?? projects.value.length
  } catch (e) {
    ElMessage.error('获取项目列表失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}
const handleSearch = () => { pagination.currentPage = 1; loadProjects() }
const handleFilter = () => { pagination.currentPage = 1; loadProjects() }
const handleSizeChange = () => loadProjects()
const handleCurrentChange = () => loadProjects()

const goToDetail = (id) => {
  const p = projects.value.find(x => x.id === id)
  if (p) ElMessage.info(p.name + ' - 可在「用例」或「套件」中按项目筛选查看')
}
const goToCases = (projectId) => {
  router.push({ path: '/ai-intelligent-mode/cases', query: { project: projectId } })
}
const goToSuites = (projectId) => {
  router.push({ path: '/ai-intelligent-mode/suites', query: { project: projectId } })
}

const editProject = (row) => {
  currentEditId.value = row.id
  editForm.name = row.name
  editForm.description = row.description ?? ''
  editForm.status = row.status
  editForm.base_url = row.base_url ?? ''
  editForm.start_date = row.start_date || null
  editForm.end_date = row.end_date || null
  showEditDialog.value = true
}

const deleteProject = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该项目吗？', '确认删除', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
    await deleteUiProject(id)
    ElMessage.success('删除成功')
    loadProjects()
  } catch (e) {
    if (e !== 'cancel') { ElMessage.error('删除失败'); console.error(e) }
  }
}

const handleCreate = async () => {
  try {
    await createFormRef.value.validate()
  } catch {
    return
  }
  try {
    const userStore = useUserStore()
    if (!userStore.user?.id) await userStore.fetchProfile()
    await createUiProject({
      ...createForm,
      owner: userStore.user.id,
      start_date: createForm.start_date || null,
      end_date: createForm.end_date || null
    })
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    createForm.name = ''; createForm.description = ''; createForm.base_url = ''; createForm.start_date = null; createForm.end_date = null
    createForm.status = 'IN_PROGRESS'
    loadProjects()
  } catch (e) {
    ElMessage.error('创建失败')
    console.error(e)
  }
}

const handleEdit = async () => {
  try {
    await editFormRef.value.validate()
  } catch {
    return
  }
  try {
    await updateUiProject(currentEditId.value, { ...editForm, start_date: editForm.start_date || null, end_date: editForm.end_date || null })
    ElMessage.success('更新成功')
    showEditDialog.value = false
    loadProjects()
  } catch (e) {
    ElMessage.error('更新失败')
    console.error(e)
  }
}

onMounted(() => loadProjects())
</script>

<style scoped>
.page-container { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { margin: 0; font-size: 24px; }
.card-container { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.filter-bar { margin-bottom: 20px; }
.pagination-container { margin-top: 20px; display: flex; justify-content: flex-end; }
</style>
