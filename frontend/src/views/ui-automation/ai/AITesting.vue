<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">AI 智能测试</h1>
    </div>

    <div class="card-container">
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="section-title">任务输入</div>
          <el-form :model="taskForm" label-position="top">
            <el-form-item class="task-desc-item">
              <template #label>
                <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; flex-wrap: nowrap;">
                  <span style="display: inline-flex; align-items: center; flex-shrink: 0;">
                    <span style="color: #f56c6c; margin-right: 4px;">*</span>
                    <span>任务描述</span>
                  </span>
                  <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 12px; color: #606266; font-weight: normal;">项目：</span>
                    <el-select
                      v-model="taskForm.projectId"
                      placeholder="选择项目"
                      style="width: 160px;"
                      size="small"
                      clearable
                    >
                      <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
                    </el-select>
                    <span style="font-size: 12px; color: #606266; font-weight: normal;">执行模式：</span>
                    <el-select v-model="taskForm.executionMode" placeholder="选择执行模式" style="width: 140px;" size="small">
                      <el-option label="自动（推荐）" value="auto" />
                      <el-option label="文本模式" value="text" />
                      <el-option label="视觉模式" value="vision" />
                    </el-select>
                    <span style="font-size: 12px; color: #606266; font-weight: normal; margin-left: 8px;">浏览器：</span>
                    <el-radio-group v-model="taskForm.headless" size="small" style="margin-left: 4px;">
                      <el-radio-button :label="false">有头</el-radio-button>
                      <el-radio-button :label="true">无头</el-radio-button>
                    </el-radio-group>
                    <span
                      v-if="taskForm.executionMode === 'vision'"
                      style="margin-left: 6px; font-size: 12px; color: #909399;"
                    >
                      视觉模式推荐使用无头；在 Docker/Linux 无图形界面环境下会自动降级为无头。
                    </span>
                    <el-tooltip placement="top" effect="light">
                      <template #content>
                        <div style="max-width: 280px; line-height: 1.5;">
                          自动=有文本配置则用文本（稳定），否则视觉；<br/>
                          文本=强制文本；视觉=强制视觉（需已配置视觉模型）。<br/>
                          选「视觉」时看图决策，适合复杂布局。
                        </div>
                      </template>
                      <el-icon style="cursor: help; color: #909399;"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </div>
                </div>
              </template>
              <el-input
                v-model="taskForm.description"
                type="textarea"
                :rows="9"
                placeholder="请用自然语言描述要执行的任务，例如：&#10;1. 访问 https://www.baidu.com&#10;2. 搜索 'TestHub'&#10;3. 点击第一条搜索结果"
                maxlength="2000"
                show-word-limit
              />
            </el-form-item>

            <el-form-item label="GIF录制">
              <el-switch
                v-model="taskForm.enableGif"
                active-text="开启"
                inactive-text="关闭"
              />
              <span style="margin-left: 10px; color: #909399; font-size: 12px;">
                开启后将录制执行过程并生成GIF文件，保存到 ai_agent_history 目录
              </span>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                @click="handleRun"
                :loading="running"
                :disabled="!taskForm.description"
              >
                <el-icon><VideoPlay /></el-icon>
                开始执行
              </el-button>
              <el-button
                type="danger"
                @click="handleStop"
                :disabled="!running || analyzing"
                v-if="running"
              >
                <el-icon><SwitchButton /></el-icon>
                停止执行
              </el-button>
              <el-button
                type="success"
                @click="handleSaveAsCase"
                :disabled="!taskForm.description"
              >
                <el-icon><DocumentAdd /></el-icon>
                保存为用例
              </el-button>
            </el-form-item>
          </el-form>
          
          <el-alert
            title="提示"
            type="info"
            :closable="false"
            style="margin-top: 20px;"
          >
            <template #default>
              <div>AI 模式使用"配置中心-AI智能模式配置"中的模型（如未添加模型，请前往添加）。</div>
              <div>支持中英文任务描述，任务描述越详细，执行效果越好。</div>
              <div>访问外部站点（如百度）时，若出现「只访问了地址、后续步骤失败」，可稍后重试或把任务拆成更小的步骤。</div>
            </template>
          </el-alert>
          
          <div class="section-title" style="margin-top: 20px;">执行日志</div>
          <div class="log-container" ref="logContainer">
            <div v-if="!logs && !running" class="empty-logs">
              暂无执行日志
            </div>
            <pre v-else class="log-content">{{ logs }}</pre>
          </div>
        </el-col>
        
        <el-col :span="12">
          <div class="section-title">任务明细</div>
          <div class="task-list-container">
            <div v-if="analyzing" class="analyzing-state">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>任务分析中...</span>
            </div>
            <div v-else-if="plannedTasks.length > 0">
              <div 
                v-for="task in plannedTasks" 
                :key="task.id" 
                class="task-item"
                :class="statusClass(task.status)"
              >
                <div class="task-status-icon">
                  <el-icon v-if="statusClass(task.status) === 'completed'" color="#67C23A"><CircleCheckFilled /></el-icon>
                  <el-icon v-else-if="statusClass(task.status) === 'in_progress'" class="is-loading" color="#409EFF"><Loading /></el-icon>
                  <el-icon v-else-if="statusClass(task.status) === 'failed'" color="#F56C6C"><CircleCloseFilled /></el-icon>
                  <el-icon v-else color="#909399"><CircleCheck /></el-icon>
                </div>
                <div class="task-content">
                  <span class="task-id">{{ task.id }}.</span>
                  <span class="task-desc">{{ task.description }}</span>
                </div>
              </div>
            </div>
            <div v-else class="empty-tasks">
              暂无任务
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 保存为用例对话框 -->
    <el-dialog v-model="showSaveDialog" title="保存为 AI 用例" :close-on-click-modal="false" :close-on-press-escape="false" :modal="true" :destroy-on-close="false" width="500px">
      <el-form :model="saveForm" :rules="saveRules" ref="saveFormRef" label-width="80px">
        <el-form-item label="所属项目">
          <el-select v-model="saveForm.projectId" placeholder="可选：绑定到项目" style="width: 100%" clearable>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <div style="margin-top: 4px; font-size: 12px; color: #909399;">绑定项目后，才能在该项目的 AI 套件中选到此用例。</div>
        </el-form-item>
        <el-form-item label="用例名称" prop="name">
          <el-input v-model="saveForm.name" placeholder="请输入用例名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="saveForm.description" type="textarea" placeholder="请输入用例描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showSaveDialog = false">取消</el-button>
          <el-button type="primary" @click="confirmSaveCase" :loading="saving">保存</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, DocumentAdd, CircleCheckFilled, CircleCheck, CircleCloseFilled, Loading, SwitchButton, QuestionFilled } from '@element-plus/icons-vue'
