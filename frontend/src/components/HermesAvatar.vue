<template>
  <div class="hermes-avatar" ref="containerRef">
    <canvas ref="canvasRef" @click="onCanvasClick"></canvas>
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <div class="loading-text">正在召唤…</div>
    </div>
    <!-- 状态指示器 -->
    <div class="status-badge" :class="state">
      <span class="status-dot"></span>
      <span class="status-text">{{ statusText }}</span>
    </div>
    <!-- TTS 开关 -->
    <div class="tts-toggle" @click="ttsEnabled = !ttsEnabled" :title="ttsEnabled ? '点击关闭语音' : '点击开启语音'">
      <el-icon :class="{ active: ttsEnabled }">
        <Microphone v-if="ttsEnabled" />
        <Mute v-else />
      </el-icon>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue'
import { Mute, Microphone } from '@element-plus/icons-vue'

// Live2D 相关（动态导入避免 SSR 问题 & 按需加载）
let PIXI = null
let Live2DModel = null

// ────────── 互动按钮配置 ──────────
// motions: 按优先级尝试播放的 motion group（按模型实际命名）
//  - haru (Cubism 4): Idle / Tap / FlickHead / TapBody
//  - shizuku (Cubism 2): idle / tap_body / flick_head / shake / pinch_in / pinch_out
//  - koharu (Cubism 2): idle / '' (空名组)
//  - izumi (Cubism 2): idle / 'null' (字符串null组)
// 实际匹配时按当前模型元数据（PRESET_MODELS[i].motions）过滤
// fallback: 兜底表情参数（确保所有模型都有视觉反馈）
// holdMs: 表情持续时间后自动 reset
// reset: 复原参数列表（只 reset 自己改过的）
const interactButtons = [
  { id: 'wave',      emoji: '👋', label: '打招呼',
    motions: ['FlickHead', 'flick_head', 'Tap', 'tap_body', 'shake', '', 'null', 'Idle', 'idle'], holdMs: 2500, fallback: 'wave',
    reset: { 'ParamAngleZ': 0, 'ParamMouthForm': 0, 'ParamMouthOpenY': 0, 'ParamEyeLOpen': 1, 'ParamEyeROpen': 1 } },
  { id: 'happy',     emoji: '😊', label: '开心',
    motions: ['Tap', 'tap_body', 'FlickHead', 'flick_head', '', 'null', 'Idle', 'idle'], holdMs: 2500, fallback: 'happy',
    reset: { 'ParamMouthForm': 0, 'ParamMouthOpenY': 0 } },
  { id: 'surprised', emoji: '😲', label: '惊讶',
    motions: ['PinchIn', 'pinch_in', 'Tap', 'tap_body', '', 'null', 'Idle', 'idle'], holdMs: 2000, fallback: 'surprised',
    reset: { 'ParamEyeLOpen': 1, 'ParamEyeROpen': 1, 'ParamEyeBallX': 0, 'ParamMouthOpenY': 0 } },
  { id: 'think',     emoji: '🤔', label: '思考',
    motions: ['TapBody', 'tap_body', 'Tap', '', 'null', 'Idle', 'idle'], holdMs: 2500, fallback: 'think',
    reset: { 'ParamEyeLOpen': 1, 'ParamEyeROpen': 1, 'ParamAngleX': 0, 'ParamAngleZ': 0 } },
  { id: 'shy',       emoji: '😳', label: '害羞',
    motions: ['FlickHead', 'flick_head', 'Shake', 'shake', '', 'null', 'Tap', 'tap_body', 'Idle', 'idle'], holdMs: 2500, fallback: 'shy',
    reset: { 'ParamEyeLOpen': 1, 'ParamEyeROpen': 1, 'ParamAngleZ': 0, 'ParamAngleX': 0 } },
]

