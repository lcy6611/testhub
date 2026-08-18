<template>
  <!-- 全局悬浮 Hermes 助手图标：可拖动，位置持久化到 localStorage -->
  <div
    v-if="visible"
    ref="dockRef"
    class="hermes-dock"
    :class="{ dragging }"
    :style="dockStyle"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    :title="dragging ? '拖动中…' : '点击打开 Hermes · 拖动可移动位置'"
  >
    <span class="hermes-dock__icon">🤖</span>
    <span v-if="!dragging && showHint" class="hermes-dock__hint">拖动我</span>
  </div>

  <!-- 右侧抽屉：Hermes 聊天窗口（可拖拽调整宽度） -->
  <el-drawer
    v-model="drawerVisible"
    direction="rtl"
    :size="drawerSize"
    :destroy-on-close="false"
    :show-close="false"
    class="hermes-dock__drawer">
    <div class="hermes-drawer-content">
      <div
        class="hermes-resize-handle"
        title="按住拖拽调整宽度"
        @pointerdown="onResizeDown"
      />
      <HermesChatPanel compact closable @close="drawerVisible = false" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute } from 'vue-router'
import HermesChatPanel from './HermesChatPanel.vue'

const STORAGE_KEY = 'hermes_dock_position'
const WIDTH_STORAGE_KEY = 'hermes_drawer_width'
const DEFAULT_DRAWER_WIDTH = 560 // 抽屉默认宽度(px)
const MIN_DRAWER_WIDTH = 360
const MAX_DRAWER_WIDTH = 1200
const SIZE = 56 // 图标直径(px)
const MARGIN = 16 // 距视口边缘最小间距(px)
const DRAG_THRESHOLD = 4 // 超过该位移才算拖动(否则算点击)

const route = useRoute()
const dockRef = ref(null)

// 位置(元素左上角相对视口)，null 表示尚未初始化(用默认右下角)
const pos = ref({ x: null, y: null })
const dragging = ref(false)
const moved = ref(false)
const showHint = ref(true)
const drawerVisible = ref(false)
const drawerWidth = ref(DEFAULT_DRAWER_WIDTH)

const drawerSize = computed(() => `${drawerWidth.value}px`)

// 在登录页 / Hermes 自身页面隐藏(避免冗余)
const visible = computed(() => {
  const p = route.path
  return !p.startsWith('/login') && p !== '/hermes'
})

const dockStyle = computed(() => {
  const { x, y } = pos.value
  if (x == null || y == null) return {}
  return { left: `${x}px`, top: `${y}px` }
})

function defaultPosition() {
  const w = window.innerWidth
  const h = window.innerHeight
  return {
    x: Math.max(MARGIN, w - SIZE - MARGIN),
    y: Math.max(MARGIN, h - SIZE - MARGIN - 8),
  }
}

function clamp(p) {
  const w = window.innerWidth
  const h = window.innerHeight
  return {
    x: Math.min(Math.max(MARGIN, p.x), Math.max(MARGIN, w - SIZE - MARGIN)),
    y: Math.min(Math.max(MARGIN, p.y), Math.max(MARGIN, h - SIZE - MARGIN)),
  }
}

function loadPosition() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (typeof parsed.x === 'number' && typeof parsed.y === 'number') {
        pos.value = clamp(parsed)
        return
      }
    }
  } catch (e) {
    // 解析失败则用默认
  }
  pos.value = defaultPosition()
}

function loadDrawerWidth() {
  try {
    const raw = localStorage.getItem(WIDTH_STORAGE_KEY)
    const w = raw ? parseInt(raw, 10) : 0
    if (w >= MIN_DRAWER_WIDTH && w <= MAX_DRAWER_WIDTH) {
      drawerWidth.value = w
    }
  } catch (e) {
    // 解析失败则用默认
  }
}

function saveDrawerWidth() {
  try {
    localStorage.setItem(WIDTH_STORAGE_KEY, String(drawerWidth.value))
  } catch (e) {
    // 忽略写入失败
  }
}

function savePosition() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pos.value))
  } catch (e) {
    // 忽略写入失败(隐私模式等)
  }
}

// ────────── 拖动逻辑(pointer 事件，兼容鼠标/触屏) ──────────
let startPointer = { x: 0, y: 0 }
let startPos = { x: 0, y: 0 }

function onPointerDown(e) {
  // 仅响应主键(左键/单指)
  if (e.button != null && e.button !== 0) return
  moved.value = false
  startPointer = { x: e.clientX, y: e.clientY }
  startPos = { ...pos.value }
  dragging.value = true
  showHint.value = false
  try { dockRef.value.setPointerCapture(e.pointerId) } catch {}
}

