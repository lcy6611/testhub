<template>
  <div class="recorder-view">
    <el-card shadow="never">
      <template #header><b>Playwright 录制回放（#329）</b></template>

      <el-alert type="info" :closable="false" style="margin-bottom:16px">
        录制在本机执行（需本机能访问被测站点）。点「生成录制命令」复制后在本机终端运行
        <code>playwright codegen</code>，操作结束后把生成的 <code>.py</code> 内容粘贴回下方保存，
        即可在平台「执行回放」。
      </el-alert>

      <el-form :model="form" label-width="120px">
        <el-form-item label="被测系统 URL" required>
          <el-input v-model="form.base_url" placeholder="http://frontend:5173/" style="max-width:480px" />
          <span class="tip">容器内默认访问地址为 http://frontend:5173/</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="genLoading" @click="onGenerateCmd">生成录制命令</el-button>
        </el-form-item>
      </el-form>

      <el-card v-if="command" shadow="never" style="margin-top:8px">
        <template #header><b>录制命令</b></template>
        <div class="cmd-box">
          <code>{{ command }}</code>
          <el-button size="small" type="success" @click="copyCommand">复制</el-button>
        </div>
      </el-card>
    </el-card>

    <el-card shadow="never" style="margin-top:16px">
      <template #header><b>粘贴录制脚本</b></template>
      <el-input
        v-model="form.playwright_code"
        type="textarea"
        :rows="14"
        placeholder="在此粘贴本机 playwright codegen 生成的 .py 代码"
      />
      <div style="margin-top:12px">
        <el-form :model="form" inline>
          <el-form-item label="脚本名称">
            <el-input v-model="form.name" placeholder="录制脚本" style="width:220px" />
          </el-form-item>
          <el-form-item label="关联 UI 项目">
            <el-select v-model="form.ui_project_id" placeholder="可选" filterable clearable style="width:220px">
              <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </el-form-item>
        </el-form>
        <el-button type="success" :loading="saveLoading" @click="onSave" :disabled="!form.playwright_code.trim()">
          保存录制脚本
        </el-button>
        <span v-if="savedId" class="tip">已保存：#{{ savedId }}（{{ savedName }}）</span>
      </div>
    </el-card>

    <el-card v-if="savedId" shadow="never" style="margin-top:16px">
      <template #header><b>执行回放</b></template>
      <el-form :model="runForm" inline>
        <el-form-item label="无头模式">
          <el-switch v-model="runForm.headless" />
        </el-form-item>
        <el-form-item>
          <el-button type="warning" :loading="runLoading" @click="onRun">执行回放</el-button>
        </el-form-item>
      </el-form>
      <el-result
        v-if="runResult"
        :status="runResult.status === 'passed' ? 'success' : 'error'"
        :title="`执行状态：${runResult.status}`"
      >
        <template #sub-title>
          <span>耗时 {{ runResult.result?.duration }}s · 退出码 {{ runResult.result?.exit_code }}</span>
        </template>
      </el-result>
      <pre v-if="runResult" class="log">{{ truncate(runResult.result?.output) }}</pre>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getUiProjects, generateCodegenCommand, saveRecordedScript, runRecordedScript,
} from '@/api/ui_automation'

const form = ref({ base_url: 'http://frontend:5173/', playwright_code: '', name: '', ui_project_id: '' })
const runForm = ref({ headless: true })
const projects = ref([])
const command = ref('')
const genLoading = ref(false)
const saveLoading = ref(false)
const runLoading = ref(false)
const savedId = ref(null)
const savedName = ref('')
const runResult = ref(null)

async function loadProjects() {
  try {
    const r = await getUiProjects({ page_size: 200 })
    projects.value = r.data.results || r.data || []
  } catch (e) { /* ignore */ }
}

async function onGenerateCmd() {
  if (!form.value.base_url.trim()) {
    ElMessage.warning('请填写被测系统 URL')
    return
  }
  genLoading.value = true
  try {
    const r = await generateCodegenCommand({ base_url: form.value.base_url })
    command.value = r.data.command
    ElMessage.success('已生成录制命令')
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

async function onSave() {
  if (!form.value.playwright_code.trim()) {
    ElMessage.warning('请先粘贴录制的 .py 代码')
    return
  }
  saveLoading.value = true
  try {
    const r = await saveRecordedScript({
      base_url: form.value.base_url,
      playwright_code: form.value.playwright_code,
      name: form.value.name || undefined,
      ui_project_id: form.value.ui_project_id || undefined,
    })
    savedId.value = r.data.id
    savedName.value = r.data.source_testcase_title || r.data.name || ('#' + r.data.id)
    runResult.value = null
    ElMessage.success(`已保存录制脚本 #${r.data.id}`)
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.detail || e.message))
  } finally {
    saveLoading.value = false
  }
}

async function onRun() {
  if (!savedId.value) return
  runLoading.value = true
  try {
    const r = await runRecordedScript(savedId.value, { headless: runForm.value.headless })
    runResult.value = r.data
    ElMessage[
      r.data.status === 'passed' ? 'success' : 'warning'
    ](`执行完成，状态：${r.data.status}`)
  } catch (e) {
    ElMessage.error('执行失败：' + (e.response?.data?.detail || e.message))
  } finally {
    runLoading.value = false
  }
}

function truncate(text) {
  if (!text) return ''
  const max = 4000
  return text.length > max ? text.slice(0, max) + '\n…（已截断）' : text
}

onMounted(loadProjects)
</script>

<style scoped>
.log {
  background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px;
  max-height: 360px; overflow: auto; white-space: pre-wrap; font-size: 12px; margin-top: 12px;
}
.tip { color: #999; margin-left: 8px; font-size: 12px; }
.cmd-box {
  display: flex; align-items: center; gap: 12px;
  background: #1e1e1e; color: #d4d4d4; padding: 10px 12px; border-radius: 6px;
}
.cmd-box code { flex: 1; word-break: break-all; font-size: 12px; }
</style>