const props = defineProps({
  /**
   * 数字人状态：
   * idle      — 空闲待机（呼吸/眨眼）
   * thinking  — 思考中（扶额/闭眼）
   * speaking  — 说话中（嘴型同步）
   * working   — 执行工具中（翻书/敲键盘）
   * error     — 出错了（摇头）
   */
  state: {
    type: String,
    default: 'idle',
  },
  /** 要朗读的文本（TTS），传空字符串则停止当前朗读 */
  speakText: {
    type: String,
    default: '',
  },
  /** 模型 URL，变化时重新加载 */
  modelUrl: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['ready', 'state-change'])

const containerRef = ref(null)
const canvasRef = ref(null)
const ttsEnabled = ref(false) // 默认关闭 TTS，用户点击开启
const statusText = ref('待机中')
// 互动按钮瞬时脉冲反馈（点击后让按钮弹跳一次，确保点击有视觉响应）
const btnPulse = reactive({})
const loading = ref(false)

let app = null
let model = null
const stateTimers = []

// 当前模型 URL（优先用 props，没有则用 localStorage 存的，再没有用默认）
function getCurrentModelUrl() {
  if (props.modelUrl) return props.modelUrl
  const saved = localStorage.getItem('hermes_model_url')
  if (saved) return saved
  return PRESET_MODELS[0].url
}

// 当前模型的元数据（含可用的 motion group 列表）
function getCurrentModelMeta() {
  const url = getCurrentModelUrl()
  return PRESET_MODELS.find(m => m.url === url) || PRESET_MODELS[0]
}

// 状态 → 中文描述
const STATE_LABELS = {
  idle: '待机中',
  thinking: '思考中',
  speaking: '回复中',
  working: '执行中',
  error: '出错了',
}

// ────────── Live2D 初始化 ──────────

async function loadLive2D() {
  try {
    // 提前识别模型版本（用于加载对应 runtime）
    const _earlyModelUrl = getCurrentModelUrl()
    const _earlyIsCubism2 = /\.model\.json(\?|$)/.test(_earlyModelUrl)

    // 1a) Cubism 4 运行时（本地 public 静态文件，避开外网 404）
    if (!_earlyIsCubism2 && !window.Live2DCubismCore) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script')
        script.src = '/live2dcubismcore.min.js'
        script.async = true
        script.onload = () => {
          console.log('[HermesAvatar] Cubism4 核心已加载（本地 public）')
          resolve()
        }
        script.onerror = () => reject(new Error('加载本地 live2dcubismcore.min.js 失败'))
        document.head.appendChild(script)
      })
    }

    // 1b) Cubism 2 运行时（本地 public 静态文件，129KB，Live2D Cubism 2.1 SDK）
    if (_earlyIsCubism2 && !window.Live2D) {
      await new Promise((resolve, reject) => {
        const script = document.createElement('script')
        script.src = '/live2d.min.js'
        script.async = true
        script.onload = () => {
          console.log('[HermesAvatar] Cubism 2.1 核心已加载（本地 public）')
          resolve()
        }
        script.onerror = () => reject(new Error('加载本地 live2d.min.js 失败（请确认 public/live2d.min.js 存在）'))
        document.head.appendChild(script)
      })
    }

    // 2) pixi.js@6 默认导出整个 namespace
    if (!PIXI) {
      const pixiModule = await import('pixi.js')
      PIXI = pixiModule.default || pixiModule
    }

    // 根据模型 URL 决定用 cubism4 还是 cubism2 入口
    const modelUrl = getCurrentModelUrl()
    const isCubism2 = /\.model\.json(\?|$)/.test(modelUrl)
    console.log('[HermesAvatar] 模型版本:', isCubism2 ? 'Cubism 2' : 'Cubism 4')

    // 切换模型时强制重新 import（避免从 Cubism4 切到 Cubism2 还用旧入口）
    const needKey = isCubism2 ? 'cubism2' : 'cubism4'
    if (window.__hermesCubismKey !== needKey) {
      window.__hermesCubismKey = needKey
      Live2DModel = null  // 触发下面重新 import
    }

    if (!Live2DModel) {
      // 让 Vite 静态分析两个入口，按需取用
      const entry = isCubism2
        ? await import('pixi-live2d-display/cubism2')
        : await import('pixi-live2d-display/cubism4')
      Live2DModel = entry.Live2DModel || entry.default
    }

    // 注册 PIXI 到 Live2D
    Live2DModel.registerTicker(PIXI.Ticker)

    // 如果已有 app，先销毁旧模型（必须先从 stage 移除，否则 PIXI 会在 stage 上残留旧 mesh 继续渲染）
    if (app) {
      try {
        app.stage.removeChildren()  // 清空整个 stage，包括旧 Live2D / 残影 / 兜底元素
      } catch {}
    }
    if (model) {
      try { model.destroy() } catch {}
      model = null
    }
    if (!app) {
      // 用外框实际尺寸初始化 canvas，避免后期被 CSS 拉伸
      // 注意：容器可能还没完全布局（avatar-panel 是 flex 容器），最多重试 3 次
      let rect = { width: 0, height: 0 }
      for (let i = 0; i < 5; i++) {
        rect = containerRef.value?.getBoundingClientRect() || rect
        if (rect.width >= 200 && rect.height >= 200) break
        await new Promise(r => setTimeout(r, 80))
        rect = containerRef.value?.getBoundingClientRect() || rect
      }
      const initW = Math.max(rect.width, 200)
      const initH = Math.max(rect.height, 200)
      console.log('[HermesAvatar] 初始化 canvas 尺寸:', initW, 'x', initH)
      app = new PIXI.Application({
        view: canvasRef.value,
        autoStart: true,
        backgroundAlpha: 0,
        width: initW,
        height: initH,
        antialias: true,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
      })
    }

    // 加载模型
    console.log('[HermesAvatar] 正在加载模型:', modelUrl)
    loading.value = true

    try {
      model = await Live2DModel.from(modelUrl, { autoInteract: true })
    } catch (e) {
      console.warn('[HermesAvatar] 模型加载失败:', e)
      // 退回到 haru 默认（共用已加载的 Live2DModel，不重复 import）
      const fallbackUrl = PRESET_MODELS[0].url
      if (fallbackUrl !== modelUrl) {
        console.log('[HermesAvatar] 尝试备用:', fallbackUrl)
        model = await Live2DModel.from(fallbackUrl, { autoInteract: true })
      } else {
        throw e
      }
    }

    // 打印模型的所有可用 motion 和参数（用于诊断）
    const internal = model.internalModel
    if (internal) {
      try {
        const motionNames = Object.keys(internal.motionManager?.definitions || internal.motionManager?._motions || {})
        console.log('[HermesAvatar] 模型 motion groups:', motionNames)
      } catch (e) {
        console.log('[HermesAvatar] 无法枚举 motion:', e?.message)
      }
    }

  // 缩放和定位 —— 居中偏下，整体完整显示，头部和脚部都可见
  const canvasW = app.renderer.width
  const canvasH = app.renderer.height

  const scale = Math.min(
    (canvasW / model.width) * 0.95,
    (canvasH / model.height) * 0.60
  )
  model.scale.set(scale)

  const scaledW = model.width * scale
  const scaledH = model.height * scale
  // 水平居中；垂直方向中心略偏下 20px，让模型在侧边栏里更靠上、避免脚被截断
  model.x = canvasW / 2
  model.y = canvasH / 2 + 20

  // 重置 anchor 到中心，确保缩放和居中一致
  if (model.anchor) {
    model.anchor.set(0.5, 0.5)
  }

  app.stage.addChild(model)

    // 启用自动眨眼和呼吸
    model.internalModel?.coreModel?.setParameterValueById?.('ParamBreath', 1)

    emit('ready', true)
    console.log('[HermesAvatar] Live2D 模型加载成功')
  } catch (e) {
    console.error('[HermesAvatar] Live2D 加载失败，使用降级模式', e)
    emit('ready', false)
  } finally {
    loading.value = false
  }
}

