<template>
  <div class="kg-browse-page">
    <div class="page-header">
      <h1>🕸️ 知识图谱</h1>
      <p>以项目为核心，关联测试用例与知识库，构建可视化的质量关系网络。</p>
    </div>

    <p v-if="kgEnabled === false" class="kg-disabled-hint">
      知识图谱已禁用。请设置 KNOWLEDGE_GRAPH_ENABLED=true 后重启服务。
    </p>

    <div v-else>
      <!-- ═══════════════ Step 1: 选项目 ═══════════════ -->
      <div class="step-section" :class="{ 'step-active': !selectedProjectId, 'step-done': selectedProjectId }">
        <div class="step-header">
          <span class="step-number">1</span>
          <span class="step-title">选择项目</span>
          <span v-if="selectedProjectId" class="step-status done">✓</span>
        </div>
        <div class="step-body">
          <div class="step-row">
            <el-select
              v-model="selectedProjectId"
              filterable
              placeholder="选择项目（必选）"
              style="width: 320px"
              :loading="projectsLoading"
              @change="onProjectChange">
              <el-option
                v-for="p in projects"
                :key="p.id"
                :label="p.name"
                :value="p.id" />
            </el-select>
            <el-select v-model="depth" style="width: 110px" :disabled="!selectedProjectId">
              <el-option label="深度 1" :value="1" />
              <el-option label="深度 2" :value="2" />
              <el-option label="深度 3" :value="3" />
            </el-select>
            <el-button type="primary" :disabled="!selectedProjectId" :loading="graphLoading" @click="loadGraph">
              加载图谱
            </el-button>
            <el-button :disabled="!selectedProjectId" :loading="exportLoading" @click="exportGraph">
              导出 JSON
            </el-button>
          </div>
        </div>
      </div>

      <!-- ═══════════════ Step 2: 构建/同步节点 ═══════════════ -->
      <div class="step-section" :class="{ 'step-active': selectedProjectId && !graphLoaded, 'step-done': graphLoaded && nodeCount > 0 }">
        <div class="step-header">
          <span class="step-number">2</span>
          <span class="step-title">构建图谱节点</span>
          <span v-if="!selectedProjectId" class="step-status locked">🔒 先选项目</span>
        </div>
        <div class="step-body" :class="{ 'step-disabled': !selectedProjectId }">
          <!-- 卡片组：三列 -->
          <div class="sync-cards">
            <!-- 卡片 A：业务对象同步 -->
            <div class="sync-card">
              <div class="sync-card-header">
                <span class="sync-card-icon">📦</span>
                <span class="sync-card-title">业务对象</span>
              </div>
              <p class="sync-card-desc">同步项目中已有的 API 接口和 UI 页面对象到图谱</p>
              <div class="sync-card-actions">
                <el-button size="small" :disabled="!selectedProjectId" :loading="apiSyncLoading" @click="syncApiRequests">
                  同步 API 接口
                </el-button>
                <el-button size="small" :disabled="!selectedProjectId" :loading="uiSyncLoading" @click="syncUiPages">
                  同步 UI 页面
                </el-button>
                <el-button size="small" type="primary" :disabled="!selectedProjectId" :loading="reqSyncLoading" @click="syncRequirements">
                  同步需求
                </el-button>
                <el-button size="small" type="primary" :disabled="!selectedProjectId" :loading="testcaseSyncLoading" @click="syncTestCases">
                  同步用例
                </el-button>
              </div>
            </div>

            <!-- 卡片 B：知识库同步 -->
            <div class="sync-card">
              <div class="sync-card-header">
                <span class="sync-card-icon">📚</span>
                <span class="sync-card-title">知识库</span>
                <span v-if="selectedSourceName" class="sync-card-tag">{{ selectedSourceName }}</span>
              </div>
              <p class="sync-card-desc">选择 Dify 知识库 或 自建知识中枢（无需 Dify），同步功能模块到当前项目图谱</p>
              <div class="sync-card-body">
                <el-radio-group v-model="knowledgeSource" size="small" @change="onKnowledgeSourceChange" style="margin-bottom: 8px">
                  <el-radio-button label="dify">Dify 知识库</el-radio-button>
                  <el-radio-button label="native">自建知识中枢</el-radio-button>
                </el-radio-group>
                <!-- Dify 路径 -->
                <template v-if="knowledgeSource === 'dify'">
                  <el-select
                    v-model="selectedDifyConfigId"
                    placeholder="Dify 配置"
                    style="width: 100%"
                    size="small"
                    :loading="difyLoading"
                    @change="onDifyConfigChange">
                    <el-option
                      v-for="c in difyConfigs"
                      :key="c.id"
                      :label="c.api_url"
                      :value="c.id" />
                  </el-select>
                  <el-select
                    v-model="selectedDatasetId"
                    filterable
                    placeholder="知识库"
                    style="width: 100%; margin-top: 8px"
                    size="small"
                    :disabled="!selectedDifyConfigId"
                    :loading="kbLoading"
                    @change="onDatasetChange">
                    <el-option
                      v-for="kb in knowledgeBases"
                      :key="kb.id"
                      :label="kb.name"
                      :value="kb.id" />
                  </el-select>
                </template>
                <!-- 自建路径 -->
                <template v-else>
                  <el-select
                    v-model="selectedNativeKbId"
                    filterable
                    placeholder="自建知识库"
                    style="width: 100%"
                    size="small"
                    :loading="nativeKbLoading"
                    @change="onNativeKbChange">
                    <el-option
                      v-for="kb in nativeKbs"
                      :key="kb.id"
                      :label="kb.name"
                      :value="kb.id" />
                  </el-select>
                  <p class="sync-card-hint" style="margin: 6px 0 0; font-size: 11px; color: #64748b">
                    无需 Dify，直接同步自建 KB 及其文档到图谱
                  </p>
                </template>
              </div>
              <div class="sync-card-actions">
                <el-button
                  v-if="knowledgeSource === 'dify'"
                  size="small"
                  type="primary"
                  :disabled="!selectedDatasetId || !selectedProjectId"
                  :loading="kbFuncSyncLoading"
                  @click="syncKbFunctions">
                  同步功能模块
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="primary"
                  :disabled="!selectedProjectId"
                  :loading="nativeKbSyncLoading"
                  @click="syncNativeKbs">
                  同步自建知识库
                </el-button>
              </div>
            </div>

            <!-- 卡片 C：AI 智能分析 -->
            <div class="sync-card">
              <div class="sync-card-header">
                <span class="sync-card-icon">🧠</span>
                <span class="sync-card-title">AI 分析</span>
                <span v-if="!selectedDatasetId" class="sync-card-tag warn">需选知识库</span>
              </div>
              <p class="sync-card-desc">AI 抽取文档功能点、跨文档关联分析，自动构建关系边</p>
              <div class="sync-card-actions">
                <el-button
                  size="small"
                  type="success"
                  :disabled="!selectedDatasetId || !selectedProjectId"
                  :loading="extractLoading"
                  @click="extractFunctionPoints">
                  AI 抽取功能点
                </el-button>
                <el-button
                  size="small"
                  type="warning"
                  :disabled="!selectedDatasetId || !selectedProjectId"
                  :loading="crossDocLoading"
                  @click="crossDocRelations">
                  跨文档关联
                </el-button>
              </div>
            </div>

            <!-- 卡片 D：代码解析 & 图谱增强（对齐 Graphify 思路） -->
            <div class="sync-card">
              <div class="sync-card-header">
                <span class="sync-card-icon">⚙️</span>
                <span class="sync-card-title">代码 & 增强</span>
              </div>
              <p class="sync-card-desc">本地 tree-sitter 解析代码入谱（零 LLM 成本）、Louvain 社区发现、多格式导出</p>
              <div class="sync-card-actions">
                <el-button
                  size="small"
                  :disabled="!selectedProjectId"
                  :loading="parseLoading"
                  @click="parseCodeDir">
                  解析代码
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  :disabled="!selectedProjectId"
                  :loading="clusterLoading"
                  @click="runCluster">
                  图聚类
                </el-button>
              </div>
              <div class="sync-card-actions">
                <el-select v-model="exportFormat" size="small" style="width: 110px">
                  <el-option label="JSON" value="json" />
                  <el-option label="Mermaid" value="mermaid" />
                  <el-option label="SVG" value="svg" />
                  <el-option label="HTML" value="html" />
                </el-select>
                <el-button
                  size="small"
                  :disabled="!selectedProjectId"
                  :loading="formatExportLoading"
                  @click="exportFormatted">
                  导出
                </el-button>
              </div>
              <p v-if="lastParseResult" class="sync-card-result">
                解析：{{ lastParseResult.files_parsed }} 文件 / {{ lastParseResult.code_files }} 文件实体 /
                {{ lastParseResult.functions }} 函数 / {{ lastParseResult.edges }} 边
              </p>
              <p v-if="lastClusterResult" class="sync-card-result">
                聚类：{{ lastClusterResult.community_count }} 个社区 / {{ lastClusterResult.node_count }} 节点（{{ lastClusterResult.algorithm }}）
              </p>
            </div>

            <!-- 卡片 E：需求 & 覆盖（B 方案核心） -->
            <div class="sync-card">
              <div class="sync-card-header">
                <span class="sync-card-icon">🎯</span>
                <span class="sync-card-title">需求 & 覆盖</span>
                <span v-if="!selectedProjectId" class="sync-card-tag warn">先选项目</span>
              </div>
              <p class="sync-card-desc">AI 抽取需求功能点、自动建覆盖边、同步生成任务溯源，打通覆盖度报告与 AI 推荐</p>
              <div class="sync-card-actions">
                <el-button
                  size="small"
                  type="success"
                  :disabled="!selectedProjectId"
                  :loading="reqFpExtractLoading"
                  @click="extractReqFunctionPoints">
                  AI 抽需求功能点
                </el-button>
                <el-button
                  size="small"
                  type="warning"
                  :disabled="!selectedProjectId"
                  :loading="autoCoverLoading"
                  @click="runAutoCover">
                  自动覆盖
                </el-button>
                <el-button
                  size="small"
                  :disabled="!selectedProjectId"
                  :loading="genTaskSyncLoading"
                  @click="syncGenerationTasks">
                  同步生成任务
                </el-button>
              </div>
              <p v-if="reqFpExtractResult" class="sync-card-result">
                抽取：{{ reqFpExtractResult.modules_processed }} 模块 / {{ reqFpExtractResult.points_extracted }} 功能点 / {{ reqFpExtractResult.edges_created }} 边
              </p>
            </div>
          </div>

          <!-- AI 分析结果 -->
          <div v-if="extractResult || crossDocResult" class="ai-results-bar">
            <el-collapse>
              <el-collapse-item v-if="extractResult" :title="`功能点抽取：${extractResult.documents_processed} 文档 / ${extractResult.points_extracted} 功能点`" name="extract">
                <el-table v-if="extractResult.details?.length" :data="extractResult.details" size="small" border>
                  <el-table-column prop="document_name" label="文档名称" min-width="200" />
                  <el-table-column prop="points_count" label="功能点数" width="100" align="center" />
                </el-table>
                <el-collapse v-if="extractResult.errors?.length">
                  <el-collapse-item title="错误详情" name="errors">
                    <ul class="error-list">
                      <li v-for="(err, i) in extractResult.errors" :key="i">{{ err }}</li>
                    </ul>
                  </el-collapse-item>
                </el-collapse>
              </el-collapse-item>
              <el-collapse-item v-if="crossDocResult" :title="`跨文档关联：${crossDocResult.count} 条关联`" name="crossdoc">
                <el-table v-if="crossDocResult.suggestions?.length" :data="crossDocResult.suggestions" size="small" border>
                  <el-table-column prop="doc_a" label="文档 A" width="120" />
                  <el-table-column prop="src_key" label="功能点 A" min-width="180" />
                  <el-table-column prop="doc_b" label="文档 B" width="120" />
                  <el-table-column prop="dst_key" label="功能点 B" min-width="180" />
                  <el-table-column prop="relation" label="关系" width="100" align="center">
                    <template #default="{ row }">
                      <el-tag :type="row.relation === 'similar_to' ? 'success' : 'warning'" size="small">{{ row.relation }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="confidence" label="置信度" width="80" align="center">
                    <template #default="{ row }">{{ (row.confidence * 100).toFixed(0) }}%</template>
                  </el-table-column>
                  <el-table-column prop="reason" label="理由" min-width="180" show-overflow-tooltip />
                </el-table>
              </el-collapse-item>
            </el-collapse>
          </div>
        </div>
      </div>

      <!-- ═══════════════ Step 3: 图谱 & 覆盖度 ═══════════════ -->
      <div class="step-section" :class="{ 'step-active': graphLoaded }">
        <div class="step-header">
          <span class="step-number">3</span>
          <span class="step-title">图谱浏览 & 覆盖度</span>
          <span v-if="graphLoaded && nodeCount > 0" class="step-meta">{{ nodeCount }} 节点 / {{ edgeCount }} 边</span>
        </div>
        <div class="step-body">
          <!-- Tab 切换 -->
          <el-tabs v-model="resultTab" class="result-tabs">
            <!-- 图谱 Tab -->
            <el-tab-pane label="📊 图谱" name="graph">
              <p v-if="graphError" class="graph-error">{{ graphError }}</p>
              <p v-else-if="graphLoaded && nodeCount === 0" class="graph-hint">
                该项目暂无图谱数据。请在 Step 2 中同步功能模块、API 接口、UI 页面，或使用 AI 抽取功能点。
              </p>
              <div v-if="graphLoaded && nodeCount > 0">
                <div class="graph-toolbar">
                  <span class="graph-mode" v-if="graphData.mode">模式：{{ graphData.mode === 'subgraph' ? '项目根遍历' : '聚合' }}</span>
                  <el-select v-model="filterDatasetId" placeholder="按知识库过滤" clearable size="small" style="width: 200px" @change="loadGraph">
                    <el-option label="全部" value="" />
                    <el-option
                      v-for="kb in knowledgeBases"
                      :key="kb.id"
                      :label="kb.name"
                      :value="kb.id" />
                  </el-select>
                  <el-switch
                    v-model="colorByCommunity"
                    active-text="按社区配色"
                    inactive-text="按类型配色"
                    size="small" />
                  <el-button size="small" text @click="loadGraph">🔄 刷新</el-button>
                </div>
                <KgGraphChart :graph-data="graphData" :height="520" :color-by-community="colorByCommunity" />
              </div>
            </el-tab-pane>

            <!-- 覆盖度 Tab -->
            <el-tab-pane label="📋 覆盖度报告" name="coverage">
              <div v-if="!selectedProjectId" class="graph-hint">请先选择项目</div>
              <div v-else>
                <el-button type="primary" size="small" :loading="coverageLoading" @click="loadCoverage" style="margin-bottom: 12px">
                  生成覆盖度报告
                </el-button>
                <div v-if="coverageData" class="coverage-section">
                  <div class="coverage-summary">
                    <div class="cov-stat">
                      <span class="cov-num">{{ coverageData.summary.test_case_count }}</span>
                      <span class="cov-label">测试用例</span>
                    </div>
                    <div class="cov-stat">
                      <span class="cov-num">{{ coverageData.summary.covered_requirement_count }}</span>
                      <span class="cov-label">覆盖需求数</span>
                    </div>
                    <div class="cov-stat">
                      <span class="cov-num">{{ coverageData.summary.covered_function_count }}</span>
                      <span class="cov-label">覆盖功能数</span>
                    </div>
                    <div class="cov-stat" v-if="coverageData.summary.test_case_coverage_rate !== null">
                      <span class="cov-num">{{ (coverageData.summary.test_case_coverage_rate * 100).toFixed(0) }}%</span>
                      <span class="cov-label">用例覆盖率</span>
                    </div>
                    <div class="cov-stat" v-if="coverageData.summary.mapped_uncovered_requirement_count > 0">
                      <span class="cov-num warn">{{ coverageData.summary.mapped_uncovered_requirement_count }}</span>
                      <span class="cov-label">未覆盖需求</span>
                    </div>
                  </div>
                  <el-table v-if="coverageData.mapped_uncovered_requirements?.length" :data="coverageData.mapped_uncovered_requirements" size="small" border style="margin-top: 12px">
                    <el-table-column prop="label" label="未覆盖需求" min-width="300" />
                    <el-table-column prop="entity_key" label="实体键" width="200" />
                  </el-table>
                  <el-table v-if="coverageData.covered_functions?.length" :data="coverageData.covered_functions" size="small" border style="margin-top: 12px">
                    <el-table-column prop="label" label="已覆盖功能模块" min-width="200" />
                    <el-table-column label="用例数" width="80" align="center">
                      <template #default="{ row }">{{ row.test_cases?.length || 0 }}</template>
                    </el-table-column>
                  </el-table>
                </div>
              </div>
            </el-tab-pane>

            <!-- AI 推荐执行 Tab -->
            <el-tab-pane label="🎯 AI 推荐执行" name="recommend">
              <div v-if="!selectedProjectId" class="graph-hint">请先选择项目</div>
              <div v-else>
                <div class="recommend-header">
                  <span class="recommend-desc">基于知识图谱的覆盖缺口和执行历史，AI 推荐下一步应该执行的测试</span>
                  <el-button type="primary" size="small" :loading="recommendLoading" @click="loadRecommendation">
                    🎯 生成推荐
                  </el-button>
                </div>
                <div v-if="recommendData" class="recommend-section">
                  <div class="recommend-summary" v-if="recommendData.summary">
                    {{ recommendData.summary }}
                  </div>
                  <el-table v-if="recommendData.recommendations?.length" :data="recommendData.recommendations" size="small" border style="margin-top: 12px">
                    <el-table-column type="index" label="#" width="50" align="center" />
                    <el-table-column prop="type" label="类型" width="100" align="center">
                      <template #default="{ row }">
                        <el-tag :type="recommendTagType(row.type)" size="small">{{ row.type }}</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column prop="label" label="目标" min-width="200" />
                    <el-table-column prop="reason" label="推荐理由" min-width="280" show-overflow-tooltip />
                    <el-table-column prop="priority" label="优先级" width="80" align="center">
                      <template #default="{ row }">
                        <el-tag :type="row.priority === 'high' ? 'danger' : row.priority === 'medium' ? 'warning' : 'info'" size="small">
                          {{ row.priority }}
                        </el-tag>
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import {
  getKgStatus,
  getKgProjectGraph,
  getKgCoverageReport,
  syncKgApiRequests,
  syncKgUiPages,
  syncKgKbFunctions,
  syncKgRequirements,
  syncKgTestCases,
  syncKgGenerationTasks,
  syncKgNativeKbs,
  autoCoverKg,
  extractFunctionPointsFromRequirements as apiExtractFunctionPointsFromRequirements,
  exportKgGraph,
  exportKgGraphFormatted,
  parseCode,
  clusterKg,
  extractFunctionPoints as apiExtractFunctionPoints,
  crossDocRelations as apiCrossDocRelations,
  recommendExecution as apiRecommendExecution,
  listNativeKbs,
} from '@/api/knowledge-graph'
import KgGraphChart from '@/components/kg/KgGraphChart.vue'

// ── 基础状态 ──
const kgEnabled = ref(null)
const projects = ref([])
const projectsLoading = ref(false)
const selectedProjectId = ref(null)
const depth = ref(2)
const graphLoading = ref(false)
const apiSyncLoading = ref(false)
const uiSyncLoading = ref(false)
const kbFuncSyncLoading = ref(false)
const exportLoading = ref(false)
const graphLoaded = ref(false)
const graphError = ref('')
const graphData = ref({ nodes: [], edges: [], root: null })
const filterDatasetId = ref('')

// ── Graphify 思路增强（代码解析 / 聚类 / 多格式导出 / 社区配色） ──
const colorByCommunity = ref(false)
const exportFormat = ref('json')
const parseLoading = ref(false)
const clusterLoading = ref(false)
const formatExportLoading = ref(false)
const lastParseResult = ref(null)
const lastClusterResult = ref(null)

// ── 知识库 ──
const difyConfigs = ref([])
const selectedDifyConfigId = ref('')
const difyLoading = ref(false)
const knowledgeBases = ref([])
const selectedDatasetId = ref('')
const selectedDatasetName = ref('')
const kbLoading = ref(false)
// 知识源：dify（Dify 数据集）/ native（自建知识中枢）
const knowledgeSource = ref('dify')
const nativeKbs = ref([])
const selectedNativeKbId = ref('')
const selectedNativeKbName = ref('')
const nativeKbLoading = ref(false)

// ── 需求 & 覆盖（B 方案：同步需求 / 用例 / 生成任务 + AI 抽功能点） ──
const reqSyncLoading = ref(false)
const testcaseSyncLoading = ref(false)
const genTaskSyncLoading = ref(false)
const autoCoverLoading = ref(false)
const reqFpExtractLoading = ref(false)
const reqFpExtractResult = ref(null)
const nativeKbSyncLoading = ref(false)

// ── AI 分析 ──
const extractLoading = ref(false)
const extractResult = ref(null)
const crossDocLoading = ref(false)
const crossDocResult = ref(null)

// ── 结果区 Tab ──
const resultTab = ref('graph')

// ── 覆盖度 ──
const coverageLoading = ref(false)
const coverageData = ref(null)

// ── AI 推荐 ──
const recommendLoading = ref(false)
const recommendData = ref(null)

const nodeCount = computed(() => (graphData.value?.nodes || []).length)
const edgeCount = computed(() => (graphData.value?.edges || []).length)

// ═══════════════ 方法 ═══════════════

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

async function loadDifyConfigs() {
  difyLoading.value = true
  try {
    const resp = await api.get('/assistant/config/dify/all/')
    difyConfigs.value = resp.data || []
  } catch {
    difyConfigs.value = []
  } finally {
    difyLoading.value = false
  }
}

function onProjectChange() {
  // 切项目时清空图谱和结果
  graphLoaded.value = false
  graphData.value = { nodes: [], edges: [] }
  coverageData.value = null
  recommendData.value = null
  extractResult.value = null
  crossDocResult.value = null
  reqFpExtractResult.value = null
  lastParseResult.value = null
  lastClusterResult.value = null
}

async function onDifyConfigChange() {
  selectedDatasetId.value = ''
  selectedDatasetName.value = ''
  knowledgeBases.value = []
  if (!selectedDifyConfigId.value) return
  kbLoading.value = true
  try {
    const resp = await api.get('/requirement-analysis/dify-knowledge-bases/', {
      params: { dify_config_id: selectedDifyConfigId.value },
    })
    knowledgeBases.value = resp.data?.data || resp.data || []
  } catch {
    knowledgeBases.value = []
  } finally {
    kbLoading.value = false
  }
}

function onDatasetChange() {
  const kb = knowledgeBases.value.find(k => k.id === selectedDatasetId.value)
  selectedDatasetName.value = kb?.name || ''
}

async function loadGraph() {
  if (!selectedProjectId.value) return
  graphLoading.value = true
  graphError.value = ''
  graphLoaded.value = false
  try {
    const resp = await getKgProjectGraph(selectedProjectId.value, {
      depth: depth.value,
      maxNodes: 500,
      datasetId: filterDatasetId.value || undefined,
    })
    graphData.value = resp.data || { nodes: [], edges: [] }
    graphLoaded.value = true
    if (!graphData.value.nodes?.length && resp.data?.detail) {
      graphError.value = resp.data.detail
    }
  } catch (error) {
    graphData.value = { nodes: [], edges: [] }
    graphLoaded.value = true
    graphError.value = error.response?.data?.detail || '加载项目图谱失败'
  } finally {
    graphLoading.value = false
  }
}

async function syncApiRequests() {
  apiSyncLoading.value = true
  try {
    const resp = await syncKgApiRequests({ projectId: selectedProjectId.value })
    ElMessage.success(`已同步 ${resp.data?.synced ?? 0} 个 API 接口到图谱`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '同步 API 接口失败')
  } finally {
    apiSyncLoading.value = false
  }
}

async function syncUiPages() {
  uiSyncLoading.value = true
  try {
    const resp = await syncKgUiPages({ projectId: selectedProjectId.value })
    ElMessage.success(`已同步 ${resp.data?.synced ?? 0} 个 UI 页面到图谱`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '同步 UI 页面失败')
  } finally {
    uiSyncLoading.value = false
  }
}

async function syncKbFunctions() {
  if (!selectedDatasetId.value || !selectedProjectId.value) return
  kbFuncSyncLoading.value = true
  try {
    const resp = await syncKgKbFunctions({
      projectId: selectedProjectId.value,
      datasetId: selectedDatasetId.value,
    })
    ElMessage.success(`已同步 ${resp.data?.synced ?? 0} 个功能模块到项目图谱`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '同步功能模块失败')
  } finally {
    kbFuncSyncLoading.value = false
  }
}

const selectedSourceName = computed(() => {
  if (knowledgeSource.value === 'native') return selectedNativeKbName.value || '自建知识中枢'
  return selectedDatasetName.value
})

async function onKnowledgeSourceChange() {
  selectedDatasetId.value = ''
  selectedDatasetName.value = ''
  selectedNativeKbId.value = ''
  selectedNativeKbName.value = ''
  if (knowledgeSource.value === 'native') {
    await loadNativeKbs()
  }
}

async function loadNativeKbs() {
  nativeKbLoading.value = true
  try {
    const resp = await listNativeKbs({ page_size: 200 })
    nativeKbs.value = resp.data?.results || resp.data || []
  } catch (error) {
    nativeKbs.value = []
    ElMessage.error(error.response?.data?.detail || '加载自建知识库失败')
  } finally {
    nativeKbLoading.value = false
  }
}

function onNativeKbChange() {
  const kb = nativeKbs.value.find(k => k.id === selectedNativeKbId.value)
  selectedNativeKbName.value = kb?.name || ''
}

async function syncNativeKbs() {
  if (!selectedProjectId.value) return
  nativeKbSyncLoading.value = true
  try {
    const resp = await syncKgNativeKbs({ projectId: selectedProjectId.value })
    ElMessage.success(`已同步 ${resp.data?.synced ?? 0} 个自建知识库到图谱`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '同步自建知识库失败')
  } finally {
    nativeKbSyncLoading.value = false
  }
}

async function syncRequirements() {
  if (!selectedProjectId.value) return
  reqSyncLoading.value = true
  try {
    const resp = await syncKgRequirements({ projectId: selectedProjectId.value })
    const reqs = resp.data?.synced_requirements ?? 0
    const docs = resp.data?.synced_documents ?? 0
    ElMessage.success(`已同步 ${reqs} 条需求、${docs} 篇需求文档到图谱`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '同步需求失败')
  } finally {
    reqSyncLoading.value = false
  }
}

async function syncTestCases() {
  if (!selectedProjectId.value) return
  testcaseSyncLoading.value = true
  try {
    const resp = await syncKgTestCases({ projectId: selectedProjectId.value, autoCover: true })
    const synced = resp.data?.synced_test_cases ?? 0
    const cover = resp.data?.auto_cover
    const covered = cover?.covered ?? 0
    const edges = cover?.edges_created ?? 0
    ElMessage.success(`已同步 ${synced} 个用例，自动覆盖 ${covered} 条，建边 ${edges} 条`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '同步用例失败')
  } finally {
    testcaseSyncLoading.value = false
  }
}

async function syncGenerationTasks() {
  if (!selectedProjectId.value) return
  genTaskSyncLoading.value = true
  try {
    const resp = await syncKgGenerationTasks({ projectId: selectedProjectId.value })
    ElMessage.success(`已同步 ${resp.data?.synced ?? 0} 个 AI 生成任务到图谱`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '同步生成任务失败')
  } finally {
    genTaskSyncLoading.value = false
  }
}

async function runAutoCover() {
  if (!selectedProjectId.value) return
  autoCoverLoading.value = true
  try {
    const resp = await autoCoverKg({ projectId: selectedProjectId.value })
    const covered = resp.data?.covered ?? 0
    const edges = resp.data?.edges_created ?? 0
    ElMessage.success(`自动覆盖完成：${covered} 条用例，新建 ${edges} 条覆盖边`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '自动覆盖失败')
  } finally {
    autoCoverLoading.value = false
  }
}

async function extractReqFunctionPoints() {
  if (!selectedProjectId.value) return
  reqFpExtractLoading.value = true
  reqFpExtractResult.value = null
  try {
    const resp = await apiExtractFunctionPointsFromRequirements({ projectId: selectedProjectId.value })
    reqFpExtractResult.value = resp.data
    const modules = resp.data?.modules_processed ?? 0
    const points = resp.data?.points_extracted ?? 0
    const edges = resp.data?.edges_created ?? 0
    ElMessage.success(`AI 抽取完成：${modules} 模块，${points} 功能点，建边 ${edges} 条`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || 'AI 抽取需求功能点失败')
  } finally {
    reqFpExtractLoading.value = false
  }
}

async function exportGraph() {
  if (!selectedProjectId.value) return
  exportLoading.value = true
  try {
    const resp = await exportKgGraph({ projectId: selectedProjectId.value })
    const data = resp.data || {}
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `kg-export-project-${selectedProjectId.value}.json`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success(`已导出 ${data.node_count ?? 0} 节点、${data.relationship_count ?? 0} 条关系`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导出图谱失败')
  } finally {
    exportLoading.value = false
  }
}

async function parseCodeDir() {
  if (!selectedProjectId.value) return
  parseLoading.value = true
  lastParseResult.value = null
  try {
    const resp = await parseCode({
      path: '/app',
      projectId: selectedProjectId.value,
      maxFiles: 200,
    })
    lastParseResult.value = resp.data || {}
    if (lastParseResult.value.detail && !lastParseResult.value.files_parsed) {
      ElMessage.warning(lastParseResult.value.detail)
    } else {
      ElMessage.success(
        `解析完成：${lastParseResult.value.files_parsed} 文件、` +
          `${lastParseResult.value.code_files} 文件实体、` +
          `${lastParseResult.value.functions} 函数、` +
          `${lastParseResult.value.edges} 条边`
      )
    }
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '代码解析失败')
  } finally {
    parseLoading.value = false
  }
}

async function runCluster() {
  if (!selectedProjectId.value) return
  clusterLoading.value = true
  lastClusterResult.value = null
  try {
    const resp = await clusterKg({ projectId: selectedProjectId.value, resolution: 1.0 })
    lastClusterResult.value = resp.data || {}
    if (lastClusterResult.value.detail && !lastClusterResult.value.communities) {
      ElMessage.warning(lastClusterResult.value.detail)
    } else {
      ElMessage.success(
        `社区发现完成：${lastClusterResult.value.community_count} 个社区，` +
          `算法 ${lastClusterResult.value.algorithm}`
      )
    }
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '图聚类失败')
  } finally {
    clusterLoading.value = false
  }
}

