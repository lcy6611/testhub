<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="录制脚本回放"
    width="720px"
    top="6vh"
    destroy-on-close
  >
    <el-form :model="form" label-width="110px">
      <el-form-item label="选择脚本" required>
        <el-select
          v-model="form.scriptId"
          filterable
          placeholder="选择已保存的录制脚本"
          style="width:100%"
          :loading="listLoading"
          @change="onSelect"
        >
          <el-option
            v-for="s in scripts"
            :key="s.id"
            :label="`#${s.id} ${s.source_testcase_title || s.name || '录制脚本'}`"
            :value="s.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="Base URL">
        <el-input :model-value="selectedBaseUrl" readonly />
      </el-form-item>

      <el-form-item label="浏览器">
        <el-select v-model="form.browser" style="width:220px">
          <el-option label="Chromium" value="chromium" />
          <el-option label="Chrome" value="chrome" />
          <el-option label="Firefox" value="firefox" />
          <el-option label="WebKit" value="webkit" />
        </el-select>
      </el-form-item>

      <el-form-item label="无头模式">
        <el-switch v-model="form.headless" />
      </el-form-item>

      <el-form-item>
        <el-button type="warning" :loading="runLoading" :disabled="!form.scriptId" @click="onRun">
          执行回放
        </el-button>
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
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getCaseScriptGenerations, runRecordedScript } from '@/api/ui_automation'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const scripts = ref([])
const listLoading = ref(false)
const runLoading = ref(false)
const runResult = ref(null)
const selectedBaseUrl = ref('')

const form = reactive({
  scriptId: '',
  browser: 'chromium',
  headless: true,
})

async function loadScripts() {
  listLoading.value = true
  try {
    const r = await getCaseScriptGenerations({ page_size: 200 })
    const items = r.data.results || r.data || []
    scripts.value = items.filter(s => (s.playwright_code || '').trim())
  } catch (e) {
    ElMessage.error('加载录制脚本列表失败')
  } finally {
    listLoading.value = false
  }
}

function onSelect(id) {
  const s = scripts.value.find(x => x.id === id)
  selectedBaseUrl.value = s?.base_url || ''
  runResult.value = null
}

async function onRun() {
  if (!form.scriptId) return
  runLoading.value = true
  try {
    const r = await runRecordedScript(form.scriptId, {
      headless: form.headless,
      browser: form.browser,
    })
    runResult.value = r.data
    ElMessage[r.data.status === 'passed' ? 'success' : 'warning'](
      `执行完成，状态：${r.data.status}`
    )
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

onMounted(loadScripts)
</script>

<style scoped>
.log {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  max-height: 320px;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 12px;
  margin-top: 12px;
}
</style>
