<template>
  <div class="ai-mode-config">
    <div class="page-header">
      <h1>🧠 AI智能模式配置</h1>
      <p>配置Browser-use执行时的智能模式与模型参数</p>
    </div>

    <div class="main-content">
      <div class="model-config-card">
        <div class="card-header">
          <h2>模型参数配置</h2>
          <el-tooltip content="配置文本模式与视觉模式使用的模型参数。执行时以「AI智能测试」页选择的执行模式为准：自动=有文本配置则优先文本（更稳定），否则视觉；文本=强制文本；视觉=强制视觉（需已配置视觉模型）。" placement="top">
            <el-icon><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
        
        <el-tabs v-model="activeTab" type="border-card">
          <el-tab-pane label="文本模式模型" name="text">
            <div class="tab-desc">
              <span class="icon">📝</span> 文本模式：基于DOM树解析，快速高效，适合结构化页面。
            </div>
            <model-form 
              v-model="config.text_model" 
              type="text"
              :has-api-key-saved="hasApiKeySavedText"
              @test="testConnection"
            />
          </el-tab-pane>
          <el-tab-pane label="视觉模式模型" name="vision">
            <div class="tab-desc">
              <span class="icon">👁</span> 视觉模式：基于页面截图，适合复杂布局与图标识别；需使用支持视觉的多模态模型。
            </div>
            <model-form 
              v-model="config.vision_model" 
              type="vision"
              :has-api-key-saved="hasApiKeySavedVision"
              @test="testConnection"
            />
          </el-tab-pane>
        </el-tabs>

        <div class="actions">
          <el-button type="primary" size="large" @click="saveConfig" :loading="saving">保存所有配置</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, defineComponent, h } from 'vue'
import { InfoFilled } from '@element-plus/icons-vue'
import { ElMessage, ElForm, ElFormItem, ElSelect, ElOption, ElInput, ElButton } from 'element-plus'
import api from '@/utils/api'

// 内联组件：模型表单
const ModelForm = defineComponent({
  props: ['modelValue', 'type', 'hasApiKeySaved'],
  emits: ['update:modelValue', 'test'],
  setup(props, { emit }) {
    const testing = ref(false)
    const apiKeyPlaceholder = () => (props.hasApiKeySaved ? '已配置，留空则不修改' : '输入API Key')

    const handleTest = async () => {
      testing.value = true
      try {
        await emit('test', props.modelValue)
      } finally {
        testing.value = false
      }
    }

    return () => h(ElForm, { model: props.modelValue, labelWidth: '120px' }, () => [
      h(ElFormItem, { label: '模型提供商' }, () => 
        h(ElSelect, { 
          modelValue: props.modelValue.provider,
          'onUpdate:modelValue': (val) => emit('update:modelValue', { ...props.modelValue, provider: val }),
          placeholder: '选择提供商',
          style: { width: '100%' }
        }, () => [
          h(ElOption, { label: 'OpenAI', value: 'openai' }),
          h(ElOption, { label: 'Azure OpenAI', value: 'azure_openai' }),
          h(ElOption, { label: 'Anthropic', value: 'anthropic' }),
          h(ElOption, { label: 'Google Gemini', value: 'google_gemini' }),
          h(ElOption, { label: 'DeepSeek', value: 'deepseek' }),
          h(ElOption, { label: '硅基流动 (SiliconFlow)', value: 'siliconflow' }),
          h(ElOption, { label: '其他 (Other)', value: 'other' })
        ])
      ),
      h(ElFormItem, { label: '模型名称' }, () => 
        h(ElInput, {
          modelValue: props.modelValue.model_name,
          'onUpdate:modelValue': (val) => emit('update:modelValue', { ...props.modelValue, model_name: val }),
          placeholder: '例如: gpt-4o, claude-3-5-sonnet'
        })
      ),
      h(ElFormItem, { label: 'API Key' }, () => 
        h(ElInput, {
          modelValue: props.modelValue.api_key,
          'onUpdate:modelValue': (val) => emit('update:modelValue', { ...props.modelValue, api_key: val }),
          type: 'password',
          placeholder: apiKeyPlaceholder()
        })
      ),
      h(ElFormItem, { label: 'Base URL' }, () => 
        h(ElInput, {
          modelValue: props.modelValue.base_url,
          'onUpdate:modelValue': (val) => emit('update:modelValue', { ...props.modelValue, base_url: val }),
          placeholder: '可选，例如: https://api.openai.com/v1'
        })
      ),
      h(ElFormItem, {}, () => 
        h(ElButton, { 
          type: 'success', 
          plain: true, 
          loading: testing.value,
          onClick: handleTest 
        }, () => '测试连接')
      )
    ])
  }
})

const saving = ref(false)
const activeTab = ref('text')
const config = ref({
  text_model: {
    provider: 'openai',
    model_name: 'gpt-4o',
    api_key: '',
    base_url: ''
  },
  vision_model: {
    provider: 'openai',
    model_name: 'gpt-4o',
    api_key: '',
    base_url: ''
  }
})

// 文本/视觉各自已存在的配置与 API Key 是否已保存
const currentTextConfigId = ref(null)
const currentVisionConfigId = ref(null)
const hasApiKeySavedText = ref(false)
const hasApiKeySavedVision = ref(false)

