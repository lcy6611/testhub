<template>
  <div class="kb-hub-config" v-loading="loading">
    <!-- 顶部：默认回退引擎标识（提示引擎切换入口） -->
    <el-alert
      :type="kbHubStore.engineType" :closable="false" show-icon
      :title="`默认回退引擎：${kbHubStore.engineDisplay}`"
      :description="kbHubStore.defaultEngine === 'dify'
        ? '项目无 Dify 知识库绑定时，AI 用例生成将使用本地 KB 检索。引擎切换请到「侧边栏·知识中枢」标题右上角下拉。'
        : '项目无本地 KB 时，AI 用例生成将回退到 Dify（如已配置）。引擎切换请到「侧边栏·知识中枢」标题右上角下拉。'"
      style="margin-bottom: 16px"
    />

    <el-tabs v-model="activeTab" type="border-card">
      <!-- ① 文档解析 -->
      <el-tab-pane label="① 文档解析" name="parser">
        <el-alert type="info" :closable="false" show-icon
          title="解析服务用于将 PDF / Word / 扫描件 转为 Markdown"
          description="推荐 MinerU（私有）或 TextIn（云端）；未配置时系统自动回退到内置 Tika，支持 100+ 格式。"
          style="margin-bottom: 16px"
        />
        <el-form label-width="180px" style="max-width: 800px">
          <el-form-item label="解析器">
            <el-select v-model="config.parser_type">
              <el-option label="Apache Tika（内置兜底）" value="tika" />
              <el-option label="MinerU（私有）" value="mineru" />
              <el-option label="TextIn（云端）" value="textin" />
            </el-select>
            <div class="hint">不配置则使用 Tika 兜底；Tika 支持 PDF/Word/Excel/PPT/Markdown 等 100+ 格式</div>
          </el-form-item>
          <el-form-item label="解析服务地址">
            <el-input v-model="config.parser_api_url" placeholder="https://your-parser-api.com/v1/parse" />
          </el-form-item>
          <el-form-item label="解析服务密钥">
            <el-input v-model="config.parser_api_key" placeholder="API Key" show-password />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- ② Embedding -->
      <el-tab-pane label="② Embedding" name="embedding">
        <el-alert type="info" :closable="false" show-icon
          title="向量模型把解析后的文本转为向量，供后续相似度检索"
          description="推荐 Qwen/Qwen3-Embedding-8B 或硅基流动平台。⚠️ 切换 Embedding 模型会使已入库向量失效，需重建索引。"
          style="margin-bottom: 16px"
        />
        <el-form label-width="180px" style="max-width: 800px">
          <el-form-item label="Embedding API 地址">
            <el-input v-model="config.embedding_api_url" placeholder="https://api.siliconflow.cn/v1/embeddings" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="config.embedding_api_key" placeholder="sk-..." show-password />
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="config.embedding_model_name" placeholder="Qwen/Qwen3-Embedding-8B" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- ③ Rerank -->
      <el-tab-pane label="③ Rerank 重排" name="rerank">
        <el-alert type="info" :closable="false" show-icon
          title="对 Embedding 检索出来的 Top-K 候选做精排"
          description="推荐 bge-reranker-v2-m3 或 Qwen/Qwen3-Reranker-8B；可与 Embedding 使用不同端点。"
          style="margin-bottom: 16px"
        />
        <el-form label-width="180px" style="max-width: 800px">
          <el-form-item label="Rerank API 地址">
            <el-input v-model="config.rerank_api_url" placeholder="https://api.siliconflow.cn/v1/rerank" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="config.rerank_api_key" placeholder="sk-..." show-password />
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="config.rerank_model_name" placeholder="Qwen/Qwen3-Reranker-8B" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- ④ 生成/抽取 -->
      <el-tab-pane label="④ 生成 / 抽取" name="extraction">
        <el-alert type="info" :closable="false" show-icon
          title="用于高价值问答综合作答 + 文档自动抽取"
          description="配置通用 LLM 模型即可（如 Qwen3、DeepSeek-V3、GPT-4 等）。"
          style="margin-bottom: 16px"
        />
        <el-form label-width="180px" style="max-width: 800px">
          <el-form-item label="LLM API 地址">
            <el-input v-model="config.extraction_api_url" placeholder="https://api.openai.com/v1/chat/completions" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="config.extraction_api_key" placeholder="sk-..." show-password />
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="config.extraction_model_name" placeholder="Qwen/Qwen3-32B-Instruct" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- ⑤ 视觉理解 -->
      <el-tab-pane label="⑤ 视觉理解" name="vision">
        <el-alert type="warning" :closable="false" show-icon
          title="可选配置：用于截图、图表、界面理解"
          description="没有视觉模型可跳过此项；OCR 与图表抽取将由 LLM/Embedding 模型承担。"
          style="margin-bottom: 16px"
        />
        <el-form label-width="180px" style="max-width: 800px">
          <el-form-item label="视觉模型 API 地址">
            <el-input v-model="config.vision_api_url" placeholder="https://api.openai.com/v1/chat/completions" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="config.vision_api_key" placeholder="sk-..." show-password />
          </el-form-item>
          <el-form-item label="模型名称">
            <el-input v-model="config.vision_model_name" placeholder="gpt-4o / Qwen2-VL-72B" />
          </el-form-item>
        </el-form>
      </el-tab-pane>

      <!-- ⑥ 检索参数（引擎切换已上提到侧边栏菜单右上角） -->
      <el-tab-pane label="⑥ 检索参数" name="retrieval">
        <el-alert type="info" :closable="false" show-icon
          title="检索参数（向量召回 + Rerank 精排）"
          description="AI 用例生成会按项目自动判定（Dify 绑定 → Dify；否则 → 本地 KB）；引擎切换请到「侧边栏·知识中枢菜单右上角」下拉选择。"
          style="margin-bottom: 16px"
        />
        <el-form label-width="180px" style="max-width: 800px">
          <el-row :gutter="20">
            <el-col :span="6">
              <el-form-item label="Top-K">
                <el-input-number v-model="config.top_k" :min="1" :max="20" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="分块大小">
                <el-input-number v-model="config.chunk_size" :min="100" :max="2000" :step="50" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="分块重叠">
                <el-input-number v-model="config.chunk_overlap" :min="0" :max="500" :step="10" />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="最低相关度">
                <el-input-number v-model="config.min_score" :min="0" :max="1" :step="0.05" :precision="2" />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <!-- 底部：保存 + 测试 -->
    <div class="footer-actions">
      <el-button type="primary" :loading="saving" @click="handleSave" size="large">
        保存全部配置
      </el-button>
      <el-button @click="activeTab = 'retrieval'; $nextTick(() => testInput?.focus())" plain>
        测试检索 →
      </el-button>
    </div>

    <!-- 检索测试折叠区 -->
    <el-collapse-transition>
      <el-card v-show="showTest" class="test-section" shadow="never">
        <template #header><span>🔍 检索测试（验证配置）</span></template>
        <el-form inline>
          <el-form-item label="测试问题">
            <el-input ref="testInput" v-model="testQuery" placeholder="输入测试问题" style="width: 400px" @keyup.enter="handleTest" />
          </el-form-item>
          <el-form-item label="Dify 配置">
            <el-select v-model="testDifyId" clearable placeholder="选择 Dify 知识库配置" style="width: 240px">
              <el-option v-for="c in difyConfigs" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="testing" @click="handleTest">检索测试</el-button>
          </el-form-item>
        </el-form>
        <div v-if="testResults.length" class="test-results">
          <el-alert
            v-for="(r, i) in testResults" :key="i"
            :title="`[${(r.score ?? 0).toFixed(4)}] ${r.document_name || (r.segment && r.segment.document && r.segment.document.name) || r.title || '未知文档'}`"
            type="info" :closable="false" show-icon
            style="margin-bottom: 8px"
          >
            <div class="result-content">{{ (r.content ?? r.segment?.content ?? '').toString().substring(0, 300) }}{{ ((r.content ?? r.segment?.content ?? '').toString().length > 300) ? '...' : '' }}</div>
          </el-alert>
        </div>
      </el-card>
    </el-collapse-transition>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getKbHubConfig, updateKbHubConfig, testRetrieval,
  getDifyConfigs,
} from '@/api/kb-hub'
import { useKbHubStore } from '@/stores/kb-hub'

