<template>
  <div class="ai-generate-page">
    <h3>性能测试用例生成</h3>
    <p class="hint">选择「性能测试用例生成」Skill，粘贴接口列表或关键业务场景，生成性能测试用例（并发/持续时间/预期指标）。</p>
    <SkillGeneratePanel
      title="性能测试用例生成"
      skill-type="testcase_generator"
      module="performance_testing"
      placeholder="粘贴接口列表 / 关键业务场景描述..."
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
