<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="录制脚本"
    width="720px"
    top="6vh"
    destroy-on-close
    @closed="onClosed"
  >
    <el-steps :active="step" finish-status="success" align-center>
      <el-step title="配置" />
      <el-step title="录制" />
      <el-step title="导入" />
    </el-steps>

    <div class="wizard-body">
      <!-- 步骤1：配置 -->
      <div v-show="step === 0" class="step-pane">
        <el-form :model="cfg" label-width="120px">
          <el-form-item label="被测系统 URL" required>
            <el-input v-model="cfg.base_url" placeholder="http://frontend:5173/" />
          </el-form-item>
          <el-form-item label="脚本名称">
            <el-input v-model="cfg.name" placeholder="如：登录流程录制" />
          </el-form-item>
          <el-form-item label="脚本语言">
            <el-select v-model="cfg.language" style="width:220px">
              <el-option label="Python" value="python" />
              <el-option label="JavaScript" value="javascript" />
            </el-select>
          </el-form-item>
          <el-form-item label="浏览器">
            <el-select v-model="cfg.browser" style="width:220px">
              <el-option label="Chromium" value="chromium" />
              <el-option label="Chrome" value="chrome" />
              <el-option label="Firefox" value="firefox" />
              <el-option label="WebKit" value="webkit" />
            </el-select>
          </el-form-item>
          <el-form-item label="设备模拟">
            <el-select v-model="cfg.device" style="width:220px" clearable>
              <el-option label="不模拟（默认）" value="" />
              <el-option label="桌面 1280×720" value="1280,720" />
              <el-option label="移动 375×667" value="375,667" />
            </el-select>
          </el-form-item>
          <el-form-item label="保存登录态">
            <el-switch v-model="cfg.save_login" />
            <span class="field-tip">勾选后录制命令附加 --save-storage，本机浏览器登录态将被保存</span>
          </el-form-item>
        </el-form>
      </div>

      <!-- 步骤2：录制 -->
      <div v-show="step === 1" class="step-pane">
        <el-alert type="info" :closable="false" show-icon>
          点击「生成录制命令」并复制到<b>本机终端</b>执行，Playwright 会自动打开浏览器并开始录制你的操作。
          录制完成后关闭浏览器，将生成的 <code>.py</code>（或 <code>.js</code>）用于下一步导入。
        </el-alert>
        <div class="record-actions">
          <el-button type="primary" :loading="genLoading" @click="onGenerate">生成录制命令</el-button>
        </div>
        <el-card v-if="command" shadow="never" class="cmd-card">
          <template #header><b>录制命令</b></template>
          <div class="cmd-box">
            <code>{{ command }}</code>
            <el-button size="small" type="success" @click="copyCommand">复制</el-button>
          </div>
        </el-card>
      </div>

      <!-- 步骤3：导入 -->
      <div v-show="step === 2" class="step-pane">
        <el-upload
          drag
          :auto-upload="false"
          :show-file-list="false"
          accept=".py,.js"
          :on-change="onFileChange"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            将录制好的 <em>.py / .js</em> 文件拖到此处，或<em>点击选择</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">仅支持 Playwright codegen 生成的 Python / JavaScript 脚本</div>
          </template>
        </el-upload>

        <el-input
          v-if="importedCode"
          :model-value="previewCode"
          type="textarea"
          :rows="8"
          readonly
          class="import-preview"
        />

        <div v-if="importedCode" class="import-actions">
          <el-form inline>
            <el-form-item label="脚本名称">
              <el-input v-model="cfg.name" style="width:260px" />
            </el-form-item>
            <el-form-item label="所属项目">
              <div style="display:flex;gap:6px">
                <el-select
                  v-model="cfg.ui_project_id"
                  placeholder="选择 UI 项目"
                  style="width:220px"
                  :loading="projectsLoading"
                >
                  <el-option
                    v-for="p in projects"
                    :key="p.id"
                    :label="p.name"
                    :value="p.id"
                  />
                </el-select>
                <el-button :icon="Refresh" :loading="projectsLoading" circle size="small" title="刷新项目列表" @click="loadProjects" />
              </div>
            </el-form-item>
          </el-form>
          <el-alert
            v-if="!projectsLoading && projects.length === 0"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom:12px"
          >
            暂无 UI 项目，请先前往「UI 自动化 &rarr; 项目管理」创建一个项目后再保存。
          </el-alert>
          <el-alert
            v-else
            type="info"
            :closable="false"
            show-icon
            style="margin-bottom:12px"
          >
            保存后脚本进入统一的脚本库，可在「录制回放」或脚本库中查看与执行。
          </el-alert>
          <el-button type="primary" :loading="saveLoading" :disabled="!cfg.ui_project_id" @click="saveScript">保存到脚本库</el-button>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button v-if="step > 0" @click="step--">上一步</el-button>
      <el-button v-if="step < 2" type="primary" @click="step++">下一步</el-button>
      <el-button v-else type="success" @click="finish">完成</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Refresh } from '@element-plus/icons-vue'
