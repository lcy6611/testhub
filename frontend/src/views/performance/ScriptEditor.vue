<template>
  <div class="script-editor-page">
    <el-container style="height: calc(100vh - 60px)">
      <!-- 左侧脚本列表 -->
      <el-aside width="260px" class="left-panel">
        <div class="left-header">
          <span>脚本列表</span>
          <el-button link size="small" @click="loadScripts">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </div>
        <div class="project-filter">
          <el-select
            v-model="selectedProject"
            clearable
            placeholder="选择项目"
            filterable
            style="width:100%"
            @change="loadScripts"
          >
            <el-option label="全部项目" :value="null" />
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </div>
        <div class="script-tree">
          <div
            v-for="item in scripts"
            :key="item.id"
            :class="['script-item', { active: currentScriptId === item.id }]"
            @click="selectScript(item.id)"
          >
            <div class="script-item-name">{{ item.name }}</div>
            <div class="script-item-meta">
              <el-tag size="small" :type="item.script_type === 'ONLINE' ? 'primary' : 'warning'">
                {{ scriptTypeLabel(item.script_type) }}
              </el-tag>
              <span class="status-dot" :class="item.status">{{ statusLabel(item.status) }}</span>
              <el-tooltip v-if="item.project_names?.length" :content="item.project_names.join(' / ')" placement="top">
                <el-tag size="small" type="info" style="max-width: 80px; overflow: hidden; text-overflow: ellipsis;">
                  {{ item.project_names.join(', ') }}
                </el-tag>
              </el-tooltip>
            </div>
            <el-button
              class="script-del-btn"
              link
              type="danger"
              size="small"
              title="删除脚本"
              @click.stop="handleDeleteScript(item)"
            >
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
          <el-empty v-if="!scripts.length" description="暂无脚本" :image-size="60" />
        </div>
      </el-aside>

      <!-- 右侧编辑区 -->
      <el-main class="right-panel">
        <div class="editor-header">
          <div class="header-actions">
            <el-button type="primary" plain @click="importJmxDialogVisible = true">
              <el-icon><Upload /></el-icon>导入 JMX
            </el-button>
            <el-button @click="createNewScript">
              <el-icon><Plus /></el-icon>新建脚本
            </el-button>
            <el-button type="primary" :loading="saving" @click="handleSave">
              <el-icon><Check /></el-icon>保存
            </el-button>
            <el-button type="success" :loading="executing" @click="handleExecute">
              <el-icon><VideoPlay /></el-icon>执行
            </el-button>
          </div>
        </div>

        <div class="editor-body">
          <!-- 基本信息 -->
          <el-card class="section-card" shadow="never">
            <div class="section-title">基本信息</div>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="脚本名称" required>
                  <el-input v-model="form.name" placeholder="请输入脚本名称" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="所属项目">
                  <el-select v-model="form.projects" multiple clearable placeholder="支持多选：脚本可被多个项目复用" filterable style="width:100%" collapse-tags collapse-tags-tooltip>
                    <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="状态">
                  <el-select v-model="form.status" style="width:100%">
                    <el-option label="草稿" value="draft" />
                    <el-option label="已发布" value="published" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="脚本模式" required>
                  <el-radio-group v-model="form.script_type">
                    <el-radio-button value="ONLINE">在线编排</el-radio-button>
                    <el-radio-button value="JMX_RAW">纯 JMX</el-radio-button>
                    <el-radio-button value="JMX_UPLOAD">上传 JMX 创建</el-radio-button>
                  </el-radio-group>
                  <el-button v-if="form.script_type === 'ONLINE'" link size="small" style="margin-left:12px" @click="exportJmx">
                    导出 JMX
                  </el-button>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="24">
                <el-form-item label="描述">
                  <el-input v-model="form.description" type="textarea" :rows="2" placeholder="脚本描述" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-card>

          <!-- 纯 JMX 模式 -->
          <el-card v-if="form.script_type === 'JMX_RAW'" class="section-card" shadow="never">
            <div class="section-title">JMX 内容</div>
            <el-input
              v-model="form.jmx_content"
              type="textarea"
              :rows="20"
              placeholder="直接粘贴 JMX XML 内容"
            />
          </el-card>

          <!-- 上传 JMX 模式 -->
          <el-card v-if="form.script_type === 'JMX_UPLOAD'" class="section-card" shadow="never">
            <div class="section-title">JMX 文件</div>
            <el-upload
              :auto-upload="false"
              accept=".jmx"
              :limit="1"
              :on-change="onFileChange"
              :on-remove="onFileRemove"
              :file-list="fileList"
            >
              <el-button type="primary">选择 JMX 文件</el-button>
              <template #tip>
                <div class="upload-tip">上传 .jmx 文件，系统会自动检测危险组件并覆盖线程数/Ramp-Up/持续时间</div>
              </template>
            </el-upload>
            <el-alert
              v-for="(w, i) in dangerWarnings" :key="i"
              :title="w" type="warning" :closable="false" show-icon
              style="margin-top: 12px"
            />
            <div style="margin-top: 12px">
              <el-button type="primary" plain :disabled="!currentScriptId" :loading="parsing" @click="handleParseToOnline">
                <el-icon><Operation /></el-icon>解析为在线编排
              </el-button>
              <span v-if="!currentScriptId" class="help-text" style="margin-left:8px">保存后可解析为在线编排</span>
            </div>
          </el-card>

          <!-- 在线编排模式 -->
          <template v-if="form.script_type === 'ONLINE'">
            <!-- 用户定义变量 -->
            <el-card class="section-card" shadow="never">
              <div class="section-header">
                <div class="section-title">用户定义的变量</div>
                <el-button link size="small" @click="addVariable">
                  <el-icon><Plus /></el-icon>添加变量
                </el-button>
              </div>
              <div class="help-text">TestPlan 级变量池，可在 URL、参数和请求体中使用，例如 {{ base_url }} 或 JMeter 原生 ${base_url}</div>
              <div v-for="(v, idx) in form.variables" :key="idx" class="variable-row">
                <el-input v-model="v.name" placeholder="变量名" style="width:180px" />
                <el-input v-model="v.value" placeholder="变量值" style="flex:1" />
                <el-button link type="danger" @click="form.variables.splice(idx, 1)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </el-card>

            <!-- CSV 文件管理 -->
            <el-card v-if="form.script_type === 'ONLINE'" class="section-card" shadow="never">
              <div class="section-header">
                <div class="section-title">CSV 文件管理</div>
                <el-upload
                  ref="csvUploadRef"
                  :auto-upload="false"
                  accept=".csv"
                  :multiple="true"
                  :show-file-list="false"
                  :on-change="onCsvFileChange"
                >
                  <el-button link size="small">
                    <el-icon><Upload /></el-icon>上传 CSV
                  </el-button>
                </el-upload>
              </div>
              <div class="help-text">执行时系统会自动把这里上传的 CSV 文件复制到 JMeter 工作目录，供 CSV 数据集读取</div>
              <div v-if="!csvFiles.length" class="empty-text">未上传 CSV 文件</div>
              <div v-for="f in csvFiles" :key="f.id" class="variable-row">
                <el-tag size="small" type="info">{{ f.filename }}</el-tag>
                <el-button link type="danger" size="small" @click="handleDeleteCsv(f.id)">
                  <el-icon><Delete /></el-icon>
                </el-button>
              </div>
            </el-card>

            <!-- 线程组 -->
            <el-card v-for="(tg, tgi) in threadGroups" :key="tgi" class="section-card thread-group-card" shadow="never">
              <div class="section-header">
                <div class="section-title">
                  <el-icon><Connection /></el-icon>
                  <el-input v-model="tg.name" class="inline-title" placeholder="线程组名称" />
                </div>
                <el-button v-if="threadGroups.length > 1" link type="danger" size="small" @click="threadGroups.splice(tgi, 1)">
                  <el-icon><Delete /></el-icon>删除线程组
                </el-button>
              </div>
              <el-row :gutter="16" class="tg-params">
                <el-col :span="6">
                  <el-form-item label="并发线程">
                    <el-input-number v-model="tg.thread_count" :min="1" style="width:100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="启动时间(秒)">
                    <el-input-number v-model="tg.ramp_up" :min="0" style="width:100%" />
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="循环次数">
                    <el-input-number v-model="tg.loops" :min="-1" style="width:100%" />
                    <div class="help-text">-1 表示循环到停止</div>
                  </el-form-item>
                </el-col>
                <el-col :span="6">
                  <el-form-item label="持续时间(秒)">
                    <el-input-number v-model="tg.duration" :min="1" style="width:100%" />
                  </el-form-item>
                </el-col>
              </el-row>

              <!-- 线程组变量 -->
              <div class="sub-section">
                <div class="sub-section-header">
                  <div class="sub-section-title">用户定义的变量</div>
                  <el-button link size="small" @click="tg.variables.push({name:'', value:''})">
                    <el-icon><Plus /></el-icon>添加变量
                  </el-button>
                </div>
                <div v-if="!tg.variables.length" class="empty-text">未配置线程组变量</div>
                <div v-for="(v, vidx) in tg.variables" :key="vidx" class="variable-row">
                  <el-input v-model="v.name" placeholder="变量名" style="width:180px" />
                  <el-input v-model="v.value" placeholder="变量值" style="flex:1" />
                  <el-button link type="danger" @click="tg.variables.splice(vidx, 1)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>

              <!-- 参数化数据集 -->
              <div class="sub-section">
                <div class="sub-section-header">
                  <div class="sub-section-title">参数化数据集</div>
                  <el-button link size="small" @click="tg.csv_datasets.push({name:'', file:'', delimiter:',', variable_names:'', encoding:'UTF-8'})">
                    <el-icon><Plus /></el-icon>添加数据集
                  </el-button>
                </div>
                <div v-if="!tg.csv_datasets.length" class="empty-text">未配置 CSV 数据集</div>
                <div v-for="(csv, cidx) in tg.csv_datasets" :key="cidx" class="csv-row">
                  <el-input v-model="csv.name" placeholder="数据集名称" style="width:150px" />
                  <el-select v-model="csv.file" placeholder="选择 CSV 文件" style="flex:1" filterable allow-create>
                    <el-option v-for="f in csvFiles" :key="f.id" :label="f.filename" :value="f.filename" />
                  </el-select>
                  <el-input v-model="csv.delimiter" placeholder="分隔符" style="width:80px" />
                  <el-input v-model="csv.variable_names" placeholder="变量名(逗号分隔)" style="width:180px" />
                  <el-button link type="danger" @click="tg.csv_datasets.splice(cidx, 1)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                </div>
              </div>

              <!-- HTTP 请求 -->
              <div class="sub-section">
                <div class="sub-section-header">
                  <div class="sub-section-title">HTTP 请求</div>
                  <el-button link size="small" @click="addRequest(tgi)">
                    <el-icon><Plus /></el-icon>添加请求
                  </el-button>
                </div>
                <div v-if="!tg.samplers.length" class="empty-text">暂无 HTTP 请求</div>
                <div v-for="(req, ri) in tg.samplers" :key="ri" class="request-block">
                  <div class="request-header">
                    <el-select v-model="req.method" style="width:100px">
                      <el-option v-for="m in ['GET','POST','PUT','PATCH','DELETE']" :key="m" :label="m" :value="m" />
                    </el-select>
                    <el-input v-model="req.name" placeholder="请求名称" style="width:200px" />
                    <el-input v-model="req.url" placeholder="URL，支持 {{var}} 或 ${var}" style="flex:1" />
                    <el-tooltip content="从 cURL / fetch / F12 复制粘贴智能解析" placement="top">
                      <el-button link type="primary" @click="openPasteDialog(req)">
                        <el-icon><DocumentCopy /></el-icon>
                        粘贴
                      </el-button>
                    </el-tooltip>
                    <el-button link type="danger" @click="tg.samplers.splice(ri, 1)">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                  <el-tabs type="border-card" class="request-tabs">
                    <el-tab-pane label="Headers">
                      <div v-for="(h, hi) in req.headers" :key="hi" class="kv-row">
                        <el-input v-model="h.name" placeholder="Key" style="width:200px" />
                        <el-input v-model="h.value" placeholder="Value，支持变量" style="flex:1" />
                        <el-button link type="danger" @click="req.headers.splice(hi, 1)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                      <el-button link size="small" @click="req.headers.push({name:'', value:''})">
                        <el-icon><Plus /></el-icon>添加 Header
                      </el-button>
                    </el-tab-pane>
                    <el-tab-pane label="Params">
                      <div v-for="(p, pi) in req.params" :key="pi" class="kv-row">
                        <el-input v-model="p.name" placeholder="Key" style="width:200px" />
                        <el-input v-model="p.value" placeholder="Value" style="flex:1" />
                        <el-button link type="danger" @click="req.params.splice(pi, 1)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                      <el-button link size="small" @click="req.params.push({name:'', value:''})">
                        <el-icon><Plus /></el-icon>添加 Param
                      </el-button>
                    </el-tab-pane>
                    <el-tab-pane v-if="['POST','PUT','PATCH','DELETE'].includes(req.method)" label="Body">
                      <el-input v-model="req.body" type="textarea" :rows="6" placeholder="请求体（JSON/文本/XML），支持 {{var}} 或 ${var}" />
                    </el-tab-pane>
                    <el-tab-pane label="断言">
                      <div v-for="(a, ai) in req.assertions" :key="ai" class="assertion-row">
                        <el-select v-model="a.type" style="width:140px">
                          <el-option label="响应码" value="response_code" />
                          <el-option label="JSON Path" value="json_path" />
                          <el-option label="响应包含" value="contains" />
                        </el-select>
                        <el-input v-if="a.type === 'json_path'" v-model="a.path" placeholder="JSON Path" style="width:180px" />
                        <el-input v-model="a.value" placeholder="期望值" style="flex:1" />
                        <el-button link type="danger" @click="req.assertions.splice(ai, 1)">
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                      <el-button link size="small" @click="req.assertions.push({type:'response_code', value:'200'})">
                        <el-icon><Plus /></el-icon>添加断言
                      </el-button>
                    </el-tab-pane>
                  </el-tabs>
                </div>
              </div>
            </el-card>

            <el-button v-if="form.script_type === 'ONLINE'" class="add-tg-btn" @click="addThreadGroup">
              <el-icon><Plus /></el-icon>添加线程组
            </el-button>
          </template>
        </div>
      </el-main>
    </el-container>

    <!-- 导入 JMX 弹窗 -->
    <el-dialog v-model="importJmxDialogVisible" title="导入 JMX 创建脚本" width="600px">
      <el-form label-width="100px">
        <el-form-item label="脚本名称">
          <el-input v-model="importForm.name" placeholder="默认使用文件名" />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="importForm.projects" multiple clearable placeholder="支持多选：脚本可被多个项目复用" style="width:100%" collapse-tags collapse-tags-tooltip>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="importForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="JMX 文件" required>
          <el-upload
            ref="jmxUploadRef"
            :auto-upload="false"
            accept=".jmx"
            :limit="1"
            :on-change="onImportFileChange"
            :on-remove="onImportFileRemove"
          >
            <el-button type="primary">选择 JMX 文件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importJmxDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" @click="submitImportJmx">导入</el-button>
      </template>
    </el-dialog>

    <!-- 智能粘贴 cURL/fetch/原始 HTTP -->
    <el-dialog v-model="pasteDialogVisible" title="智能粘贴 cURL / fetch / 原始 HTTP" width="720px" :close-on-click-modal="false">
      <el-alert
        type="info"
        :closable="false"
        style="margin-bottom: 12px"
        title="支持格式"
        description="cURL (bash/PowerShell)、fetch (Node.js)、原始 HTTP 请求、原始 Header 列表。粘贴后点「解析预览」可看到拆解结果。"
      />
      <el-input
        v-model="pasteInput"
        type="textarea"
        :rows="10"
        placeholder="把 F12 Network → Copy as cURL / fetch 的内容，或直接复制的 Header 列表粘到这里"
        @paste="onPasteAutoDetect"
      />
      <div v-if="pastePreview" style="margin-top: 12px; padding: 12px; background: #f5f7fa; border-radius: 4px;">
        <div style="font-weight: 600; margin-bottom: 8px">解析预览：</div>
        <div>Method: <el-tag size="small">{{ pastePreview.method }}</el-tag></div>
        <div>URL: <code style="word-break: break-all">{{ pastePreview.url || '(未识别)' }}</code></div>
        <div v-if="pastePreview.headers.length">Headers（{{ pastePreview.headers.length }}）：
          <span v-for="(h, i) in pastePreview.headers" :key="i" style="margin-right: 8px">
            <el-tag size="small" type="info">{{ h.name }}: {{ h.value.length > 30 ? h.value.slice(0,30)+'...' : h.value }}</el-tag>
          </span>
        </div>
        <div v-else>Headers: <span style="color: #909399">(无)</span></div>
        <div v-if="pastePreview.body">Body（{{ pastePreview.body.length }} 字符）：<code style="word-break: break-all">{{ pastePreview.body.length > 100 ? pastePreview.body.slice(0,100)+'...' : pastePreview.body }}</code></div>
      </div>
      <template #footer>
        <el-button @click="pasteDialogVisible = false">取消</el-button>
        <el-button @click="previewPaste">解析预览</el-button>
        <el-button type="primary" :disabled="!pastePreview" @click="applyPaste">填入请求</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh, Upload, Plus, Check, VideoPlay, Delete, Connection, Operation, DocumentCopy
} from '@element-plus/icons-vue'
import {
  getScripts, getScript, createScript, updateScript, deleteScript,
  executeScript, checkJmx, importJmx, exportJmx as exportJmxApi, getProjects, getLoadLimits,
  parseJmxToOnline,
  uploadScriptCsvFiles, getScriptCsvFiles, deleteScriptCsvFile
} from '@/api/performance'
import { parseCurl } from '@/utils/curlParser'

