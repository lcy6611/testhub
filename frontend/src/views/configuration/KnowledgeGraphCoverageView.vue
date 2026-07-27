<template>
  <div class="kg-coverage-page">
    <div class="page-header">
      <h1>📊 覆盖度报告</h1>
      <p>基于图谱 <code>covers</code> 边，查看项目用例对业务需求 / 功能模块的覆盖与映射缺口。</p>
    </div>

    <p v-if="kgEnabled === false" class="kg-disabled-hint">
      知识图谱已禁用。请设置 KNOWLEDGE_GRAPH_ENABLED=true 后重启服务。
    </p>

    <div v-else class="toolbar">
      <el-select
        v-model="selectedProjectId"
        filterable
        placeholder="选择项目"
        style="width: 280px"
        :loading="projectsLoading">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-button type="primary" :disabled="!selectedProjectId" :loading="reportLoading" @click="loadReport">
        生成报告
      </el-button>
    </div>

    <p v-if="reportError" class="report-error">{{ reportError }}</p>

    <template v-if="reportLoaded && summary">
      <div class="summary-grid">
        <div class="summary-card">
          <span class="summary-value">{{ summary.test_case_count }}</span>
          <span class="summary-label">项目用例</span>
        </div>
        <div class="summary-card">
          <span class="summary-value">{{ summary.test_cases_with_covers }}</span>
          <span class="summary-label">已覆盖用例</span>
          <span v-if="summary.test_case_coverage_rate != null" class="summary-sub">
            用例覆盖率 {{ formatRate(summary.test_case_coverage_rate) }}
          </span>
        </div>
        <div class="summary-card warn" v-if="(summary.test_cases_without_covers_count || 0) > 0">
          <span class="summary-value">{{ summary.test_cases_without_covers_count }}</span>
          <span class="summary-label">未覆盖用例</span>
          <span class="summary-sub">项目用例 - 已覆盖用例</span>
        </div>
        <div class="summary-card">
          <span class="summary-value">{{ summary.covered_requirement_count }}</span>
          <span class="summary-label">已覆盖需求</span>
        </div>
        <div class="summary-card">
          <span class="summary-value">{{ summary.covered_function_count }}</span>
          <span class="summary-label">已覆盖功能</span>
        </div>
        <div class="summary-card">
          <span class="summary-value">{{ summary.covered_document_count || 0 }}</span>
          <span class="summary-label">已覆盖文档</span>
        </div>
        <div class="summary-card warn">
          <span class="summary-value">{{ summary.mapped_uncovered_requirement_count }}</span>
          <span class="summary-label">映射未覆盖需求</span>
          <span v-if="summary.mapped_requirement_coverage_rate != null" class="summary-sub">
            映射覆盖率 {{ formatRate(summary.mapped_requirement_coverage_rate) }}
          </span>
        </div>
        <div class="summary-card muted">
          <span class="summary-value">{{ summary.generation_task_count }}</span>
          <span class="summary-label">生成任务</span>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="report-tabs">
        <el-tab-pane :label="`已覆盖需求 (${coveredRequirements.length})`" name="req">
          <p v-if="coveredRequirements.length === 0" class="tab-empty">暂无 covers 到业务需求的记录。</p>
          <el-table v-else :data="coveredRequirements" stripe size="small">
            <el-table-column label="业务需求" min-width="200">
              <template #default="{ row }">{{ row.label || row.entity_key }}</template>
            </el-table-column>
            <el-table-column label="覆盖用例数" width="100">
              <template #default="{ row }">{{ (row.test_cases || []).length }}</template>
            </el-table-column>
            <el-table-column label="覆盖用例" min-width="240">
              <template #default="{ row }">
                <span v-for="(tc, idx) in (row.test_cases || []).slice(0, 3)" :key="tc.entity_key">
                  <router-link
                    v-if="tc.ref_id"
                    :to="{ name: 'TestCaseDetail', params: { id: tc.ref_id } }"
                    class="report-link">
                    {{ tc.label || ('用例 #' + tc.ref_id) }}
                  </router-link>
                  <span v-else>{{ tc.label }}</span>
                  <span v-if="idx < Math.min(3, (row.test_cases || []).length) - 1">、</span>
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`已覆盖功能 (${coveredFunctions.length})`" name="func">
          <p v-if="coveredFunctions.length === 0" class="tab-empty">暂无 covers 到功能模块的记录。</p>
          <el-table v-else :data="coveredFunctions" stripe size="small">
            <el-table-column label="功能模块" min-width="200">
              <template #default="{ row }">{{ row.label || row.entity_key }}</template>
            </el-table-column>
            <el-table-column label="覆盖用例数" width="100">
              <template #default="{ row }">{{ (row.test_cases || []).length }}</template>
            </el-table-column>
            <el-table-column label="覆盖用例" min-width="240">
              <template #default="{ row }">
                <span v-for="(tc, idx) in (row.test_cases || []).slice(0, 3)" :key="tc.entity_key">
                  <router-link
                    v-if="tc.ref_id"
                    :to="{ name: 'TestCaseDetail', params: { id: tc.ref_id } }"
                    class="report-link">
                    {{ tc.label || ('用例 #' + tc.ref_id) }}
                  </router-link>
                  <span v-else>{{ tc.label }}</span>
                  <span v-if="idx < Math.min(3, row.test_cases.length) - 1">、</span>
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`已覆盖文档 (${coveredDocuments.length})`" name="doc">
          <p v-if="coveredDocuments.length === 0" class="tab-empty">暂无 covers 到知识库文档的记录。</p>
          <el-table v-else :data="coveredDocuments" stripe size="small">
            <el-table-column label="知识库文档" min-width="200">
              <template #default="{ row }">{{ row.label || row.entity_key }}</template>
            </el-table-column>
            <el-table-column label="覆盖用例数" width="100">
              <template #default="{ row }">{{ (row.test_cases || []).length }}</template>
            </el-table-column>
            <el-table-column label="覆盖用例" min-width="240">
              <template #default="{ row }">
                <span v-for="(tc, idx) in (row.test_cases || []).slice(0, 3)" :key="tc.entity_key">
                  <router-link
                    v-if="tc.ref_id"
                    :to="{ name: 'TestCaseDetail', params: { id: tc.ref_id } }"
                    class="report-link">
                    {{ tc.label || ('用例 #' + tc.ref_id) }}
                  </router-link>
                  <span v-else>{{ tc.label }}</span>
                  <span v-if="idx < Math.min(3, row.test_cases.length) - 1">、</span>
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`未覆盖用例 (${withoutCoversTabLabel})`" name="nogap">
          <p class="tab-desc">
            尚未通过 covers 边关联到任何业务需求/功能模块的测试用例。等于「项目用例 − 已覆盖用例」。
          </p>
          <p v-if="withoutCovers.length === 0" class="tab-empty">
            <template v-if="summary.test_case_count === 0">无项目用例。</template>
            <template v-else>所有项目用例均已有 covers 边，覆盖完整。</template>
          </p>
          <el-table v-else :data="withoutCovers" stripe size="small">
            <el-table-column label="用例" min-width="240">
              <template #default="{ row }">
                <router-link
                  v-if="row.ref_id"
                  :to="{ name: 'TestCaseDetail', params: { id: row.ref_id } }"
                  class="report-link">
                  {{ row.label || ('用例 #' + row.ref_id) }}
                </router-link>
                <span v-else>{{ row.label || row.entity_key }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane :label="`映射缺口 (${mappedUncovered.length})`" name="gap">
          <p class="tab-desc">
            已 maps_to 到本项目生成任务引用的功能模块，但尚无项目用例 covers 的业务需求。
          </p>
          <p v-if="mappedUncovered.length === 0" class="tab-empty">无映射覆盖缺口。</p>
          <el-table v-else :data="mappedUncovered" stripe size="small">
            <el-table-column label="业务需求" min-width="280">
              <template #default="{ row }">{{ row.label || row.entity_key }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { getKgStatus, getKgCoverageReport } from '@/api/knowledge-graph'

const kgEnabled = ref(null)
const projects = ref([])
const projectsLoading = ref(false)
const selectedProjectId = ref(null)
const reportLoading = ref(false)
const reportLoaded = ref(false)
const reportError = ref('')
const report = ref(null)
const activeTab = ref('req')

const summary = computed(() => report.value?.summary || null)
const coveredRequirements = computed(() => report.value?.covered_requirements || [])
const coveredFunctions = computed(() => report.value?.covered_functions || [])
const coveredDocuments = computed(() => report.value?.covered_documents || [])
const withoutCovers = computed(() => report.value?.test_cases_without_covers || [])
const withoutCoversTruncated = computed(() => !!report.value?.test_cases_without_covers_truncated)
const withoutCoversTabLabel = computed(() => {
  const total = summary.value?.test_cases_without_covers_count ?? withoutCovers.value.length
  const shown = withoutCovers.value.length
  if (withoutCoversTruncated.value && total !== shown) {
    return `${shown}/${total}`
  }
  return String(total || shown || 0)
})
const mappedUncovered = computed(() => report.value?.mapped_uncovered_requirements || [])

function formatRate(rate) {
  if (rate == null) return '—'
  return `${Math.round(Number(rate) * 1000) / 10}%`
}

async function loadProjects() {
  projectsLoading.value = true
  try {
    const resp = await api.get('/projects/', { params: { page_size: 200 } })
    projects.value = resp.data?.results || resp.data || []
  } catch {
    projects.value = []
    ElMessage.error('加载项目列表失败')
  } finally {
    projectsLoading.value = false
  }
}

async function loadKgStatus() {
  try {
    const resp = await getKgStatus()
    kgEnabled.value = resp.data?.enabled !== false
  } catch {
    kgEnabled.value = false
  }
}

async function loadReport() {
  if (!selectedProjectId.value) return
  reportLoading.value = true
  reportError.value = ''
  reportLoaded.value = false
  try {
    const resp = await getKgCoverageReport(selectedProjectId.value)
    report.value = resp.data
    reportLoaded.value = true
    if (resp.data?.detail && !summary.value?.test_case_count && !summary.value?.generation_task_count) {
      reportError.value = resp.data.detail
    }
  } catch (error) {
    report.value = null
    reportLoaded.value = true
    reportError.value = error.response?.data?.detail || '加载覆盖度报告失败'
  } finally {
    reportLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadKgStatus(), loadProjects()])
})
</script>

