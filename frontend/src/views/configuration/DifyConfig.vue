<template>
  <div class="dify-config-container">
    <div class="page-header">
      <h1>🤖 AI评测师配置</h1>
      <p>添加多个 Dify 应用配置，聊天时可下拉选择使用哪个应用</p>
    </div>

    <div class="main-content">
      <div class="section-header">
        <h2>评测师配置列表</h2>
        <el-button type="primary" class="add-config-btn" @click="openAddModal">
          <el-icon><Plus /></el-icon>
          添加配置
        </el-button>
      </div>

      <div class="configs-grid">
        <div v-if="configs.length === 0" class="empty-state">
          <div class="empty-icon">🤖</div>
          <h3>暂无 AI 评测师配置</h3>
          <p>请先添加配置；或至少启用一条配置（如果后端全量接口不可用，将仅展示启用项）。</p>
        </div>

        <el-card v-for="cfg in configs" :key="cfg.id" class="config-card">
          <template #header>
            <div class="card-header">
              <div class="card-title">
                <span class="title-text">{{ cfg.app_type || '未命名配置' }}</span>
                <div class="config-badges">
                  <el-tag :type="cfg.is_active ? 'success' : 'info'">
                    {{ cfg.is_active ? '已启用' : '已禁用' }}
                  </el-tag>
                  <el-tag v-if="!cfg.has_api_key" type="warning">无应用 Key</el-tag>
                  <el-tag v-else-if="cfg.has_dataset_api_key" type="info">含知识库 Key</el-tag>
                </div>
              </div>
              <div class="config-actions">
                <button
                  class="test-btn"
                  @click="testConnection(cfg)"
                  :disabled="isTestingConnection && testingConfigId === cfg.id"
                >
                  <span v-if="isTestingConnection && testingConfigId === cfg.id">🔄</span>
                  <span v-else>🔗</span>
                  测试连接
                </button>
                <button class="edit-btn" @click="editConfig(cfg)" type="button">✏️</button>
                <button class="delete-btn" @click="deleteConfig(cfg.id)" type="button">🗑️</button>
              </div>
            </div>
          </template>

          <div class="config-body">
            <div class="detail-item">
              <label>API URL</label>
              <span class="mono-text">{{ cfg.api_url }}</span>
            </div>
            <div class="detail-item">
              <label>API Key</label>
              <span class="mono-text">{{ cfg.has_api_key ? (cfg.api_key_masked || '****') : '未配置（AI 评测师不可用）' }}</span>
            </div>
            <div class="detail-item">
              <label>知识库 API Key</label>
              <span class="mono-text">{{ cfg.dataset_api_key_masked || '未配置' }}</span>
            </div>
            <div class="detail-item">
              <label>创建时间</label>
              <span>{{ formatDate(cfg.created_at) }}</span>
            </div>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 添加/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑 AI评测师配置' : '添加 AI评测师配置'"
      width="680px"
      @close="resetDialog"
    >
      <el-form
        ref="dialogFormRef"
        :model="dialogForm"
        :rules="rules"
        label-width="120px"
      >
        <el-form-item label="配置名称" prop="app_type">
          <el-input v-model="dialogForm.app_type" placeholder="请输入名称，例如：工作流A/对话B" clearable />
        </el-form-item>

        <el-form-item label="调用模式" prop="invoke_mode">
          <el-select v-model="dialogForm.invoke_mode" placeholder="选择与 Dify 应用类型一致的模式" style="width: 100%">
            <el-option label="工作流应用（workflows/run）" value="workflow" />
            <el-option label="对话应用（chat-messages）" value="chat" />
          </el-select>
          <div class="form-tip">
            AI 评测师专用。Dify 里是「工作流」选第一项，「聊天助手/Agent」选第二项。
          </div>
        </el-form-item>

        <el-form-item label="API URL" prop="api_url">
          <el-input v-model="dialogForm.api_url" placeholder="https://api.dify.ai/v1" clearable>
            <template #prepend>
              <el-icon><Link /></el-icon>
            </template>
          </el-input>
          <div class="form-tip">
            Dify 服务地址，与浏览器打开 Dify 的地址一致（如 http://localhost:8081）。
            TestHub 在本机运行时请用 localhost，不要用 host.docker.internal。
          </div>
        </el-form-item>

        <el-form-item label="API Key" prop="api_key">
          <el-input
            v-model="dialogForm.api_key"
            type="password"
            show-password
            :placeholder="isEditing ? '留空则不修改；AI 评测师 / Dify 应用对话用' : 'app- 开头，可选'"
            clearable
          >
            <template #prepend>
              <el-icon><Key /></el-icon>
            </template>
          </el-input>
          <div class="form-tip">
            仅「AI 评测师」调用 Dify 应用时需要（app- 开头）。
            只做 AI 用例生成 + 知识库时可不填。
          </div>
        </el-form-item>

        <el-form-item label="知识库 API Key" prop="dataset_api_key">
          <el-input
            v-model="dialogForm.dataset_api_key"
            type="password"
            show-password
            :placeholder="isEditing ? '留空则不修改；AI 用例生成检索知识库' : 'dataset- 开头的知识库 API Key'"
            clearable
          >
            <template #prepend>
              <el-icon><Key /></el-icon>
            </template>
          </el-input>
          <div class="form-tip">
            「AI 用例生成 → 启用知识库」时必填。在 Dify 知识库 → API 访问 中获取（dataset- 开头）。
          </div>
        </el-form-item>

        <el-form-item label="启用状态" prop="is_active">
          <el-switch v-model="dialogForm.is_active" />
          <span class="switch-label">{{ dialogForm.is_active ? '已启用' : '已禁用' }}</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="dialogTesting"
            @click="testConnectionInDialog"
          >
            测试连接
          </el-button>
          <el-button type="success" :loading="saving" @click="saveDialogConfig">
            <el-icon><Check /></el-icon>
            保存配置
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Link, Key, Connection, Check, Plus } from '@element-plus/icons-vue'
import api from '@/utils/api'

