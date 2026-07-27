<template>
  <div class="text2sql-page">
    <el-row :gutter="16" class="full-height">
      <el-col :span="7" class="full-height">
        <el-card class="panel-card full-height" :body-style="{ padding: '16px', height: '100%' }">
          <div class="panel-title">查询环境</div>

          <div class="form-row">
            <div class="form-label">环境</div>
            <el-select v-model="selectedEnvId" placeholder="选择数据库直连环境" style="width: 100%" @change="onEnvChange">
              <el-option
                v-for="env in dbEnvironments"
                :key="env.id"
                :label="`${env.name} (${env.db_type || 'mysql'}://${env.db_host || '?'})`"
                :value="env.id"
              />
            </el-select>
            <div v-if="!dbEnvironments.length" class="form-hint warning">
              ⚠️ 当前没有「数据库直连」类型的环境，请到「环境管理」新建一个（host 填 <code>host.docker.internal</code>）。
            </div>
            <div v-else-if="currentEnv && !currentEnv.db_host" class="form-hint warning">
              ⚠️ 该环境未配置数据库主机，无法执行 SQL。
            </div>
          </div>

          <div class="form-row">
            <div class="form-label">构建数据库</div>
            <el-select v-model="selectedDb" multiple placeholder="请选择要扫描的数据库（可多选）" style="width: 100%">
              <el-option v-for="db in databases" :key="db" :label="db" :value="db" />
            </el-select>
            <div class="form-hint">请先点击连接，连接成功后再查询数据库</div>
          </div>

          <div class="form-row actions">
            <el-button type="primary" @click="connectEnv">连接并查询数据库</el-button>
            <el-button @click="refreshStatus">刷新状态</el-button>
            <el-button @click="buildIndex">构建索引</el-button>
          </div>

          <div class="info-block" v-if="currentEnv">
            <div class="info-title">连接信息</div>
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="分类">{{ currentEnv.category || '-' }}</el-descriptions-item>
              <el-descriptions-item label="访问方式">{{ currentEnv.access_method_display }}</el-descriptions-item>
              <el-descriptions-item label="数据库范围">{{ currentEnv.database_scope || '-' }}</el-descriptions-item>
              <el-descriptions-item label="统一状态">
                <el-tag :type="envStatusType">{{ currentEnv.status_display }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="最近同步">{{ currentEnv.last_sync || '-' }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </el-col>

      <el-col :span="17" class="full-height">
        <el-card class="panel-card full-height" :body-style="{ padding: '16px', height: '100%', display: 'flex', flexDirection: 'column' }">
          <div class="panel-title">Text2SQL 工作台</div>

          <div class="mode-bar">
            <el-radio-group v-model="mode" @change="onModeChange">
              <el-radio-button label="query">查询模式</el-radio-button>
              <el-radio-button label="dml">数据变更模式</el-radio-button>
            </el-radio-group>
            <span class="mode-tip">{{ modeTip }}</span>
          </div>

          <div class="form-label">自然语言查询</div>
          <el-input
            v-model="question"
            type="textarea"
            :rows="4"
            placeholder="请输入业务问题，例如：查询最近 30 天 P1 缺陷趋势"
            resize="none"
          />

          <div class="actions">
            <el-button type="primary" @click="generateSQL" :loading="generating">生成 SQL</el-button>
            <el-button @click="validateSQL" :loading="validating">校验 SQL</el-button>
            <el-button type="success" @click="executeSQL" :loading="executing">执行 SQL</el-button>
          </div>

          <div class="form-label" style="margin-top: 12px;">SQL 编辑器</div>
          <el-input
            v-model="sql"
            type="textarea"
            :rows="6"
            placeholder="生成后的 SQL 将显示在这里"
            resize="none"
          />

          <div class="form-label" style="margin-top: 12px;">执行结果</div>
          <div class="result-box" v-if="result">
            <el-alert v-if="result.message" :title="result.message" type="info" :closable="false" />
            <el-alert v-if="result.error" :title="result.error" type="error" :closable="false" show-icon />
            <el-table v-if="result.rows && result.rows.length" :data="result.rows" size="small" style="margin-top: 8px;">
              <el-table-column v-for="key in resultKeys" :key="key" :prop="key" :label="key" />
            </el-table>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const MODE_TIPS = {
  query: '适用于查询数据，只读 SQL 真实执行，写操作仅回滚演示。',
  dml: '适用于数据变更，INSERT/UPDATE/DELETE 将真实提交落库，请谨慎使用。',
}
import { ElMessage } from 'element-plus'
import {
  getEnvironments,
  connectEnvironment,
  getEnvironmentDatabases,
  createText2SQLRecord,
  generateSQL as apiGenerateSQL,
  validateSQL as apiValidateSQL,
  executeSQL as apiExecuteSQL,
} from '@/api/ops-tools'

const environments = ref([])
const selectedEnvId = ref(null)
const currentEnv = ref(null)
const databases = ref([])
const selectedDb = ref([])
const mode = ref('query')
const question = ref('')
const sql = ref('')
const result = ref(null)
const recordId = ref(null)
const generating = ref(false)
const validating = ref(false)
const executing = ref(false)

const dbEnvironments = computed(() =>
  (environments.value || []).filter(e => e.access_method === 'db')
)

const modeTip = computed(() => MODE_TIPS[mode.value] || MODE_TIPS.query)

function onModeChange(val) {
  mode.value = val
}

const envStatusType = computed(() => {
  const s = currentEnv.value?.status
  if (s === 'ready') return 'success'
  if (s === 'error') return 'danger'
  return 'info'
})

const resultKeys = computed(() => {
  if (!result.value?.rows?.length) return []
  return Object.keys(result.value.rows[0])
})

async function loadEnvironments() {
  const res = await getEnvironments()
  environments.value = res.data.results || res.data || []
  // 如果当前选中的 env 不再属于 db 类型（或被删了），清空选中
  if (selectedEnvId.value && !dbEnvironments.value.find(e => e.id === selectedEnvId.value)) {
    selectedEnvId.value = null
    currentEnv.value = null
  }
  // 默认选中第一个 db 环境
  if (!selectedEnvId.value && dbEnvironments.value.length) {
    onEnvChange(dbEnvironments.value[0].id)
  }
}

function onEnvChange(id) {
  currentEnv.value = environments.value.find(e => e.id === id) || null
  selectedDb.value = []
  databases.value = []
  // 切换环境后清空上次生成的记录/SQL/结果，否则用户会误以为"在 sakila 查"实际还在用 testhub_dev 的 record
  recordId.value = null
  sql.value = ''
  result.value = null
}

async function connectEnv() {
  if (!selectedEnvId.value) return ElMessage.warning('请选择环境')
  const res = await connectEnvironment(selectedEnvId.value)
  ElMessage.success(res.data.detail)
  currentEnv.value.status = res.data.status
  const dbRes = await getEnvironmentDatabases(selectedEnvId.value)
  databases.value = dbRes.data.databases || []
}

function refreshStatus() {
  loadEnvironments()
  ElMessage.success('已刷新')
}

function buildIndex() {
  ElMessage.info('构建索引功能待接入真实数据库')
}

async function generateSQL() {
  if (!question.value.trim()) return ElMessage.warning('请输入自然语言问题')
  if (!selectedEnvId.value) return ElMessage.warning('请选择数据库直连环境')
  if (currentEnv.value && !currentEnv.value.db_host) {
    return ElMessage.warning('该环境未配置数据库主机，无法生成 SQL')
  }
  generating.value = true
  result.value = null
  try {
    const createRes = await createText2SQLRecord({
      environment: selectedEnvId.value,
      mode: mode.value,
      question: question.value,
    })
    recordId.value = createRes.data.id
    const res = await apiGenerateSQL(recordId.value, {
      question: question.value,
      mode: mode.value,
      current_env_id: selectedEnvId.value,
    })
    sql.value = res.data.generated_sql
    if (res.data.status === 'failed') {
      result.value = { error: res.data.error_message || 'SQL 生成失败' }
      ElMessage.error('SQL 生成失败，详见右侧结果')
    } else {
      ElMessage.success('SQL 已生成')
    }
  } catch (err) {
    result.value = { error: err.response?.data?.detail || err.message || '生成失败' }
    ElMessage.error('SQL 生成失败，详见右侧结果')
  } finally {
    generating.value = false
  }
}

async function validateSQL() {
  if (!recordId.value) return ElMessage.warning('请先生成 SQL')
  validating.value = true
  try {
    const res = await apiValidateSQL(recordId.value, {
      sql: sql.value,
      current_env_id: selectedEnvId.value,
    })
    ElMessage.success(`校验状态：${res.data.status_display}`)
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '校验失败')
  } finally {
    validating.value = false
  }
}

async function executeSQL() {
  if (!recordId.value) return ElMessage.warning('请先生成 SQL')
  if (currentEnv.value && !currentEnv.value.db_host) {
    result.value = { error: '该环境未配置数据库主机，无法执行 SQL。请在「环境管理」中配置 db_host。' }
    return ElMessage.error('环境未配置数据库主机')
  }
  executing.value = true
  result.value = null
  try {
    const res = await apiExecuteSQL(recordId.value, {
      sql: sql.value,
      mode: mode.value,
      current_env_id: selectedEnvId.value,
    })
    if (res.data.status === 'failed') {
      result.value = { error: res.data.error_message || '执行失败' }
      ElMessage.error('执行失败，详见右侧结果')
    } else {
      result.value = res.data.result
      ElMessage.success('执行成功')
    }
  } catch (err) {
    result.value = { error: err.response?.data?.detail || err.message || '执行失败' }
    ElMessage.error('执行失败，详见右侧结果')
  } finally {
    executing.value = false
  }
}

onMounted(loadEnvironments)
</script>

<style lang="scss" scoped>
.text2sql-page {
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
.form-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.form-hint.warning {
  color: #e6a23c;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  padding: 6px 10px;
  border-radius: 4px;
}
.form-hint.warning code {
  background: rgba(0,0,0,0.05);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: var(--el-font-family-monospace);
}
.actions {
  margin: 12px 0;
  display: flex;
  gap: 8px;
}
.mode-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.mode-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.info-block {
  margin-top: 20px;
}
.info-title {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin-bottom: 8px;
}
.result-box {
  flex: 1;
  overflow: auto;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  padding: 12px;
}
/* 结果表格紧凑布局：行高 22、cell padding 缩到 0 8px、长字段按字符换行 */
.result-box :deep(.el-table) {
  --el-table-row-height: 22px;
  font-size: 12px;
}
.result-box :deep(.el-table .cell) {
  padding: 0 8px;
  line-height: 22px;
  word-break: break-all;
  white-space: pre-wrap;
}
.result-box :deep(.el-table th.el-table__cell) {
  padding: 4px 0;
  background: #f4f6f8;
}
.result-box :deep(.el-table td.el-table__cell) {
  padding: 2px 0;
}
.result-box :deep(.el-table .el-table__header-wrapper) {
  line-height: 1.2;
}
</style>
