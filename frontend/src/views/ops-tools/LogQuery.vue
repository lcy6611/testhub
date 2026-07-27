<template>
  <div class="log-query-page">
    <el-row :gutter="16" class="full-height">
      <el-col :span="7" class="full-height">
        <el-card class="panel-card full-height" :body-style="{ padding: '16px', height: '100%', display: 'flex', flexDirection: 'column' }">
          <div class="panel-title">查询日志</div>

          <div class="form-row">
            <div class="form-label">选择环境</div>
            <el-select v-model="selectedEnvId" placeholder="选择环境" style="width: 100%" @change="onEnvChange">
              <el-option v-for="env in environments" :key="env.id" :label="env.name" :value="env.id" />
            </el-select>
          </div>

          <div class="form-row">
            <div class="form-label">选择日志目录</div>
            <el-input v-model="currentDir" placeholder="/var/log" />
          </div>

          <div class="form-row actions">
            <el-button type="primary" @click="loadDirs">重新连接</el-button>
            <el-button @click="disconnect">断开连接</el-button>
          </div>

          <div v-if="connected" class="status-tip success">
            {{ currentEnv && currentEnv.access_method === 'local' ? '本地日志目录连接成功' : 'SSH 连接成功' }}
          </div>

          <el-tree
            v-if="treeData.length"
            :data="treeData"
            :props="{ label: 'name', children: 'children' }"
            @node-click="onNodeClick"
            style="margin-top: 12px; flex: 1; overflow: auto;"
          />

          <div class="info-block" v-if="currentEnv">
            <div class="info-title">连接信息</div>
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="当前环境">{{ currentEnv.name }}</el-descriptions-item>
              <el-descriptions-item label="所属分类">{{ currentEnv.category || '-' }}</el-descriptions-item>
              <el-descriptions-item label="当前目录">{{ currentDir || '-' }}</el-descriptions-item>
              <el-descriptions-item label="当前文件">{{ currentFile || '-' }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </el-col>

      <el-col :span="17" class="full-height">
        <el-card class="panel-card full-height" :body-style="{ padding: '16px', height: '100%', display: 'flex', flexDirection: 'column' }">
          <div class="toolbar">
            <div class="toolbar-left">
              <el-input
                v-model="keywordInput"
                placeholder="输入关键字后回车添加"
                style="width: 220px"
                @keyup.enter="addKeyword"
              />
              <el-button @click="addKeyword">添加关键字</el-button>
              <el-tag
                v-for="(k, i) in keywords"
                :key="k"
                closable
                @close="removeKeyword(i)"
                style="margin-left: 6px;"
              >{{ k }}</el-tag>
            </div>
            <div class="toolbar-right">
              <el-select v-model="tailLines" style="width: 120px">
                <el-option label="最近 100 行" :value="100" />
                <el-option label="最近 200 行" :value="200" />
                <el-option label="最近 500 行" :value="500" />
                <el-option label="最近 1000 行" :value="1000" />
              </el-select>
              <el-switch v-model="realtime" active-text="实时查询" style="margin-left: 12px;" />
              <el-button @click="loadLog" style="margin-left: 12px;">刷新</el-button>
              <el-button @click="clearLog">清空</el-button>
              <el-button @click="downloadLog">下载日志</el-button>
            </div>
          </div>

          <div class="log-box" v-if="logContent" ref="logBoxRef">
            <pre>{{ logContent }}</pre>
          </div>
          <el-empty v-else description="选择文件后显示日志内容" style="flex: 1;" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { getEnvironments, listLogDirs, readLog } from '@/api/ops-tools'

const environments = ref([])
const selectedEnvId = ref(null)
const currentEnv = ref(null)
const currentDir = ref('/var/log')
const currentFile = ref('')
const connected = ref(false)
const treeData = ref([])
const keywordInput = ref('')
const keywords = ref([])
const tailLines = ref(200)
const realtime = ref(false)
const logContent = ref('')
const logBoxRef = ref(null)

async function loadEnvironments() {
  const res = await getEnvironments()
  environments.value = res.data.results || res.data || []
}

function onEnvChange(id) {
  currentEnv.value = environments.value.find(e => e.id === id) || null
  connected.value = false
  treeData.value = []
  // 本地环境默认指向其配置的目录
  if (currentEnv.value && currentEnv.value.access_method === 'local') {
    currentDir.value = currentEnv.value.current_dir || '/host_logs'
  } else {
    currentDir.value = '/var/log'
  }
}

async function loadDirs() {
  if (!selectedEnvId.value) return ElMessage.warning('请选择环境')
  const res = await listLogDirs({ environment: selectedEnvId.value, parent: currentDir.value })
  const { base, dirs, files } = res.data
  currentDir.value = base
  treeData.value = [
    ...dirs.map(d => ({ ...d, children: [] })),
    ...files.map(f => ({ ...f, isLeaf: true })),
  ]
  connected.value = true
}

function disconnect() {
  connected.value = false
  treeData.value = []
  logContent.value = ''
  ElMessage.info('已断开连接')
}

async function onNodeClick(node) {
  if (node.type === 'dir') {
    currentDir.value = node.path
    await loadDirs()
  } else {
    currentFile.value = node.path
    await loadLog()
  }
}

async function loadLog() {
  if (!selectedEnvId.value || !currentFile.value) return
  const res = await readLog({
    environment: selectedEnvId.value,
    path: currentFile.value,
    keywords: keywords.value,
    tail_lines: tailLines.value,
  })
  logContent.value = res.data.content
  await nextTick()
  if (logBoxRef.value) {
    logBoxRef.value.scrollTop = logBoxRef.value.scrollHeight
  }
}

function addKeyword() {
  const k = keywordInput.value.trim()
  if (!k) return
  if (!keywords.value.includes(k)) keywords.value.push(k)
  keywordInput.value = ''
}

function removeKeyword(i) {
  keywords.value.splice(i, 1)
}

function clearLog() {
  logContent.value = ''
}

function downloadLog() {
  if (!logContent.value) return ElMessage.warning('无日志内容可下载')
  const blob = new Blob([logContent.value], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = currentFile.value.split('/').pop() || 'log.txt'
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(loadEnvironments)
</script>

<style lang="scss" scoped>
.log-query-page {
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
  margin-bottom: 12px;
}
.actions {
  display: flex;
  gap: 8px;
}
.status-tip {
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 12px;
  &.success {
    color: #67c23a;
    background: #f0f9eb;
  }
}
.info-block {
  margin-top: 16px;
}
.info-title {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}
.toolbar-left, .toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.log-box {
  flex: 1;
  overflow: auto;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 6px;
  padding: 12px;
  pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-all;
    font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
    font-size: 13px;
    line-height: 1.6;
  }
}
</style>