const router = useRouter()
const route = useRoute()

const scripts = ref([])
const projects = ref([])
const selectedProject = ref(null)
const currentScriptId = ref(null)
const saving = ref(false)
const executing = ref(false)
const parsing = ref(false)
const fileList = ref([])
const jmxFile = ref(null)
const dangerWarnings = ref([])
const importJmxDialogVisible = ref(false)
const importing = ref(false)
const importForm = reactive({ name: '', project: null, description: '', file: null })
const jmxUploadRef = ref(null)
const csvFiles = ref([])
const csvUploadRef = ref(null)
const uploadingCsv = ref(false)

// 智能粘贴：cURL/fetch/原始 HTTP
const pasteDialogVisible = ref(false)
const pasteInput = ref('')
const pasteTargetReq = ref(null)  // 解析后要填到的请求
const pastePreview = ref(null)    // 解析预览 { method, url, headers, body }

const defaultThreadGroup = () => ({
  name: '默认线程组',
  thread_count: 10,
  ramp_up: 10,
  loops: -1,
  duration: 60,
  variables: [],
  csv_datasets: [],
  samplers: []
})

const defaultSampler = () => ({
  name: '',
  method: 'GET',
  url: '',
  headers: [],
  params: [],
  body: '',
  assertions: [{ type: 'response_code', value: '200' }]
})

