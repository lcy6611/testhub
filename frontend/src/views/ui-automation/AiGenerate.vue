<template>
  <div class="ai-generate-page">
    <h3>UI 自动化用例生成</h3>
    <p class="hint">选择「UI 自动化用例生成」Skill，粘贴需求描述与界面说明，生成结构化 UI 自动化测试用例。</p>
    <SkillGeneratePanel
      title="UI 自动化用例生成"
      skill-type="testcase_generator"
      module="ui_automation"
      placeholder="粘贴需求描述 + 界面截图说明..."
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