const configs = ref([])
const dialogVisible = ref(false)
const dialogFormRef = ref(null)

const isEditing = ref(false)
const editingId = ref(null)

const isTestingConnection = ref(false)
const testingConfigId = ref(null)
const saving = ref(false)
const dialogTesting = ref(false)

const dialogForm = ref({
  api_url: '',
  api_key: '',
  dataset_api_key: '',
  is_active: false,
  app_type: '',
  invoke_mode: 'workflow'
})

const rules = {
  api_url: [
    { required: true, message: '请输入 API URL', trigger: 'blur' },
    { type: 'url', message: '请输入有效的 URL', trigger: 'blur' }
  ],
  api_key: [
    { min: 8, message: 'API Key长度至少8位', trigger: 'blur' }
  ],
  app_type: [
    { required: true, message: '请输入配置名称', trigger: 'blur' }
  ]
}

const formatDate = (dateString) => {
  if (!dateString) return '-'
  const date = new Date(dateString)
  return date.toLocaleString('zh-CN')
}

const loadConfigs = async () => {
  // 先用“激活配置”兜底，保证页面至少能显示出配置卡片
  let fallbackList = []
  try {
    const resp2 = await api.get('/assistant/config/dify/')
    const data = resp2.data || {}
    if (data && data.id) fallbackList = [data]
  } catch (e2) {
    console.error('加载 Dify 配置 fallback 失败:', e2)
    fallbackList = []
  }

  configs.value = fallbackList

  // 再尝试拉取多配置全量列表
  try {
    const response = await api.get('/assistant/config/dify/all/')
    const list = Array.isArray(response.data) ? response.data : []
    // 只有当后端真的返回全量数组时，才覆盖 fallback
    if (list.length >= 0) {
      configs.value = list
    }
  } catch (error) {
    // 全量接口可能不存在（404/500），这时保持 fallbackList
    console.warn('加载 Dify 全量配置失败，使用 fallback（激活配置）:', error?.response?.status)
  }
}

const resetDialog = () => {
  dialogForm.value = {
    api_url: '',
    api_key: '',
    dataset_api_key: '',
    is_active: false,
    app_type: '',
    invoke_mode: 'workflow'
  }
  isEditing.value = false
  editingId.value = null
  isTestingConnection.value = false
  testingConfigId.value = null
  saving.value = false
  dialogFormRef.value?.clearValidate?.()
}

