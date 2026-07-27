<template>
  <div class="file-transfer-page">
    <el-row :gutter="16" class="full-height">
      <el-col :span="7" class="full-height">
        <el-card class="panel-card full-height" :body-style="{ padding: '16px' }">
          <div class="panel-title">传输设置</div>

          <div class="form-row">
            <div class="form-label">目标环境</div>
            <el-select v-model="selectedEnvId" placeholder="选择环境" style="width: 100%">
              <el-option v-for="env in environments" :key="env.id" :label="env.name" :value="env.id" />
            </el-select>
          </div>

          <div class="form-row">
            <div class="form-label">传输方向</div>
            <el-radio-group v-model="direction">
              <el-radio-button label="upload">上传到服务器</el-radio-button>
              <el-radio-button label="download">下载到本地</el-radio-button>
            </el-radio-group>
          </div>

          <div class="form-row">
            <div class="form-label">远程路径</div>
            <el-input v-model="remotePath" placeholder="/tmp/uploaded_file.txt" />
          </div>

          <div class="form-row" v-if="direction === 'upload'">
            <div class="form-label">本地文件</div>
            <el-upload
              drag
              :auto-upload="false"
              :on-change="handleFileChange"
              :show-file-list="false"
              style="width: 100%"
            >
              <el-icon class="el-icon--upload"><upload-filled /></el-icon>
              <div class="el-upload__text">拖拽文件到此处或 <em>点击上传</em></div>
            </el-upload>
            <div v-if="selectedFile" class="file-name">已选择：{{ selectedFile.name }} ({{ formatSize(selectedFile.size) }})</div>
          </div>

          <div class="form-row actions">
            <el-button type="primary" @click="startTransfer" :loading="transferring">开始传输</el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :span="17" class="full-height">
        <el-card class="panel-card full-height" :body-style="{ padding: '16px' }">
          <div class="panel-title">传输记录</div>
          <el-table :data="tasks" stripe>
            <el-table-column prop="name" label="文件名称" />
            <el-table-column prop="environment_name" label="目标环境" />
            <el-table-column prop="direction_display" label="方向" />
            <el-table-column prop="remote_path" label="远程路径" show-overflow-tooltip />
            <el-table-column label="大小">
              <template #default="{ row }">{{ formatSize(row.size) }}</template>
            </el-table-column>
            <el-table-column label="状态">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'info'">{{ row.status_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button v-if="row.local_file" link type="primary" @click="downloadFile(row.id)">下载</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { getEnvironments, getFileTransfers, uploadFile, downloadFile as apiDownloadFile } from '@/api/ops-tools'

const environments = ref([])
const selectedEnvId = ref(null)
const direction = ref('upload')
const remotePath = ref('/tmp/')
const selectedFile = ref(null)
const tasks = ref([])
const transferring = ref(false)

async function loadEnvironments() {
  const res = await getEnvironments()
  environments.value = res.data.results || res.data || []
}

async function loadTasks() {
  const res = await getFileTransfers()
  tasks.value = res.data.results || res.data || []
}

function handleFileChange(file) {
  selectedFile.value = file.raw
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

async function startTransfer() {
  if (!selectedEnvId.value) return ElMessage.warning('请选择目标环境')
  if (direction.value === 'upload' && !selectedFile.value) return ElMessage.warning('请选择本地文件')
  if (!remotePath.value.trim()) return ElMessage.warning('请填写远程路径')

  transferring.value = true
  try {
    if (direction.value === 'upload') {
      const form = new FormData()
      form.append('environment', selectedEnvId.value)
      form.append('remote_path', remotePath.value)
      form.append('file', selectedFile.value)
      await uploadFile(form)
      ElMessage.success('上传成功')
    } else {
      ElMessage.info('下载功能待接入远程文件拉取')
    }
    selectedFile.value = null
    await loadTasks()
  } finally {
    transferring.value = false
  }
}

async function downloadFile(id) {
  const res = await apiDownloadFile(id)
  const blob = new Blob([res.data])
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'download'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadEnvironments()
  loadTasks()
})
</script>

<style lang="scss" scoped>
.file-transfer-page {
  height: 100%;
}
.full-height {
  height: 100%;
}
.panel-card {
  height: 100%;
  background: var(--app-card-bg, #ffffff);
}
.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 16px;
}
.form-label {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin-bottom: 6px;
}
.form-row {
  margin-bottom: 16px;
}
.actions {
  display: flex;
  gap: 8px;
}
.file-name {
  margin-top: 8px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
</style>