const form = reactive({
  name: '',
  description: '',
  projects: [],
  status: 'draft',
  script_type: 'ONLINE',
  jmx_config: {},
  jmx_content: '',
  variables: [],
  csv_datasets: [],
  thread_count: 10,
  ramp_up: 10,
  duration: 60,
  realtime_enabled: false
})

const threadGroups = computed({
  get() {
    return form.jmx_config?.thread_groups || []
  },
  set(val) {
    if (!form.jmx_config) form.jmx_config = {}
    form.jmx_config.thread_groups = val
  }
})

function scriptTypeLabel(type) {
  const map = { ONLINE: '在线编排', JMX_RAW: '纯 JMX', JMX_UPLOAD: '上传 JMX' }
  return map[type] || type
}

function statusLabel(status) {
  return status === 'published' ? '已发布' : '草稿'
}

async function loadProjects() {
  try {
    const res = await getProjects()
    projects.value = res.data?.results || res.data || []
  } catch (e) { /* ignore */ }
}

async function loadScripts() {
  try {
    const params = {}
    if (selectedProject.value) params.project = selectedProject.value
    const res = await getScripts(params)
    scripts.value = res.data?.results || res.data || []
  } catch (e) {
    ElMessage.error('加载脚本列表失败')
  }
}

async function selectScript(id) {
  if (saving.value) return
  currentScriptId.value = id
  try {
    const res = await getScript(id)
    const d = res.data
    Object.assign(form, {
      name: d.name || '',
      description: d.description || '',
      projects: d.projects || [],
      status: d.status || 'draft',
      script_type: d.script_type || 'ONLINE',
      jmx_config: d.jmx_config || { thread_groups: [defaultThreadGroup()] },
      jmx_content: d.jmx_content || '',
      variables: d.variables || [],
      csv_datasets: d.csv_datasets || [],
      thread_count: d.thread_count || 10,
      ramp_up: d.ramp_up || 10,
      duration: d.duration || 60,
      realtime_enabled: d.realtime_enabled || false
    })
    if (!form.jmx_config.thread_groups || !form.jmx_config.thread_groups.length) {
      form.jmx_config.thread_groups = [defaultThreadGroup()]
    }
    // 兼容旧数据：确保数组字段存在
    form.jmx_config.thread_groups.forEach(tg => {
      tg.variables = tg.variables || []
      tg.csv_datasets = tg.csv_datasets || []
      tg.samplers = tg.samplers || []
      tg.samplers.forEach(s => {
        s.headers = s.headers || []
        s.params = s.params || []
        s.assertions = s.assertions || [{ type: 'response_code', value: '200' }]
      })
    })
    fileList.value = []
    jmxFile.value = null
    dangerWarnings.value = []
    csvFiles.value = []
    if (d.jmx_file_url) {
      fileList.value = [{ name: d.jmx_file_url.split('/').pop(), url: d.jmx_file_url }]
    }
    await loadCsvFiles()
  } catch (e) {
    ElMessage.error('加载脚本失败')
  }
}