<style scoped>
.kg-coverage-page {
  max-width: 1100px;
}
.page-header h1 {
  margin: 0 0 8px;
  font-size: 1.4rem;
  color: #1e293b;
}
.page-header p {
  margin: 0 0 20px;
  color: #64748b;
  font-size: 14px;
  line-height: 1.5;
}
.page-header code {
  font-size: 12px;
  background: #f1f5f9;
  padding: 1px 4px;
  border-radius: 3px;
}
.kg-disabled-hint {
  margin: 0;
  font-size: 13px;
  color: #94a3b8;
}
.toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 20px;
}
.report-error {
  margin: 0 0 12px;
  color: #b91c1c;
  font-size: 13px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.summary-card {
  padding: 14px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.summary-card.warn {
  background: #fffbeb;
  border-color: #fde68a;
}
.summary-card.muted {
  background: #f1f5f9;
}
.summary-value {
  font-size: 1.5rem;
  font-weight: 600;
  color: #0f172a;
  line-height: 1.2;
}
.summary-label {
  font-size: 12px;
  color: #64748b;
}
.summary-sub {
  font-size: 11px;
  color: #92400e;
}
.report-tabs {
  margin-top: 8px;
}
.tab-empty,
.tab-desc {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
}
.report-link {
  color: #2563eb;
  text-decoration: none;
}
.report-link:hover {
  text-decoration: underline;
}
</style>
