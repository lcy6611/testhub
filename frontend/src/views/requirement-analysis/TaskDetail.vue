<template>
  <div class="task-detail">
    <div class="page-header">
      <div class="header-left">
        <h2>任务详情 - {{ task.title }}</h2>
        <div class="task-info">
          <span class="task-id">任务ID: {{ taskId }}</span>
          <span class="task-status" :class="task.status">{{ getStatusText(task.status) }}</span>
        </div>
      </div>
      <div class="header-actions">
        <button 
          v-if="testCases.length > 0" 
          class="export-btn" 
          @click="exportToExcel"
          :disabled="isExporting">
          <span v-if="isExporting">💾 导出中...</span>
          <span v-else>💾 导出Excel</span>
        </button>
      </div>
    </div>

    <div v-if="isLoading" class="loading-state">
      <p>🔄 正在加载任务详情...</p>
    </div>

    <div v-else-if="!task.task_id" class="error-state">
      <h3>任务不存在或已被删除</h3>
      <router-link to="/generated-testcases">返回任务列表</router-link>
    </div>

    <div v-else class="task-content">
      <!-- 继续优化：补充要求 / 新截图 -->
      <div
        v-if="canContinueRefine"
        class="continue-refine-section">
        <div class="continue-refine-card">
          <h3>✏️ 在此基础上继续改</h3>
          <p class="refine-desc">
            在<strong>当前用例</strong>上追加补充说明或新截图，AI 会增删改用例，不会从零重写。
            新截图请标注「页面样式」或「操作步骤」。
          </p>
          <div class="form-group">
            <label>补充要求</label>
            <textarea
              v-model="refinementInstructions"
              class="form-textarea"
              rows="4"
              placeholder="例如：补充密码错误 3 次锁定账号的边界用例；根据新截图完善操作步骤…"
              :disabled="isRefining"></textarea>
          </div>
          <div class="image-upload-row">
            <input
              type="file"
              ref="refineImageInput"
              accept="image/*"
              multiple
              style="display: none"
              @change="handleRefineImageSelect"
              :disabled="isRefining">
            <button
              type="button"
              class="refine-upload-btn"
              :disabled="isRefining || uploadingImages || refineImageAttachments.length >= 12"
              @click="$refs.refineImageInput.click()">
              {{ uploadingImages ? '上传中...' : `添加截图 (${refineImageAttachments.length}/12)` }}
            </button>
          </div>
          <div v-if="refineImageAttachments.length" class="refine-image-list">
            <div
              v-for="(item, idx) in refineImageAttachments"
              :key="idx"
              class="refine-image-item">
              <img :src="item.previewUrl" :alt="item.name" class="refine-thumb">
              <div class="refine-image-fields">
                <select v-model="item.role" class="form-select" @change="onRefineImageRoleChange(item)">
                  <option value="ui_layout">页面样式参考</option>
                  <option value="operation_step">操作步骤参考</option>
                </select>
                <input
                  v-model="item.caption"
                  type="text"
                  class="form-input"
                  :placeholder="item.role === 'operation_step' ? '步骤说明' : '界面说明'">
                <input
                  v-if="item.role === 'operation_step'"
                  v-model.number="item.step_index"
                  type="number"
                  min="1"
                  class="form-input refine-step-input"
                  placeholder="序号">
              </div>
              <button type="button" class="refine-remove-btn" @click="removeRefineImage(idx)">删除</button>
            </div>
          </div>
          <button
            class="continue-refine-btn"
            :disabled="!canSubmitRefine || isRefining"
            @click="submitContinueRefine">
            <span v-if="isRefining">🔄 优化中...</span>
            <span v-else>🚀 提交并继续优化</span>
          </button>
        </div>
      </div>

      <!-- 知识图谱关联（只读） -->
      <KgRelationPanel
        v-if="task.task_id && !isLoading"
        ref="kgPanel"
        :entity-key="kgTaskEntityKey"
        title="🔗 关联图谱"
        mode="outgoing"
        :expansion-hint="graphExpansionHint"
        :extra-hint="kgRefinementHint"
        empty-hint="暂无图谱数据。任务创建后会自动建边；若为本功能上线前生成的任务，请重新生成或继续优化一次。" />

      <!-- 知识中枢引用溯源 -->
      <div
        v-if="kbSources.length > 0"
        class="kb-sources-panel">
        <div class="kb-sources-header" @click="kbSourcesExpanded = !kbSourcesExpanded">
          <span class="kb-sources-title">
            📎 知识中枢引用溯源
            <span class="kb-sources-badge">{{ kbSources.length }}</span>
          </span>
          <span class="kb-sources-engine" v-if="kbEngineName">{{ kbEngineName }}</span>
          <span class="kb-sources-toggle">{{ kbSourcesExpanded ? '收起 ▲' : '展开 ▼' }}</span>
        </div>
        <transition name="kb-collapse">
          <div v-show="kbSourcesExpanded" class="kb-sources-body">
            <div
              v-for="(src, idx) in kbSources"
              :key="idx"
              class="kb-source-item">
              <div class="kb-source-meta">
                <span class="kb-source-doc">
                  <span class="kb-source-index">{{ idx + 1 }}</span>
                  {{ src.document_name || '未知文档' }}
                </span>
                <span
                  v-if="src.score != null"
                  class="kb-source-score"
                  :class="kbScoreClass(src.score)">
                  {{ (src.score * 100).toFixed(1) }}%
                </span>
              </div>
              <p v-if="src.snippet" class="kb-source-snippet">{{ src.snippet }}</p>
            </div>
            <div v-if="kbGraphSummary" class="kb-graph-summary">
              <span class="kb-graph-label">🔗 图谱扩展</span>
              <span>{{ kbGraphSummary }}</span>
            </div>
          </div>
        </transition>
      </div>

      <!-- 批量操作区域 -->
      <div class="batch-actions" v-if="testCases.length > 0">
        <div class="selection-info">
          <label class="select-all">
            <input 
              type="checkbox" 
              :checked="isAllSelected" 
              @change="toggleSelectAll">
            全选
          </label>
          <span class="selected-count" v-if="selectedCases.length > 0">
            已选择 {{ selectedCases.length }} 条用例
          </span>
        </div>
        <div class="batch-buttons">
          <button 
            class="batch-adopt-btn" 
            :disabled="selectedCases.length === 0"
            @click="batchAdopt">
            ✅ 一键采纳 ({{ selectedCases.length }})
          </button>
          <button 
            class="batch-discard-btn" 
            :disabled="selectedCases.length === 0"
            @click="batchDiscard">
            ❌ 一键弃用 ({{ selectedCases.length }})
          </button>
        </div>
      </div>

      <!-- 测试用例列表 -->
      <div class="testcases-table" v-if="testCases.length > 0">
        <div class="table-header">
          <div class="header-cell checkbox-cell">选择</div>
          <div class="header-cell">测试用例编号</div>
          <div class="header-cell">测试场景</div>
          <div class="header-cell">前置条件</div>
          <div class="header-cell">操作步骤</div>
          <div class="header-cell">预期结果</div>
          <div class="header-cell">优先级</div>
          <div class="header-cell">操作</div>
        </div>
        
        <div class="table-body">
          <div 
            v-for="(testCase, index) in paginatedTestCases" 
            :key="testCase.id || index"
            class="table-row">
            <div class="body-cell checkbox-cell">
              <input 
                type="checkbox" 
                :value="testCase"
                v-model="selectedCases"
                @change="updateSelectAll">
            </div>
            <div class="body-cell">{{ testCase.caseId || `TC${String(index + 1).padStart(3, '0')}` }}</div>
            <div class="body-cell">{{ testCase.scenario }}</div>
            <div class="body-cell">{{ testCase.precondition }}</div>
            <div class="body-cell">{{ testCase.steps }}</div>
            <div class="body-cell">{{ testCase.expected }}</div>
            <div class="body-cell">
              <span class="priority-tag" :class="testCase.priority?.toLowerCase()">{{ testCase.priority || '中' }}</span>
            </div>
            <div class="body-cell">
              <div class="action-buttons">
                <button class="view-btn" @click="viewCaseDetail(testCase, index)">📖 查看详情</button>
                <button class="adopt-btn" @click="adoptSingleCase(testCase, index)">✅ 采纳</button>
                <button class="discard-btn" @click="discardSingleCase(testCase, index)">❌ 弃用</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <h3>{{ isPolling || isRefining ? '用例优化中，请稍候…' : '暂无测试用例数据' }}</h3>
        <p v-if="isPolling || isRefining">
          {{ getStatusText(task.status) }}（进度 {{ task.progress || 0 }}%）
        </p>
        <p v-else-if="task.status === 'failed'">
          {{ task.error_message || '生成过程中出现错误，请返回重试或查看 AI 生成用例记录' }}
        </p>
        <p v-else>该任务还没有生成测试用例或用例已被清空</p>
      </div>

      <!-- 分页 -->
      <div v-if="testCases.length > 0" class="pagination-section">
        <div class="pagination-info">
          显示 {{ paginationStart }}-{{ paginationEnd }} 条，共 {{ testCases.length }} 条
        </div>
        <div class="pagination-controls">
          <div class="page-size-selector">
            <label>每页显示：</label>
            <select v-model="pageSize" @change="currentPage = 1">
              <option value="10">10 条</option>
              <option value="20">20 条</option>
              <option value="50">50 条</option>
            </select>
          </div>
          <div class="pagination-buttons">
            <button :disabled="currentPage <= 1" @click="currentPage--">上一页</button>
            <span class="current-page">第 {{ currentPage }} 页，共 {{ totalPages }} 页</span>
            <button :disabled="currentPage >= totalPages" @click="currentPage++">下一页</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 用例详情弹窗 -->
    <div v-if="showCaseDetail" class="case-detail-modal" @click="closeCaseDetail">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>测试用例详情</h3>
          <button class="close-btn" @click="closeCaseDetail">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-item">
            <label>用例编号:</label>
            <span>{{ selectedCase.caseId || `TC${String(selectedCaseIndex + 1).padStart(3, '0')}` }}</span>
          </div>
          <div class="detail-item">
            <label>测试场景:</label>
            <p>{{ selectedCase.scenario }}</p>
          </div>
          <div class="detail-item">
            <label>前置条件:</label>
            <p>{{ selectedCase.precondition }}</p>
          </div>
          <div class="detail-item">
            <label>操作步骤:</label>
            <p class="test-steps">{{ selectedCase.steps }}</p>
          </div>
          <div class="detail-item">
            <label>预期结果:</label>
            <p>{{ selectedCase.expected }}</p>
          </div>
          <div class="detail-item">
            <label>优先级:</label>
            <span class="priority-tag" :class="selectedCase.priority?.toLowerCase()">{{ selectedCase.priority || '中' }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'
import { normalizeExportCell } from '@/utils/testcaseExport'
import { formatGraphExpansionHint } from '@/utils/kgLabels'
import KgRelationPanel from '@/components/kg/KgRelationPanel.vue'

export default {
  name: 'TaskDetail',
  components: { KgRelationPanel },
  data() {
    return {
      taskId: '',
      task: {},
      testCases: [],
      selectedCases: [],
      isLoading: true,
      isPolling: false,
      pollInterval: null,
      showCaseDetail: false,
      selectedCase: {},
      selectedCaseIndex: 0,
      currentPage: 1,
      pageSize: 10,
      isExporting: false,
      kbSourcesExpanded: true,

      refinementInstructions: '',
      refineImageAttachments: [],
      uploadingImages: false,
      isRefining: false
    }
  },

  computed: {
    canContinueRefine() {
      const s = this.task.status
      const hasCases = this.testCases.length > 0
      const idle = ['completed', 'failed', 'cancelled'].includes(s)
      return hasCases && idle && !this.isLoading && !this.isRefining && !this.isPolling
    },

    canSubmitRefine() {
      const hasText = (this.refinementInstructions || '').trim().length > 0
      const hasImages = this.refineImageAttachments.length > 0
      return hasText || hasImages
    },

    isAllSelected() {
      return this.testCases.length > 0 && this.selectedCases.length === this.testCases.length
    },

    totalPages() {
      return Math.ceil(this.testCases.length / this.pageSize)
    },

    paginatedTestCases() {
      const start = (this.currentPage - 1) * this.pageSize
      const end = start + this.pageSize
      return this.testCases.slice(start, end)
    },

    paginationStart() {
      return (this.currentPage - 1) * this.pageSize + 1
    },

    paginationEnd() {
      return Math.min(this.currentPage * this.pageSize, this.testCases.length)
    },

    kgTaskEntityKey() {
      return this.task?.task_id ? `gen_task:${this.task.task_id}` : ''
    },

    graphExpansionHint() {
      return formatGraphExpansionHint(this.task?.kb_context_meta)
    },

    kgRefinementHint() {
      const notes = (this.task?.refinement_notes || '').trim()
      if (!notes) return ''
      const count = (notes.match(/--- 迭代补充/g) || []).length || 1
      const preview = notes.replace(/\s+/g, ' ').trim()
      const short = preview.length > 100 ? `${preview.slice(0, 100)}…` : preview
      return `已迭代优化 ${count} 次${short ? `，最近补充：${short}` : ''}`
    },

    kbSources() {
      const meta = this.task?.kb_context_meta
      if (!meta || typeof meta !== 'object') return []
      return Array.isArray(meta.sources) ? meta.sources : []
    },

    kbEngineName() {
      const meta = this.task?.kb_context_meta
      if (!meta || typeof meta !== 'object') return ''
      const engine = meta.engine || ''
      const names = meta.kb_names || []
      if (names.length > 0) {
        return names.join('、')
      }
      if (engine === 'dify') return 'Dify 知识库'
      if (engine === 'native') return '自建知识中枢'
      return engine
    },

    kbGraphSummary() {
      const meta = this.task?.kb_context_meta
      if (!meta || typeof meta !== 'object') return ''
      return meta.graph_summary || ''
    }
  },

  mounted() {
    this.taskId = this.$route.params.taskId
    this.loadTaskDetail()
  },

  beforeUnmount() {
    this.stopPolling()
  },

  methods: {
    shouldPollStatus(status) {
      return ['pending', 'generating', 'reviewing', 'revising'].includes(status)
    },

    kbScoreClass(score) {
      const s = parseFloat(score)
      if (isNaN(s)) return 'score-na'
      if (s >= 0.8) return 'score-high'
      if (s >= 0.5) return 'score-mid'
      return 'score-low'
    },

    buildRefineImagePayload() {
      return this.refineImageAttachments.map((item) => {
        const entry = { url: item.url, role: item.role || 'ui_layout' }
        if ((item.caption || '').trim()) entry.caption = item.caption.trim()
        if (entry.role === 'operation_step') entry.step_index = item.step_index || 1
        return entry
      })
    },

    reindexRefineSteps() {
      let step = 1
      for (const item of this.refineImageAttachments) {
        if (item.role === 'operation_step') {
          item.step_index = step
          step += 1
        }
      }
    },

    onRefineImageRoleChange(item) {
      if (item.role === 'operation_step' && !item.step_index) {
        item.step_index = this.refineImageAttachments.filter(a => a.role === 'operation_step').length
      }
      this.reindexRefineSteps()
    },

    removeRefineImage(idx) {
      const item = this.refineImageAttachments[idx]
      if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl)
      this.refineImageAttachments.splice(idx, 1)
      this.reindexRefineSteps()
    },

    async handleRefineImageSelect(event) {
      const files = Array.from(event.target.files || [])
      event.target.value = ''
      for (const file of files) {
        if (this.refineImageAttachments.length >= 12) {
          ElMessage.warning('最多上传 12 张截图')
          break
        }
        if (!file.type?.startsWith('image/')) continue
        await this.uploadRefineImage(file)
      }
    },

    async uploadRefineImage(file) {
      this.uploadingImages = true
      try {
        const fd = new FormData()
        fd.append('files', file)
        const resp = await api.post('/requirement-analysis/testcase-generation/upload-images/', fd, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        const url = (resp.data?.image_data_urls || [])[0]
        if (!url) {
          ElMessage.error('图片解析失败')
          return
        }
        this.refineImageAttachments.push({
          url,
          role: 'ui_layout',
          caption: '',
          step_index: null,
          previewUrl: URL.createObjectURL(file),
          name: file.name
        })
      } catch (error) {
        ElMessage.error(error.response?.data?.detail || '上传截图失败')
      } finally {
        this.uploadingImages = false
      }
    },

    async submitContinueRefine() {
      if (!this.canSubmitRefine) {
        ElMessage.warning('请填写补充要求或上传新截图')
        return
      }
      if (!confirm('将基于当前用例按您的补充要求重新生成，是否继续？')) {
        return
      }

      this.isRefining = true
      this.selectedCases = []
      try {
        const payload = {
          refinement_instructions: (this.refinementInstructions || '').trim()
        }
        const images = this.buildRefineImagePayload()
        if (images.length) payload.image_attachments = images

        await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/continue-refine/`, payload)

        ElMessage.success('已开始优化，请稍候…')
        this.refinementInstructions = ''
        for (const item of this.refineImageAttachments) {
          if (item.previewUrl) URL.revokeObjectURL(item.previewUrl)
        }
        this.refineImageAttachments = []
        this.testCases = []
        this.task.status = 'generating'
        this.startPolling()
      } catch (error) {
        console.error('继续优化失败:', error)
        ElMessage.error(error.response?.data?.detail || '继续优化失败')
        this.isRefining = false
      }
    },

    refreshKgPanel() {
      this.$refs.kgPanel?.refresh?.()
    },

    applyTaskData(task) {
      this.task = task
      const raw = (task.final_test_cases || task.generated_test_cases || '').trim()
      if (raw) {
        this.testCases = this.parseTestCases(raw)
      }
    },

    startPolling() {
      if (this.pollInterval) return
      this.isPolling = true
      this.pollInterval = setInterval(async () => {
        try {
          const response = await api.get(`/requirement-analysis/testcase-generation/${this.taskId}/progress/`)
          this.applyTaskData(response.data)
          if (!this.shouldPollStatus(response.data.status)) {
            this.stopPolling()
            this.isRefining = false
            if (response.data.status === 'completed' && this.testCases.length > 0) {
              ElMessage.success('测试用例优化完成')
            } else if (response.data.status === 'failed') {
              ElMessage.error(response.data.error_message || '用例优化失败')
            }
            this.refreshKgPanel()
          }
        } catch (error) {
          console.error('轮询任务进度失败:', error)
        }
      }, 2000)
    },

    stopPolling() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval)
        this.pollInterval = null
      }
      this.isPolling = false
    },

    async loadTaskDetail() {
      try {
        const taskResponse = await api.get(`/requirement-analysis/testcase-generation/${this.taskId}/`)
        this.applyTaskData(taskResponse.data)
        if (this.shouldPollStatus(taskResponse.data.status)) {
          this.startPolling()
        } else {
          this.refreshKgPanel()
        }
      } catch (error) {
        console.error('加载任务详情失败:', error)
        ElMessage.error('加载任务详情失败')
      } finally {
        this.isLoading = false
      }
    },

    parseTestCases(content) {
      // 复用RequirementAnalysisView中的解析逻辑
      if (!content) return []
      
      const lines = content.split('\n').filter(line => line.trim())
      const testCases = []
      
      // 尝试解析表格格式
      let isTableFormat = false
      const tableData = []
      
      for (let line of lines) {
        const trimmedLine = line.trim()
        if (trimmedLine.includes('|') && !trimmedLine.includes('--------')) {
          const cells = trimmedLine.split('|').map(cell => cell.trim()).filter(cell => cell)
          if (cells.length > 1) {
            tableData.push(cells)
            isTableFormat = true
          }
        }
      }
      
      if (isTableFormat && tableData.length > 1) {
        // 表格格式解析
        const headers = tableData[0]
        for (let i = 1; i < tableData.length; i++) {
          const row = tableData[i]
          const testCase = {}
          
          headers.forEach((header, index) => {
            const value = row[index] || ''
            if (header.includes('编号') || header.includes('ID') || header.includes('用例ID')) {
              testCase.caseId = value
            } else if (header.includes('场景') || header.includes('标题') || header.includes('测试目标')) {
              testCase.scenario = value
            } else if (header.includes('前置')) {
              testCase.precondition = value
            } else if (header.includes('步骤') || header.includes('操作步骤')) {
              testCase.steps = value
            } else if (header.includes('预期') || header.includes('结果')) {
              testCase.expected = value
            } else if (header.includes('优先级')) {
              testCase.priority = value
            }
          })
          
          if (testCase.scenario || testCase.caseId) {
            // 如果没有steps字段，使用scenario作为steps的默认值
            if (!testCase.steps && testCase.scenario) {
              testCase.steps = '参考测试目标执行相应操作'
            }
            testCases.push(testCase)
          }
        }
      } else {
        // 结构化文本格式解析
        let currentTestCase = {}
        let caseNumber = 1
        
        for (const line of lines) {
          if (line.includes('测试用例') || line.includes('Test Case') || 
              line.match(/^(\d+\.|\*|\-|\d+、)/)) {
            
            if (Object.keys(currentTestCase).length > 0) {
              testCases.push(currentTestCase)
              caseNumber++
            }
            
            currentTestCase = {
              caseId: `TC${String(caseNumber).padStart(3, '0')}`,
              scenario: line.replace(/^(\d+\.|\*|\-|\d+、)\s*/, '').replace(/测试用例\d*[:：]?\s*/, ''),
              precondition: '',
              steps: '',
              expected: '',
              priority: '中'
            }
          } else if (line.includes('前置条件') || line.includes('前提')) {
            currentTestCase.precondition = line.replace(/.*?[:：]\s*/, '')
          } else if (line.includes('测试步骤') || line.includes('操作步骤') || line.includes('步骤')) {
            currentTestCase.steps = line.replace(/.*?[:：]\s*/, '')
          } else if (line.includes('预期结果') || line.includes('Expected')) {
            currentTestCase.expected = line.replace(/.*?[:：]\s*/, '')
          } else if (line.includes('优先级')) {
            currentTestCase.priority = line.replace(/.*?[:：]\s*/, '')
          }
        }
        
        if (Object.keys(currentTestCase).length > 0) {
          testCases.push(currentTestCase)
        }
      }
      
      return testCases
    },

    getStatusText(status) {
      const statusMap = {
        'pending': '需求分析中',
        'generating': '用例编写中',
        'reviewing': '用例评审中',
        'revising': '最终版生成中',
        'completed': '已完成',
        'failed': '失败',
        'cancelled': '已弃用'
      }
      return statusMap[status] || status
    },

    toggleSelectAll() {
      if (this.isAllSelected) {
        this.selectedCases = []
      } else {
        this.selectedCases = [...this.testCases]
      }
    },

    updateSelectAll() {
      // 这个方法会在单个checkbox变化时触发，用于更新全选状态
      // Vue的v-model会自动处理selectedCases数组的更新
    },

    async batchAdopt() {
      if (this.selectedCases.length === 0) {
        ElMessage.warning('请先选择要采纳的测试用例')
        return
      }

      if (!confirm(`确定要采纳选中的 ${this.selectedCases.length} 条测试用例吗？`)) {
        return
      }

      try {
        const casesData = this.selectedCases.map((testCase, index) => ({
          title: testCase.scenario || `测试用例${index + 1}`,
          description: testCase.scenario || '',
          preconditions: testCase.precondition || '',
          steps: testCase.steps || '',
          expected_result: testCase.expected || '',
          priority: this.mapPriority(testCase.priority),
          test_type: 'functional',
          status: 'draft'
        }))

        await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/batch-adopt-selected/`, {
          test_cases: casesData
        })

        ElMessage.success(`成功采纳 ${this.selectedCases.length} 条测试用例！`)
        this.selectedCases = []
        
        // 不再移除已采纳的用例，保留在列表中供多次采纳
        // this.testCases = this.testCases.filter(tc => !this.selectedCases.includes(tc))
        
      } catch (error) {
        console.error('批量采纳失败:', error)
        ElMessage.error('批量采纳失败: ' + (error.response?.data?.message || error.message))
      }
    },

    async batchDiscard() {
      if (this.selectedCases.length === 0) {
        ElMessage.warning('请先选择要弃用的测试用例')
        return
      }

      if (!confirm(`确定要弃用选中的 ${this.selectedCases.length} 条测试用例吗？此操作不可恢复。`)) {
        return
      }

      try {
        // 获取选中用例的全局索引（不是分页索引）
        const caseIndices = this.selectedCases.map(selectedCase => {
          // 在完整列表中查找索引
          const globalIndex = this.testCases.findIndex(tc => 
            tc.scenario === selectedCase.scenario && 
            tc.steps === selectedCase.steps && 
            tc.expected === selectedCase.expected
          )
          return globalIndex
        }).filter(index => index !== -1) // 过滤掉未找到的(-1)

        const response = await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/discard-selected-cases/`, {
          case_indices: caseIndices
        })

        if (response.data.task_deleted) {
          ElMessage.success('所有测试用例已弃用，任务已删除')
          // 返回到AI生成用例记录列表
          this.$router.push('/generated-testcases')
        } else {
          ElMessage.success(`成功弃用 ${response.data.discarded_count} 条测试用例`)
          
          // 重新解析更新后的测试用例
          if (response.data.updated_test_cases) {
            this.testCases = this.parseTestCases(response.data.updated_test_cases)
            this.selectedCases = []
            this.currentPage = 1 // 重置到第一页
          }
        }
        
      } catch (error) {
        console.error('批量弃用失败:', error)
        ElMessage.error('批量弃用失败: ' + (error.response?.data?.error || error.message))
      }
    },

    viewCaseDetail(testCase, index) {
      this.selectedCase = testCase
      this.selectedCaseIndex = index
      this.showCaseDetail = true
    },

    closeCaseDetail() {
      this.showCaseDetail = false
      this.selectedCase = {}
    },

    async adoptSingleCase(testCase, index) {
      if (!confirm(`确定要采纳测试用例"${testCase.scenario}"吗？`)) {
        return
      }

      try {
        const caseData = {
          title: testCase.scenario || `测试用例${index + 1}`,
          description: testCase.scenario || '',
          preconditions: testCase.precondition || '',
          steps: testCase.steps || '',
          expected_result: testCase.expected || '',
          priority: this.mapPriority(testCase.priority),
          test_type: 'functional',
          status: 'draft'
        }

        await api.post('/testcases/', caseData)
        ElMessage.success('测试用例采纳成功！')
        
        // 不再移除已采纳的用例，保留在列表中供多次采纳
        // this.testCases.splice(this.testCases.indexOf(testCase), 1)
        
      } catch (error) {
        console.error('采纳用例失败:', error)
        ElMessage.error('采纳用例失败: ' + (error.response?.data?.message || error.message))
      }
    },

    discardSingleCase(testCase, index) {
      if (!confirm(`确定要弃用测试用例"${testCase.scenario}"吗？此操作不可恢复。`)) {
        return
      }

      try {
        // 计算全局索引（当前页面起始位置 + 当前索引）
        const globalIndex = (this.currentPage - 1) * this.pageSize + index

        // 调用后端API弃用单个测试用例
        api.post(`/requirement-analysis/testcase-generation/${this.taskId}/discard-single-case/`, {
          case_index: globalIndex
        }).then(response => {
          if (response.data.task_deleted) {
            ElMessage.success('所有测试用例已弃用，任务已删除')
            // 返回到AI生成用例记录列表
            this.$router.push('/generated-testcases')
          } else {
            ElMessage.success('测试用例已弃用')
            
            // 重新解析更新后的测试用例
            if (response.data.updated_test_cases) {
              this.testCases = this.parseTestCases(response.data.updated_test_cases)
              
              // 如果当前页没有数据了，回到上一页
              if (this.currentPage > 1 && this.paginatedTestCases.length === 0) {
                this.currentPage--
              }
            }
          }
        }).catch(error => {
          console.error('弃用用例失败:', error)
          ElMessage.error('弃用用例失败: ' + (error.response?.data?.error || error.message))
        })
        
      } catch (error) {
        console.error('弃用用例失败:', error)
        ElMessage.error('弃用用例失败')
      }
    },

    mapPriority(priority) {
      const priorityMap = {
        '最高': 'critical',
        '高': 'high',
        '中': 'medium',
        '低': 'low',
        'L1': 'high',
        'L2': 'medium',
        'L3': 'low',
        'P0': 'critical',
        'P1': 'high',
        'P2': 'medium',
        'P3': 'low'
      }
      return priorityMap[priority] || 'medium'
    },

    // 导出到Excel
    exportToExcel() {
      if (this.testCases.length === 0) {
        ElMessage.warning('没有测试用例可以导出')
        return
      }

      this.isExporting = true

      try {
        // 创建工作簿
        const workbook = XLSX.utils.book_new()

        // 准备数据
        const worksheetData = []
        
        // 添加表头
        worksheetData.push(['测试用例编号', '测试场景', '前置条件', '操作步骤', '预期结果', '优先级'])

        // 添加数据行
        this.testCases.forEach((testCase, index) => {
          worksheetData.push([
            normalizeExportCell(testCase.caseId || `TC${String(index + 1).padStart(3, '0')}`),
            normalizeExportCell(testCase.scenario || ''),
            normalizeExportCell(testCase.precondition || ''),
            normalizeExportCell(testCase.steps || ''),
            normalizeExportCell(testCase.expected || ''),
            normalizeExportCell(testCase.priority || '中')
          ])
        })

        // 创建工作表
        const worksheet = XLSX.utils.aoa_to_sheet(worksheetData)

        // 设置列宽
        const colWidths = [
          { wch: 15 }, // 测试用例编号
          { wch: 30 }, // 测试场景
          { wch: 25 }, // 前置条件
          { wch: 40 }, // 操作步骤
          { wch: 30 }, // 预期结果
          { wch: 10 }  // 优先级
        ]
        worksheet['!cols'] = colWidths

        // 将工作表添加到工作簿
        XLSX.utils.book_append_sheet(workbook, worksheet, '测试用例')

        // 生成文件名
        const fileName = `测试用例_${this.taskId}_${new Date().toISOString().slice(0, 10)}.xlsx`

        // 导出文件
        XLSX.writeFile(workbook, fileName)

        ElMessage.success('测试用例导出成功')
      } catch (error) {
        console.error('导出Excel失败:', error)
        ElMessage.error('导出Excel失败: ' + (error.message || '未知错误'))
      } finally {
        this.isExporting = false
      }
    }
  }
}
</script>

<style scoped>
.task-detail {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-left {
  flex: 1;
}

.page-header h2 {
  color: #2c3e50;
  margin: 0 0 10px 0;
}

.task-info {
  display: flex;
  gap: 20px;
  align-items: center;
}

.task-id {
  color: #666;
  font-family: monospace;
}

.task-status {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 0.9rem;
  font-weight: bold;
}

.task-status.completed {
  background: #e8f5e8;
  color: #388e3c;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.export-btn {
  background: #27ae60;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background 0.3s ease;
  white-space: nowrap;
}

.export-btn:hover:not(:disabled) {
  background: #229954;
}

.export-btn:disabled {
  background: #bdc3c7;
  cursor: not-allowed;
}

.continue-refine-section { margin-bottom: 20px; }
.continue-refine-card {
  background: #f8fafc;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  padding: 20px;
}
.continue-refine-card h3 { margin: 0 0 8px 0; color: #1e40af; font-size: 1.1rem; }
.refine-desc { margin: 0 0 16px 0; font-size: 13px; color: #475569; line-height: 1.6; }
.continue-refine-card .form-group { margin-bottom: 12px; }
.continue-refine-card label { display: block; font-size: 13px; color: #334155; margin-bottom: 6px; }
.form-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
  resize: vertical;
  box-sizing: border-box;
}
.image-upload-row { margin-bottom: 12px; }
.refine-upload-btn {
  padding: 8px 14px;
  border: 1px solid #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.refine-upload-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.refine-image-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 14px; }
.refine-image-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
.refine-thumb {
  width: 80px;
  height: 54px;
  object-fit: cover;
  border-radius: 4px;
  flex-shrink: 0;
}
.refine-image-fields { flex: 1; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.refine-image-fields .form-select,
.refine-image-fields .form-input { padding: 6px 8px; border: 1px solid #cbd5e1; border-radius: 4px; font-size: 13px; }
.refine-step-input { width: 72px; }
.refine-remove-btn {
  border: none;
  background: #fee2e2;
  color: #b91c1c;
  padding: 6px 10px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  flex-shrink: 0;
}
.continue-refine-btn {
  padding: 10px 20px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.continue-refine-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.batch-actions {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.selection-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.select-all {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.selected-count {
  color: #3498db;
  font-weight: bold;
}

.batch-buttons {
  display: flex;
  gap: 10px;
}

.batch-adopt-btn, .batch-discard-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s ease;
}

.batch-adopt-btn {
  background: #27ae60;
  color: white;
}

.batch-adopt-btn:hover:not(:disabled) {
  background: #229954;
}

.batch-discard-btn {
  background: #e74c3c;
  color: white;
}

.batch-discard-btn:hover:not(:disabled) {
  background: #c0392b;
}

.batch-adopt-btn:disabled, .batch-discard-btn:disabled {
  background: #bdc3c7;
  cursor: not-allowed;
}

.testcases-table {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.table-header {
  display: grid;
  grid-template-columns: 60px 120px 1fr 1fr 1fr 1fr 80px 150px;
  background: #f8f9fa;
  font-weight: bold;
  color: #2c3e50;
}

.table-body .table-row {
  display: grid;
  grid-template-columns: 60px 120px 1fr 1fr 1fr 1fr 80px 150px;
  border-bottom: 1px solid #eee;
  transition: background 0.2s ease;
}

.table-row:hover {
  background: #f8f9fa;
}

.header-cell, .body-cell {
  padding: 12px 8px;
  display: flex;
  align-items: center;
  border-right: 1px solid #eee;
  word-break: break-word;
}

.checkbox-cell {
  justify-content: center;
}

.header-cell:last-child, .body-cell:last-child {
  border-right: none;
}

.priority-tag {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: bold;
}

.priority-tag.low {
  background: #e8f5e8;
  color: #388e3c;
}

.priority-tag.medium {
  background: #e3f2fd;
  color: #1976d2;
}

.priority-tag.high {
  background: #fff3e0;
  color: #f57c00;
}

.priority-tag.critical {
  background: #ffebee;
  color: #d32f2f;
}

.action-buttons {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}

.view-btn, .adopt-btn, .discard-btn {
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s ease;
}

.view-btn {
  background: #3498db;
  color: white;
}

.view-btn:hover {
  background: #2980b9;
}

.adopt-btn {
  background: #27ae60;
  color: white;
}

.adopt-btn:hover {
  background: #229954;
}

.discard-btn {
  background: #e74c3c;
  color: white;
}

.discard-btn:hover {
  background: #c0392b;
}

.pagination-section {
  margin-top: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 20px;
}

.page-size-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-buttons {
  display: flex;
  align-items: center;
  gap: 15px;
}

.pagination-buttons button {
  padding: 6px 12px;
  border: 1px solid #ddd;
  background: white;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.pagination-buttons button:hover:not(:disabled) {
  background: #f0f0f0;
}

.pagination-buttons button:disabled {
  color: #ccc;
  cursor: not-allowed;
}

.case-detail-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  max-width: 800px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 30px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  color: #2c3e50;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #666;
}

.modal-body {
  padding: 30px;
}

.detail-item {
  margin-bottom: 20px;
}

.detail-item label {
  font-weight: bold;
  color: #2c3e50;
  display: block;
  margin-bottom: 8px;
}

.detail-item span, .detail-item p {
  color: #666;
  line-height: 1.6;
}

.test-steps {
  white-space: pre-line;
  background: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
  border-left: 4px solid #3498db;
}

.loading-state, .error-state, .empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #666;
}

.error-state h3, .empty-state h3 {
  color: #2c3e50;
  margin-bottom: 10px;
}

.error-state a {
  color: #3498db;
  text-decoration: none;
}

.error-state a:hover {
  text-decoration: underline;
}

/* 知识中枢引用溯源 */
.kb-sources-panel {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 20px;
  overflow: hidden;
}

.kb-sources-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  background: #f1f5f9;
  transition: background 0.2s;
}

.kb-sources-header:hover {
  background: #e2e8f0;
}

.kb-sources-title {
  font-weight: 600;
  font-size: 14px;
  color: #1e293b;
}

.kb-sources-badge {
  display: inline-block;
  background: #3b82f6;
  color: #fff;
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 10px;
  margin-left: 4px;
}

.kb-sources-engine {
  font-size: 12px;
  color: #64748b;
  background: #e0f2fe;
  padding: 2px 8px;
  border-radius: 4px;
}

.kb-sources-toggle {
  margin-left: auto;
  font-size: 12px;
  color: #64748b;
}

.kb-sources-body {
  padding: 12px 16px;
}

.kb-source-item {
  padding: 10px 0;
  border-bottom: 1px dashed #e2e8f0;
}

.kb-source-item:last-child {
  border-bottom: none;
}

.kb-source-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.kb-source-doc {
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 6px;
}

.kb-source-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  background: #cbd5e1;
  color: #1e293b;
  font-size: 11px;
  border-radius: 50%;
  font-weight: 600;
}

.kb-source-score {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
}

.kb-source-score.score-high {
  background: #dcfce7;
  color: #166534;
}

.kb-source-score.score-mid {
  background: #fef9c3;
  color: #854d0e;
}

.kb-source-score.score-low {
  background: #fee2e2;
  color: #991b1b;
}

.kb-source-score.score-na {
  background: #f1f5f9;
  color: #64748b;
}

.kb-source-snippet {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  margin: 4px 0 0 24px;
  padding: 6px 10px;
  background: #fff;
  border-left: 3px solid #cbd5e1;
  border-radius: 0 4px 4px 0;
}

.kb-graph-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 8px 12px;
  background: #f0fdf4;
  border-radius: 6px;
  font-size: 12px;
  color: #166534;
}

.kb-graph-label {
  font-weight: 600;
  white-space: nowrap;
}

.kb-collapse-enter-active,
.kb-collapse-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.kb-collapse-enter-from,
.kb-collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>