function createNewScript() {
  currentScriptId.value = null
  Object.assign(form, {
    name: '',
    description: '',
    projects: [],
    status: 'draft',
    script_type: 'ONLINE',
    jmx_config: { thread_groups: [defaultThreadGroup()] },
    jmx_content: '',
    variables: [],
    csv_datasets: [],
    thread_count: 10,
    ramp_up: 10,
    duration: 60,
    realtime_enabled: false
  })
  fileList.value = []
  jmxFile.value = null
  dangerWarnings.value = []
}

function addThreadGroup() {
  form.jmx_config.thread_groups.push(defaultThreadGroup())
}

function addRequest(tgIdx) {
  form.jmx_config.thread_groups[tgIdx].samplers.push(defaultSampler())
}

function addVariable() {
  form.variables.push({ name: '', value: '' })
}

async function handleParseToOnline() {
  if (!currentScriptId.value) {
    ElMessage.warning('请先保存脚本')
    return
  }
  parsing.value = true
  try {
    const res = await parseJmxToOnline(currentScriptId.value)
    ElMessage.success(res.data?.detail || '解析成功')
    if (res.data?.warnings?.length) {
      res.data.warnings.forEach(w => ElMessage.warning(w))
    }
    await selectScript(currentScriptId.value)
    await loadScripts()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || JSON.stringify(e.response?.data) || '解析失败')
  } finally {
    parsing.value = false
  }
}

