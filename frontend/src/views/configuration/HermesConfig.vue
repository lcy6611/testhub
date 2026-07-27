<template>
  <div class="hermes-config">
    <div class="page-header">
      <h1>🤖 数字人配置</h1>
      <p>配置 Hermes 质量数字人的系统提示词、模型、形象与默认启用技能</p>
    </div>

    <div class="main-content">
      <el-card v-loading="loading" class="config-card">
        <el-form :model="form" label-width="120px">
          <el-form-item label="配置名称">
            <el-input v-model="form.name" placeholder="例如：默认配置" />
          </el-form-item>

          <el-form-item label="系统提示词">
            <el-input
              v-model="form.system_prompt"
              type="textarea"
              :rows="8"
              placeholder="为空则使用 Hermes 内置默认系统提示词"
            />
          </el-form-item>

          <el-form-item label="AI 模型配置">
            <el-select v-model="form.model_config" clearable placeholder="不选则使用系统默认 writer 配置" style="width: 100%">
              <el-option
                v-for="cfg in modelConfigs"
                :key="cfg.id"
                :label="`${cfg.name} (${cfg.model_name})`"
                :value="cfg.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="数字人模型 URL">
            <el-input
              v-model="form.avatar_url"
              placeholder="Live2D 模型地址，为空则使用内置预设"
            />
          </el-form-item>

          <el-form-item label="默认启用技能">
            <el-select
              v-model="form.active_skills"
              multiple
              collapse-tags
              collapse-tags-tooltip
              clearable
              placeholder="选择数字人默认加载的 Skill"
              style="width: 100%"
            >
              <el-option
                v-for="skill in digitalHumanSkills"
                :key="skill.id"
                :label="`${skill.icon || '🤖'} ${skill.name}`"
                :value="skill.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="TTS 朗读">
            <el-switch v-model="form.tts_enabled" active-text="开启" inactive-text="关闭" />
          </el-form-item>

          <el-form-item label="是否启用">
            <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" @click="saveConfig" :loading="saving">保存配置</el-button>
            <el-button @click="loadConfig">刷新</el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { getHermesConfigs, updateHermesConfig, createHermesConfig } from '@/api/agent'

const loading = ref(false)
const saving = ref(false)
const modelConfigs = ref([])
const digitalHumanSkills = ref([])

const form = ref({
  id: null,
  name: '默认配置',
  system_prompt: '',
  model_config: null,
  avatar_url: '',
  tts_enabled: true,
  active_skills: [],
  is_active: true,
})

async function loadModelConfigs() {
  try {
    const res = await api.get('/requirement-analysis/ai-models/')
    const data = res.data.results || res.data || []
    modelConfigs.value = data.filter(c => c && c.id)
  } catch (err) {
    ElMessage.error('加载模型配置失败')
    console.error(err)
  }
}

async function loadSkills() {
  try {
    const res = await api.get('/requirement-analysis/skills/', {
      params: { skill_type: 'digital_human', is_active: true }
    })
    const data = res.data.results || res.data || []
    digitalHumanSkills.value = data.filter(s => s && s.id)
  } catch (err) {
    ElMessage.error('加载 Skill 列表失败')
    console.error(err)
  }
}

async function loadConfig() {
  loading.value = true
  try {
    const res = await getHermesConfigs()
    const configs = res.data.results || res.data || []
    const active = configs.find(c => c.is_active) || configs[0]
    if (active) {
      form.value = {
        id: active.id,
        name: active.name || '默认配置',
        system_prompt: active.system_prompt || '',
        model_config: active.model_config || null,
        avatar_url: active.avatar_url || '',
        tts_enabled: active.tts_enabled !== false,
        active_skills: active.active_skills || [],
        is_active: active.is_active !== false,
      }
    }
  } catch (err) {
    ElMessage.error('加载数字人配置失败')
    console.error(err)
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      system_prompt: form.value.system_prompt,
      model_config: form.value.model_config || null,
      avatar_url: form.value.avatar_url,
      tts_enabled: form.value.tts_enabled,
      active_skills: form.value.active_skills || [],
      is_active: form.value.is_active,
    }
    if (form.value.id) {
      await updateHermesConfig(form.value.id, payload)
    } else {
      await createHermesConfig(payload)
    }
    ElMessage.success('保存成功')
    await loadConfig()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '保存失败')
    console.error(err)
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadModelConfigs(), loadSkills(), loadConfig()])
})
</script>

<style scoped>
.hermes-config {
  padding: 20px;
}
.page-header {
  margin-bottom: 24px;
}
.page-header h1 {
  margin: 0 0 8px;
  font-size: 24px;
  color: var(--el-text-color-primary);
}
.page-header p {
  margin: 0;
  color: var(--el-text-color-regular);
}
.main-content {
  max-width: 900px;
}
.config-card {
  padding: 12px;
}
</style>
