<template>
  <template v-for="node in nodes" :key="node.path">
    <el-sub-menu v-if="node.type === 'dir'" :index="node.path">
      <template #title>
        <el-icon><Folder /></el-icon>
        <span>{{ node.name }}</span>
      </template>
      <DocTreeMenu :nodes="node.children" @select="(p) => $emit('select', p)" />
    </el-sub-menu>
    <el-menu-item v-else :index="node.path" @click="$emit('select', node.path)">
      <el-icon><Document /></el-icon>
      <span>{{ node.title || node.name }}</span>
    </el-menu-item>
  </template>
</template>

<script setup>
import { Document, Folder } from '@element-plus/icons-vue'

// 递归渲染目录树：dir -> el-sub-menu，file -> el-menu-item
defineProps({
  nodes: {
    type: Array,
    default: () => []
  }
})
defineEmits(['select'])
</script>