async function loadCsvFiles() {
  if (!currentScriptId.value) return
  try {
    const res = await getScriptCsvFiles(currentScriptId.value)
    csvFiles.value = res.data || []
  } catch (e) {
    ElMessage.error('加载 CSV 文件失败')
  }
}

async function onCsvFileChange(file, fileList) {
  if (!currentScriptId.value) {
    ElMessage.warning('请先保存脚本再上传 CSV')
    csvUploadRef.value?.clearFiles()
    return
  }
  const readyFiles = fileList.filter(f => f.status === 'ready').map(f => f.raw).filter(Boolean)
  if (!readyFiles.length) return
  uploadingCsv.value = true
  try {
    const formData = new FormData()
    readyFiles.forEach(f => formData.append('files', f))
    await uploadScriptCsvFiles(currentScriptId.value, formData)
    ElMessage.success('CSV 上传成功')
    await loadCsvFiles()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || JSON.stringify(e.response?.data) || 'CSV 上传失败')
  } finally {
    uploadingCsv.value = false
    csvUploadRef.value?.clearFiles()
  }
}

async function handleDeleteCsv(fileId) {
  try {
    await ElMessageBox.confirm('确定删除该 CSV 文件吗？', '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteScriptCsvFile(currentScriptId.value, { file_id: fileId })
    ElMessage.success('已删除')
    await loadCsvFiles()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || JSON.stringify(e.response?.data) || '删除失败')
  }
}

