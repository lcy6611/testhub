<template>
  <div class="ai-generate-page">
    <h3>AI 生成接口用例</h3>
    <p class="hint">选择「接口用例生成」Skill，粘贴 Swagger/OpenAPI 或接口文档，一键生成结构化接口测试用例。</p>
    <SkillGeneratePanel
      title="接口用例生成"
      skill-type="testcase_generator"
      module="api_testing"
      placeholder="粘贴 Swagger/OpenAPI JSON 或接口文档文本..."
    />
  </div>
</template>

<script setup>
import SkillGeneratePanel from '@/components/SkillGeneratePanel.vue'
</script>

<style scoped>
.ai-generate-page {
  padding: 20px;
  max-width: 960px;
}
.ai-generate-page h3 {
  margin: 0 0 8px 0;
  color: #303133;
}
.hint {
  color: #909399;
  font-size: 13px;
  margin: 0 0 16px;
}
</style>
