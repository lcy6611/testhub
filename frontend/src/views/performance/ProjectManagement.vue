<template>
  <div class="perf-project-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>性能测试项目管理</span>
          <el-button type="primary" @click="loadProjects">
            <el-icon><Refresh /></el-icon>刷新
          </el-button>
        </div>
      </template>

      <el-alert
        title="关联说明"
        type="info"
        :closable="false"
        description="需要在「配置中心 - 项目管理」中编辑项目，绑定「性能测试」模块后，才能在脚本编排中关联该项目。脚本支持多项目复用。"
        style="margin-bottom: 16px"
      />

      <el-table :data="projects" v-loading="loading" stripe border>
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column prop="description" label="描述" min-width="240" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status === 'active' ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="openRelDialog(row)">
              <el-icon><Connection /></el-icon>关联脚本
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 关联脚本弹窗 -->
    <el-dialog
      v-model="relDialogVisible"
      :title="`关联脚本 - ${currentProject?.name || ''}`"
      width="820px"
      :close-on-click-modal="false"
      @opened="onDialogOpened"
    >
      <el-alert
        title="使用说明"
        type="info"
        :closable="false"
        description="列表展示该项目下已关联的所有性能测试脚本。默认全部勾选 → 点击「执行」即批量执行；取消勾选的脚本仍保持关联，只是本次不执行。点击行尾「解绑」可解除该脚本与本项目的关联。"
        style="margin-bottom: 12px"
      />

      <!-- 工具栏 -->
      <div class="toolbar">
        <div class="toolbar-left">
          <el-checkbox
            v-model="selectAllChecked"
            :indeterminate="selectAllIndeterminate"
            @change="onSelectAllChange"
          >
            全选
          </el-checkbox>
          <el-button link size="small" @click="invertSelection">反选</el-button>
          <span class="stat">已勾选 <b>{{ selectedScripts.length }}</b> / {{ projectScripts.length }}</span>
          <el-divider direction="vertical" />
          <el-button type="primary" size="small" @click="openAddDialog">
            <el-icon><Plus /></el-icon>添加脚本
          </el-button>
        </div>
        <div class="toolbar-right">
          <el-input
            v-model="scriptFilter"
            size="small"
            placeholder="搜索脚本名称"
            clearable
            style="width: 200px"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </div>

      <el-table
        ref="scriptTableRef"
        :data="filteredScripts"
        v-loading="relLoading"
        stripe
        border
        height="420"
        @selection-change="handleSelectionChange"
        row-key="id"
      >
        <el-table-column type="selection" width="48" :reserve-selection="false" />
        <el-table-column prop="name" label="脚本名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="script_type_display" label="模式" width="100" align="center" />
        <el-table-column prop="thread_count" label="默认线程" width="90" align="center" />
        <el-table-column prop="duration" label="默认持续(s)" width="110" align="center" />
        <el-table-column label="所属项目" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag
              v-for="(pn, i) in row.project_names || []"
              :key="i"
              size="small"
              :type="pn === currentProject?.name ? 'success' : 'info'"
              effect="light"
              style="margin-right: 4px; margin-bottom: 2px"
            >
              {{ pn }}
            </el-tag>
            <span v-if="!row.project_names?.length" style="color:#c0c4cc">未关联</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="danger"
              size="small"
              :loading="unbindingId === row.id"
              @click="handleUnbind(row)"
            >解绑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!relLoading && filteredScripts.length === 0" style="text-align: center; padding: 24px; color: #909399;">
        <span v-if="!projectScripts.length">该项目暂无关联的性能测试脚本，请到「脚本编排」中勾选该项目保存</span>
        <span v-else>没有匹配的脚本</span>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <span class="footer-hint">
            <el-icon><InfoFilled /></el-icon>
            已勾选 <b style="color:#409EFF">{{ selectedScripts.length }}</b> 个脚本，点击「执行」仅执行勾选项
          </span>
          <div>
            <el-button @click="relDialogVisible = false">关闭</el-button>
            <el-button
              type="success"
              :disabled="selectedScripts.length === 0"
              :loading="executing"
              @click="handleExecuteSelected"
            >
              <el-icon><VideoPlay /></el-icon>
              执行勾选脚本（{{ selectedScripts.length }}）
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 添加脚本弹窗 -->
    <el-dialog
      v-model="addDialogVisible"
      :title="`添加脚本到项目 - ${currentProject?.name || ''}`"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-alert
        title="使用说明"
        type="info"
        :closable="false"
        description="选择要加入该项目的脚本，可多选。已关联的脚本不会出现在列表中。"
        style="margin-bottom: 12px"
      />

      <div class="toolbar">
        <div class="toolbar-left">
          <span class="stat">已选择 <b>{{ selectedAddScripts.length }}</b> 个脚本</span>
        </div>
        <div class="toolbar-right">
          <el-input
            v-model="addScriptFilter"
            size="small"
            placeholder="搜索脚本名称"
            clearable
            style="width: 200px"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </div>

      <el-table
        ref="addTableRef"
        :data="filteredAddScripts"
        v-loading="addLoading"
        stripe
        border
        height="360"
        @selection-change="handleAddSelectionChange"
        row-key="id"
      >
        <el-table-column type="selection" width="48" :reserve-selection="false" />
        <el-table-column prop="name" label="脚本名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="script_type_display" label="模式" width="100" align="center" />
        <el-table-column prop="thread_count" label="默认线程" width="90" align="center" />
        <el-table-column prop="duration" label="默认持续(s)" width="110" align="center" />
        <el-table-column label="所属项目" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag
              v-for="(pn, i) in row.project_names || []"
              :key="i"
              size="small"
              type="info"
              effect="light"
              style="margin-right: 4px; margin-bottom: 2px"
            >
              {{ pn }}
            </el-tag>
            <span v-if="!row.project_names?.length" style="color:#c0c4cc">未关联</span>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!addLoading && filteredAddScripts.length === 0" style="text-align: center; padding: 24px; color: #909399;">
        暂无未关联的性能测试脚本
      </div>

      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="selectedAddScripts.length === 0"
          :loading="adding"
          @click="handleConfirmAdd"
        >
          确认添加（{{ selectedAddScripts.length }}）
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, VideoPlay, Connection, Search, InfoFilled, Plus } from '@element-plus/icons-vue'
import {
  getProjects,
  getScripts,
  createBatchExecution,
  updateScript,
} from '@/api/performance'