async function handleDeleteScript(item) {
  try {
    await ElMessageBox.confirm(
      `确定删除脚本「${item.name}」吗？其关联的执行记录与报告也会一并删除，且不可恢复。`,
      '确认删除脚本',
      { type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteScript(item.id)
    ElMessage.success('脚本已删除')
    if (currentScriptId.value === item.id) {
      currentScriptId.value = null
    }
    await loadScripts()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || JSON.stringify(e.response?.data) || '删除失败')
  }
}

function onFileChange(file) {
  jmxFile.value = file.raw || file
}

function onFileRemove() {
  jmxFile.value = null
  fileList.value = []
}

function onImportFileChange(file) {
  importForm.file = file.raw || file
  if (!importForm.name) importForm.name = file.name
}

function onImportFileRemove() {
  importForm.file = null
}

async function submitImportJmx() {
  if (!importForm.file) {
    ElMessage.warning('请选择 JMX 文件')
    return
  }
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('jmx_file', importForm.file)
    if (importForm.name) formData.append('name', importForm.name)
    importForm.projects.forEach(pid => formData.append('projects', pid))
    if (importForm.description) formData.append('description', importForm.description)
    const res = await importJmx(formData)
    ElMessage.success('导入成功')
    importJmxDialogVisible.value = false
    await loadScripts()
    selectScript(res.data.id)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || JSON.stringify(e.response?.data) || '导入失败')
  } finally {
    importing.value = false
  }
}

