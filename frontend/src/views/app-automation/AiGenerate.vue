<template>
  <div class="ai-generate-page">
    <h3>APP 自动化用例生成</h3>
    <p class="hint">选择「全能用例生成」Skill，粘贴需求描述与操作步骤说明，生成结构化 APP 自动化测试用例。</p>
    <SkillGeneratePanel
      title="APP 自动化用例生成"
      skill-type="testcase_generator"
      module="app_automation"
      placeholder="粘贴需求描述 / 操作步骤说明..."
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