const loadConfig = async () => {
  try {
    const response = await api.get('/ui-automation/config/ai-mode/')
    const items = Array.isArray(response.data) ? response.data : []
    const textItems = items.filter(i => i.role === 'browser_use_text')
    const visionItems = items.filter(i => i.role === 'browser_use_vision')
    const pickActive = (arr) => arr.find(item => item.is_active) || arr[0]
    if (textItems.length > 0) {
      const active = pickActive(textItems)
      currentTextConfigId.value = active.id
      hasApiKeySavedText.value = !!(active.api_key_length && active.api_key_length > 0)
      config.value.text_model = {
        ...config.value.text_model,
        provider: active.model_type || config.value.text_model.provider,
        model_name: active.model_name || config.value.text_model.model_name,
        base_url: active.base_url || config.value.text_model.base_url,
        api_key: ''
      }
    } else {
      currentTextConfigId.value = null
      hasApiKeySavedText.value = false
    }
    if (visionItems.length > 0) {
      const active = pickActive(visionItems)
      currentVisionConfigId.value = active.id
      hasApiKeySavedVision.value = !!(active.api_key_length && active.api_key_length > 0)
      config.value.vision_model = {
        ...config.value.vision_model,
        provider: active.model_type || config.value.vision_model.provider,
        model_name: active.model_name || config.value.vision_model.model_name,
        base_url: active.base_url || config.value.vision_model.base_url,
        api_key: ''
      }
    } else {
      currentVisionConfigId.value = null
      hasApiKeySavedVision.value = false
    }
  } catch (error) {
    console.error('加载配置失败:', error)
    ElMessage.error('加载配置失败')
  }
}

const testConnection = async (modelConfig) => {
  if (!modelConfig.api_key) {
    ElMessage.warning('请先输入API Key')
    return
  }
  
  try {
    await api.post('/ui-automation/config/ai-mode/test_connection/', modelConfig)
    ElMessage.success('连接测试成功！')
  } catch (error) {
    console.error('连接测试失败:', error)
    const msg = error.response?.data?.error || '连接测试失败'
    ElMessage.error(msg)
    throw error
  }
}

const saveConfig = async () => {
  saving.value = true
  try {
    const isText = activeTab.value === 'text'
    const model = isText ? config.value.text_model : config.value.vision_model
    const currentId = isText ? currentTextConfigId.value : currentVisionConfigId.value
    const hasSaved = isText ? hasApiKeySavedText.value : hasApiKeySavedVision.value

    const payload = {
      name: model.model_name || (isText ? 'BrowserUse 文本模型' : 'BrowserUse 视觉模型'),
      model_type: model.provider || 'other',
      model_name: model.model_name,
      base_url: model.base_url || '',
      is_active: true,
      role: isText ? 'browser_use_text' : 'browser_use_vision'
    }
    if (currentId && (!model.api_key || !String(model.api_key).trim()) && hasSaved) {
      // 留空则不修改
    } else {
      payload.api_key = model.api_key || ''
    }

    if (!payload.model_name) {
      ElMessage.warning('请填写模型名称')
      saving.value = false
      return
    }
    if (!payload.api_key && !(currentId && hasSaved)) {
      ElMessage.warning('请填写 API Key')
      saving.value = false
      return
    }

    if (currentId) {
      await api.put(`/ui-automation/config/ai-mode/${currentId}/`, payload)
    } else {
      const resp = await api.post('/ui-automation/config/ai-mode/', payload)
      if (isText) {
        currentTextConfigId.value = resp.data?.id || null
      } else {
        currentVisionConfigId.value = resp.data?.id || null
      }
    }

    if (typeof payload.api_key === 'undefined') {
      if (isText) hasApiKeySavedText.value = true
      else hasApiKeySavedVision.value = true
    } else {
      if (isText) hasApiKeySavedText.value = !!(payload.api_key && String(payload.api_key).trim())
      else hasApiKeySavedVision.value = !!(payload.api_key && String(payload.api_key).trim())
    }
    ElMessage.success('配置保存成功')
  } catch (error) {
    console.error('保存配置失败:', error)
    const msg = error.response?.data?.error || '保存配置失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.ai-mode-config {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
}

.page-header {
  text-align: center;
  margin-bottom: 40px;
}

.page-header h1 {
  font-size: 2.5rem;
  color: #2c3e50;
  margin-bottom: 10px;
}

.page-header p {
  color: #666;
  font-size: 1.1rem;
}

.main-content {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.model-config-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.card-header h2 {
  margin: 0;
  font-size: 1.2rem;
  color: var(--el-text-color-primary);
}

.tab-desc {
  margin-bottom: 20px;
  padding: 10px 15px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  color: var(--el-text-color-regular);
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-desc .icon {
  font-size: 18px;
}

.actions {
  margin-top: 30px;
  display: flex;
  justify-content: center;
}

/* 让「文本 / 视觉」两个 Tab 的选中与未选中状态一眼能分清 */
:deep(.el-tabs--border-card .el-tabs__header .el-tabs__item) {
  font-size: 15px;
}
:deep(.el-tabs--border-card .el-tabs__item.is-active) {
  color: var(--el-color-primary);
  font-weight: 600;
  background-color: var(--el-bg-color);
  border-bottom-color: var(--el-bg-color);
}
:deep(.el-tabs--border-card .el-tabs__item:not(.is-active)) {
  color: var(--el-text-color-secondary);
  background-color: var(--el-fill-color);
}
:deep(.el-tabs--border-card .el-tabs__item:not(.is-active):hover) {
  color: var(--el-text-color-primary);
  background-color: var(--el-fill-color-light);
}
</style>