function onPointerMove(e) {
  if (!dragging.value) return
  const dx = e.clientX - startPointer.x
  const dy = e.clientY - startPointer.y
  if (!moved.value && Math.hypot(dx, dy) > DRAG_THRESHOLD) {
    moved.value = true
  }
  if (moved.value) {
    pos.value = clamp({ x: startPos.x + dx, y: startPos.y + dy })
  }
}

function onPointerUp(e) {
  if (!dragging.value) return
  try { dockRef.value.releasePointerCapture(e.pointerId) } catch {}
  dragging.value = false
  if (moved.value) {
    // 拖动结束 → 持久化位置
    savePosition()
  } else {
    // 未拖动 → 视为点击，右侧抽屉打开 Hermes
    drawerVisible.value = true
  }
}

function onResize() {
  // 视口变化时确保图标仍在可视范围内
  pos.value = clamp(pos.value)
  // 同时防止抽屉宽度超出视口
  const maxW = Math.max(MIN_DRAWER_WIDTH, window.innerWidth - 48)
  if (drawerWidth.value > maxW) {
    drawerWidth.value = maxW
  }
}

// ────────── 抽屉宽度调整逻辑 ──────────
let resizeStartX = 0
let resizeStartWidth = DEFAULT_DRAWER_WIDTH
let resizing = false

function onResizeDown(e) {
  if (e.button != null && e.button !== 0) return
  resizing = true
  resizeStartX = e.clientX
  resizeStartWidth = drawerWidth.value
  const handle = e.currentTarget
  try { handle.setPointerCapture(e.pointerId) } catch {}
  window.addEventListener('pointermove', onResizeMove)
  window.addEventListener('pointerup', onResizeUp)
}

function onResizeMove(e) {
  if (!resizing) return
  // rtl 抽屉固定在右侧：鼠标往左移(clientX 变小) → 宽度增加
  const delta = resizeStartX - e.clientX
  const maxW = Math.min(MAX_DRAWER_WIDTH, window.innerWidth - 48)
  drawerWidth.value = Math.max(MIN_DRAWER_WIDTH, Math.min(maxW, resizeStartWidth + delta))
}

function onResizeUp() {
  if (!resizing) return
  resizing = false
  saveDrawerWidth()
  window.removeEventListener('pointermove', onResizeMove)
  window.removeEventListener('pointerup', onResizeUp)
}

onMounted(() => {
  loadPosition()
  loadDrawerWidth()
  window.addEventListener('resize', onResize)
  // 5 秒后淡出"拖动我"提示
  setTimeout(() => { showHint.value = false }, 5000)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
.hermes-dock {
  position: fixed;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff 0%, #67c23a 100%);
  box-shadow: 0 6px 18px rgba(64, 158, 255, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  user-select: none;
  touch-action: none; /* 关键：阻止触屏拖动时页面滚动 */
  z-index: 2000;
  transition: box-shadow 0.2s, transform 0.1s;
}
.hermes-dock:hover {
  box-shadow: 0 8px 24px rgba(64, 158, 255, 0.6);
}
.hermes-dock:active {
  cursor: grabbing;
}
.hermes-dock.dragging {
  cursor: grabbing;
  transform: scale(1.08);
  box-shadow: 0 10px 28px rgba(64, 158, 255, 0.7);
  transition: none;
}
.hermes-dock__icon {
  font-size: 28px;
  line-height: 1;
  pointer-events: none;
}
.hermes-dock__hint {
  position: absolute;
  bottom: -22px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  color: #909399;
  white-space: nowrap;
  pointer-events: none;
  background: rgba(255, 255, 255, 0.9);
  padding: 1px 6px;
  border-radius: 8px;
}

/* 抽屉内 Hermes 聊天面板铺满 */
.hermes-dock__drawer :deep(.el-drawer__header) {
  display: none;
}
.hermes-dock__drawer :deep(.el-drawer__body) {
  padding: 0;
  height: 100%;
  overflow: hidden;
}
.hermes-drawer-content {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.hermes-drawer-content > .chat-panel {
  flex: 1;
  min-width: 0;
}

/* 左侧拖拽调整宽度的把手 */
.hermes-resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 8px;
  cursor: col-resize;
  z-index: 10;
  background: transparent;
  transition: background 0.2s;
}
.hermes-resize-handle:hover,
.hermes-resize-handle:active {
  background: rgba(13, 148, 136, 0.25);
}
.hermes-resize-handle::after {
  content: '';
  position: absolute;
  left: 2px;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 48px;
  border-radius: 2px;
  background: rgba(13, 148, 136, 0.35);
}
</style>
