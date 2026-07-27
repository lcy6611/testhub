<template>
  <div class="kb-library" v-loading="loading">
    <el-tabs v-model="activeTab" type="border-card">
      <!-- ===== Tab 1：知识库与外部数据源 ===== -->
      <el-tab-pane label="① 知识库与外部数据源" name="kb">
        <el-alert type="info" :closable="false" show-icon
          title="本页面管理「自建知识库」和「外部数据源」"
          description="外部数据源（飞书/Confluence/Notion）同步的内容会落到自建知识库内；之后 AI 用例生成/知识问答按项目自动选用。"
          style="margin-bottom: 16px"
        />

        <!-- 自建知识库 -->
        <div class="section-header">
          <h3>自建知识库</h3>
          <div>
            <el-button size="small" type="success" plain :loading="syncAllLoading" @click="handleSyncAllKg">
              🧠 一键同步全部到图谱
            </el-button>
            <el-button type="primary" size="small" @click="kbDialogVisible = true">+ 新建知识库</el-button>
          </div>
        </div>
        <el-table :data="nativeKbs" stripe v-loading="kbLoading">
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
          <el-table-column label="共享范围" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.is_global" size="small" type="warning">全局</el-tag>
              <el-tag v-else-if="row.project" size="small">项目专属</el-tag>
              <el-tag v-else size="small" type="info">私有</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status_display" label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 'published' ? 'success' : 'info'" size="small">{{ row.status_display }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="document_count" label="文档数" width="80" align="center" />
          <el-table-column prop="chunk_count" label="分块数" width="80" align="center" />
          <el-table-column label="图谱" width="80" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.document_count > 0 ? 'success' : 'info'">
                {{ row.document_count > 0 ? `${row.document_count}节点` : '空' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="280" align="center" :show-overflow-tooltip="false">
            <template #default="{ row }">
              <el-button size="small" type="success" plain @click="openKbGraph(row)">图谱</el-button>
              <el-button size="small" style="margin-left:2px" @click="$router.push({ path: '/configuration/knowledge-hub/documents', query: { kb: row.id } })">文档</el-button>
              <el-button size="small" style="margin-left:2px" @click="openEditKb(row)">编辑</el-button>
              <el-button v-if="row.status !== 'published'" size="small" type="primary" style="margin-left:2px" @click="handlePublish(row)">发布</el-button>
              <el-button v-else size="small" type="warning" plain style="margin-left:2px" @click="handleUnpublish(row)">取消</el-button>
              <el-popconfirm title="确定删除？" @confirm="handleDeleteKb(row.id)">
                <template #reference>
                  <el-button size="small" type="danger" style="margin-left:2px">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <!-- 外部数据源 -->
        <div class="section-header" style="margin-top: 24px">
          <h3>外部数据源（飞书 / Confluence / Notion）</h3>
          <el-button type="primary" size="small" @click="sourceDialogVisible = true">+ 新建数据源</el-button>
        </div>
        <el-table :data="kbSources" stripe v-loading="sourceLoading">
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column label="类型" width="120" align="center">
            <template #default="{ row }">
              <el-tag size="small">
                {{ row.external_type === 'feishu'
                  ? (row.feishu_mode === 'drive' ? '飞书·云盘' : '飞书·知识库')
                  : row.external_type === 'notion' ? 'Notion'
                  : row.external_type === 'confluence' ? 'Confluence'
                  : row.external_type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="同步状态" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="row.sync_status === 'success' ? 'success' : row.sync_status === 'failed' ? 'danger' : 'info'" size="small">
                {{ {pending:'未同步',syncing:'同步中',success:'成功',failed:'失败'}[row.sync_status] || row.sync_status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="doc_count" label="文档数" width="80" align="center" />
          <el-table-column prop="target_kb_name" label="目标知识库" min-width="140" show-overflow-tooltip />
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" :loading="row._syncing" @click="handleSyncSource(row)">同步</el-button>
              <el-popconfirm title="确定删除？" @confirm="handleDeleteSource(row.id)">
                <template #reference><el-button size="small" type="danger">删除</el-button></template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ===== Tab 2：Dify 知识库绑定 ===== -->
      <el-tab-pane label="② Dify 知识库绑定" name="dify">
        <el-alert type="info" :closable="false" show-icon
          title="把 Dify 数据集绑定到指定项目，AI 用例生成时按项目自动选用"
          description="绑定后，AI 用例生成「启用知识库」时：项目有 Dify 绑定 → 用 Dify；项目无 Dify 绑定 → 用本地 KB。"
          style="margin-bottom: 16px"
        />

        <el-form :inline="true" style="margin-bottom: 12px">
          <el-form-item label="查看项目绑定">
            <el-select v-model="bindingProject" filterable placeholder="选择项目查看已绑定" style="width: 280px" @change="loadBindings">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="small" @click="openBindingDialog()">+ 绑定 Dify 知识库</el-button>
          </el-form-item>
        </el-form>
        <el-table :data="difyBindings" stripe v-loading="bindingLoading">
          <el-table-column prop="dataset_name" label="数据集名称" min-width="200" />
          <el-table-column prop="dataset_id" label="数据集 ID" min-width="220" show-overflow-tooltip />
          <el-table-column prop="document_count" label="文档数" width="90" align="center" />
          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-popconfirm title="确定解除绑定？" @confirm="handleUnbind(row.id)">
                <template #reference><el-button size="small" type="danger">解绑</el-button></template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="bindingProject && !difyBindings.length" description="该项目尚未绑定任何 Dify 知识库" />
        <el-empty v-if="!bindingProject" description="请选择项目查看已绑定的 Dify 知识库" />
      </el-tab-pane>
    </el-tabs>

    <!-- 新建外部数据源弹窗 -->
    <el-dialog v-model="sourceDialogVisible" title="新建外部数据源" width="520px">
      <el-form :model="newSource" label-width="110px">
        <el-form-item label="名称" required><el-input v-model="newSource.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="newSource.external_type" style="width:200px" @change="onSourceTypeChange">
            <el-option label="飞书" value="feishu" />
            <el-option label="Notion" value="notion" />
            <el-option label="Confluence" value="confluence" />
          </el-select>
        </el-form-item>
        <template v-if="newSource.external_type === 'feishu'">
          <el-form-item label="接入方式">
            <el-radio-group v-model="newSource.feishu_mode">
              <el-radio label="wiki">知识库（Wiki）</el-radio>
              <el-radio label="drive">云盘（云文档）</el-radio>
            </el-radio-group>
            <div class="hint">知识库=Wiki 空间文档；云盘=云空间文件（docx/表格/多维表格/上传文件）</div>
          </el-form-item>
          <el-form-item label="云盘根目录" v-if="newSource.feishu_mode === 'drive'">
            <el-input v-model="newSource.feishu_root_folder_token" placeholder="可选；留空则从「我的空间」根目录开始遍历" />
          </el-form-item>
          <el-form-item label="App ID"><el-input v-model="newSource.app_id" placeholder="飞书开放平台应用的 App ID" /></el-form-item>
          <el-form-item label="App Secret"><el-input v-model="newSource.app_secret" show-password placeholder="飞书应用 App Secret" /></el-form-item>
          <el-form-item label="Tenant Key"><el-input v-model="newSource.tenant_key" placeholder="可选" /></el-form-item>
          <el-form-item label="API 地址"><el-input v-model="newSource.base_url" placeholder="https://open.feishu.cn" /></el-form-item>
        </template>
        <template v-if="newSource.external_type === 'notion'">
          <el-form-item label="Integration Token" required>
            <el-input v-model="newSource.app_secret" show-password placeholder="secret_xxx... 或 ntn_xxx..." />
          </el-form-item>
          <el-form-item label="根页面 ID">
            <el-input v-model="newSource.app_id" placeholder="可选；留空同步整个 workspace" />
          </el-form-item>
          <el-form-item label="API 地址">
            <el-input v-model="newSource.base_url" placeholder="https://api.notion.com" />
          </el-form-item>
        </template>
        <template v-if="newSource.external_type === 'confluence'">
          <el-form-item label="Cloud 站点 URL" required>
            <el-input v-model="newSource.app_id" placeholder="https://your-domain.atlassian.net/wiki" />
            <div class="hint">必填：Confluence Cloud 站点完整 URL（含 /wiki 后缀）</div>
          </el-form-item>
          <el-form-item label="邮箱:API Token" required>
            <el-input v-model="newSource.app_secret" show-password placeholder="user@example.com:ATATT3x..." />
            <div class="hint">
              API Token 在 <el-link href="https://id.atlassian.com/manage-profile/security/api-tokens" target="_blank" type="primary">Atlassian 账户中心</el-link> 生成；
              此处填入 <code>邮箱:Token</code>（中间英文冒号）。
            </div>
          </el-form-item>
          <el-form-item label="限定 Space Key">
            <el-input v-model="newSource.tenant_key" placeholder="可选；留空同步所有空间" />
            <div class="hint">如只要同步某个空间，填其 Key（在 Space 列表页 URL 里能看到）</div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sourceCreating" @click="handleCreateSource">创建</el-button>
      </template>
    </el-dialog>

    <!-- 新建/编辑知识库弹窗 -->
    <el-dialog v-model="kbDialogVisible" :title="editKbId ? '编辑知识库' : '新建知识库'" width="540px">
      <el-form :model="newKb" label-width="110px">
        <el-form-item label="名称" required><el-input v-model="newKb.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="newKb.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="全局共享">
          <el-switch v-model="newKb.is_global" active-text="对所有项目可见" inactive-text="仅指定项目" />
          <div class="hint">开启后该知识库对所有项目可用；关闭后可指定共享给若干项目（跨项目复用）</div>
        </el-form-item>
        <el-form-item label="绑定项目" v-if="!newKb.is_global">
          <el-select v-model="newKb.shared_project_ids" multiple filterable placeholder="可选：额外共享给指定项目" style="width:100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kbDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="kbCreating" @click="handleCreateKb">{{ editKbId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- Dify 知识库绑定弹窗 -->
    <el-dialog v-model="bindingDialogVisible" title="绑定 Dify 知识库到项目" width="720px">
      <el-form :inline="true" style="margin-bottom: 12px">
        <el-form-item label="项目" required>
          <el-select v-model="bindProject" filterable placeholder="选择项目" style="width: 280px" @change="loadAvailable">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <el-table :data="difyAvailable" stripe v-loading="availableLoading" max-height="420">
        <el-table-column prop="name" label="数据集名称" min-width="200" />
        <el-table-column prop="document_count" label="文档数" width="90" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.bound ? 'success' : 'info'" size="small">{{ row.bound ? '已绑定' : '未绑定' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button v-if="!row.bound" size="small" type="primary" :loading="row._binding" @click="handleBind(row)">绑定</el-button>
            <el-button v-else size="small" type="danger" :loading="row._binding" @click="handleUnbind(row.bound_id)">解绑</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!availableLoading && bindProject && !difyAvailable.length" description="该 Dify 配置下暂无数据集" />
    </el-dialog>

    <!-- KB 知识图谱弹窗 -->
    <KbGraphDialog v-model="graphDialogVisible" :kb-id="graphKbId" :kb-name="graphKbName" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import {
  getNativeKbs, createNativeKb, updateNativeKb, deleteNativeKb, publishNativeKb, unpublishNativeKb,
  getKbSources, createKbSource, deleteKbSource, syncKbSource,
  getDifyBindings, bindDifyKb, unbindDifyKb, getDifyAvailableDatasets,
  syncAllNativeKbsToKg,
} from '@/api/kb-hub'
import KbGraphDialog from './KbGraphDialog.vue'

const loading = ref(false)
const activeTab = ref('kb')
const projects = ref([])

const nativeKbs = ref([])
const kbLoading = ref(false)
const kbDialogVisible = ref(false)
const editKbId = ref(null)
const newKb = reactive({ name: '', description: '', is_global: false, shared_project_ids: [] })
const kbCreating = ref(false)

const kbSources = ref([])
const sourceLoading = ref(false)
const sourceDialogVisible = ref(false)
const newSource = reactive({
  name: '', external_type: 'feishu', feishu_mode: 'wiki', feishu_root_folder_token: '',
  app_id: '', app_secret: '',
  tenant_key: '', base_url: 'https://open.feishu.cn',
})
const sourceCreating = ref(false)

const bindingProject = ref('')
const difyBindings = ref([])
const bindingLoading = ref(false)
const bindingDialogVisible = ref(false)
const bindProject = ref('')
const difyAvailable = ref([])
const availableLoading = ref(false)

// KB 图谱弹窗
const graphDialogVisible = ref(false)
const graphKbId = ref(null)
const graphKbName = ref('')
const syncAllLoading = ref(false)

const loadProjects = async () => {
  try { projects.value = (await api.get('/projects/')).data?.results || [] } catch {}
}
const loadNativeKbs = async () => {
  kbLoading.value = true
  try { nativeKbs.value = (await getNativeKbs({ page_size: 200 })).data?.results || [] }
  finally { kbLoading.value = false }
}
const loadKbSources = async () => {
  sourceLoading.value = true
  try { kbSources.value = (await getKbSources({ page_size: 200 })).data?.results || [] }
  finally { sourceLoading.value = false }
}

const onSourceTypeChange = (val) => {
  if (val === 'feishu') {
    newSource.base_url = 'https://open.feishu.cn'
  } else if (val === 'notion') {
    newSource.base_url = 'https://api.notion.com'
    newSource.tenant_key = ''
    newSource.feishu_mode = 'wiki'
    newSource.feishu_root_folder_token = ''
  } else if (val === 'confluence') {
    newSource.base_url = ''
    newSource.feishu_mode = 'wiki'
    newSource.feishu_root_folder_token = ''
    newSource.app_id = ''
  }
}

const handleCreateKb = async () => {
  if (!newKb.name) { ElMessage.warning('请输入名称'); return }
  kbCreating.value = true
  try {
    if (editKbId.value) {
      await updateNativeKb(editKbId.value, { ...newKb })
      ElMessage.success('已保存')
    } else {
      await createNativeKb({ ...newKb })
      ElMessage.success('创建成功')
    }
    kbDialogVisible.value = false
    editKbId.value = null
    Object.assign(newKb, { name: '', description: '', is_global: false, shared_project_ids: [] })
    await loadNativeKbs()
  } finally { kbCreating.value = false }
}
const openEditKb = (row) => {
  editKbId.value = row.id
  Object.assign(newKb, {
    name: row.name,
    description: row.description || '',
    is_global: !!row.is_global,
    shared_project_ids: [...(row.shared_projects || [])],
  })
  kbDialogVisible.value = true
}
const handleDeleteKb = async (id) => {
  await deleteNativeKb(id)
  ElMessage.success('已删除')
  await loadNativeKbs()
}
const handlePublish = async (row) => {
  await publishNativeKb(row.id)
  ElMessage.success('已发布（AI 检索可用）')
  await loadNativeKbs()
}
const handleUnpublish = async (row) => {
  await unpublishNativeKb(row.id)
  ElMessage.success('已取消发布（退回草稿）')
  await loadNativeKbs()
}

const openKbGraph = (row) => {
  graphKbId.value = row.id
  graphKbName.value = row.name
  graphDialogVisible.value = true
}

const handleSyncAllKg = async () => {
  try {
    await ElMessageBox.confirm('将把所有自建知识库（KB+文档）同步写入知识图谱。是否继续？', '一键同步到图谱', { type: 'warning' })
  } catch { return }
  syncAllLoading.value = true
  try {
    const { data } = await syncAllNativeKbsToKg()
    ElMessage.success(`同步完成：共 ${data?.synced ?? 0} 个 KB 写入图谱`)
  } catch (e) {
    ElMessage.error('同步失败：' + (e?.response?.data?.detail || e?.message))
  } finally {
    syncAllLoading.value = false
  }
}

const handleCreateSource = async () => {
  if (!newSource.name) { ElMessage.warning('请填写名称'); return }
  if (newSource.external_type === 'feishu' && (!newSource.app_id || !newSource.app_secret)) {
    ElMessage.warning('请填写飞书 App ID / App Secret'); return
  }
  if (newSource.external_type === 'notion' && !newSource.app_secret) {
    ElMessage.warning('请填写 Notion Integration Token'); return
  }
  if (newSource.external_type === 'confluence' && (!newSource.app_id || !newSource.app_secret)) {
    ElMessage.warning('请填写 Confluence 站点 URL 和「邮箱:API Token」'); return
  }
  sourceCreating.value = true
  try {
    await createKbSource(newSource)
    ElMessage.success('创建成功')
    sourceDialogVisible.value = false
    Object.assign(newSource, { name: '', external_type: 'feishu', feishu_mode: 'wiki', feishu_root_folder_token: '', app_id: '', app_secret: '', tenant_key: '', base_url: 'https://open.feishu.cn' })
    await loadKbSources()
  } finally { sourceCreating.value = false }
}
const handleDeleteSource = async (id) => {
  await deleteKbSource(id)
  ElMessage.success('已删除')
  await loadKbSources()
}
const handleSyncSource = async (row) => {
  row._syncing = true
  try {
    const res = await syncKbSource(row.id)
    if (res.data?.ok) {
      ElMessage.success(`同步完成: 文档 ${res.data.doc_count} 失败 ${res.data.failed_count}`)
    } else {
      ElMessage.error(res.data?.error || '同步失败')
    }
    await loadKbSources()
  } catch (e) { ElMessage.error('同步失败: ' + (e?.response?.data?.detail || e?.message)) }
  finally { row._syncing = false }
}

const loadBindings = async () => {
  if (!bindingProject.value) { difyBindings.value = []; return }
  bindingLoading.value = true
  try { difyBindings.value = (await getDifyBindings(bindingProject.value)).data || [] }
  finally { bindingLoading.value = false }
}

const openBindingDialog = async () => {
  bindingDialogVisible.value = true
  bindProject.value = bindingProject.value || (projects.value[0]?.id || '')
  await loadAvailable()
}

const loadAvailable = async () => {
  if (!bindProject.value) { difyAvailable.value = []; return }
  availableLoading.value = true
  try {
    const res = await getDifyAvailableDatasets(bindProject.value)
    difyAvailable.value = res.data?.data || []
  } catch (e) {
    ElMessage.error('加载 Dify 数据集失败: ' + (e?.response?.data?.detail || e?.message))
    difyAvailable.value = []
  } finally { availableLoading.value = false }
}

const handleBind = async (row) => {
  if (!bindProject.value) { ElMessage.warning('请先选择项目'); return }
  row._binding = true
  try {
    await bindDifyKb({
      project: bindProject.value,
      dataset_id: row.id,
      dataset_name: row.name,
      document_count: row.document_count || 0,
    })
    ElMessage.success('已绑定')
    await loadAvailable()
    if (bindingProject.value === bindProject.value) await loadBindings()
  } catch (e) {
    ElMessage.error('绑定失败: ' + (e?.response?.data?.detail || e?.message))
  } finally { row._binding = false }
}

const handleUnbind = async (id) => {
  if (!id) return
  try {
    await unbindDifyKb(id)
    ElMessage.success('已解绑')
    await loadAvailable()
    await loadBindings()
  } catch (e) { ElMessage.error('解绑失败: ' + (e?.response?.data?.detail || e?.message)) }
}

onMounted(async () => {
  loading.value = true
  await Promise.all([loadProjects(), loadNativeKbs(), loadKbSources()])
  loading.value = false
})
</script>

<style scoped>
.kb-library { padding: 16px; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.section-header h3 { margin: 0; font-size: 16px; color: #303133; }
.hint { color: #909399; font-size: 12px; line-height: 1.5; margin-top: 4px; }
</style>