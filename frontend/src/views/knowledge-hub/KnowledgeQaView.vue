<template>
  <KbChatView />
</template>

<script setup>
// 知识问答（沿用 AI 评测师问答页面，但绕过 Dify 工作流，直接检索知识库）
// 实际后端逻辑由 KbChatView 内部决定是否走 native KB 检索
import KbChatView from '@/views/requirement-analysis/KbChatView.vue'
</script>