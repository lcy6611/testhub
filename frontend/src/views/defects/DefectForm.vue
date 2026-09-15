<template>
  <el-form :model="form" label-width="100px" label-position="right" ref="elForm">
    <el-form-item label="标题" required>
      <el-input v-model="form.title" maxlength="300" show-word-limit />
    </el-form-item>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="所属项目" required>
          <el-select v-model="form.project" filterable style="width:100%" @change="onProjectChange">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="严重度">
          <el-select v-model="form.severity" style="width:100%">
            <el-option v-for="s in severityOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
      </el-col>
    </el-row>
    <el-row :gutter="16">
      <el-col :span="8">
        <el-form-item label="优先级">
          <el-select v-model="form.priority" style="width:100%">
            <el-option v-for="s in priorityOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item label="缺陷类型">
          <el-select v-model="form.defect_type" style="width:100%">
            <el-option v-for="s in typeOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
      </el-col>
    </el-row>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="发现版本">
          <el-select v-model="form.version" filterable clearable style="width:100%">
            <el-option v-for="v in versions" :key="v.id" :label="v.name" :value="v.id" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="所属模块">
          <el-input v-model="form.module" placeholder="如：登录模块" />
        </el-form-item>
      </el-col>
    </el-row>
    <el-row :gutter="16">
      <el-col :span="8">
        <el-form-item label="指派人">
          <el-select v-model="form.assigned_to" filterable clearable style="width:100%">
            <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item label="处理人">
          <el-select v-model="form.resolver" filterable clearable style="width:100%">
            <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :span="8">
        <el-form-item label="验证人">
          <el-select v-model="form.verifier" filterable clearable style="width:100%">
            <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-col>
    </el-row>
    <el-form-item label="关联用例">
      <el-select v-model="form.related_testcase" filterable clearable style="width:100%">
        <el-option v-for="t in testcases" :key="t.id" :label="`#${t.id} ${t.title}`" :value="t.id" />
      </el-select>
    </el-form-item>
    <el-form-item label="期望修复">
      <el-date-picker v-model="form.due_at" type="datetime" placeholder="期望修复时间" style="width:100%" value-format="YYYY-MM-DDTHH:mm:ss" />
    </el-form-item>
    <el-form-item label="描述">
      <el-input v-model="form.description" type="textarea" :rows="3" />
    </el-form-item>
    <el-form-item label="复现步骤">
      <el-input v-model="form.steps_to_reproduce" type="textarea" :rows="3" />
    </el-form-item>
    <el-row :gutter="16">
      <el-col :span="12">
        <el-form-item label="预期结果">
          <el-input v-model="form.expected_result" type="textarea" :rows="2" />
        </el-form-item>
      </el-col>
      <el-col :span="12">
        <el-form-item label="实际结果">
          <el-input v-model="form.actual_result" type="textarea" :rows="2" />
        </el-form-item>
      </el-col>
    </el-row>
    <el-form-item label="来源">
      <el-select v-model="form.source" style="width:100%">
        <el-option v-for="s in sourceOptions" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
    </el-form-item>
    <el-form-item label="环境信息">
      <el-input v-model="form.environment" placeholder="如：Chrome 125 / Win11 / 测试服" />
    </el-form-item>
  </el-form>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { patchDefect } from '@/api/defects'
import request from '@/utils/api'

const props = defineProps({
  defect: { type: Object, required: true },
  versions: { type: Array, default: () => [] },
  testcases: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] },
})

const elForm = ref(null)
const projects = ref([])

const severityOptions = [
  { value: 'S1', label: '致命' }, { value: 'S2', label: '严重' },
  { value: 'S3', label: '一般' }, { value: 'S4', label: '轻微' },
]
const priorityOptions = [
  { value: 'P0', label: 'P0-紧急' }, { value: 'P1', label: 'P1-高' },
  { value: 'P2', label: 'P2-中' }, { value: 'P3', label: 'P3-低' },
]
const typeOptions = [
  { value: 'functional', label: '功能缺陷' }, { value: 'ui', label: '界面缺陷' },
  { value: 'compatibility', label: '兼容性缺陷' }, { value: 'performance', label: '性能缺陷' },
  { value: 'security', label: '安全缺陷' }, { value: 'data', label: '数据缺陷' },
  { value: 'other', label: '其他' },
]
const statusOptions = [
  { value: 'new', label: '新建' }, { value: 'open', label: '待处理' },
  { value: 'in_progress', label: '处理中' }, { value: 'resolved', label: '已修复' },
  { value: 'fixed', label: '待验证' }, { value: 'closed', label: '已关闭' },
  { value: 'rejected', label: '已驳回' }, { value: 'reopened', label: '重新打开' },
]
const sourceOptions = [
  { value: 'manual', label: '手动创建' }, { value: 'execution', label: '用例执行' },
  { value: 'performance', label: '性能测试' }, { value: 'hermes', label: '数字人' },
  { value: 'ai', label: 'AI分析' }, { value: 'api_testing', label: '接口测试' },
  { value: 'ui_automation', label: 'UI自动化' }, { value: 'app_automation', label: 'APP自动化' },
  { value: 'production', label: '生产反馈' },
]

const form = reactive({
  title: props.defect.title || '',
  project: props.defect.project || null,
  severity: props.defect.severity || 'S3',
  priority: props.defect.priority || 'P2',
  defect_type: props.defect.defect_type || 'functional',
  status: props.defect.status || 'open',
  version: props.defect.version || null,
  module: props.defect.module || '',
  assigned_to: props.defect.assigned_to || null,
  resolver: props.defect.resolver || null,
  verifier: props.defect.verifier || null,
  related_testcase: props.defect.related_testcase || null,
  due_at: props.defect.due_at || null,
  description: props.defect.description || '',
  steps_to_reproduce: props.defect.steps_to_reproduce || '',
  expected_result: props.defect.expected_result || '',
  actual_result: props.defect.actual_result || '',
  source: props.defect.source || 'manual',
  environment: props.defect.environment || '',
})

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/', { params: { page_size: 200 } })
    const data = res.data || res
    projects.value = data.results || data || []
  } catch (e) {}
}
const onProjectChange = () => {}

const submit = async () => {
  if (!form.title.trim()) { throw new Error('请填写标题') }
  if (!form.project) { throw new Error('请选择项目') }
  await patchDefect(props.defect.id, {
    title: form.title,
    project: form.project,
    severity: form.severity,
    priority: form.priority,
    defect_type: form.defect_type,
    status: form.status,
    version: form.version || null,
    module: form.module,
    assigned_to: form.assigned_to || null,
    resolver: form.resolver || null,
    verifier: form.verifier || null,
    related_testcase: form.related_testcase || null,
    due_at: form.due_at || null,
    description: form.description,
    steps_to_reproduce: form.steps_to_reproduce,
    expected_result: form.expected_result,
    actual_result: form.actual_result,
    source: form.source,
    environment: form.environment,
  })
}

loadProjects()
defineExpose({ submit })
</script>