async function exportFormatted() {
  if (!selectedProjectId.value) return
  formatExportLoading.value = true
  const fmt = exportFormat.value
  try {
    const resp = await exportKgGraphFormatted({
      projectId: selectedProjectId.value,
      format: fmt,
      maxNodes: 5000,
      maxEdges: 10000,
    })
    if (fmt === 'json') {
      const data = resp.data || {}
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `kg-${fmt}-project-${selectedProjectId.value}.json`
      link.click()
      URL.revokeObjectURL(url)
    } else {
      const blob = new Blob([resp.data], {
        type: fmt === 'svg' ? 'image/svg+xml' : fmt === 'html' ? 'text/html' : 'text/plain',
      })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `kg-${fmt}-project-${selectedProjectId.value}.${fmt}`
      link.click()
      URL.revokeObjectURL(url)
    }
    ElMessage.success(`已导出 ${fmt.toUpperCase()} 格式`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导出失败')
  } finally {
    formatExportLoading.value = false
  }
}

async function extractFunctionPoints() {
  if (!selectedDatasetId.value) return
  extractLoading.value = true
  extractResult.value = null
  try {
    const resp = await apiExtractFunctionPoints({
      dify_config_id: selectedDifyConfigId.value,
      dataset_id: selectedDatasetId.value,
      project_id: selectedProjectId.value || undefined,
    })
    extractResult.value = resp.data
    const processed = resp.data?.documents_processed ?? 0
    const points = resp.data?.points_extracted ?? 0
    ElMessage.success(`AI 抽取完成：${processed} 篇文档，${points} 个功能点`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || 'AI 抽取功能点失败')
  } finally {
    extractLoading.value = false
  }
}

async function crossDocRelations() {
  if (!selectedDatasetId.value) return
  crossDocLoading.value = true
  crossDocResult.value = null
  try {
    const resp = await apiCrossDocRelations({
      dify_config_id: selectedDifyConfigId.value,
      dataset_id: selectedDatasetId.value,
      min_confidence: 0.6,
      persist: true,
      project_id: selectedProjectId.value || undefined,
    })
    crossDocResult.value = resp.data
    const count = resp.data?.count ?? 0
    ElMessage.success(`跨文档关联分析完成：发现 ${count} 条关联`)
    await loadGraph()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '跨文档关联分析失败')
  } finally {
    crossDocLoading.value = false
  }
}