const kbHubStore = useKbHubStore()
const loading = ref(true)
const saving = ref(false)
const activeTab = ref('parser')
const showTest = ref(false)

const config = reactive({
  engine: 'dify',
  parser_type: 'tika', parser_api_url: '', parser_api_key: '',
  embedding_api_url: '', embedding_api_key: '', embedding_model_name: 'Qwen/Qwen3-Embedding-8B',
  rerank_api_url: '', rerank_api_key: '', rerank_model_name: 'Qwen/Qwen3-Reranker-8B',
  extraction_api_url: '', extraction_api_key: '', extraction_model_name: '',
  vision_api_url: '', vision_api_key: '', vision_model_name: '',
  top_k: 5, chunk_size: 500, chunk_overlap: 80, min_score: 0.30,
})

const difyConfigs = ref([])
const testQuery = ref('')
const testDifyId = ref(null)
const testing = ref(false)
const testResults = ref([])

const loadConfig = async () => {
  try {
    const { data } = await getKbHubConfig()
    if (data) Object.assign(config, data)
    await kbHubStore.loadDefaultEngine()
  } catch (e) { console.error(e) }
}
const loadDifyConfigs = async () => {
  try { difyConfigs.value = (await getDifyConfigs()).data?.results || [] } catch {}
}

const handleSave = async () => {
  saving.value = true
  try {
    await updateKbHubConfig(config)
    ElMessage.success('保存成功')
  } catch (e) { ElMessage.error('保存失败') }
  finally { saving.value = false }
}

const handleTest = async () => {
  if (!testQuery.value) { ElMessage.warning('请输入测试问题'); return }
  testing.value = true
  testResults.value = []
  try {
    const { data } = await testRetrieval(testQuery.value, testDifyId.value)
    testResults.value = data?.records || data?.results || []
    if (!testResults.value.length) ElMessage.info('未检索到内容')
  } catch (e) { ElMessage.error('检索失败: ' + (e?.response?.data?.detail || e?.message)) }
  finally { testing.value = false }
}

onMounted(async () => {
  await Promise.all([loadConfig(), loadDifyConfigs()])
  loading.value = false
})
</script>

<style scoped>
.kb-hub-config { padding: 16px; max-width: 1280px; margin: 0 auto; }
.footer-actions { margin-top: 16px; text-align: right; }
.test-section { margin-top: 16px; }
.hint { color: #909399; font-size: 12px; line-height: 1.5; margin-top: 4px; }
.result-content { white-space: pre-wrap; color: #606266; font-size: 13px; line-height: 1.6; }
</style>