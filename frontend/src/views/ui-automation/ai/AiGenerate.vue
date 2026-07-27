<template>
  <div class="ai-generate-page">
    <h3>AI 智能模式用例生成</h3>
    <p class="hint">选择「全能用例生成」Skill，粘贴业务场景或操作流程，生成可驱动 Browser-use 智能执行的测试用例。</p>
    <SkillGeneratePanel
      title="AI 智能模式用例生成"
      skill-type="testcase_generator"
      module="ai_mode"
      placeholder="粘贴业务场景 / 操作流程描述..."
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
