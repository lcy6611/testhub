<template>
  <div class="page-container defect-detail-page" v-loading="loading">
    <div class="page-header">
      <div class="title-block">
        <el-button text @click="$router.push('/defects')">
          <el-icon><ArrowLeft /></el-icon> 返回
        </el-button>
        <span class="bug-code" v-if="d.bug_code">{{ d.bug_code }}</span>
        <h1 class="page-title">{{ d.title }}</h1>
        <el-tag :type="statusTagType(d.status)" size="small">{{ d.status_display }}</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="openEditDialog"><el-icon><Edit /></el-icon> 编辑</el-button>
        <el-button type="primary" @click="openTransitionDialog">
          <el-icon><Switch /></el-icon> 状态流转
        </el-button>
      </div>
    </div>

    <el-row :gutter="16" v-if="!loading">
      <!-- 左：基本信息 + 流转时间线 -->
      <el-col :span="16">
        <el-card shadow="never" class="block">
          <template #header><span class="block-title">基本信息</span></template>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="严重程度">
              <el-tag :type="severityTagType(d.severity)" size="small">{{ d.severity_display }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="优先级">
              <el-tag size="small">{{ d.priority_display }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="缺陷类型">{{ d.defect_type_display }}</el-descriptions-item>
            <el-descriptions-item label="所属模块">{{ d.module || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发现版本">{{ d.version_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="来源">{{ d.source_display || '手动创建' }}</el-descriptions-item>
            <el-descriptions-item label="报告人">{{ d.reported_by_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="指派人">{{ d.assigned_to_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="处理人">{{ d.resolver_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="验证人">{{ d.verifier_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="期望修复时间">{{ formatTime(d.due_at) }}</el-descriptions-item>
            <el-descriptions-item label="解决时间">{{ formatTime(d.resolved_at) }}</el-descriptions-item>
            <el-descriptions-item label="关闭时间">{{ formatTime(d.closed_at) }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(d.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="更新时间">{{ formatTime(d.updated_at) }}</el-descriptions-item>
          </el-descriptions>

          <el-divider content-position="left">描述 / 复现</el-divider>
          <div class="field-p"><b>描述：</b>{{ d.description || '-' }}</div>
          <div class="field-p"><b>复现步骤：</b><pre class="pre">{{ d.steps_to_reproduce || '-' }}</pre></div>
          <div class="field-p"><b>预期结果：</b>{{ d.expected_result || '-' }}</div>
          <div class="field-p"><b>实际结果：</b>{{ d.actual_result || '-' }}</div>
          <div class="field-p"><b>环境：</b>{{ d.environment || '-' }}</div>

          <el-divider content-position="left">关联</el-divider>
          <div class="rel-row">
            <el-tag v-if="d.requirement_id" type="success" effect="plain">需求 #{{ d.requirement_id }}：{{ d.requirement_title }}</el-tag>
            <el-tag v-if="d.related_testcase_id" type="warning" effect="plain">用例 #{{ d.related_testcase_id }}：{{ d.related_testcase_title }}</el-tag>
            <el-tag v-if="d.test_run_id" type="info" effect="plain">执行 #{{ d.test_run_id }}</el-tag>
            <span v-if="!d.requirement_id && !d.related_testcase_id && !d.test_run_id" class="muted">无</span>
          </div>
        </el-card>

        <el-card shadow="never" class="block">
          <template #header><span class="block-title">流转历史</span></template>
          <el-timeline v-if="d.transition_logs && d.transition_logs.length">
            <el-timeline-item
              v-for="t in d.transition_logs"
              :key="t.id"
              :timestamp="formatTime(t.created_at)"
              placement="top"
            >
              <div class="tl-row">
                <el-tag size="small">{{ t.from_status_display || '—' }}</el-tag>
                <el-icon><Right /></el-icon>
                <el-tag size="small" :type="statusTagType(t.to_status)">{{ t.to_status_display }}</el-tag>
                <span class="tl-op">操作人：{{ t.operator_name || '-' }}</span>
                <span v-if="t.target_user_name" class="tl-op">指派给：{{ t.target_user_name }}</span>
              </div>
              <div class="tl-comment" v-if="t.comment">{{ t.comment }}</div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无流转记录" :image-size="60" />
        </el-card>
      </el-col>

      <!-- 右：评论 + 附件 -->
      <el-col :span="8">
        <el-card shadow="never" class="block">
          <template #header><span class="block-title">附件 ({{ (d.attachments||[]).length }})</span></template>
          <el-upload
            :http-request="uploadAtt"
            :show-file-list="false"
            multiple
            accept="image/*,.log,.txt,.zip"
            :before-upload="beforeUpload"
          >
            <el-button type="primary" plain size="small"><el-icon><Upload /></el-icon> 上传附件</el-button>
          </el-upload>
          <div class="att-grid" v-if="d.attachments && d.attachments.length">
            <div v-for="att in d.attachments" :key="att.id" class="att-card">
              <el-image
                v-if="att.kind === 'screenshot'"
                :src="att.file_url"
                :preview-src-list="d.attachments.filter(a => a.kind==='screenshot').map(a=>a.file_url)"
                :preview-teleported="true" fit="cover" class="att-card-img"
              />
              <a v-else :href="att.file_url" target="_blank" class="att-card-file">
                <el-icon><Document /></el-icon><span>{{ att.original_name || '附件' }}</span>
              </a>
              <el-button size="small" type="danger" link class="att-del" @click="removeAtt(att)">
                <el-icon><Delete /></el-icon>
              </el-button>
              <div class="att-cap">{{ att.caption || att.original_name || '' }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无附件" :image-size="50" />
        </el-card>

        <el-card shadow="never" class="block">
          <template #header><span class="block-title">评论 ({{ (d.comments||[]).length }})</span></template>
          <div class="comment-list" v-if="d.comments && d.comments.length">
            <div v-for="c in d.comments" :key="c.id" class="comment-item">
              <div class="c-head">
                <b>{{ c.author_name || '匿名' }}</b>
                <span class="c-time">{{ formatTime(c.created_at) }}</span>
                <el-button size="small" type="danger" link @click="removeComment(c)">删除</el-button>
              </div>
              <div class="c-body">{{ c.content }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无评论" :image-size="50" />
          <el-input
            v-model="commentText"
            type="textarea"
            :rows="3"
            placeholder="发表评论..."
            class="comment-input"
          />
          <el-button type="primary" size="small" @click="postComment" :disabled="!commentText.trim()">发送</el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editVisible" title="编辑缺陷" width="780px" :close-on-click-modal="false" destroy-on-close>
      <DefectForm ref="formRef" :defect="d" :versions="versions" :testcases="testcases" :users="users" />
      <template #footer>
        <el-button @click="editVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 流转弹窗 -->
    <el-dialog v-model="transVisible" title="状态流转" width="480px" :close-on-click-modal="false">
      <el-form label-width="90px">
        <el-form-item label="当前状态">
          <el-tag :type="statusTagType(d.status)" size="small">{{ d.status_display }}</el-tag>
        </el-form-item>
        <el-form-item label="目标状态" required>
          <el-select v-model="transForm.to_status" style="width:100%">
            <el-option v-for="s in allStatusOptions" :key="s.value" :label="s.label" :value="s.value" :disabled="s.value===d.status" />
          </el-select>
        </el-form-item>
        <el-form-item label="指派给">
          <el-select v-model="transForm.target_user" filterable clearable style="width:100%">
            <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="transForm.comment" type="textarea" :rows="3" placeholder="流转说明（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transVisible=false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doTransition">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, Edit, Switch, Upload, Delete, Document, Right
} from '@element-plus/icons-vue'
import {
  getDefect, transitionDefect,
  createDefectComment, deleteDefectComment,
  uploadDefectAttachment, deleteDefectAttachment
} from '@/api/defects'
import request from '@/utils/api'
import DefectForm from './DefectForm.vue'

const route = useRoute()
const defectId = route.params.id

const loading = ref(true)
const d = ref({})
const users = ref([])
const versions = ref([])
const testcases = ref([])

const editVisible = ref(false)
const transVisible = ref(false)
const saving = ref(false)
const formRef = ref(null)

const commentText = ref('')
const transForm = reactive({ to_status: '', target_user: null, comment: '' })

const allStatusOptions = [
  { value: 'new', label: '新建' },
  { value: 'open', label: '待处理' },
  { value: 'in_progress', label: '处理中' },
  { value: 'resolved', label: '已修复' },
  { value: 'fixed', label: '待验证' },
  { value: 'closed', label: '已关闭' },
  { value: 'rejected', label: '已驳回' },
  { value: 'reopened', label: '重新打开' },
]

const loadDetail = async () => {
  loading.value = true
  try {
    const res = await getDefect(defectId)
    d.value = res.data || res
  } catch (e) {
    ElMessage.error('加载缺陷失败：' + (e.message || ''))
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const res = await request.get('/users/users/', { params: { page_size: 200 } })
    const data = res.data || res
    users.value = data.results || data || []
  } catch (e) {}
}
const loadVersions = async () => {
  try {
    const res = await request.get('/versions/', { params: { projects: d.value.project, page_size: 200 } })
    const data = res.data || res
    versions.value = data.results || data || []
  } catch (e) {}
}
const loadTestcases = async () => {
  try {
    const res = await request.get('/testcases/', { params: { project: d.value.project, page_size: 200 } })
    const data = res.data || res
    testcases.value = data.results || data || []
  } catch (e) {}
}

const postComment = async () => {
  if (!commentText.value.trim()) return
  try {
    await createDefectComment(defectId, { content: commentText.value.trim() })
    commentText.value = ''
    ElMessage.success('已发表')
    loadDetail()
  } catch (e) {
    ElMessage.error('评论失败：' + (e.message || ''))
  }
}
const removeComment = async (c) => {
  try {
    await ElMessageBox.confirm('确认删除该评论？', '提示', { type: 'warning' })
    await deleteDefectComment(defectId, c.id)
    ElMessage.success('已删除')
    loadDetail()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败：' + (e.message || '')) }
}

const uploadAtt = async (options) => {
  const fd = new FormData()
  fd.append('file', options.file)
  fd.append('kind', options.file.type.startsWith('image/') ? 'screenshot' : 'log')
  try {
    await uploadDefectAttachment(defectId, fd)
    ElMessage.success('已上传')
    loadDetail()
  } catch (e) { ElMessage.error('上传失败：' + (e.message || '')) }
}
const beforeUpload = (file) => {
  if (file.size / 1024 / 1024 > 20) { ElMessage.error(`${file.name} 超过 20MB`); return false }
}
const removeAtt = async (att) => {
  try {
    await ElMessageBox.confirm('确认删除该附件？', '提示', { type: 'warning' })
    await deleteDefectAttachment(defectId, att.id)
    ElMessage.success('已删除')
    loadDetail()
  } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败：' + (e.message || '')) }
}

const openEditDialog = () => { loadVersions(); loadTestcases(); editVisible.value = true }
const submitEdit = async () => {
  saving.value = true
  try {
    await formRef.value.submit()
    ElMessage.success('已保存')
    editVisible.value = false
    loadDetail()
  } catch (e) {
    // form 内部已提示
  } finally { saving.value = false }
}

const openTransitionDialog = () => { transForm.to_status = ''; transForm.target_user = null; transForm.comment = ''; transVisible.value = true }
const doTransition = async () => {
  if (!transForm.to_status) return ElMessage.warning('请选择目标状态')
  saving.value = true
  try {
    await transitionDefect(defectId, {
      to_status: transForm.to_status,
      target_user: transForm.target_user || null,
      comment: transForm.comment
    })
    ElMessage.success('流转成功')
    transVisible.value = false
    loadDetail()
  } catch (e) {
    ElMessage.error('流转失败：' + (e.message || ''))
  } finally { saving.value = false }
}

const severityTagType = (s) => ({ S1: 'danger', S2: 'warning', S3: 'info', S4: '' })[s] || ''
const statusTagType = (s) => ({
  new: 'info', open: 'danger', in_progress: 'warning', resolved: 'success',
  fixed: 'warning', closed: 'info', rejected: 'info', reopened: 'warning'
}[s] || '')
const formatTime = (t) => {
  if (!t) return '-'
  const dt = new Date(t)
  const pad = (n) => String(n).padStart(2, '0')
  return `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())} ${pad(dt.getHours())}:${pad(dt.getMinutes())}`
}

onMounted(() => { loadUsers(); loadDetail() })
</script>

<style scoped>
.defect-detail-page { padding: 20px; }
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.title-block { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.page-title { margin:0; font-size:20px; font-weight:600; }
.bug-code { font-family: monospace; background:#f4f4f5; padding:2px 8px; border-radius:4px; color:#409eff; font-size:13px; }
.block { margin-bottom:16px; }
.block-title { font-weight:600; }
.field-p { font-size:13px; margin:6px 0; color:#303133; }
.field-p .pre, pre { white-space:pre-wrap; background:#f4f4f5; padding:8px; border-radius:4px; margin:4px 0 0; font-family:inherit; font-size:12px; }
.tl-row { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
.tl-op { font-size:12px; color:#909399; }
.tl-comment { margin-top:4px; font-size:13px; color:#606266; background:#fafafa; padding:6px 8px; border-radius:4px; }
.rel-row { display:flex; gap:8px; flex-wrap:wrap; }
.att-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(120px,1fr)); gap:10px; margin-top:10px; }
.att-card { position:relative; border:1px solid #ebeef5; border-radius:6px; padding:6px; background:#fafafa; min-height:90px; }
.att-card-img { width:100%; height:90px; object-fit:cover; border-radius:4px; }
.att-card-file { display:flex; align-items:center; gap:6px; height:90px; padding:8px; text-decoration:none; color:#606266; font-size:12px; word-break:break-all; }
.att-del { position:absolute; top:4px; right:4px; background:rgba(255,255,255,.8); border-radius:50%; }
.att-cap { margin-top:4px; font-size:11px; color:#909399; text-align:center; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.comment-list { margin-bottom:10px; }
.comment-item { border-bottom:1px solid #f0f0f0; padding:8px 0; }
.c-head { display:flex; align-items:center; gap:8px; font-size:13px; }
.c-time { color:#909399; font-size:12px; }
.c-body { margin-top:4px; font-size:13px; color:#303133; white-space:pre-wrap; }
.comment-input { margin:8px 0; }
.muted { color:#c0c4cc; }
</style>