const router = useRouter()
const projects = ref([])
const loading = ref(false)

const relDialogVisible = ref(false)
const relLoading = ref(false)
const currentProject = ref(null)
const projectScripts = ref([])
const selectedScripts = ref([])
const executing = ref(false)
const unbindingId = ref(null)
const scriptTableRef = ref(null)

const scriptFilter = ref('')

const addDialogVisible = ref(false)
const addLoading = ref(false)
const addDialogProject = ref(null)
const allScripts = ref([])
const selectedAddScripts = ref([])
const adding = ref(false)
const addTableRef = ref(null)
const addScriptFilter = ref('')

const filteredAddScripts = computed(() => {
  const currentId = addDialogProject.value?.id
  const already = new Set(projectScripts.value.map(s => s.id))
  let list = allScripts.value.filter(s => !already.has(s.id))
  if (currentId) {
    list = list.filter(s => !(s.projects || []).includes(currentId))
  }
  if (!addScriptFilter.value) return list
  const kw = addScriptFilter.value.toLowerCase()
  return list.filter(s => (s.name || '').toLowerCase().includes(kw))
})

// 全选状态
const selectAllChecked = ref(false)
const selectAllIndeterminate = ref(false)

const filteredScripts = computed(() => {
  if (!scriptFilter.value) return projectScripts.value
  const kw = scriptFilter.value.toLowerCase()
  return projectScripts.value.filter(s => (s.name || '').toLowerCase().includes(kw))
})

const formatTime = (val) => val ? new Date(val).toLocaleString('zh-CN', { hour12: false }) : '-'

async function loadProjects() {
  loading.value = true
  try {
    const res = await getProjects()
    projects.value = res.data?.results || res.data || []
  } catch (e) {
    ElMessage.error('加载项目失败')
  } finally {
    loading.value = false
  }
}

async function openRelDialog(row) {
  currentProject.value = row
  relDialogVisible.value = true
  relLoading.value = true
  selectedScripts.value = []
  selectAllChecked.value = false
  selectAllIndeterminate.value = false
  scriptFilter.value = ''
  try {
    const res = await getScripts({ project: row.id, page_size: 999 })
    projectScripts.value = res.data?.results || res.data || []
  } catch (e) {
    ElMessage.error('加载脚本失败')
  } finally {
    relLoading.value = false
  }
}

// 弹窗打开后默认全选
async function onDialogOpened() {
  await nextTick()
  if (projectScripts.value.length && scriptTableRef.value) {
    // 逐行 toggleSelect 以触发 @selection-change
    projectScripts.value.forEach(row => {
      scriptTableRef.value.toggleRowSelection(row, true)
    })
  }
}

function handleSelectionChange(selection) {
  selectedScripts.value = selection
  const total = filteredScripts.value.length
  const selected = selection.length
  if (selected === 0) {
    selectAllChecked.value = false
    selectAllIndeterminate.value = false
  } else if (selected === total) {
    selectAllChecked.value = true
    selectAllIndeterminate.value = false
  } else {
    selectAllChecked.value = false
    selectAllIndeterminate.value = true
  }
}