// ────────── 状态驱动表情/动作 ──────────

function clearTimers() {
  stateTimers.forEach(t => { clearTimeout(t); clearInterval(t) })
  stateTimers.length = 0
}

function setModelParam(param, value) {
  if (!model?.internalModel?.coreModel) return
  try {
    model.internalModel.coreModel.setParameterValueById(param, value)
  } catch {
    // 参数不存在时忽略
  }
}

function playMotion(group, index = 0) {
  if (!model) return
  try {
    model.motion(group, index)
  } catch {
    // motion 不存在时忽略
  }
}

function applyState(state) {
  if (!model) return
  clearTimers()
  statusText.value = STATE_LABELS[state] || state
  emit('state-change', state)

  switch (state) {
    case 'idle':
      setModelParam('ParamEyeLOpen', 1)
      setModelParam('ParamEyeROpen', 1)
      setModelParam('ParamMouthOpenY', 0)
      playMotion('Idle', 0)
      break

    case 'thinking':
      setModelParam('ParamEyeLOpen', 0.3)
      setModelParam('ParamEyeROpen', 0.3)
      setModelParam('ParamAngleZ', 5)
      playMotion('TapBody', 0)
      break

    case 'speaking':
      setModelParam('ParamEyeLOpen', 1)
      setModelParam('ParamEyeROpen', 1)
      // 随机微动头
      const headSway = setInterval(() => {
        if (!model) return
        setModelParam('ParamAngleX', (Math.random() - 0.5) * 10)
        setModelParam('ParamAngleY', (Math.random() - 0.5) * 8)
      }, 2000)
      stateTimers.push(headSway)
      break

    case 'working':
      setModelParam('ParamAngleY', 10)
      setModelParam('ParamEyeLOpen', 0.7)
      setModelParam('ParamEyeROpen', 0.7)
      break

    case 'error':
      let shakeCount = 0
      const shake = setInterval(() => {
        if (!model || shakeCount >= 4) {
          clearInterval(shake)
          setModelParam('ParamAngleZ', 0)
          return
        }
        setModelParam('ParamAngleZ', shakeCount % 2 === 0 ? -8 : 8)
        shakeCount++
      }, 200)
      stateTimers.push(shake)
      break
  }
}

