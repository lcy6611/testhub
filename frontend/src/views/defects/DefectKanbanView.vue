<template>
  <div class="page-container kanban-page">
    <div class="page-header">
      <h1 class="page-title"><el-icon><Grid /></el-icon> 缺陷看板</h1>
      <div class="header-actions">
        <el-select v-model="filterProject" placeholder="项目" clearable filterable @change="load" style="width:180px">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button @click="$router.push('/defects')"><el-icon><List /></el-icon> 列表</el-button>
        <el-button @click="$router.push('/defects/stats')"><el-icon><DataAnalysis /></el-icon> 统计</el-button>
      </div>
    </div>

    <div class="kanban-board" v-loading="loading">
      <div class="kanban-col" v-for="col in columns" :key="col.value">
        <div class="col-head" :class="`col-${col.value}`">
          <span class="col-title">{{ col.label }}</span>
          <span class="col-count">{{ grouped[col.value]?.length || 0 }}</span>
        </div>
        <div class="col-body">
          <div
            v-for="item in grouped[col.value]"
            :key="item.id"
            class="kanban-card"
            @click="goDetail(item)"
          >
            <div class="card-top">
              <span class="card-code" v-if="item.bug_code">{{ item.bug_code }}</span>
              <el-tag :type="severityTagType(item.severity)" size="small">{{ item.severity_display }}</el-tag>
              <el-tag size="small">{{ item.priority_display }}</el-tag>
            </div>
            <div class="card-title">{{ item.title }}</div>
            <div class="card-meta">
              <span>{{ item.assigned_to_name || '未指派' }}</span>
              <el-dropdown trigger="click" @command="(s)=>move(item,s)" @click.stop>
                <el-button size="small" type="primary" link>流转<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item
                      v-for="s in columns.filter(c=>c.value!==col.value)"
                      :key="s.value"
                      :command="s.value"
                    >{{ s.label }}</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
          <el-empty v-if="!grouped[col.value]?.length" :image-size="40" description="空" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Grid, List, DataAnalysis, ArrowDown } from '@element-plus/icons-vue'
import { getDefects, transitionDefect } from '@/api/defects'
import request from '@/utils/api'

const router = useRouter()
const loading = ref(false)
const defects = ref([])
const projects = ref([])
const filterProject = ref(null)

const columns = [
  { value: 'new', label: '新建' },
  { value: 'open', label: '待处理' },
  { value: 'in_progress', label: '处理中' },
  { value: 'resolved', label: '已修复' },
  { value: 'fixed', label: '待验证' },
  { value: 'closed', label: '已关闭' },
  { value: 'rejected', label: '已驳回' },
  { value: 'reopened', label: '重新打开' },
]

const grouped = reactive({})
columns.forEach(c => { grouped[c.value] = [] })

const load = async () => {
  loading.value = true
  try {
    const params = { page_size: 200 }
    if (filterProject.value) params.project = filterProject.value
    const res = await getDefects(params)
    const data = res.data || res
    defects.value = data.results || data || []
    columns.forEach(c => { grouped[c.value] = [] })
    defects.value.forEach(d => { if (grouped[d.status]) grouped[d.status].push(d) })
  } catch (e) {
    ElMessage.error('加载看板失败：' + (e.message || ''))
  } finally { loading.value = false }
}

const loadProjects = async () => {
  try {
    const res = await request.get('/projects/', { params: { page_size: 200 } })
    const data = res.data || res
    projects.value = data.results || data || []
    if (projects.value.length) { filterProject.value = projects.value[0].id; load() }
  } catch (e) {}
}

const move = async (item, toStatus) => {
  try {
    await transitionDefect(item.id, { to_status: toStatus })
    ElMessage.success('已流转')
    load()
  } catch (e) { ElMessage.error('流转失败：' + (e.message || '')) }
}

const goDetail = (item) => router.push(`/defects/${item.id}`)

const severityTagType = (s) => ({ S1: 'danger', S2: 'warning', S3: 'info', S4: '' })[s] || ''

onMounted(loadProjects)
</script>

<style scoped>
.kanban-page { padding: 20px; }
.page-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.page-title { display:flex; align-items:center; gap:8px; margin:0; font-size:20px; font-weight:600; }
.header-actions { display:flex; gap:8px; }
.kanban-board { display:flex; gap:12px; overflow-x:auto; align-items:flex-start; }
.kanban-col { min-width:220px; flex:1; background:#f5f7fa; border-radius:8px; padding:8px; }
.col-head { display:flex; justify-content:space-between; align-items:center; padding:6px 8px; border-radius:6px 6px 0 0; font-weight:600; }
.col-count { background:#fff; border-radius:10px; padding:0 8px; font-size:12px; }
.col-new { background:#ecf5ff; color:#409eff; }
.col-open { background:#fef0f0; color:#f56c6c; }
.col-in_progress { background:#fdf6ec; color:#e6a23c; }
.col-resolved { background:#f0f9eb; color:#67c23a; }
.col-fixed { background:#fdf6ec; color:#e6a23c; }
.col-closed { background:#f4f4f5; color:#909399; }
.col-rejected { background:#f4f4f5; color:#909399; }
.col-reopened { background:#fdf6ec; color:#e6a23c; }
.col-body { padding:8px 0; min-height:60px; }
.kanban-card { background:#fff; border-radius:6px; padding:8px; margin-bottom:8px; box-shadow:0 1px 3px rgba(0,0,0,.06); cursor:pointer; transition:all .15s; }
.kanban-card:hover { box-shadow:0 2px 8px rgba(0,0,0,.12); transform:translateY(-1px); }
.card-top { display:flex; align-items:center; gap:6px; margin-bottom:4px; }
.card-code { font-family:monospace; font-size:11px; color:#409eff; }
.card-title { font-size:13px; color:#303133; margin-bottom:6px; line-height:1.4; }
.card-meta { display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#909399; }
</style>