import {
  runAdhocAITask,
  createAICase,
  getUiProjects,
  getAIExecutionRecordDetail,
  stopAITask
} from '@/api/ui_automation'

const running = ref(false)
const analyzing = ref(false)
const saving = ref(false)
const logs = ref('')
const plannedTasks = ref([])
const currentExecutionId = ref(null)
const logContainer = ref(null)
const projects = ref([])

const taskForm = reactive({
  description: '',
  projectId: null,
  executionMode: 'auto',  // 执行模式：auto=自动(推荐), text=文本, vision=视觉
  headless: false,
  enableGif: true  // GIF录制开关，默认开启
})

// 视觉模式：首次切换时默认无头（用户仍可手动改回有头）
watch(() => taskForm.executionMode, (v, oldV) => {
  if (v === 'vision' && oldV !== 'vision') taskForm.headless = true
})

const showSaveDialog = ref(false)
const saveForm = reactive({
  projectId: null,
  name: '',
  description: ''
})
const saveFormRef = ref(null)

const saveRules = {
  name: [{ required: true, message: '请输入用例名称', trigger: 'blur' }]
}

// 统一状态映射函数，保证任务状态在不同来源下都能正确显示
const statusClass = (status) => {
  if (!status) return ''
  const s = String(status).toLowerCase()

  if (['completed', 'done', 'success', 'passed', 'finished'].includes(s)) {
    return 'completed'
  }
  if (['in_progress', 'running', 'processing', 'doing'].includes(s)) {
    return 'in_progress'
  }
  if (['failed', 'error', 'stopped'].includes(s)) {
    return 'failed'
  }
  return ''
}

// 执行任务
const handleRun = async () => {
  running.value = true
  analyzing.value = true
  logs.value = '正在初始化 AI Agent...\n'
  plannedTasks.value = []

  try {
    const response = await runAdhocAITask({
      project_id: taskForm.projectId,
      task_description: taskForm.description,
      execution_mode: taskForm.executionMode || 'auto',
      headless: taskForm.headless,
      enable_gif: taskForm.enableGif
    })

    currentExecutionId.value = response.data.execution_id
    ElMessage.success('任务开始执行')
    
    // 开始轮询日志
    pollLogs()
    
  } catch (error) {
    console.error('执行失败:', error)
    ElMessage.error('执行失败: ' + (error.response?.data?.error || error.message))
    running.value = false
    analyzing.value = false
  }
}

