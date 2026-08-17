<template>
  <div class="hermes-chat-view">
    <!-- 左侧：会话列表 -->
    <div class="conversation-panel">
      <div class="conversation-header">
        <div class="header-brand">
          <el-icon class="brand-icon"><Cpu /></el-icon>
          <span class="brand-title">Hermes</span>
        </div>
        <el-button type="primary" size="small" :icon="Plus" @click="onNewConversation">
          新建
        </el-button>
      </div>

      <div class="conversation-list" v-loading="hermesStore.loadingConversations">
        <div
          v-for="conv in hermesStore.conversations"
          :key="conv.id"
          :class="['conversation-item', { active: conv.id === hermesStore.currentConversationId }]"
          @click="hermesStore.selectConversation(conv.id)"
        >
          <el-icon class="conv-icon"><ChatDotRound /></el-icon>
          <div class="conv-info">
            <div class="conv-title" :title="conv.title || '新会话'">
              {{ conv.title || '新会话' }}
            </div>
            <div class="conv-time">{{ formatTime(conv.updated_at) }}</div>
          </div>
          <el-dropdown
            class="conv-actions"
            trigger="click"
            @command="(cmd) => handleConvCommand(cmd, conv)"
            @click.stop
          >
            <el-icon><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="rename">重命名</el-dropdown-item>
                <el-dropdown-item command="clear">清空消息</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>

        <div v-if="!hermesStore.conversations.length" class="conversation-empty">
          <el-icon><ChatLineRound /></el-icon>
          <p>暂无会话，点击「新建」开始</p>
        </div>
      </div>
    </div>

    <!-- 右侧：聊天面板 -->
    <HermesChatPanel />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Cpu, ChatDotRound, MoreFilled, ChatLineRound,
} from '@element-plus/icons-vue'
import { useHermesStore } from '@/stores/hermes'
import HermesChatPanel from '@/components/HermesChatPanel.vue'
import dayjs from 'dayjs'

const hermesStore = useHermesStore()

function formatTime(ts) {
  if (!ts) return ''
  return dayjs(ts).format('MM-DD HH:mm')
}

function onNewConversation() {
  hermesStore.createConversation()
}

async function handleConvCommand(cmd, conv) {
  if (cmd === 'rename') {
    try {
      const { value } = await ElMessageBox.prompt('请输入新标题', '重命名会话', {
        inputValue: conv.title || '',
        confirmButtonText: '确定',
        cancelButtonText: '取消',
      })
      if (value !== null) {
        await hermesStore.renameConversation(conv.id, value.trim())
      }
    } catch {
      // 取消
    }
  } else if (cmd === 'clear') {
    try {
      await ElMessageBox.confirm('确定清空该会话的所有消息？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
      await hermesStore.clearConversation(conv.id)
    } catch {
      // 取消
    }
  } else if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm('确定删除该会话？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })
      await hermesStore.removeConversation(conv.id)
    } catch {
      // 取消
    }
  }
}

onMounted(async () => {
  // 会话加载/创建由 HermesChatPanel 统一处理，这里兜底确保列表非空
  if (!hermesStore.conversations.length && !hermesStore.loadingConversations) {
    await hermesStore.loadConversations()
    if (!hermesStore.conversations.length) {
      await hermesStore.createConversation()
    } else {
      hermesStore.selectConversation(hermesStore.conversations[0].id)
    }
  }
})
</script>

<style scoped>
.hermes-chat-view {
  display: flex;
  height: 100%;
  background: #f5f7fa;
  overflow: hidden;
  min-height: 0;
}

/* 左侧会话列表面板 */
.conversation-panel {
  width: 280px;
  flex: 0 0 280px;
  height: 100%;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.conversation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #e4e7ed;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-icon {
  font-size: 24px;
  color: #409eff;
}

.brand-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
}

.conversation-item:hover {
  background: #f5f7fa;
}

.conversation-item.active {
  background: #ecf5ff;
}

.conv-icon {
  font-size: 18px;
  color: #909399;
  flex-shrink: 0;
}

.conv-info {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-time {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.conv-actions {
  opacity: 0;
  transition: opacity 0.2s;
  color: #909399;
  cursor: pointer;
  flex-shrink: 0;
}

.conversation-item:hover .conv-actions {
  opacity: 1;
}

.conversation-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #909399;
  gap: 8px;
}

.conversation-empty .el-icon {
  font-size: 40px;
}
</style>
