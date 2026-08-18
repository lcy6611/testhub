<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="emit('update:modelValue', $event)"
    title="录制脚本回放"
    width="760px"
    top="5vh"
    destroy-on-close
  >
    <el-form :model="form" label-width="110px">
      <el-form-item label="选择脚本" required>
        <div style="display:flex;gap:8px;width:100%">
          <el-select
            v-model="form.scriptId"
            filterable
            placeholder="选择脚本库中的脚本"
            style="flex:1"
            :loading="listLoading"
            @change="onSelect"
          >
            <el-option
              v-for="s in scripts"
              :key="s.id"
              :label="`#${s.id} ${s.name || '脚本'}`"
              :value="s.id"
            />
          </el-select>
          <el-button :icon="Refresh" :loading="listLoading" @click="loadScripts">刷新</el-button>
        </div>
        <div v-if="!listLoading && scripts.length === 0" style="color:#e6a23c;font-size:12px;margin-top:4px">
          脚本库暂无 Playwright 脚本，请先通过「开始录制」向导或编辑器保存。
        </div>
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

      <el-form-item>
        <template #label>
          <span>无头模式</span>
          <el-tooltip content="开启后浏览器在后端容器后台运行，不会弹出窗口；关闭后容器内通常没有显示器，会直接报错。" placement="top">
            <el-icon style="margin-left:4px;vertical-align:middle;color:#909399"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <el-switch v-model="form.headless" />
        <span v-if="form.headless" style="margin-left:10px;color:#909399;font-size:12px">后台执行，只返回结果与日志</span>
        <span v-else style="margin-left:10px;color:#e6a23c;font-size:12px">容器环境大概率无法显示浏览器窗口</span>
      </el-form-item>

      <el-form-item>
        <template #label>
          <span>录制回放视频</span>
          <el-tooltip content="执行时同步录制浏览器操作视频，执行完成后可回放观看。" placement="top">
            <el-icon style="margin-left:4px;vertical-align:middle;color:#909399"><QuestionFilled /></el-icon>
          </el-tooltip>
        </template>
        <el-switch v-model="form.recordVideo" />
        <span style="margin-left:10px;color:#909399;font-size:12px">推荐开启，执行完即可回看</span>
      </el-form-item>

      <el-form-item label="脚本代码">
        <div style="width:100%">
          <el-button size="small" :icon="Edit" @click="showCode = !showCode">
            {{ showCode ? '收起' : '展开 / 编辑脚本' }}
          </el-button>
          <span style="margin-left:8px;color:#909399;font-size:12px">
            回放前可手动修正 locator（如把不稳定的 get_by_role 改为稳定的 selector）
          </span>
          <el-input
            v-if="showCode"
            v-model="editableCode"
            type="textarea"
            :rows="12"
            style="margin-top:8px;font-family:monospace;font-size:12px"
            placeholder="录制脚本内容"
          />
        </div>
      </el-form-item>

      <el-form-item>
        <el-button type="warning" :loading="runLoading" :disabled="!form.scriptId" @click="onRun">
          执行回放
        </el-button>
        <span v-if="runLoading" style="margin-left:10px;color:#606266;font-size:12px">
          执行中，可能需要几十秒，请等待…
        </span>
      </el-form-item>
    </el-form>

    <el-result
      v-if="runResult"
      :status="runResult.status === 'passed' ? 'success' : 'error'"
      :title="`执行状态：${runResult.status}`"
    >
      <template #sub-title>
        <span>执行耗时 {{ runResult.result?.duration }}s · 退出码 {{ runResult.result?.exit_code }}</span>
        <div style="color:#909399;font-size:12px;margin-top:6px">
          <span v-if="runResult.result?.video_url">
            已生成回放视频，时长 {{ formatDuration(runResult.result?.video_duration) }}，下方可直接观看。
          </span>
          <span v-else>未录制视频或录制失败，仅返回结果与日志。</span>
        </div>
      </template>
    </el-result>

    <!-- 回放视频 -->
    <div v-if="runResult?.result?.video_url" class="replay-video">
      <div class="video-title">
        回放视频
        <span v-if="runResult.result?.video_duration" class="video-duration">
          {{ formatDuration(runResult.result.video_duration) }}
        </span>
      </div>
      <video
        controls
        preload="metadata"
        :src="runResult.result.video_url"
        style="width:100%;max-height:360px;background:#000;border-radius:6px"
      >
        您的浏览器不支持视频播放。
      </video>
      <div style="color:#909399;font-size:12px;margin-top:6px">
        提示：脚本在容器内全速执行，若操作间隔很短，视频时长会短于执行耗时，这属于正常现象。
      </div>
    </div>

    <!-- 失败友好步骤提示 -->
    <div v-if="runResult && runResult.status !== 'passed' && failureHint" class="failure-hint">
      <div class="fh-title">
        <el-icon><WarningFilled /></el-icon>
        可能的失败原因与建议
      </div>
      <div v-if="failureHint.lineNo" class="fh-line">
        失败脚本行号：<code>L{{ failureHint.lineNo }}</code>
      </div>
      <div v-if="failureHint.snippet" class="fh-snippet"><code>{{ failureHint.snippet }}</code></div>
      <ul class="fh-tips">
        <li v-for="(t, i) in failureHint.tips" :key="i">{{ t }}</li>
      </ul>
    </div>

    <pre v-if="runResult" class="log">{{ truncate(runResult.result?.output) }}</pre>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Edit, WarningFilled, QuestionFilled } from '@element-plus/icons-vue'
import { getTestScripts, runTestScript } from '@/api/ui_automation'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

const scripts = ref([])
const listLoading = ref(false)
const runLoading = ref(false)
const runResult = ref(null)
const failureHint = ref(null)
const selectedBaseUrl = ref('')
const showCode = ref(false)
const editableCode = ref('')