function onSelectAllChange(val) {
  if (!scriptTableRef.value) return
  if (val) {
    filteredScripts.value.forEach(row => {
      scriptTableRef.value.toggleRowSelection(row, true)
    })
  } else {
    filteredScripts.value.forEach(row => {
      scriptTableRef.value.toggleRowSelection(row, false)
    })
  }
}

function invertSelection() {
  if (!scriptTableRef.value) return
  const currentSelected = new Set(selectedScripts.value.map(s => s.id))
  filteredScripts.value.forEach(row => {
    scriptTableRef.value.toggleRowSelection(row, !currentSelected.has(row.id))
  })
}

async function handleUnbind(row) {
  try {
    await ElMessageBox.confirm(
      `确认解除脚本「${row.name}」与项目「${currentProject.value?.name}」的关联？该脚本将不再在本项目下展示，但脚本本身不会被删除。`,
      '解绑确认',
      { type: 'warning', confirmButtonText: '解绑', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  unbindingId.value = row.id
  try {
    // 取当前脚本的所属项目列表，过滤掉当前项目
    const newProjects = (row.projects || []).filter(pid => pid !== currentProject.value.id)
    const fd = new FormData()
    // 与 ScriptEditor.handleSave 保持一致：append 多次而非 JSON 字符串
    newProjects.forEach(pid => fd.append('projects', String(pid)))
    await updateScript(row.id, fd)
    ElMessage.success('已解绑')
    // 刷新列表
    projectScripts.value = projectScripts.value.filter(s => s.id !== row.id)
    selectedScripts.value = selectedScripts.value.filter(s => s.id !== row.id)
    if (scriptTableRef.value) {
      scriptTableRef.value.clearSelection()
    }
    // 重新设置全选
    await nextTick()
    projectScripts.value.forEach(r => {
      scriptTableRef.value?.toggleRowSelection(r, true)
    })
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '解绑失败')
  } finally {
    unbindingId.value = null
  }
}

async function handleExecuteSelected() {
  if (selectedScripts.value.length === 0) {
    ElMessage.warning('请至少勾选一个脚本')
    return
  }
  executing.value = true
  try {
    const data = {
      project: currentProject.value?.id,
      script_ids: selectedScripts.value.map(s => s.id),
      name: `${currentProject.value?.name || ''}-批量执行-${selectedScripts.value.length}个脚本`,
    }
    const res = await createBatchExecution(data)
    ElMessage.success(`批量执行已创建，包含 ${data.script_ids.length} 个脚本`)
    relDialogVisible.value = false
    router.push(`/performance-testing/batch-executions/${res.data.id}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建批量执行失败')
  } finally {
    executing.value = false
  }
}

async function openAddDialog() {
  addDialogProject.value = currentProject.value
  addDialogVisible.value = true
  addLoading.value = true
  allScripts.value = []
  selectedAddScripts.value = []
  addScriptFilter.value = ''
  try {
    const res = await getScripts({ page_size: 999 })
    allScripts.value = res.data?.results || res.data || []
  } catch (e) {
    ElMessage.error('加载脚本失败')
  } finally {
    addLoading.value = false
  }
}

function handleAddSelectionChange(selection) {
  selectedAddScripts.value = selection
}

async function handleConfirmAdd() {
  if (selectedAddScripts.value.length === 0) {
    ElMessage.warning('请至少选择一个脚本')
    return
  }
  adding.value = true
  try {
    const projectId = addDialogProject.value?.id
    if (!projectId) {
      ElMessage.warning('当前项目信息缺失')
      return
    }
    await Promise.all(
      selectedAddScripts.value.map(async (script) => {
        const newProjects = Array.from(new Set([...(script.projects || []), projectId]))
        const fd = new FormData()
        newProjects.forEach(pid => fd.append('projects', String(pid)))
        return updateScript(script.id, fd)
      })
    )
    ElMessage.success(`成功添加 ${selectedAddScripts.value.length} 个脚本到项目`)
    addDialogVisible.value = false
    // 刷新当前项目关联列表
    await openRelDialog(currentProject.value)
    await nextTick()
    // 默认全选新列表
    projectScripts.value.forEach(row => {
      scriptTableRef.value?.toggleRowSelection(row, true)
    })
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '添加脚本失败')
  } finally {
    adding.value = false
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding: 6px 0;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.toolbar-left .stat {
  color: #606266;
  font-size: 13px;
}
.toolbar-left .stat b {
  color: #409EFF;
}
.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.footer-hint {
  color: #909399;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
