<template>
  <div class="skill-gen-panel">
    <div class="sgp-header">
      <span class="sgp-title">{{ title }}</span>
      <el-select
        v-model="selectedSkillId"
        placeholder="选择 Skill"
        size="small"
        class="sgp-select"
        clearable
      >
        <el-option
          v-for="s in skills"
          :key="s.id"
          :label="`${s.icon || ''} ${s.name}`"
          :value="s.id"
        />
      </el-select>
    </div>

    <el-input
      v-model="inputText"
      type="textarea"
      :rows="6"
      :placeholder="placeholder"
      class="sgp-input"
    />

    <div class="sgp-actions">
      <el-button
        type="primary"
        size="small"
        @click="run"
        :disabled="!selectedSkillId || !inputText.trim() || loading"
      >
        {{ loading ? '生成中...' : '生成' }}
      </el-button>
      <el-button v-if="result" size="small" @click="copyResult">复制结果</el-button>
      <el-button
        v-if="result && module"
        type="success"
        size="small"
        @click="openSaveDialog"
      >
        保存为用例
      </el-button>
    </div>

    <div v-if="result" class="sgp-result">
      <pre>{{ result }}</pre>
    </div>

    <el-dialog
      v-model="saveDialogVisible"
      title="保存为用例"
      width="480px"
      @close="onDialogClose"
    >
      <el-form label-width="84px">
        <el-form-item label="名称" required>
          <el-input v-model="saveName" placeholder="用例名称" maxlength="200" />
        </el-form-item>
        <el-form-item :label="projectLabel" :required="projectRequired">
          <el-select
            v-model="saveProjectId"
            placeholder="选择项目"
            filterable
            clearable
            style="width: 100%"
            :loading="projectsLoading"
          >
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <div v-if="savedResult" class="sgp-saved">
        已保存：<b>{{ savedResult.name }}</b>
        <el-button type="text" @click="goToDetail">去查看</el-button>
      </div>
      <template #footer>
        <el-button size="small" @click="saveDialogVisible = false">关闭</el-button>
        <el-button
          v-if="!savedResult"
          type="primary"
          size="small"
          :disabled="!canSave"
          :loading="saving"
          @click="doSave"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { getSkills, runSkill, saveSkillCase } from '@/api/requirement-analysis'
import request from '@/utils/api'
import { ElMessage } from 'element-plus'

const PROJECT_API = {
  api_testing: '/api/api-testing/projects/',
  ui_automation: '/api/ui-automation/projects/',
  app_automation: '/api/app-automation/projects/',
  performance_testing: '/api/projects/',
  ai_mode: '/api/ui-automation/projects/',
}
const MODULE_LABEL = {
  api_testing: '接口测试',
  ui_automation: 'UI自动化',
  app_automation: 'APP自动化',
  performance_testing: '性能测试',
  ai_mode: 'AI智能模式',
}
const PROJECT_REQUIRED = ['ui_automation']

export default {
  name: 'SkillGeneratePanel',
  props: {
    title: { type: String, default: 'AI 生成' },
    skillType: { type: String, default: '' },
    module: { type: String, default: '' },
    placeholder: { type: String, default: '粘贴需求描述 / 接口文档 / 截图说明...' }
  },
  data() {
    return {
      skills: [],
      selectedSkillId: '',
      inputText: '',
      loading: false,
      result: '',
      saveDialogVisible: false,
      saveName: '',
      saveProjectId: '',
      projects: [],
      projectsLoading: false,
      saving: false,
      savedResult: null
    }
  },
  computed: {
    projectRequired() {
      return PROJECT_REQUIRED.includes(this.module)
    },
    projectLabel() {
      return this.module === 'performance_testing' ? '核心项目' : '所属项目'
    },
    canSave() {
      if (this.saving) return false
      if (this.projectRequired && !this.saveProjectId) return false
      return true
    }
  },
  async created() {
    await this.loadSkills()
  },
  methods: {
    async loadSkills() {
      try {
        const res = await getSkills({})
        const all = res.data.results || res.data || []
        this.skills = all.filter(
          (s) => s.is_active !== false && (!this.skillType || s.skill_type === this.skillType)
        )
      } catch (e) {
        this.skills = []
      }
    },
    async run() {
      if (!this.selectedSkillId || !this.inputText.trim()) return
      this.loading = true
      try {
        const res = await runSkill(this.selectedSkillId, this.inputText)
        this.result = res.data.output || ''
        ElMessage.success('生成完成')
      } catch (e) {
        ElMessage.error('生成失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        this.loading = false
      }
    },
    copyResult() {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(this.result).then(
          () => ElMessage.success('已复制'),
          () => ElMessage.warning('复制失败，请手动选择')
        )
      } else {
        ElMessage.warning('当前环境不支持自动复制')
      }
    },
    guessName() {
      const m = this.result.match(/^#{1,3}\s*(.+)$/m)
      return m ? m[1].trim().slice(0, 50) : ''
    },
    openSaveDialog() {
      this.savedResult = null
      this.saveName = this.guessName() || `AI生成${MODULE_LABEL[this.module] || ''}用例`
      this.saveProjectId = ''
      this.projects = []
      this.loadProjects()
      this.saveDialogVisible = true
    },
    async loadProjects() {
      const api = PROJECT_API[this.module]
      if (!api) return
      this.projectsLoading = true
      try {
        const res = await request({ url: api, method: 'get' })
        this.projects = res.data.results || res.data || []
      } catch (e) {
        this.projects = []
      } finally {
        this.projectsLoading = false
      }
    },
    async doSave() {
      if (this.projectRequired && !this.saveProjectId) {
        ElMessage.warning('请选择所属项目')
        return
      }
      this.saving = true
      try {
        const res = await saveSkillCase({
          module: this.module,
          name: this.saveName,
          project_id: this.saveProjectId || '',
          content: this.result,
          skill_id: this.selectedSkillId
        })
        this.savedResult = res.data
        ElMessage.success('已保存为用例')
      } catch (e) {
        ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        this.saving = false
      }
    },
    goToDetail() {
      if (this.savedResult && this.savedResult.detail_path) {
        this.$router.push(this.savedResult.detail_path)
        this.saveDialogVisible = false
      }
    },
    onDialogClose() {
      this.savedResult = null
    }
  }
}
</script>

<style scoped>
.skill-gen-panel {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px;
  background: #fff;
}
.sgp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  gap: 12px;
}
.sgp-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}
.sgp-select {
  width: 240px;
}
.sgp-input {
  margin-bottom: 10px;
}
.sgp-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.sgp-result {
  background: #f7f8fa;
  border-radius: 6px;
  padding: 12px;
  max-height: 480px;
  overflow: auto;
}
.sgp-result pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
}
.sgp-saved {
  background: #f0f9eb;
  border-radius: 6px;
  padding: 10px 12px;
  color: #67c23a;
  font-size: 13px;
}
</style>