// ────────── 互动：点击模型 + 互动按钮 ──────────

function onCanvasClick() {
  // 点击画布时随机播放一个动作（兼容 Cubism 4 / 2 多套命名）
  // 注：表情互动按钮已下线，点击仅触发动作、不再弹表情提示
  const meta = getCurrentModelMeta()
  const motions = meta.motions || []
  if (motions.length === 0) return
  const random = motions[Math.floor(Math.random() * motions.length)]
  playMotion(random, 0)
}

function triggerInteract(btn) {
  // 即时视觉反馈：按钮立刻 pulse（无论模型是否就绪，点击都有响应）
  btnPulse[btn.id] = true
  setTimeout(() => { btnPulse[btn.id] = false }, 600)

  if (!model) {
    console.log('[HermesAvatar] 模型未就绪，互动按钮无反应')
    return
  }

  // 用当前模型的 hardcoded motion 列表 + 按钮优先级匹配
  const meta = getCurrentModelMeta()
  const availableGroups = meta.motions || []
  if (btn.motions && availableGroups.length > 0) {
    for (const m of btn.motions) {
      if (availableGroups.includes(m)) {
        try {
          model.motion(m, 0)
          console.log(`[HermesAvatar] 互动: ${btn.id} → 播放 motion [${m}]`)
          break
        } catch (e) {
          console.warn(`[HermesAvatar] motion(${m}) 失败:`, e?.message)
        }
      }
    }
  }

  // 兜底：设置表情参数（让用户立即看到反馈，无论 motion 是否播放成功）
  applyExpression(btn.fallback)

  // holdMs 后恢复（只 reset 本按钮改过的参数）
  if (btn.holdMs && btn.reset) {
    setTimeout(() => {
      // 只在 idle 状态下 reset（避免覆盖 thinking/working 等状态机的设置）
      if (props.state === 'idle') {
        for (const [p, v] of Object.entries(btn.reset)) {
          setModelParam(p, v)
        }
      }
    }, btn.holdMs)
  }
}

