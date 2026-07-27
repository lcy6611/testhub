<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">AI 用例管理</h1>
    </div>

    <div class="card-container">
      <div class="filter-bar">
        <el-input
          v-model="searchText"
          placeholder="搜索用例名称或描述"
          clearable
          @input="handleSearch"
          style="width: 300px;"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <el-table :data="cases" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="用例名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="task_description" label="任务描述" min-width="300" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="180" :formatter="formatDate" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="success" @click="openRunDialog(row)">
              <el-icon><VideoPlay /></el-icon>
              执行
            </el-button>
            <el-button size="small" type="primary" @click="editCase(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button size="small" type="danger" @click="deleteCase(row.id)">
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
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <!-- 执行选项对话框 -->
    <el-dialog v-model="showRunDialog" title="执行 AI 用例" width="480px" @close="runForm.executionMode = 'auto'; runForm.headless = false; runForm.enableGif = true">
      <el-form :model="runForm" label-width="100px">
        <el-form-item label="执行模式">
          <el-select v-model="runForm.executionMode" placeholder="选择执行模式" style="width: 100%;">
            <el-option label="自动（推荐）" value="auto" />
            <el-option label="文本模式" value="text" />
            <el-option label="视觉模式" value="vision" />
          </el-select>
          <div class="form-hint">自动=有文本配置则用文本，否则视觉；文本=强制文本；视觉=看图决策。</div>
        </el-form-item>
        <el-form-item label="浏览器">
          <el-radio-group v-model="runForm.headless">
            <el-radio-button :label="false">有头</el-radio-button>
            <el-radio-button :label="true">无头</el-radio-button>
          </el-radio-group>
          <div v-if="runForm.executionMode === 'vision'" class="form-hint">
            视觉模式推荐使用无头；在 Docker/Linux 无图形界面环境下会自动降级为无头。
          </div>
        </el-form-item>
        <el-form-item label="GIF 录制">
          <el-switch v-model="runForm.enableGif" active-text="开启" inactive-text="关闭" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showRunDialog = false">取消</el-button>
          <el-button type="primary" @click="confirmRun" :loading="running">开始执行</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 编辑对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑 AI 用例" :close-on-click-modal="false" :close-on-press-escape="false" :modal="true" :destroy-on-close="false" width="600px">
      <el-form :model="editForm" :rules="formRules" ref="editFormRef" label-width="100px">
        <el-form-item label="用例名称" prop="name">
          <el-input v-model="editForm.name" placeholder="请输入用例名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="editForm.description" type="textarea" placeholder="请输入用例描述" />
        </el-form-item>
        <el-form-item label="任务描述" prop="task_description">
          <el-input 
            v-model="editForm.task_description" 
            type="textarea" 
            :rows="6"
            placeholder="请输入自然语言任务描述" 
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showEditDialog = false">取消</el-button>
          <el-button type="primary" @click="confirmEdit" :loading="saving">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, VideoPlay, Edit, Delete } from '@element-plus/icons-vue'
import { useRouter, useRoute } from 'vue-router'
import {
  getAICases,
  updateAICase,
  deleteAICase,
  runAICase
} from '@/api/ui_automation'

const router = useRouter()
const route = useRoute()
const cases = ref([])
const loading = ref(false)
const searchText = ref('')
const total = ref(0)
const pagination = reactive({
  currentPage: 1,
  pageSize: 20
})

const showEditDialog = ref(false)
const showRunDialog = ref(false)
const running = ref(false)
const runCaseRow = ref(null)
const runForm = reactive({
  executionMode: 'auto',
  headless: false,
  enableGif: true
})
const saving = ref(false)
const currentCaseId = ref(null)
const editForm = reactive({
  name: '',
  description: '',
  task_description: ''
})
const editFormRef = ref(null)

const formRules = {
  name: [{ required: true, message: '请输入用例名称', trigger: 'blur' }],
  task_description: [{ required: true, message: '请输入任务描述', trigger: 'blur' }]
}

// 加载用例列表
const loadCases = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.currentPage,
      page_size: pagination.pageSize,
      search: searchText.value
    }
    const projectId = route.query.project || route.query.project_id
    if (projectId) params.project = projectId
    const response = await getAICases(params)

    cases.value = response.data.results || []
    total.value = response.data.count || 0
  } catch (error) {
    console.error('获取用例列表失败:', error)
    ElMessage.error('获取用例列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.currentPage = 1
  loadCases()
}

const handleSizeChange = () => {
  pagination.currentPage = 1
  loadCases()
}

const handleCurrentChange = () => {
  loadCases()
}

// 编辑用例
const editCase = (row) => {
  currentCaseId.value = row.id
  editForm.name = row.name
  editForm.description = row.description
  editForm.task_description = row.task_description
  showEditDialog.value = true
}

const confirmEdit = async () => {
  if (!editFormRef.value) return
  
  await editFormRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        await updateAICase(currentCaseId.value, {
          name: editForm.name,
          description: editForm.description,
          task_description: editForm.task_description
        })
        
        ElMessage.success('更新成功')
        showEditDialog.value = false
        loadCases()
      } catch (error) {
        console.error('更新失败:', error)
        ElMessage.error('更新失败')
      } finally {
        saving.value = false
      }
    }
  })
}

// 删除用例
const deleteCase = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该用例吗?', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    await deleteAICase(id)
    ElMessage.success('删除成功')
    loadCases()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

// 打开执行对话框
const openRunDialog = (row) => {
  runCaseRow.value = row
  runForm.executionMode = 'auto'
  runForm.headless = false
  runForm.enableGif = true
  showRunDialog.value = true
}

// 视觉模式：首次切换时默认无头（用户仍可手动改回有头）
watch(() => runForm.executionMode, (v, oldV) => {
  if (v === 'vision' && oldV !== 'vision') runForm.headless = true
})

// 确认执行用例
const confirmRun = async () => {
  const row = runCaseRow.value
  if (!row) return
  running.value = true
  try {
    await runAICase(row.id, {
      execution_mode: runForm.executionMode,
      headless: runForm.headless,
      enable_gif: runForm.enableGif
    })
    ElMessage.success('用例开始执行')
    showRunDialog.value = false
    router.push('/ai-intelligent-mode/execution-records')
  } catch (error) {
    console.error('执行失败:', error)
    ElMessage.error(error.response?.data?.error || '执行失败')
  } finally {
    running.value = false
  }
}

const formatDate = (row, column, cellValue) => {
  if (!cellValue) return ''
  return new Date(cellValue).toLocaleString()
}

onMounted(() => {
  loadCases()
})
</script>

<style lang="scss" scoped>
.page-container {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  
  .page-title {
    font-size: 20px;
    font-weight: 600;
    margin: 0;
  }
}

.card-container {
  background-color: #fff;
  border-radius: 4px;
  padding: 20px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.filter-bar {
  margin-bottom: 20px;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