// ===== 智能粘贴 cURL/fetch/原始 HTTP =====
function openPasteDialog(req) {
  pasteTargetReq.value = req
  pasteInput.value = ''
  pastePreview.value = null
  pasteDialogVisible.value = true
}

function onPasteAutoDetect(e) {
  // 粘贴后 200ms 自动解析预览
  setTimeout(() => {
    if (pasteInput.value && pasteInput.value.length > 10) {
      try {
        pastePreview.value = parseCurl(pasteInput.value)
      } catch (err) {
        // 解析失败不报错，让用户手动点"解析预览"
      }
    }
  }, 200)
}

function previewPaste() {
  if (!pasteInput.value) {
    ElMessage.warning('请先粘贴内容')
    return
  }
  try {
    pastePreview.value = parseCurl(pasteInput.value)
    if (!pastePreview.value.url && pastePreview.value.headers.length === 0 && !pastePreview.value.body) {
      ElMessage.warning('未能解析出 URL/Headers/Body，请检查粘贴内容格式')
    } else {
      ElMessage.success(`解析成功：${pastePreview.value.method} ${pastePreview.value.url || '(无URL)'} · ${pastePreview.value.headers.length} 个 Header`)
    }
  } catch (err) {
    ElMessage.error('解析失败：' + err.message)
  }
}

function applyPaste() {
  const req = pasteTargetReq.value
  const p = pastePreview.value
  if (!req || !p) return

  // 1) 覆盖 method/url
  if (p.method && ['GET','POST','PUT','PATCH','DELETE'].includes(p.method)) {
    req.method = p.method
  }
  if (p.url) {
    req.url = p.url
  }

  // 2) Headers 合并（避免重复同名）
  if (p.headers && p.headers.length) {
    if (!Array.isArray(req.headers)) req.headers = []
    const existing = new Set(req.headers.map(h => h.name.toLowerCase()))
    for (const h of p.headers) {
      if (!h.name) continue
      if (existing.has(h.name.toLowerCase())) continue
      req.headers.push({ name: h.name, value: h.value })
      existing.add(h.name.toLowerCase())
    }
  }

  // 3) Body
  if (p.body) {
    req.body = p.body
  }

  ElMessage.success('已填入请求，记得点「保存」持久化')
  pasteDialogVisible.value = false
  pasteInput.value = ''
  pastePreview.value = null
  pasteTargetReq.value = null
}