import {
  generateCodegenCommand, createTestScript, getUiProjects,
} from '@/api/ui_automation'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  projectId: { type: [String, Number], default: '' },
})
const emit = defineEmits(['update:modelValue', 'imported'])

const step = ref(0)
const genLoading = ref(false)
const saveLoading = ref(false)
const command = ref('')
const importedCode = ref('')
const projects = ref([])
const projectsLoading = ref(false)

const cfg = reactive({
  base_url: 'http://frontend:5173/',
  name: '',
  language: 'python',
  browser: 'chromium',
  device: '',
  save_login: false,
  ui_project_id: props.projectId || '',
})

const previewCode = ref('')

async function loadProjects() {
  projectsLoading.value = true
  try {
    const r = await getUiProjects({ page_size: 200 })
    const list = r.data.results || r.data || []
    projects.value = list
    if (!cfg.ui_project_id && list.length > 0) {
      cfg.ui_project_id = list[0].id
    }
  } catch (e) {
    ElMessage.error('加载项目列表失败：' + (e.response?.data?.detail || e.message))
  } finally {
    projectsLoading.value = false
  }
}

async function onGenerate() {
  if (!cfg.base_url.trim()) {
    ElMessage.warning('请填写被测系统 URL')
    return
  }
  genLoading.value = true
  try {
    const r = await generateCodegenCommand({
      base_url: cfg.base_url,
      language: cfg.language,
      browser: cfg.browser,
      device: cfg.device || undefined,
      save_login: cfg.save_login,
    })
    command.value = r.data.command
    ElMessage.success('已生成录制命令，请复制到本机执行')
  } catch (e) {
    ElMessage.error('生成命令失败：' + (e.response?.data?.detail || e.message))
  } finally {
    genLoading.value = false
  }
}

async function copyCommand() {
  try {
    await navigator.clipboard.writeText(command.value)
    ElMessage.success('已复制到剪贴板')
  } catch (e) {
    ElMessage.warning('复制失败，请手动选择文本复制')
  }
}

function onFileChange(file) {
  const raw = file.raw
  if (!raw) return
  if (!/\.(py|js)$/.test(raw.name)) {
    ElMessage.warning('仅支持 .py / .js 文件')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    importedCode.value = String(reader.result || '')
    previewCode.value = importedCode.value.length > 600
      ? importedCode.value.slice(0, 600) + '\n…（已截断预览，导入后可见完整内容）'
      : importedCode.value
    if (!cfg.name) cfg.name = raw.name.replace(/\.(py|js)$/, '')
  }
  reader.readAsText(raw)
}

async function saveScript() {
  if (!importedCode.value.trim()) {
    ElMessage.warning('请先选择录制文件')
    return
  }
  if (!cfg.ui_project_id) {
    ElMessage.warning(projects.value.length === 0 ? '暂无可用项目，请先创建 UI 项目' : '请选择所属项目')
    return
  }
  saveLoading.value = true
  try {
    const r = await createTestScript({
      project: cfg.ui_project_id,
      name: cfg.name || '录制脚本',
      description: '通过录制向导保存的 Playwright 脚本',
      script_type: 'CODE',
      content: importedCode.value,
      language: cfg.language,
      framework: 'playwright',
    })
    ElMessage.success(`已保存到脚本库：#${r.data.id}，可在「录制回放」中选择执行`)
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    saveLoading.value = false
  }
}

function finish() {
  emit('update:modelValue', false)
}

function onClosed() {
  step.value = 0
  command.value = ''
  importedCode.value = ''
  previewCode.value = ''
  cfg.name = ''
  cfg.device = ''
  cfg.save_login = false
  cfg.ui_project_id = props.projectId || ''
}

loadProjects()

watch(() => props.projectId, (v) => {
  if (v && !cfg.ui_project_id) {
    cfg.ui_project_id = v
  }
})
</script>

<style scoped>
.wizard-body {
  margin-top: 24px;
  min-height: 280px;
}
.step-pane { padding: 4px 8px; }
.field-tip {
  margin-left: 10px;
  font-size: 12px;
  color: #999;
}
.record-actions { margin-top: 12px; }
.cmd-card { margin-top: 16px; }
.cmd-box {
  display: flex;
  align-items: center;
  gap: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 10px 12px;
  border-radius: 6px;
}
.cmd-box code { flex: 1; word-break: break-all; font-size: 12px; }
.import-preview { margin-top: 16px; font-family: monospace; }
.import-actions { margin-top: 16px; }
</style>