const openAddModal = () => {
  resetDialog()
  isEditing.value = false
  dialogVisible.value = true
  // 新建默认启用：保证没有全量接口时页面不会一直“空白”
  dialogForm.value.is_active = true
}

const editConfig = (cfg) => {
  resetDialog()
  isEditing.value = true
  editingId.value = cfg.id
  dialogForm.value.api_url = cfg.api_url
  dialogForm.value.is_active = !!cfg.is_active
  dialogForm.value.app_type = cfg.app_type || ''
  dialogForm.value.invoke_mode = cfg.invoke_mode || 'workflow'
  dialogVisible.value = true
}

const toggleActive = async (cfg) => {
  try {
    await api.patch(`/assistant/config/dify/${cfg.id}/`, {
      is_active: !!cfg.is_active
    })
    // PATCH 成功后刷新列表（因为置灰其它配置的逻辑在后端）
    await loadConfigs()
  } catch (error) {
    console.error('切换启用状态失败:', error)
    ElMessage.error(error.response?.data?.error || '切换启用状态失败')
    await loadConfigs()
  }
}

const deleteConfig = async (id) => {
  if (!confirm('确定要删除该配置吗？')) {
    return
  }
  try {
    await api.delete(`/assistant/config/dify/${id}/`)
    ElMessage.success('删除成功')
    await loadConfigs()
  } catch (error) {
    console.error('删除配置失败:', error)
    ElMessage.error(error.response?.data?.error || '删除失败')
  }
}

const testConnection = async (cfg) => {
  isTestingConnection.value = true
  testingConfigId.value = cfg.id
  try {
    const resp = await api.post('/assistant/config/dify/test_connection/', {
      config_id: cfg.id
    }, {
      // 测试连接会按多种端点/鉴权回退，耗时可能超过默认 10s
      timeout: 120000
    })
    ElMessage.success(resp.data?.message || '连接测试成功！')
  } catch (error) {
    console.error('测试连接失败:', error)
    const err = error?.response?.data
    const msg = (err && (err.error || err.message)) ? (err.error || err.message) : '测试连接失败'
    const detail = err?.detail
    if (typeof detail === 'string' && detail.length > 0 && detail.length < 800) {
      ElMessage.error(`${msg}：${detail}`)
    } else {
      ElMessage.error(msg)
    }
  } finally {
    isTestingConnection.value = false
    testingConfigId.value = null
  }
}

const buildTestConnectionPayload = () => {
  const payload = {
    api_url: dialogForm.value.api_url?.trim?.() || dialogForm.value.api_url,
  }
  if (isEditing.value && editingId.value) {
    payload.config_id = editingId.value
  }
  if (dialogForm.value.api_key && dialogForm.value.api_key.trim()) {
    payload.api_key = dialogForm.value.api_key.trim()
  }
  if (dialogForm.value.dataset_api_key && dialogForm.value.dataset_api_key.trim()) {
    payload.dataset_api_key = dialogForm.value.dataset_api_key.trim()
  }
  return payload
}

const testConnectionInDialog = async () => {
  dialogTesting.value = true
  try {
    const payload = buildTestConnectionPayload()
    if (!payload.api_url) {
      ElMessage.error('请先填写 API URL')
      return
    }
    if (!payload.api_key && !payload.dataset_api_key && !(isEditing.value && payload.config_id)) {
      ElMessage.error('请至少填写「应用 API Key」或「知识库 API Key」之一')
      return
    }

    const resp = await api.post('/assistant/config/dify/test_connection/', payload, {
      timeout: 120000
    })
    ElMessage.success(resp.data?.message || '连接测试成功！')
  } catch (error) {
    console.error('弹窗测试连接失败:', error)
    const err = error?.response?.data
    const msg = (err && (err.error || err.message)) ? (err.error || err.message) : '测试连接失败'
    const detail = err?.detail
    if (typeof detail === 'string' && detail.length > 0 && detail.length < 800) {
      ElMessage.error(`${msg}：${detail}`)
    } else {
      ElMessage.error(msg)
    }
  } finally {
    dialogTesting.value = false
  }
}

