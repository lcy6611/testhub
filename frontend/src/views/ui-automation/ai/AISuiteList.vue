<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">AI 套件管理</h1>
      <el-select v-model="projectId" placeholder="选择项目" style="width: 200px; margin-right: 12px" @change="onProjectChange">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        新增套件
      </el-button>
    </div>
    <div class="card-container">
      <el-input v-model="searchText" placeholder="搜索套件名称或描述" clearable style="width: 300px; margin-bottom: 16px" @input="loadSuites">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-table :data="suites" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="套件名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="用例数" width="90">
          <template #default="{ row }">{{ row.case_count ?? row.suite_cases?.length ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="执行状态" width="100">
          <template #default="{ row }">
            <el-tag :type="executionStatusType(row.execution_status)">{{ executionStatusText(row.execution_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="通过" width="80"><template #default="{ row }"><span class="text-success">{{ row.passed_count ?? 0 }}</span></template></el-table-column>
        <el-table-column label="失败" width="80"><template #default="{ row }"><span class="text-danger">{{ row.failed_count ?? 0 }}</span></template></el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="editSuite(row)">编辑</el-button>
            <el-button size="small" type="success" @click="openRunDialog(row)">运行</el-button>
            <el-button size="small" type="danger" @click="deleteSuite(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          @size-change="loadSuites"
          @current-change="loadSuites"
        />
      </div>
    </div>
    <el-dialog v-model="showFormDialog" :title="editingId ? '编辑套件' : '新增套件'" width="900px">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="90px">
        <el-form-item label="套件名称" prop="name"><el-input v-model="form.name" placeholder="请输入套件名称" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" placeholder="套件描述" /></el-form-item>
        <el-form-item label="选择用例">
          <div class="case-selector">
            <div class="selector-panel">
              <div class="panel-header">
                <h4>可用用例</h4>
                <el-input
                  v-model="testCaseSearchText"
                  placeholder="搜索用例"
                  size="small"
                  clearable
                  style="width: 200px;"
                >
                  <template #prefix>
                    <el-icon><Search /></el-icon>
                  </template>
                </el-input>
              </div>
              <div class="panel-content">
                <el-table
                  :data="filteredAvailableCases"
                  height="320"
                  size="small"
                  :row-style="() => ({ height: '44px' })"
                  :cell-style="() => ({ paddingTop: '6px', paddingBottom: '6px' })"
                >
                  <el-table-column prop="name" label="用例名称" min-width="160" show-overflow-tooltip />
                  <el-table-column label="操作" width="70" fixed="right">
                    <template #default="{ row }">
                      <el-button size="small" text @click="addCase(row)">
                        <el-icon><ArrowRight /></el-icon>
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>

            <div class="selector-panel">
              <div class="panel-header">
                <h4>已选用例 ({{ selectedCases.length }})</h4>
              </div>
              <div class="panel-content">
                <el-table
                  :data="selectedCases"
                  height="320"
                  size="small"
                  :row-style="() => ({ height: '44px' })"
                  :cell-style="() => ({ paddingTop: '6px', paddingBottom: '6px' })"
                >
                  <el-table-column prop="name" label="用例名称" min-width="160" show-overflow-tooltip />
                  <el-table-column label="操作" width="120" fixed="right">
                    <template #default="{ row, $index }">
                      <el-button size="small" text @click="moveUp($index)" :disabled="$index===0">
                        <el-icon><Top /></el-icon>
                      </el-button>
                      <el-button size="small" text @click="moveDown($index)" :disabled="$index===selectedCases.length-1">
                        <el-icon><Bottom /></el-icon>
                      </el-button>
                      <el-button size="small" text type="danger" @click="removeCase($index)">
                        <el-icon><Delete /></el-icon>
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </div>
          </div>
          <div class="form-hint">仅展示当前项目下的 AI 用例，无脚本。</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFormDialog = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="showRunDialog" title="执行套件" width="440px">
      <el-form label-width="90px">
        <el-form-item label="执行模式">
          <el-select v-model="runForm.executionMode" style="width: 100%">
            <el-option label="自动（推荐）" value="auto" />
            <el-option label="文本模式" value="text" />
            <el-option label="视觉模式" value="vision" />
          </el-select>
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
      </el-form>
      <template #footer>
        <el-button @click="showRunDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmRun" :loading="running">开始执行</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, ArrowRight, Top, Bottom, Delete } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { getUiProjects } from '@/api/ui_automation'
import { getAICases } from '@/api/ui_automation'
import { getAISuites, createAISuite, getAISuiteDetail, updateAISuite, deleteAISuite, runAISuite } from '@/api/ui_automation'

const router = useRouter()
const projectId = ref('')
const projects = ref([])
const suites = ref([])
const projectCases = ref([])
const loading = ref(false)
const saving = ref(false)
const running = ref(false)
const total = ref(0)
const searchText = ref('')
const pagination = reactive({ currentPage: 1, pageSize: 20 })
const showFormDialog = ref(false)
const showRunDialog = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const form = reactive({ name: '', description: '', ai_cases: [] })
const formRules = { name: [{ required: true, message: '请输入套件名称', trigger: 'blur' }] }
const runForm = reactive({ executionMode: 'auto', headless: false })
watch(() => runForm.executionMode, (v, oldV) => {
  if (v === 'vision' && oldV !== 'vision') runForm.headless = true
})
const runSuiteRow = ref(null)
const testCaseSearchText = ref('')

const executionStatusType = (s) => ({ not_run: 'info', running: 'warning', passed: 'success', failed: 'danger' }[s] || 'info')
const executionStatusText = (s) => ({ not_run: '未执行', running: '执行中', passed: '通过', failed: '失败' }[s] || s || '未执行')

async function loadProjects() {
  try {
    const res = await getUiProjects({ page_size: 500 })
    projects.value = res.data.results || res.data || []
    if (projects.value.length && !projectId.value) projectId.value = projects.value[0].id
  } catch (e) {
    console.error(e)
    const msg = e.response?.data?.detail || e.response?.data?.error || '加载项目失败'
    ElMessage.error(typeof msg === 'string' ? msg : '加载项目失败')
  }
}

async function loadSuites() {
  if (!projectId.value) { suites.value = []; total.value = 0; return }
  loading.value = true
  try {
    const params = { project: projectId.value, page: pagination.currentPage, page_size: pagination.pageSize }
    if (searchText.value) params.search = searchText.value
    const res = await getAISuites(params)
    suites.value = res.data.results || res.data || []
    total.value = res.data.count ?? suites.value.length
  } catch (e) {
    console.error(e)
    const msg = e.response?.data?.detail || e.response?.data?.error || '加载套件失败'
    ElMessage.error(typeof msg === 'string' ? msg : '加载套件失败')
  } finally {
    loading.value = false
  }
}

async function loadProjectCases() {
  if (!projectId.value) { projectCases.value = []; return }
  try {
    // 不在后端按 project 过滤，前端自行筛选：
    // 1）当前项目下的 AI 用例
    // 2）以及未绑定项目的老用例（兼容历史数据）
    const res = await getAICases({ page_size: 500 })
    const all = res.data.results || res.data || []
    projectCases.value = all.filter(c => {
      const p = c.project
      if (!p) return true  // 兼容旧数据：project 为空也允许选择
      return String(p.id) === String(projectId.value)
    })
  } catch (e) {
    projectCases.value = []
  }
}

const filteredAvailableCases = computed(() => {
  const picked = new Set(form.ai_cases || [])
  const keyword = (testCaseSearchText.value || '').trim().toLowerCase()
  return (projectCases.value || []).filter(c => {
    if (picked.has(c.id)) return false
    if (!keyword) return true
    return (c.name || '').toLowerCase().includes(keyword)
  })
})

const selectedCases = computed(() => {
  const map = new Map((projectCases.value || []).map(c => [c.id, c]))
  return (form.ai_cases || []).map(id => map.get(id)).filter(Boolean)
})

function addCase(row) {
  if (!row || !row.id) return
  if (!form.ai_cases.includes(row.id)) {
    form.ai_cases.push(row.id)
  }
}
function removeCase(idx) {
  form.ai_cases.splice(idx, 1)
}
function moveUp(idx) {
  if (idx <= 0) return
  const arr = form.ai_cases
  ;[arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]
}
function moveDown(idx) {
  const arr = form.ai_cases
  if (idx >= arr.length - 1) return
  ;[arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]]
}

function onProjectChange() {
  pagination.currentPage = 1
  loadSuites()
  loadProjectCases()
}

watch(projectId, (v) => { if (v) loadProjectCases() })

function openCreate() {
  if (!projectId.value) { ElMessage.warning('请先选择项目'); return }
  editingId.value = null
  form.name = ''
  form.description = ''
  form.ai_cases = []
  showFormDialog.value = true
}

async function editSuite(row) {
  editingId.value = row.id
  try {
    const res = await getAISuiteDetail(row.id)
    const d = res.data
    form.name = d.name
    form.description = d.description ?? ''
    form.ai_cases = (d.suite_cases || []).map(sc => sc.ai_case)
    showFormDialog.value = true
  } catch (e) {
    ElMessage.error('加载套件详情失败')
    console.error(e)
  }
}

async function submitForm() {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateAISuite(editingId.value, { project: projectId.value, name: form.name, description: form.description, ai_cases: form.ai_cases })
      ElMessage.success('更新成功')
    } else {
      await createAISuite({ project: projectId.value, name: form.name, description: form.description, ai_cases: form.ai_cases })
      ElMessage.success('创建成功')
    }
    showFormDialog.value = false
    loadSuites()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.response?.data?.error || '保存失败')
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function deleteSuite(id) {
  try {
    await ElMessageBox.confirm('确定要删除该套件吗？', '提示', { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' })
    await deleteAISuite(id)
    ElMessage.success('删除成功')
    loadSuites()
  } catch (e) {
    if (e !== 'cancel') { ElMessage.error('删除失败'); console.error(e) }
  }
}

function openRunDialog(row) {
  runSuiteRow.value = row
  runForm.executionMode = 'auto'
  runForm.headless = false
  showRunDialog.value = true
}

async function confirmRun() {
  const row = runSuiteRow.value
  if (!row) return
  running.value = true
  try {
    await runAISuite(row.id, { execution_mode: runForm.executionMode, headless: runForm.headless, enable_gif: true })
    ElMessage.success('套件已开始执行')
    showRunDialog.value = false
    router.push('/ai-intelligent-mode/execution-records')
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '执行失败')
    console.error(e)
  } finally {
    running.value = false
  }
}

onMounted(() => {
  loadProjects().then(() => {
    const q = router.currentRoute.value.query?.project
    if (q) projectId.value = Number(q) || q
    loadSuites()
    loadProjectCases()
  })
})
</script>

<style scoped>
.page-container { padding: 20px; }
.page-header { display: flex; align-items: center; margin-bottom: 20px; }
.page-title { margin: 0; font-size: 24px; margin-right: 16px; }
.card-container { background: #fff; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.pagination-container { margin-top: 16px; display: flex; justify-content: flex-end; }
.form-hint { font-size: 12px; color: #909399; margin-top: 4px; }
.text-success { color: #67c23a; font-weight: bold; }
.text-danger { color: #f56c6c; font-weight: bold; }

/* 与 UI 自动化套件一致的左右选择器样式 */
.case-selector {
  display: flex;
  gap: 20px;
  width: 100%;
}
.case-selector :deep(.el-table__row) {
  height: 44px;
}
.case-selector :deep(.el-table__cell) {
  padding-top: 6px !important;
  padding-bottom: 6px !important;
}
.selector-panel {
  flex: 1;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
}
.panel-header {
  background: #f5f7fa;
  padding: 12px 15px;
  border-bottom: 1px solid #dcdfe6;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-header h4 {
  margin: 0;
  font-size: 14px;
  color: #303133;
}
.panel-content {
  padding: 10px;
}
</style>
