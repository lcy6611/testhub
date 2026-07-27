<template>
  <div class="kb-documents" v-loading="loading">
    <el-alert type="info" :closable="false" show-icon
      title="文档管理：支持文件上传 / 文档级多项目共享 / 一键抽取"
      description="上传文档后会进入解析 → 分块 → Embedding 流程；可设置文档级多项目绑定（与 KB 级共享并行生效）。"
      style="margin-bottom: 16px"
    />

    <el-card>
      <template #header>
        <div class="card-header">
          <div>
            <el-select v-model="filterProject" placeholder="按项目筛选（不选看全部文档）" clearable filterable style="width: 240px; margin-right: 8px" @change="onFilterChange">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
            <el-select v-model="filterKb" placeholder="选择知识库" clearable filterable style="width: 240px" @change="loadDocuments">
              <el-option v-for="kb in filteredKbs" :key="kb.id" :label="kb.name" :value="kb.id" />
            </el-select>
          </div>
          <div>
            <el-upload :show-file-list="false" :before-upload="handleUploadDoc" accept=".txt,.md,.pdf,.docx,.doc" :disabled="!filterKb">
              <el-button type="primary" :disabled="!filterKb">上传文档</el-button>
            </el-upload>
          </div>
        </div>
      </template>

      <el-table :data="documents" stripe v-loading="docLoading">
        <el-table-column prop="title" label="文档标题" min-width="220" />
        <el-table-column prop="kb_name" label="所属知识库" min-width="140" />
        <el-table-column prop="source_type_display" label="来源" width="100" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'parsed' ? 'success' : row.status === 'failed' ? 'danger' : 'info'" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="word_count" label="字数" width="80" align="center" />
        <el-table-column label="共享项目" min-width="180">
          <template #default="{ row }">
            <el-tag v-for="pid in row.shared_projects" :key="pid" size="small" type="info" style="margin-right: 4px">
              {{ projectName(pid) }}
            </el-tag>
            <span v-if="!row.shared_projects?.length" class="text-muted">仅归属 KB</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" :loading="row._ingesting" @click="handleIngest(row)">入库</el-button>
            <el-button size="small" @click="handleReindex(row)">重建</el-button>
            <el-button size="small" @click="openShareDialog(row)">共享…</el-button>
            <el-button size="small" type="danger" @click="handleDeleteDoc(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 共享项目弹窗 -->
    <el-dialog v-model="shareDialogVisible" title="文档级多项目共享" width="540px">
      <p class="dialog-hint">
        文档 <strong>{{ shareDoc?.title }}</strong> 所属 KB：{{ shareDoc?.kb_name }}。
        下列项目在 AI 用例生成时也会检索到本文档（与 KB 级共享并行生效）。
      </p>
      <el-select v-model="shareProjectIds" multiple filterable placeholder="选择要共享的项目" style="width:100%">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <template #footer>
        <el-button @click="shareDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="shareSaving" @click="handleSaveShare">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import {
  getNativeKbs, getNativeKbDocuments, getNativeKbAllDocuments,
  uploadNativeDoc, deleteNativeDoc, ingestNativeDoc, reindexNativeDoc, clearNativeDocChunks,
  updateNativeDoc,
} from '@/api/kb-hub'

const loading = ref(false)
const projects = ref([])
const allKbs = ref([])
const documents = ref([])
const docLoading = ref(false)

const filterProject = ref(null)
const filterKb = ref(null)

const filteredKbs = computed(() => {
  if (!filterProject.value) return allKbs.value
  // 项目筛选：直接归属 + 全局共享 + 显式绑定
  return allKbs.value.filter(kb => {
    if (kb.is_global) return true
    if (String(kb.project) === String(filterProject.value)) return true
    if (kb.shared_projects?.includes(filterProject.value)) return true
    return false
  })
})

const shareDialogVisible = ref(false)
const shareDoc = ref(null)
const shareProjectIds = ref([])
const shareSaving = ref(false)

const loadProjects = async () => {
  try { projects.value = (await api.get('/projects/')).data?.results || [] } catch {}
}
const loadKbs = async () => {
  try { allKbs.value = (await getNativeKbs({ page_size: 500 })).data?.results || [] }
  catch {}
}
const loadDocuments = async () => {
  docLoading.value = true
  try {
    if (filterKb.value) {
      documents.value = (await getNativeKbDocuments(filterKb.value)).data?.data || []
    } else {
      // 不选项目也不选 KB：看全站；只选项目：看该项目可见 KB 下的全部文档
      const params = filterProject.value ? { project: filterProject.value } : {}
      documents.value = (await getNativeKbAllDocuments(params)).data?.data || []
    }
  } finally { docLoading.value = false }
}
const onFilterChange = () => {
  filterKb.value = null
  loadDocuments()
}

const projectName = (pid) => projects.value.find(p => p.id === pid)?.name || `项目${pid}`

const handleUploadDoc = async (file) => {
  if (!filterKb.value) { ElMessage.warning('请先选择知识库'); return false }
  const fd = new FormData()
  fd.append('kb', filterKb.value)
  fd.append('file', file)
  try { await uploadNativeDoc(fd); ElMessage.success('上传成功'); await loadDocuments() }
  catch (e) { ElMessage.error('上传失败') }
  return false
}
const handleIngest = async (row) => {
  row._ingesting = true
  try { await ingestNativeDoc(row.id); ElMessage.success('已触发入库'); await loadDocuments() }
  catch (e) { ElMessage.error('入库失败') }
  finally { row._ingesting = false }
}
const handleReindex = async (row) => {
  try { await clearNativeDocChunks(row.id); await reindexNativeDoc(row.id); ElMessage.success('已重建'); await loadDocuments() }
  catch (e) { ElMessage.error('重建失败') }
}
const handleDeleteDoc = async (id) => {
  try { await ElMessageBox.confirm('确定删除该文档？此操作不可恢复', '确认', { type: 'warning' }) }
  catch { return }
  await deleteNativeDoc(id)
  ElMessage.success('已删除')
  await loadDocuments()
}

const openShareDialog = (row) => {
  shareDoc.value = row
  shareProjectIds.value = [...(row.shared_projects || [])]
  shareDialogVisible.value = true
}
const handleSaveShare = async () => {
  shareSaving.value = true
  try {
    await updateNativeDoc(shareDoc.value.id, { shared_project_ids: shareProjectIds.value })
    ElMessage.success('已保存共享设置')
    shareDialogVisible.value = false
    await loadDocuments()
  } catch (e) { ElMessage.error('保存失败') }
  finally { shareSaving.value = false }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([loadProjects(), loadKbs()])
  loading.value = false
})
</script>

<style scoped>
.kb-documents { padding: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
.dialog-hint { color: #606266; line-height: 1.6; margin: 0 0 12px; }
.text-muted { color: #c0c4cc; font-size: 12px; }
</style>