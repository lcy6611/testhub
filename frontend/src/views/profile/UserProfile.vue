<template>
  <div class="page-container">
    <div class="page-header">
      <h1 class="page-title">个人设置</h1>
    </div>
    
    <div class="card-container">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <el-form v-if="userStore.user" :model="userStore.user" label-width="100px">
            <el-form-item label="用户名">
              <el-input v-model="userStore.user.username" disabled />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="userStore.user.email" />
            </el-form-item>
            <el-form-item label="姓名">
              <el-input v-model="userStore.user.first_name" />
            </el-form-item>
            <el-form-item label="部门">
              <el-input v-model="userStore.user.department" />
            </el-form-item>
            <el-form-item label="职位">
              <el-input v-model="userStore.user.position" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary">保存</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        
        <el-tab-pane label="修改密码" name="password">
          <el-form label-width="100px">
            <el-form-item label="当前密码">
              <el-input type="password" />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input type="password" />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input type="password" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary">修改密码</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="Hermes 助手" name="hermes">
          <el-form label-width="120px">
            <el-form-item label="Hermes 虚拟形象">
              <el-switch
                v-model="themeStore.hermesAvatarEnabled"
                active-text="开启"
                inactive-text="关闭"
                @change="onHermesToggle"
              />
            </el-form-item>
            <el-form-item>
              <span class="hermes-tip">关闭后，右下角的 Hermes 助手（含眼睛表头）将不再显示。</span>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const themeStore = useThemeStore()
const activeTab = ref('basic')

function onHermesToggle(val) {
  themeStore.setHermesAvatarEnabled(val)
  ElMessage.success(val ? '已开启 Hermes 虚拟形象' : '已关闭 Hermes 虚拟形象')
}
</script>

<style scoped>
.hermes-tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}
</style>