const saveDialogConfig = async () => {
  if (!dialogFormRef.value) return

  await dialogFormRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      if (!isEditing.value) {
        const hasAppKey = dialogForm.value.api_key && dialogForm.value.api_key.trim()
        const hasDatasetKey = dialogForm.value.dataset_api_key && dialogForm.value.dataset_api_key.trim()
        if (!hasAppKey && !hasDatasetKey) {
          ElMessage.error('创建配置时请至少填写「应用 API Key」或「知识库 API Key」之一')
          return
        }
      }

      const dataToSave = {
        api_url: dialogForm.value.api_url?.trim?.() || dialogForm.value.api_url,
        is_active: dialogForm.value.is_active,
        app_type: dialogForm.value.app_type,
        invoke_mode: dialogForm.value.invoke_mode || 'workflow'
      }

      if (dialogForm.value.api_key && dialogForm.value.api_key.trim()) {
        dataToSave.api_key = dialogForm.value.api_key.trim()
      }

      if (dialogForm.value.dataset_api_key && dialogForm.value.dataset_api_key.trim()) {
        dataToSave.dataset_api_key = dialogForm.value.dataset_api_key.trim()
      }

      if (isEditing.value) {
        await api.patch(`/assistant/config/dify/${editingId.value}/`, dataToSave)
      } else {
        await api.post('/assistant/config/dify/', dataToSave)
      }

      ElMessage.success('保存成功')
      dialogVisible.value = false
      await loadConfigs()
    } catch (error) {
      console.error('保存配置失败:', error)
      ElMessage.error(error.response?.data?.error || '保存配置失败')
    } finally {
      saving.value = false
    }
  })
}

onMounted(() => {
  loadConfigs()
})
</script>

<style scoped lang="scss">
.dify-config-container {
  padding: 20px;
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  text-align: center;
  margin-bottom: 30px;

  h1 {
    font-size: 2rem;
    color: #2c3e50;
    margin-bottom: 10px;
  }

  p {
    color: #666;
    font-size: 1rem;
  }
}

.main-content {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  h2 {
    font-size: 18px;
    margin: 0;
  }
}

.add-config-btn {
  display: flex;
  align-items: center;
  gap: 6px;
}

.configs-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.empty-state {
  grid-column: 1 / -1;
  padding: 30px 16px;
  text-align: center;
  border: 1px dashed #d9ecff;
  border-radius: 12px;
  background: #f8fbff;

  .empty-icon {
    font-size: 34px;
    margin-bottom: 10px;
  }

  h3 {
    margin: 0 0 6px;
    font-size: 16px;
    color: var(--el-text-color-primary);
  }

  p {
    margin: 0;
    color: var(--el-text-color-secondary);
    font-size: 13px;
  }
}

.config-card {
  border-radius: 12px;

  :deep(.el-card__header) {
    padding: 12px 16px;
  }
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  overflow: hidden;

  .card-title {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .title-text {
    font-weight: 700;
    color: var(--el-text-color-primary);
  }
}

.config-body {
  padding-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 10px;

  .detail-item {
    display: flex;
    gap: 10px;
    align-items: center;
    word-break: break-all;

    label {
      width: 76px;
      color: var(--el-text-color-secondary);
      font-size: 12px;
      flex-shrink: 0;
    }

    span {
      flex: 1;
    }
  }
}

.mono-text {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.switch-label {
  margin-left: 10px;
  color: var(--el-text-color-regular);
}

.config-badges {
  display: inline-flex;
  gap: 8px;
}

.config-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
}

.test-btn, .edit-btn, .delete-btn {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.3s ease;
  background: transparent;
}

.test-btn {
  background: #3498db;
  color: white;
}

.test-btn:hover:not(:disabled) {
  background: #2980b9;
}

.test-btn:disabled {
  background: #bdc3c7;
  cursor: not-allowed;
}

.edit-btn {
  background: #f39c12;
  color: white;
}

.edit-btn:hover {
  background: #e67e22;
}

.delete-btn {
  background: #e74c3c;
  color: white;
}

.delete-btn:hover {
  background: #c0392b;
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  width: 100%;
  gap: 12px;
}

.dialog-footer-left {
  display: flex;
  align-items: center;
}

.dialog-footer-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