async function exportJmx() {
  if (!currentScriptId.value) {
    ElMessage.warning('请先保存脚本')
    return
  }
  try {
    const res = await exportJmxApi(currentScriptId.value)
    const blob = new Blob([res.data], { type: 'application/xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${form.name || 'script'}.jmx`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('导出 JMX 失败')
  }
}

async function handleSave(opts = {}) {
  const silent = !!opts.silent
  if (!form.name) {
    ElMessage.warning('请输入脚本名称')
    return
  }
  if (form.script_type === 'JMX_UPLOAD' && !currentScriptId.value && !jmxFile.value) {
    ElMessage.warning('JMX 导入模式必须上传 JMX 文件')
    return
  }
  saving.value = true
  try {
    const formData = new FormData()
    formData.append('name', form.name)
    formData.append('description', form.description || '')
    form.projects.forEach(pid => formData.append('projects', pid))
    formData.append('status', form.status)
    formData.append('script_type', form.script_type)
    formData.append('thread_count', String(form.thread_count))
    formData.append('ramp_up', String(form.ramp_up))
    formData.append('duration', String(form.duration))
    formData.append('realtime_enabled', String(form.realtime_enabled))

    if (form.script_type === 'ONLINE') {
      // 同步顶层默认参数到线程组
      const config = JSON.parse(JSON.stringify(form.jmx_config))
      config.variables = form.variables || []
      config.csv_datasets = form.csv_datasets || []
      formData.append('jmx_config', JSON.stringify(config))
      formData.append('variables', JSON.stringify(form.variables || []))
      formData.append('csv_datasets', JSON.stringify(form.csv_datasets || []))
    } else if (form.script_type === 'JMX_RAW') {
      formData.append('jmx_content', form.jmx_content || '')
    } else if (jmxFile.value) {
      formData.append('jmx_file', jmxFile.value)
    }

    let res
    if (currentScriptId.value) {
      res = await updateScript(currentScriptId.value, formData)
    } else {
      res = await createScript(formData)
      currentScriptId.value = res.data.id
    }
    if (!silent) {
      ElMessage.success('保存成功')
    }
    await loadScripts()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || JSON.stringify(e.response?.data) || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleExecute() {
  if (!currentScriptId.value) {
    ElMessage.warning('请先保存脚本')
    return
  }
  try {
    await ElMessageBox.confirm('确定要立即执行该性能脚本吗？', '执行确认', { type: 'warning' })
  } catch {
    return
  }
  executing.value = true
  try {
    // 执行前先自动保存，确保 jmx_config（线程组的 thread_count/ramp_up/duration/loops）
    // 已持久化到数据库，避免「改了 tg 参数但没点保存就执行」时 JMeter 读到旧值
    await handleSave({ silent: true })
    // 把当前默认线程组的参数作为覆盖值传给后端，让 execution 顶部元信息
    // （线程数 / Ramp-Up / 持续）正确反映用户实际设置
    const tg = (threadGroups.value && threadGroups.value[0]) || {}
    const overrides = {
      thread_count: tg.thread_count,
      ramp_up: tg.ramp_up,
      duration: tg.duration,
      loops: tg.loops,
    }
    const res = await executeScript(currentScriptId.value, overrides)
    ElMessage.success(`执行已触发，执行ID: ${res.data.execution_id}`)
    router.push(`/performance-testing/executions/${res.data.id}`)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || JSON.stringify(e.response?.data) || '执行失败')
  } finally {
    executing.value = false
  }
}

onMounted(() => {
  loadProjects()
  if (route.query.project) {
    const pid = Number(route.query.project)
    selectedProject.value = pid
    form.projects = [pid]
  }
  loadScripts().then(() => {
    if (route.params.id) {
      selectScript(Number(route.params.id))
    } else if (!currentScriptId.value) {
      createNewScript()
    }
  })
})
</script>

<style scoped>
.script-editor-page {
  background: #f5f7fa;
}
.left-panel {
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}
.left-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 600;
}
.project-filter {
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
  background: #fafbfc;
}
.script-tree {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.script-item {
  position: relative;
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}
.script-item:hover, .script-item.active {
  background: #ecf5ff;
}
.script-del-btn {
  position: absolute;
  top: 6px;
  right: 6px;
  opacity: 0;
  transition: opacity 0.2s;
  padding: 2px;
}
.script-item:hover .script-del-btn {
  opacity: 1;
}
.script-item-name {
  font-size: 14px;
  color: #303133;
  margin-bottom: 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.script-item-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-dot {
  font-size: 12px;
  color: #909399;
}
.status-dot.published {
  color: #67c23a;
}
.right-panel {
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.editor-header {
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: flex-end;
  align-items: center;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.editor-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.section-card {
  margin-bottom: 16px;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.section-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 6px;
}
.inline-title {
  width: 220px;
}
.inline-title :deep(.el-input__inner) {
  font-weight: 600;
  font-size: 15px;
  border: none;
  padding: 0;
  background: transparent;
}
.help-text {
  font-size: 12px;
  color: #909399;
  margin-bottom: 10px;
}
.variable-row, .csv-row, .kv-row, .assertion-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.tg-params {
  margin-bottom: 16px;
}
.sub-section {
  background: #f8f9fb;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}
.sub-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #606266;
  margin-bottom: 10px;
}
.sub-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.sub-section-header .sub-section-title {
  margin-bottom: 0;
}
.empty-text {
  font-size: 12px;
  color: #909399;
  padding: 6px 0 12px;
}
.request-block {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}
.request-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.request-tabs {
  margin-top: 8px;
}
.add-tg-btn {
  width: 100%;
  margin-bottom: 24px;
}
.upload-tip {
  color: #909399;
  font-size: 12px;
}
</style>
