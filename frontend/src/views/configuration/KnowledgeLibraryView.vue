<template>
  <div class="kb-library" v-loading="loading">
    <!-- 自建知识库 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span>自建知识库</span>
          <el-button type="primary" size="small" @click="kbDialogVisible = true">+ 新建知识库</el-button>
        </div>
      </template>
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
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="openDocManager(row)">文档</el-button>
            <el-button v-if="row.status !== 'published'" size="small" type="success" @click="handlePublish(row)">发布</el-button>
            <el-popconfirm title="确定删除？" @confirm="handleDeleteKb(row.id)">
              <template #reference><el-button size="small" type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 外部数据源（飞书等 SaaS 知识库） -->
    <el-card style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>外部数据源（飞书等）</span>
          <el-button type="primary" size="small" @click="sourceDialogVisible = true">+ 新建数据源</el-button>
        </div>
      </template>
      <div class="hint" style="margin-bottom: 12px">外部数据源内容会同步到自建知识库；之后在「AI 用例生成」选择项目时即可选用。</div>
      <el-table :data="kbSources" stripe v-loading="sourceLoading">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column label="类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small">
              {{ row.external_type === 'feishu'
                ? (row.feishu_mode === 'drive' ? '飞书·云盘' : '飞书·知识库')
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
    </el-card>

    <!-- Dify 知识库绑定（按项目） -->
    <el-card v-if="kbHubStore.defaultEngine === 'dify'" style="margin-top: 16px">
      <template #header>
        <div class="card-header">
          <span>Dify 知识库绑定（按项目）</span>
          <el-tag size="small" type="success">🔒 当前引擎生效中</el-tag>
          <el-button type="primary" size="small" @click="openBindingDialog()">+ 绑定知识库</el-button>
        </div>
      </template>
      <el-alert
        type="info" :closable="false" show-icon
        style="margin-bottom: 12px"
        title="本区块由「知识中枢配置」的引擎开关自动决定显示/隐藏"
        description="当前生效引擎为 Dify 知识库，因此此处可绑定 Dify 数据集。仅当引擎切回自建时本区块才会隐藏。引擎切换请到「知识中枢配置」页操作。"
      />
      <div class="hint" style="margin-bottom: 12px">
        将 Dify 中的数据集绑定到项目后，在「AI 用例生成」选择该项目时即可勾选对应的 Dify 知识库（解决「启用知识库」一直显示未配置的问题）。
      </div>
      <el-form :inline="true" style="margin-bottom: 12px">
        <el-form-item label="项目">
          <el-select v-model="bindingProject" filterable placeholder="选择项目查看已绑定" style="width: 280px" @change="loadBindings">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
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
    </el-card>

    <!-- 引擎为自建时，Dify 绑定不生效的提示 -->
    <el-card v-else style="margin-top: 16px">
      <el-alert
        type="warning" :closable="false" show-icon
        :title="`🔒 当前生效引擎：${kbHubStore.engineDisplay}，Dify 绑定暂不可用`"
        description="「知识中枢配置」的引擎开关当前为自建知识中枢，因此 Dify 绑定区已自动隐藏。Dify 知识库绑定不会参与 AI 用例生成。如需使用 Dify 知识库，请前往「知识中枢配置」将引擎切换为 Dify。"
      />
    </el-card>

    <!-- 新建外部数据源弹窗 -->
    <el-dialog v-model="sourceDialogVisible" title="新建外部数据源" width="520px">
      <el-form :model="newSource" label-width="110px">
        <el-form-item label="名称" required><el-input v-model="newSource.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="newSource.external_type" style="width:200px" @change="onSourceTypeChange">
            <el-option label="飞书" value="feishu" />
            <el-option label="Notion" value="notion" />
          </el-select>
        </el-form-item>
        <!-- 飞书专属配置 -->
        <template v-if="newSource.external_type === 'feishu'">
          <el-form-item label="接入方式">
            <el-radio-group v-model="newSource.feishu_mode">
              <el-radio label="wiki">知识库（Wiki）</el-radio>
              <el-radio label="drive">云盘（云文档）</el-radio>
            </el-radio-group>
            <div class="hint">知识库=Wiki 空间文档；云盘=云空间文件（docx/表格/多维表格/上传文件），需应用具备 drive 云空间权限</div>
          </el-form-item>
          <el-form-item label="云盘根目录" v-if="newSource.feishu_mode === 'drive'">
            <el-input v-model="newSource.feishu_root_folder_token" placeholder="可选；留空则从「我的空间」根目录开始遍历" />
            <div class="hint">如需只同步云盘中的某个文件夹，填入该文件夹的 Token（从文件夹 URL 获取）</div>
          </el-form-item>
          <el-form-item label="App ID"><el-input v-model="newSource.app_id" placeholder="飞书开放平台应用的 App ID" /></el-form-item>
          <el-form-item label="App Secret"><el-input v-model="newSource.app_secret" show-password placeholder="飞书应用 App Secret" /></el-form-item>
          <el-form-item label="Tenant Key"><el-input v-model="newSource.tenant_key" placeholder="可选" /></el-form-item>
          <el-form-item label="API 地址"><el-input v-model="newSource.base_url" placeholder="https://open.feishu.cn" /></el-form-item>
        </template>
        <!-- Notion 专属配置 -->
        <template v-if="newSource.external_type === 'notion'">
          <el-form-item label="Integration Token" required>
            <el-input v-model="newSource.app_secret" show-password placeholder="secret_xxx... 或 ntn_xxx..." />
            <div class="hint">
              在 <a href="https://www.notion.so/my-integrations" target="_blank">notion.so/my-integrations</a> 创建 Internal Integration 获取；
              然后把要同步的页面/数据库通过「... → 连接 → 添加连接」分享给该 Integration
            </div>
          </el-form-item>
          <el-form-item label="根页面 ID">
            <el-input v-model="newSource.app_id" placeholder="可选；留空同步整个 workspace" />
            <div class="hint">如需限定只同步某个页面子树，填入该页面的 ID（从页面 URL 末尾 32 位字符取）</div>
          </el-form-item>
          <el-form-item label="API 地址">
            <el-input v-model="newSource.base_url" placeholder="https://api.notion.com" />
            <div class="hint">默认即可；如使用代理或自部署 Notion 兼容服务可改</div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sourceCreating" @click="handleCreateSource">创建</el-button>
      </template>
    </el-dialog>

    <!-- 新建知识库弹窗 -->
    <el-dialog v-model="kbDialogVisible" title="新建知识库" width="540px">
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
          <div class="hint">不选则仅归属「关联项目」；选择后这些项目也能在生成用例时使用该知识库</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kbDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="kbCreating" @click="handleCreateKb">创建</el-button>
      </template>
    </el-dialog>

    <!-- 文档管理弹窗 -->
    <el-dialog v-model="docDialogVisible" :title="`文档管理 - ${currentKb?.name || ''}`" width="800px">
      <el-upload :show-file-list="false" :before-upload="handleUploadDoc" accept=".txt,.md,.pdf,.docx,.doc">
        <el-button type="primary" size="small">上传文档</el-button>
      </el-upload>
      <el-table :data="kbDocuments" stripe style="margin-top: 12px" v-loading="docLoading">
        <el-table-column prop="title" label="文档标题" min-width="200" />
        <el-table-column prop="source_type_display" label="来源" width="100" align="center" />
        <el-table-column prop="status_display" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'parsed' ? 'success' : row.status === 'failed' ? 'danger' : 'info'" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="word_count" label="字数" width="80" align="center" />
        <el-table-column label="操作" width="240" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" :loading="row._ingesting" @click="handleIngest(row)">入库</el-button>
            <el-button size="small" @click="handleReindex(row)">重建</el-button>
            <el-button size="small" type="danger" @click="handleDeleteDoc(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { useKbHubStore } from '@/stores/kb-hub'
import {
  getNativeKbs, createNativeKb, deleteNativeKb, publishNativeKb,
  getNativeKbDocuments,
  uploadNativeDoc, deleteNativeDoc, ingestNativeDoc, reindexNativeDoc, clearNativeDocChunks,
  getKbSources, createKbSource, deleteKbSource, syncKbSource,
  getDifyBindings, bindDifyKb, unbindDifyKb, getDifyAvailableDatasets,
} from '@/api/kb-hub'

const loading = ref(false)
const projects = ref([])

const nativeKbs = ref([])
const kbLoading = ref(false)
const kbDialogVisible = ref(false)
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

const docDialogVisible = ref(false)
const currentKb = ref(null)
const kbDocuments = ref([])
const docLoading = ref(false)

// Dify 知识库绑定（按项目）
const bindingProject = ref('')
const difyBindings = ref([])
const bindingLoading = ref(false)
const bindingDialogVisible = ref(false)
const bindProject = ref('')
const difyAvailable = ref([])
const availableLoading = ref(false)

// 当前生效的知识中枢引擎（dify / native），来自 stores/kb-hub.js 全局状态
const kbHubStore = useKbHubStore()

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
const loadKbHubEngine = async () => {
  await kbHubStore.loadDefaultEngine()
}

const onSourceTypeChange = (val) => {
  // 切换类型时，重置 base_url 到平台默认值
  if (val === 'feishu') {
    newSource.base_url = 'https://open.feishu.cn'
  } else if (val === 'notion') {
    newSource.base_url = 'https://api.notion.com'
    newSource.tenant_key = ''
  }
}

const handleCreateKb = async () => {
  if (!newKb.name) { ElMessage.warning('请输入名称'); return }
  kbCreating.value = true
  try {
    await createNativeKb(newKb)
    ElMessage.success('创建成功')
    kbDialogVisible.value = false
    Object.assign(newKb, { name: '', description: '', is_global: false, shared_project_ids: [] })
    await loadNativeKbs()
  } finally { kbCreating.value = false }
}
const handleDeleteKb = async (id) => {
  await deleteNativeKb(id)
  ElMessage.success('已删除')
  await loadNativeKbs()
}
const handlePublish = async (row) => {
  await publishNativeKb(row.id)
  ElMessage.success('已发布')
  await loadNativeKbs()
}
const openDocManager = async (row) => {
  currentKb.value = row
  docDialogVisible.value = true
  await loadDocuments()
}
const loadDocuments = async () => {
  if (!currentKb.value) return
  docLoading.value = true
  try { kbDocuments.value = (await getNativeKbDocuments(currentKb.value.id)).data?.results || [] }
  finally { docLoading.value = false }
}
const handleUploadDoc = async (file) => {
  if (!currentKb.value) { ElMessage.warning('请先选择知识库'); return false }
  const fd = new FormData()
  fd.append('kb', currentKb.value.id)
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
  await deleteNativeDoc(id)
  ElMessage.success('已删除')
  await loadDocuments()
}

const handleCreateSource = async () => {
  if (!newSource.name || !newSource.app_id || !newSource.app_secret) { ElMessage.warning('请填写名称/App ID/App Secret'); return }
  sourceCreating.value = true
  try {
    await createKbSource(newSource)
    ElMessage.success('创建成功')
    sourceDialogVisible.value = false
    Object.assign(newSource, { name: '', external_type: 'feishu', feishu_mode: 'wiki', feishu_root_folder_token: '', app_id: '', app_secret: '', tenant_key: '', base_url: 'https://open.feishu.cn', root_page_id: '' })
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

// ── Dify 知识库绑定逻辑 ──
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
  await Promise.all([loadProjects(), loadNativeKbs(), loadKbSources(), loadKbHubEngine()])
  loading.value = false
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.hint { color: #909399; font-size: 12px; line-height: 1.5; }
</style>