const form = reactive({
  scriptId: '',
  browser: 'chromium',
  headless: true,
  recordVideo: true,
})

async function loadScripts() {
  listLoading.value = true
  try {
    const r = await getTestScripts({ page_size: 200, framework: 'playwright' })
    const items = r.data.results || r.data || []
    // 脚本库即统一数据源：录制向导 / 编辑器保存的脚本都在这里
    scripts.value = items.filter(s => s.framework === 'playwright' && (s.content || '').trim())
  } catch (e) {
    ElMessage.error('加载脚本列表失败')
  } finally {
    listLoading.value = false
  }
}

function onSelect(id) {
  const s = scripts.value.find(x => x.id === id)
  // 从脚本中取首个 goto/start_with 的 URL 作为可读 Base URL
  const m = (s?.content || '').match(/url\s*=\s*["']([^"']+)["']|goto\(\s*["']([^"']+)["']/)
  selectedBaseUrl.value = (m && (m[1] || m[2])) || ''
  editableCode.value = s?.content || ''
  showCode.value = false
  runResult.value = null
  failureHint.value = null
}

async function onRun() {
  if (!form.scriptId) return
  runLoading.value = true
  try {
    const r = await runTestScript(form.scriptId, {
      headless: form.headless,
      browser: form.browser,
      record_video: form.recordVideo,
      // 把编辑后的代码一并传回，优先于库中保存的（用于修正 locator）
      playwright_code: showCode.value ? editableCode.value : undefined,
    })
    runResult.value = r.data
    failureHint.value = r.data.status === 'passed' ? null : parseFailure(r.data.result?.output || '')
    ElMessage[r.data.status === 'passed' ? 'success' : 'warning'](
      `执行完成，状态：${r.data.status}`
    )
  } catch (e) {
    ElMessage.error('执行失败：' + (e.response?.data?.detail || e.message))
  } finally {
    runLoading.value = false
  }
}

// 解析 traceback，提取失败行号 + 代码片段 + 可操作建议
function parseFailure(output) {
  if (!output) return null
  const hint = { lineNo: null, snippet: '', tips: [] }

  // 1) 提取失败行号（traceback 中 "line N" 或 "line N,"）
  const lineMatches = [...output.matchAll(/line\s+(\d+)/g)]
  if (lineMatches.length) {
    hint.lineNo = parseInt(lineMatches[lineMatches.length - 1][1], 10)
    // 如果 editableCode 有内容，尝试抽取该行片段
    if (editableCode.value && hint.lineNo) {
      const lines = editableCode.value.split('\n')
      if (lines[hint.lineNo - 1]) hint.snippet = lines[hint.lineNo - 1].trim()
    }
  }

  // 2) 识别常见失败类型并给出建议
  const hasTimeout = /Timeout\s+\d+ms exceeded|TimeoutError/i.test(output)
  const hasConnRefused = /ERR_CONNECTION_REFUSED|net::ERR_CONNECTION/i.test(output)
  const hasLocator = /(get_by_role|get_by_text|get_by_placeholder|locator\(|get_by_.*)\(/i.test(output)

  if (hasConnRefused) {
    hint.tips.push('连接被拒绝：Base URL 在后端容器内不可达。容器内 localhost 指向容器自身，请改用 http://host.docker.internal:端口 或服务容器名（如 http://frontend:5173/）。')
  }
  if (hasTimeout && hasLocator) {
    hint.tips.push('定位器超时：录制时的元素定位在回放时失效（页面结构/文案变化）。建议在上方「脚本代码」中把该行 locator 改为更稳定的 selector（如 input[name="wd"]），或在操作前加 page.wait_for_selector(...)。')
    hint.tips.push('录制回放最适合测内部结构稳定的页面；对首页/外部站点（如百度）这类易变页面，locator 容易失效。')
  }
  if (!hint.tips.length) {
    hint.tips.push('执行未通过。可展开下方完整日志查看 traceback，或在上方的「脚本代码」里修正后再次回放。')
  }
  return hint
}

function truncate(text) {
  if (!text) return ''
  const max = 4000
  return text.length > max ? text.slice(0, max) + '\n…（已截断）' : text
}

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return '--'
  const total = Math.round(seconds * 100) / 100
  const m = Math.floor(total / 60)
  const s = (total % 60).toFixed(2).padStart(5, '0')
  return m > 0 ? `${m}:${s}` : `0:${s}`
}

onMounted(loadScripts)
// 每次打开弹窗都重新拉取列表，避免显示保存前的旧快照
watch(() => props.modelValue, (v) => {
  if (v) loadScripts()
})
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
.failure-hint {
  background: #fef0f0;
  border: 1px solid #fbc4c4;
  border-radius: 6px;
  padding: 12px 14px;
  margin-top: 12px;
}
.fh-title {
  font-weight: 600;
  color: #f56c6c;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}
.fh-line {
  font-size: 13px;
  color: #303133;
  margin-bottom: 6px;
}
.fh-line code, .fh-snippet code {
  background: #f5f5f5;
  padding: 1px 6px;
  border-radius: 4px;
  color: #d63384;
}
.fh-snippet {
  background: #fff;
  border: 1px dashed #fbc4c4;
  border-radius: 4px;
  padding: 6px 8px;
  margin-bottom: 8px;
  font-family: monospace;
  font-size: 12px;
  white-space: pre-wrap;
}
.fh-tips {
  margin: 0;
  padding-left: 18px;
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
}
.replay-video {
  margin-top: 12px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
}
.replay-video .video-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.replay-video .video-duration {
  font-weight: normal;
  font-size: 12px;
  color: #606266;
  background: #e4e7ed;
  padding: 1px 6px;
  border-radius: 4px;
}
</style>