// 设置表情参数（fallback 方案，确保眼睛/嘴型/头部有明显反馈）
function applyExpression(fallback) {
  if (!fallback) return
  // 参数值范围统一在 -1~1 之间（Cubism 4 多数参数范围）
  // eye open: 0=闭眼 1=全开 嘴 open: 0=闭 ~1=大张
  switch (fallback) {
    case 'happy':
      setModelParam('ParamEyeLOpen', 1)
      setModelParam('ParamEyeROpen', 1)
      setModelParam('ParamMouthForm', 1)    // 笑（笑脸嘴型）
      setModelParam('ParamMouthOpenY', 0.2) // 微张
      break
    case 'surprised':
      setModelParam('ParamEyeLOpen', 1.5)
      setModelParam('ParamEyeROpen', 1.5)
      setModelParam('ParamEyeBallX', 0)
      setModelParam('ParamMouthOpenY', 1.0)  // 大张
      break
    case 'think':
      setModelParam('ParamEyeLOpen', 0.4)
      setModelParam('ParamEyeROpen', 0.6)    // 不对称更像思考
      setModelParam('ParamAngleX', 8)        // 侧头
      setModelParam('ParamAngleZ', 5)
      break
    case 'shy':
      setModelParam('ParamEyeLOpen', 0.5)
      setModelParam('ParamEyeROpen', 0.5)
      setModelParam('ParamAngleZ', -10)      // 歪头
      setModelParam('ParamAngleX', -3)
      break
    case 'wave':
      setModelParam('ParamAngleZ', 8)        // 歪头打招呼
      setModelParam('ParamMouthForm', 1)
      setModelParam('ParamEyeLOpen', 1)
      setModelParam('ParamEyeROpen', 1)
      break
  }
}

// ────────── TTS 语音合成 ──────────

let currentUtterance = null

function speak(text) {
  if (!ttsEnabled.value || !text) {
    stopSpeak()
    return
  }

  stopSpeak()

  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = 'zh-CN'
  utterance.rate = 1.0
  utterance.pitch = 1.0

  // 嘴型同步
  utterance.onboundary = () => {
    if (!model) return
    setModelParam('ParamMouthOpenY', Math.random() * 0.8 + 0.2)
    setTimeout(() => {
      setModelParam('ParamMouthOpenY', 0.1)
    }, 80)
  }

  utterance.onend = () => {
    setModelParam('ParamMouthOpenY', 0)
    currentUtterance = null
  }

  currentUtterance = utterance
  window.speechSynthesis.speak(utterance)
}

function stopSpeak() {
  if (window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
  setModelParam('ParamMouthOpenY', 0)
  currentUtterance = null
}

// ────────── 生命周期 ──────────

let resizeObserver = null
function onResize() {
  if (!app || !containerRef.value || !model) return
  const rect = containerRef.value.getBoundingClientRect()
  const w = Math.max(rect.width, 100)
  const h = Math.max(rect.height, 100)
  app.renderer.resize(w, h)
  // 重新按 contain 比例居中，整体完整显示
  const scale = Math.min(
    (w / model.width) * 0.95,
    (h / model.height) * 0.60
  )
  model.scale.set(scale)
  const scaledW = model.width * scale
  const scaledH = model.height * scale
  model.x = w / 2
  model.y = h / 2 + 20
}

onMounted(() => {
  loadLive2D()
  // 监听外框尺寸变化（窗口缩放、面板折叠等）
  if (window.ResizeObserver && containerRef.value) {
    resizeObserver = new ResizeObserver(onResize)
    resizeObserver.observe(containerRef.value)
  } else {
    window.addEventListener('resize', onResize)
  }
})

onBeforeUnmount(() => {
  clearTimers()
  stopSpeak()
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  } else {
    window.removeEventListener('resize', onResize)
  }
  if (model) {
    try { model.destroy() } catch {}
  }
  if (app) {
    try { app.destroy(true) } catch {}
  }
})

// 监听状态变化
watch(() => props.state, (newState) => {
  applyState(newState)
})

// 监听说话文本
watch(() => props.speakText, (text) => {
  if (text) {
    speak(text)
  } else {
    stopSpeak()
  }
})

// 监听 TTS 开关
watch(ttsEnabled, (enabled) => {
  if (!enabled) stopSpeak()
})

// 监听模型 URL 变化，重新加载
watch(() => props.modelUrl, (newUrl, oldUrl) => {
  if (newUrl && newUrl !== oldUrl) {
    console.log('[HermesAvatar] 模型 URL 变化，重新加载:', newUrl)
    loadLive2D()
  }
})

// 暴露方法给父组件
defineExpose({
  triggerInteract,
  playMotion,
  setModelParam,
})
</script>

