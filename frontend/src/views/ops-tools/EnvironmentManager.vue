<template>
  <div class="env-manager-page">
    <el-card class="panel-card">
      <template #header>
        <div class="card-header">
          <span class="panel-title">环境管理 / 数据库连接</span>
          <el-button type="primary" @click="openDialog()">新增环境</el-button>
        </div>
      </template>

      <el-table :data="environments" stripe>
        <el-table-column prop="name" label="环境名称" />
        <el-table-column prop="category" label="所属分类" />
        <el-table-column prop="access_method_display" label="访问方式" />
        <el-table-column prop="host" label="主机" />
        <el-table-column prop="db_type_display" label="数据库类型" />
        <el-table-column prop="database_scope" label="数据库范围" />
        <el-table-column label="状态">
          <template #default="{ row }">
            <el-tag :type="row.status === 'ready' ? 'success' : 'info'">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button link type="primary" @click="connectEnv(row)">连接</el-button>
            <el-button link @click="openDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="deleteEnv(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑环境' : '新增环境'" width="600px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="环境名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="所属分类">
          <el-input v-model="form.category" placeholder="如：Mac本地开发环境" />
        </el-form-item>
        <el-form-item label="访问方式">
          <el-radio-group v-model="form.access_method">
            <el-radio-button label="ssh">SSH</el-radio-button>
            <el-radio-button label="local">本地</el-radio-button>
            <el-radio-button label="db">数据库直连</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="主机地址" v-if="form.access_method !== 'db'">
          <el-input v-model="form.host" />
        </el-form-item>
        <el-form-item label="端口" v-if="form.access_method !== 'db'">
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名" v-if="form.access_method !== 'db'">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" v-if="form.access_method !== 'db'">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="数据库类型" v-if="form.access_method === 'db'">
          <el-select v-model="form.db_type" style="width: 100%">
            <el-option label="MySQL" value="mysql" />
            <el-option label="PostgreSQL" value="postgresql" />
            <el-option label="SQLite" value="sqlite" />
            <el-option label="Oracle" value="oracle" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据库主机" v-if="form.access_method === 'db'">
          <el-input v-model="form.db_host" />
        </el-form-item>
        <el-form-item label="数据库端口" v-if="form.access_method === 'db'">
          <el-input-number v-model="form.db_port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="数据库名" v-if="form.access_method === 'db'">
          <el-input v-model="form.db_name" />
        </el-form-item>
        <el-form-item label="数据库用户名" v-if="form.access_method === 'db'">
          <el-input v-model="form.db_username" />
        </el-form-item>
        <el-form-item label="数据库密码" v-if="form.access_method === 'db'">
          <el-input v-model="form.db_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="数据库范围">
          <el-input v-model="form.database_scope" placeholder="多个数据库用逗号分隔" />
        </el-form-item>
        <el-form-item label="默认目录">
          <el-input v-model="form.current_dir" placeholder="/var/log" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEnv">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getEnvironments,
  createEnvironment,
  updateEnvironment,
  deleteEnvironment,
  connectEnvironment,
} from '@/api/ops-tools'

const environments = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const currentId = ref(null)
const form = ref({
  name: '',
  category: '',
  access_method: 'ssh',
  host: '',
  port: 22,
  username: '',
  password: '',
  db_type: 'mysql',
  db_host: '',
  db_port: 3306,
  db_name: '',
  db_username: '',
  db_password: '',
  database_scope: '',
  current_dir: '/var/log',
})

async function loadEnvironments() {
  const res = await getEnvironments()
  environments.value = res.data.results || res.data || []
}

function openDialog(row) {
  isEdit.value = !!row
  currentId.value = row?.id || null
  form.value = row ? { ...row } : {
    name: '',
    category: '',
    access_method: 'ssh',
    host: '',
    port: 22,
    username: '',
    password: '',
    db_type: 'mysql',
    db_host: '',
    db_port: 3306,
    db_name: '',
    db_username: '',
    db_password: '',
    database_scope: '',
    current_dir: '/var/log',
  }
  dialogVisible.value = true
}

async function saveEnv() {
  if (isEdit.value) {
    await updateEnvironment(currentId.value, form.value)
    ElMessage.success('更新成功')
  } else {
    await createEnvironment(form.value)
    ElMessage.success('创建成功')
  }
  dialogVisible.value = false
  await loadEnvironments()
}

async function connectEnv(row) {
  const res = await connectEnvironment(row.id)
  ElMessage.success(res.data.detail)
  await loadEnvironments()
}

async function deleteEnv(row) {
  await ElMessageBox.confirm(`确定删除环境 ${row.name} 吗？`, '提示', { type: 'warning' })
  await deleteEnvironment(row.id)
  ElMessage.success('删除成功')
  await loadEnvironments()
}

onMounted(loadEnvironments)
</script>

<style lang="scss" scoped>
.env-manager-page {
  height: 100%;
}
.panel-card {
  background: var(--app-card-bg, #ffffff);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
</style>