async function loadCoverage() {
  if (!selectedProjectId.value) return
  coverageLoading.value = true
  try {
    const resp = await getKgCoverageReport(selectedProjectId.value, { limit: 100 })
    coverageData.value = resp.data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '生成覆盖度报告失败')
  } finally {
    coverageLoading.value = false
  }
}

async function loadRecommendation() {
  if (!selectedProjectId.value) return
  recommendLoading.value = true
  recommendData.value = null
  try {
    const resp = await apiRecommendExecution({ projectId: selectedProjectId.value })
    recommendData.value = resp.data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '生成推荐失败')
  } finally {
    recommendLoading.value = false
  }
}

function recommendTagType(type) {
  const map = { api: 'primary', ui: 'success', testcase: 'warning', coverage_gap: 'danger' }
  return map[type] || 'info'
}

onMounted(async () => {
  await Promise.all([loadKgStatus(), loadProjects(), loadDifyConfigs()])
})
</script>

<style scoped>
.kg-browse-page {
  max-width: 1280px;
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
}
.kg-disabled-hint {
  margin: 0;
  font-size: 13px;
  color: #94a3b8;
}

/* ── Step 卡片 ── */
.step-section {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin-bottom: 16px;
  overflow: hidden;
  transition: border-color 0.2s;
}
.step-section.step-active {
  border-color: #3b82f6;
  box-shadow: 0 0 0 1px #3b82f6 inset;
}
.step-section.step-done {
  border-color: #c6f6d5;
}
.step-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}
.step-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}
.step-active .step-number {
  background: #3b82f6;
  color: #fff;
}
.step-done .step-number {
  background: #22c55e;
  color: #fff;
}
.step-title {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}
.step-status.done {
  color: #22c55e;
  font-weight: 600;
}
.step-status.locked {
  color: #94a3b8;
  font-size: 13px;
}
.step-meta {
  margin-left: auto;
  font-size: 13px;
  color: #64748b;
}
.step-body {
  padding: 16px 20px;
}
.step-body.step-disabled {
  opacity: 0.5;
  pointer-events: none;
}
.step-row {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

/* ── Step 2: 卡片组 ── */
.sync-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}
@media (max-width: 900px) {
  .sync-cards {
    grid-template-columns: 1fr;
  }
}
.sync-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sync-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
}
.sync-card-icon {
  font-size: 18px;
}
.sync-card-title {
  font-weight: 600;
  font-size: 14px;
  color: #1e293b;
}
.sync-card-tag {
  margin-left: auto;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #dbeafe;
  color: #1e40af;
}
.sync-card-tag.warn {
  background: #fef3c7;
  color: #92400e;
}
.sync-card-desc {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.sync-card-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sync-card-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: auto;
}
.sync-card-result {
  margin: 8px 0 0;
  font-size: 11px;
  color: #475569;
  line-height: 1.5;
}

/* ── AI 结果折叠区 ── */
.ai-results-bar {
  margin-top: 12px;
}

/* ── 图谱区 ── */
.graph-toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 10px;
}
.graph-mode {
  font-size: 13px;
  color: #64748b;
}
.graph-error {
  margin: 0 0 12px;
  color: #b91c1c;
  font-size: 13px;
}
.graph-hint {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 13px;
}

/* ── 结果 Tab ── */
.result-tabs {
  margin-top: 4px;
}

/* ── 覆盖度 ── */
.coverage-summary {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  padding: 16px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
}
.cov-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.cov-num {
  font-size: 28px;
  font-weight: 700;
  color: #166534;
}
.cov-num.warn {
  color: #dc2626;
}
.cov-label {
  font-size: 12px;
  color: #64748b;
}

/* ── AI 推荐 ── */
.recommend-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.recommend-desc {
  font-size: 13px;
  color: #64748b;
}
.recommend-section {
  margin-top: 8px;
}
.recommend-summary {
  padding: 12px 16px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  font-size: 14px;
  color: #1e40af;
  line-height: 1.6;
}

/* ── 错误列表 ── */
.error-list {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #b91c1c;
}
</style>