<style scoped>
.hermes-avatar {
  position: relative;
  width: 100%;
  height: 100%;
  flex: 1;             /* 在父级 flex column 中撑满剩余高度（避开顶栏选择器） */
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.hermes-avatar canvas {
  /* 关键：模型按原比例居中显示，不被外框拉伸 */
  max-width: 100%;
  max-height: 100%;
  width: auto !important;
  height: auto !important;
  cursor: pointer;
  display: block;
}

/* 加载中遮罩 */
.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(2px);
  color: #fff;
  font-size: 13px;
  z-index: 4;
  pointer-events: none;
}
.loading-spinner {
  width: 28px;
  height: 28px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: #67c23a;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 状态指示器 */
.status-badge {
  position: absolute;
  bottom: 56px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 12px;
  color: #fff;
  backdrop-filter: blur(4px);
  background: rgba(0, 0, 0, 0.4);
  transition: background 0.3s;
  white-space: nowrap;
  z-index: 2;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #909399;
  animation: pulse 2s ease-in-out infinite;
}
.status-badge.idle .status-dot { background: #67c23a; }
.status-badge.thinking { background: rgba(64, 158, 255, 0.6); }
.status-badge.thinking .status-dot { background: #409eff; }
.status-badge.speaking { background: rgba(103, 194, 58, 0.6); }
.status-badge.speaking .status-dot { background: #67c23a; }
.status-badge.working { background: rgba(230, 162, 60, 0.6); }
.status-badge.working .status-dot { background: #e6a23c; }
.status-badge.error { background: rgba(245, 108, 108, 0.6); }
.status-badge.error .status-dot { background: #f56c6c; }

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.85); }
}

/* TTS 开关按钮 */
.tts-toggle {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  background: rgba(0, 0, 0, 0.3);
  color: #c0c4cc;
  font-size: 16px;
  transition: all 0.2s;
  z-index: 3;
}
.tts-toggle:hover {
  background: rgba(0, 0, 0, 0.5);
  transform: scale(1.1);
}
.tts-toggle .active {
  color: #67c23a;
}
</style>

<!-- 预置数据：必须放普通 script 块，<script setup> 不支持 export -->
<script>
// ────────── 预置模型列表（本地 public 资源，不依赖外网） ──────────
// modelUrl 末尾是 .model3.json 的用 Cubism 4，.model.json 的用 Cubism 2（自动判断）
// motions: 该模型实际可用的 motion group 名（用于互动按钮的优先级匹配）
export const PRESET_MODELS = [
  { id: 'haru',    name: '🌸 Haru·问好',     url: '/live2d/haru/haru_greeter_t03.model3.json',
    motions: ['Idle', 'Tap', 'FlickHead', 'TapBody'] },
  { id: 'shizuku', name: '💧 Shizuku·滴',    url: '/live2d/shizuku/shizuku.model.json',
    motions: ['idle', 'tap_body', 'flick_head', 'shake', 'pinch_in', 'pinch_out'] },
  { id: 'koharu',  name: '🌺 Koharu·小春',   url: '/live2d/koharu/koharu.model.json',
    motions: ['idle', ''] },
  { id: 'izumi',   name: '🌊 Izumi·泉',      url: '/live2d/izumi/izumi.model.json',
    motions: ['idle', 'null'] },
]

// ────────── 预置背景主题 ──────────
export const BG_THEMES = [
  { id: 'deepblue', name: '深夜蓝', gradient: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)' },
  { id: 'purple',   name: '星空紫', gradient: 'linear-gradient(180deg, #1a0a2e 0%, #3d1a5e 50%, #5b2a86 100%)' },
  { id: 'aurora',   name: '极光绿', gradient: 'linear-gradient(180deg, #0a1a1a 0%, #0d3b3b 50%, #1a5c4a 100%)' },
  { id: 'sunset',   name: '日落橙', gradient: 'linear-gradient(180deg, #2e1a0a 0%, #5e3a1a 50%, #8b5a2b 100%)' },
  { id: 'sakura',   name: '樱花粉', gradient: 'linear-gradient(180deg, #2e1a1e 0%, #5e2a3e 50%, #8b4a6a 100%)' },
  { id: 'dark',     name: '纯黑',   gradient: '#0a0a0a' },
]
</script>