// 停止任务
const handleStop = async () => {
  if (!currentExecutionId.value) return
  
  try {
    await stopAITask(currentExecutionId.value)
    ElMessage.warning('正在停止任务...')
  } catch (error) {
    console.error('停止失败:', error)
    ElMessage.error('停止失败')
  }
}

// 轮询日志
const pollLogs = () => {
  const pollInterval = setInterval(async () => {
    if (!currentExecutionId.value) {
      clearInterval(pollInterval)
      return
    }
    
    try {
      const response = await getAIExecutionRecordDetail(currentExecutionId.value)
      const record = response.data
      
      logs.value = record.logs || ''
      plannedTasks.value = record.planned_tasks || []
      
      // 如果获取到了任务列表，则取消"分析中"状态
      if (plannedTasks.value.length > 0) {
        analyzing.value = false
      }
      
      // 滚动到底部
      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      })
      
      if (record.status === 'passed' || record.status === 'failed' || record.status === 'stopped') {
        clearInterval(pollInterval)
        running.value = false
        analyzing.value = false
        if (record.status === 'passed') {
          ElMessage.success('执行成功')
        } else if (record.status === 'stopped') {
          ElMessage.warning('任务已停止')
        } else {
          ElMessage.error('执行失败')
        }
      }
    } catch (error) {
      console.error('获取日志失败:', error)
    }
  }, 2000)
}

// 保存为用例
const handleSaveAsCase = () => {
  showSaveDialog.value = true
  saveForm.name = ''
  saveForm.description = ''
  saveForm.projectId = taskForm.projectId || null
}

const confirmSaveCase = async () => {
  if (!saveFormRef.value) return

  await saveFormRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        await createAICase({
          project: saveForm.projectId || null,
          name: saveForm.name,
          description: saveForm.description,
          task_description: taskForm.description
        })

        ElMessage.success('保存成功')
        showSaveDialog.value = false
      } catch (error) {
        console.error('保存失败:', error)
        ElMessage.error('保存失败')
      } finally {
        saving.value = false
      }
    }
  })
}

const loadProjects = async () => {
  try {
    const res = await getUiProjects({ page_size: 500 })
    projects.value = res.data.results || res.data || []
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style lang="scss" scoped>
.page-container {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;

  .page-title {
    font-size: 20px;
    font-weight: 600;
    margin: 0;
  }
}

.card-container {
  background-color: #fff;
  border-radius: 4px;
  padding: 20px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  min-height: calc(100vh - 140px);
}

.task-desc-item :deep(.el-form-item__label) {
  margin-bottom: 6px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 15px;
  padding-left: 10px;
  border-left: 4px solid #409eff;
}

.task-list-container {
  background-color: #f5f7fa;
  border-radius: 4px;
  padding: 15px;
  margin-bottom: 20px;
  height: calc(100vh - 200px);
  overflow-y: auto;
  
  .task-item {
    display: flex;
    align-items: flex-start;
    padding: 10px;
    border-bottom: 1px solid #e4e7ed;
    transition: all 0.3s;
    
    &:last-child {
      border-bottom: none;
    }
    
    &.completed {
      background-color: #f0f9eb;
      .task-desc {
        color: #67c23a;
        text-decoration: line-through;
      }
    }
    
    &.in_progress {
      background-color: #ecf5ff;
      .task-desc {
        color: #409eff;
        font-weight: bold;
      }
    }

    &.failed {
      background-color: #fef0f0;
      .task-desc {
        color: #f56c6c;
        font-weight: bold;
      }
    }
    
    .task-status-icon {
      margin-right: 10px;
      margin-top: 2px;
      font-size: 16px;
    }
    
    .task-content {
      flex: 1;
      line-height: 1.5;
      
      .task-id {
        font-weight: bold;
        margin-right: 5px;
      }
    }
  }
}

.empty-tasks {
  color: #909399;
  text-align: center;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.analyzing-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #409eff;
  
  .el-icon {
    font-size: 24px;
    margin-bottom: 10px;
  }
}

.log-container {
  background-color: #1e1e1e;
  border-radius: 4px;
  height: 300px;
  overflow-y: auto;
  padding: 15px;
  color: #fff;
  font-family: 'Consolas', 'Monaco', monospace;
  
  .empty-logs {
    color: #909399;
    text-align: center;
    margin-top: 100px;
  }
  
  .log-content {
    margin: 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    font-size: 14px;
    line-height: 1.5;
  }
}
</style>
