<template>
  <div class="kb-hub-config" v-loading="loading">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>知识中枢配置</span>
          <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
        </div>
      </template>

      <el-alert
        type="info" :closable="false" show-icon
        title="本页配置知识中枢的引擎与检索参数"
        description="自建知识库、文档管理、外部数据源(飞书)、Dify 项目绑定等已迁出到独立的「知识库管理」模块，请前往该模块维护内容。"
        style="margin-bottom: 16px"
      />

      <el-alert
        :type="config.engine === 'dify' ? 'success' : 'warning'"
        :closable="false" show-icon
        :title="`当前生效引擎：${config.engine === 'dify' ? 'Dify 知识库' : '自建知识中枢（Native）'}`"
        :description="config.engine === 'dify'
          ? 'AI 用例生成等场景会使用「知识库管理」中绑定的 Dify 数据集。'
          : '当前全局使用自建知识中枢，Dify 绑定不会参与生成。切换为 Dify 后，方可使用知识库管理里绑定的 Dify 数据集。'"
        style="margin-bottom: 16px"
      />

      <el-form label-width="160px" style="max-width: 800px">
        <el-form-item label="知识中枢引擎">
          <el-radio-group v-model="config.engine" @change="handleSwitchEngine">
            <el-radio label="dify">Dify 知识库</el-radio>
            <el-radio label="native">自建知识中枢</el-radio>
          </el-radio-group>
          <div class="hint" style="margin-top: 6px">
            全局唯一，决定 AI 用例生成的知识库来源：Dify = 用知识库管理中绑定的 Dify 数据集；自建 = 用已发布的自建知识库与外部同步内容。
          </div>
        </el-form-item>
      </el-form>

      <el-form label-width="160px" style="max-width: 800px">
        <el-form-item label="检索参数">
          <div class="hint" style="margin-bottom: 8px">这些参数会作用于「AI 用例生成」等场景调用 Dify 知识库时的检索行为。</div>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="Top-K">
              <el-input-number v-model="config.top_k" :min="1" :max="20" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="分块大小(字符)">
              <el-input-number v-model="config.chunk_size" :min="100" :max="2000" :step="50" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="分块重叠(字符)">
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
    </el-card>

    <!-- 测试检索 -->
    <el-card style="margin-top: 16px">
      <template #header><span>检索测试</span></template>
      <el-form inline>
        <el-form-item label="测试问题">
          <el-input v-model="testQuery" placeholder="输入测试问题" style="width: 400px" @keyup.enter="handleTest" />
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
          v-for="(r, i) in testResults"
          :key="i"
          :title="`[${(r.score ?? 0).toFixed(4)}] ${r.document_name || (r.segment && r.segment.document && r.segment.document.name) || r.title || '未知文档'}`"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 8px"
        >
          <div class="result-content">{{ (r.content ?? r.segment?.content ?? '').toString().substring(0, 300) }}{{ ((r.content ?? r.segment?.content ?? '').toString().length > 300) ? '...' : '' }}</div>
        </el-alert>
      </div>
    </el-card>
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
const config = reactive({
  engine: 'dify',
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
    // 同步全局引擎状态，供 AI 生成页 / 知识库管理页读取
    await kbHubStore.loadDefaultEngine()
    if (kbHubStore.defaultEngine) config.engine = kbHubStore.defaultEngine
  } catch (e) { console.error(e) }
}
const loadDifyConfigs = async () => {
  try { difyConfigs.value = (await getDifyConfigs()).data?.results || [] } catch {}
}

const handleSwitchEngine = async (val) => {
  const ok = await kbHubStore.setDefaultEngine(val)
  if (ok) {
    config.engine = kbHubStore.defaultEngine
    ElMessage.success('已切换默认回退引擎为 ' + (val === 'dify' ? 'Dify 知识库' : '自建知识中枢'))
  } else {
    ElMessage.error('切换失败，已回滚')
    await kbHubStore.loadDefaultEngine(true)
    config.engine = kbHubStore.defaultEngine
  }
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
    testResults.value = data?.results || []
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
.card-header { display: flex; justify-content: space-between; align-items: center; }
.hint { color: #909399; font-size: 12px; line-height: 1.5; }
.result-content { white-space: pre-wrap; color: #606266; font-size: 13px; line-height: 1.6; }
</style>
