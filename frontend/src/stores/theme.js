import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/utils/api'
import { SKINS, DEFAULT_PRIMARY, findSkin } from '@/theme/skins'

const STORAGE_KEY = 'testhub_ui_settings'

function hexToRgb(hex) {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const num = parseInt(full, 16)
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255]
}

function mix(hex, target, weight) {
  const [r1, g1, b1] = hexToRgb(hex)
  const [r2, g2, b2] = hexToRgb(target)
  const r = Math.round(r1 * (1 - weight) + r2 * weight)
  const g = Math.round(g1 * (1 - weight) + r2 * weight)
  const b = Math.round(b1 * (1 - weight) + b2 * weight)
  return `rgb(${r}, ${g}, ${b})`
}

// 计算 Element Plus 需要的主题色阶
function computeShades(hex) {
  return {
    '--el-color-primary-light-3': mix(hex, '#ffffff', 0.3),
    '--el-color-primary-light-5': mix(hex, '#ffffff', 0.5),
    '--el-color-primary-light-7': mix(hex, '#ffffff', 0.7),
    '--el-color-primary-light-8': mix(hex, '#ffffff', 0.8),
    '--el-color-primary-light-9': mix(hex, '#ffffff', 0.9),
    '--el-color-primary-dark-2': mix(hex, '#000000', 0.2),
  }
}

function isGradient(v) {
  return /^(linear|radial|conic)-gradient/.test(v || '')
}

// 面板与壁纸默认参数
const DEFAULT_MODE = 'light'
const DEFAULT_PANEL_OPACITY = 0.78
const DEFAULT_PANEL_BLUR = 12
const DEFAULT_WALLPAPER_DIM = 0.12
const DEFAULT_HERMES_AVATAR = true
const DEFAULT_HERMES_EYE = true
const DEFAULT_HERMES_EYE_STYLE = 'warrior'

// Hermes 眼睛风格可选值
export const HERMES_EYE_STYLES = [
  { value: 'warrior', label: '战斗眼（橙红）' },
  { value: 'gundam', label: '高达（红）' },
  { value: 'awaken', label: '觉醒之眼（黄）' },
  { value: 'ironman', label: '钢铁侠（蓝）' },
  { value: 'hud', label: '科技 HUD（青）' },
]

export const useThemeStore = defineStore('theme', () => {
  const mode = ref(DEFAULT_MODE) // light | dark
  const primary = ref(DEFAULT_PRIMARY)
  const skin = ref('')
  const wallpaper = ref('') // 最终背景值：图片URL 或 CSS 渐变 或 空

  // 玻璃面板 / 壁纸显示参数
  const panelOpacity = ref(DEFAULT_PANEL_OPACITY)
  const panelBlur = ref(DEFAULT_PANEL_BLUR)
  const wallpaperDim = ref(DEFAULT_WALLPAPER_DIM)
  const transparentMode = ref(false)

  // 是否启用 Hermes 虚拟形象（眼睛表头助手）
  const hermesAvatarEnabled = ref(DEFAULT_HERMES_AVATAR)

  // 是否启用 Hermes 表头眼睛特效（可独立于助手总开关）
  const hermesEyeEnabled = ref(DEFAULT_HERMES_EYE)

  // Hermes 眼睛风格：warrior | gundam | awaken | ironman | hud
  const hermesEyeStyle = ref(DEFAULT_HERMES_EYE_STYLE)

  // 临时记忆「直接显示壁纸」关闭前的用户自定义值
  let lastCustomOpacity = DEFAULT_PANEL_OPACITY
  let lastCustomBlur = DEFAULT_PANEL_BLUR
  let lastCustomDim = DEFAULT_WALLPAPER_DIM

  function loadLocal() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const o = JSON.parse(raw)
      mode.value = o.mode || DEFAULT_MODE
      primary.value = o.primary || DEFAULT_PRIMARY
      skin.value = o.skin || ''
      wallpaper.value = o.wallpaper || ''
      panelOpacity.value = typeof o.panelOpacity === 'number' ? o.panelOpacity : DEFAULT_PANEL_OPACITY
      panelBlur.value = typeof o.panelBlur === 'number' ? o.panelBlur : DEFAULT_PANEL_BLUR
      wallpaperDim.value = typeof o.wallpaperDim === 'number' ? o.wallpaperDim : DEFAULT_WALLPAPER_DIM
      transparentMode.value = !!o.transparentMode
      hermesAvatarEnabled.value = o.hermesAvatarEnabled !== undefined ? !!o.hermesAvatarEnabled : DEFAULT_HERMES_AVATAR
      hermesEyeEnabled.value = o.hermesEyeEnabled !== undefined ? !!o.hermesEyeEnabled : DEFAULT_HERMES_EYE
      hermesEyeStyle.value = o.hermesEyeStyle && typeof o.hermesEyeStyle === 'string' ? o.hermesEyeStyle : DEFAULT_HERMES_EYE_STYLE
      if (transparentMode.value) {
        lastCustomOpacity = typeof o.lastCustomOpacity === 'number' ? o.lastCustomOpacity : DEFAULT_PANEL_OPACITY
        lastCustomBlur = typeof o.lastCustomBlur === 'number' ? o.lastCustomBlur : DEFAULT_PANEL_BLUR
        lastCustomDim = typeof o.lastCustomDim === 'number' ? o.lastCustomDim : DEFAULT_WALLPAPER_DIM
      }
    } catch (e) {
      /* ignore */
    }
  }

  function persist() {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        mode: mode.value,
        primary: primary.value,
        skin: skin.value,
        wallpaper: wallpaper.value,
        panelOpacity: panelOpacity.value,
        panelBlur: panelBlur.value,
        wallpaperDim: wallpaperDim.value,
        transparentMode: transparentMode.value,
        hermesAvatarEnabled: hermesAvatarEnabled.value,
        hermesEyeEnabled: hermesEyeEnabled.value,
        hermesEyeStyle: hermesEyeStyle.value,
        lastCustomOpacity,
        lastCustomBlur,
        lastCustomDim,
      })
    )
  }

  // 将当前主题应用到 DOM（Element Plus 变量 + body 背景 + 玻璃面板）
  function applyTheme() {
    const root = document.documentElement
    const dark = mode.value === 'dark'
    root.classList.toggle('theme-dark', dark)
    root.classList.toggle('theme-light', !dark)
    // 同时触发 Element Plus 官方暗色变量
    root.classList.toggle('dark', dark)

    // 主题色
    root.style.setProperty('--el-color-primary', primary.value)
    const shades = computeShades(primary.value)
    Object.entries(shades).forEach(([k, v]) => root.style.setProperty(k, v))

    // 背景
    const wp = wallpaper.value
    let image = ''
    if (wp) image = isGradient(wp) ? wp : `url("${wp}")`
    document.body.style.backgroundImage = image
    document.body.style.backgroundSize = 'cover'
    document.body.style.backgroundRepeat = 'no-repeat'
    document.body.style.backgroundAttachment = 'fixed'
    document.body.style.backgroundPosition = 'center'
    document.body.style.backgroundColor = dark ? '#141414' : '#f5f7fa'

    // 玻璃面板变量
    const opacity = panelOpacity.value
    const blur = panelBlur.value
    root.style.setProperty('--app-panel-opacity', opacity)
    root.style.setProperty('--app-panel-blur', `${blur}px`)
    root.style.setProperty('--app-wallpaper-dim', wallpaperDim.value)

    const cardRgb = dark ? '29,29,31' : '255,255,255'
    const mainRgb = dark ? '28,28,30' : '245,247,250'
    root.style.setProperty('--app-card-bg', `rgba(${cardRgb}, ${opacity})`)
    root.style.setProperty('--app-bg-soft', `rgba(${mainRgb}, ${opacity})`)
    root.style.setProperty('--app-border', dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)')
    root.style.setProperty('--app-text', dark ? '#e5eaf3' : '#303133')
    root.style.setProperty('--app-text-secondary', dark ? '#a8abb2' : '#909399')

    // 侧边栏跟随主题色（深色基调 + 主题色倾向）
    const sidebarBase = dark ? '#000000' : '#000000'
    root.style.setProperty('--app-sidebar-bg', mix(primary.value, sidebarBase, 0.28))
    root.style.setProperty('--app-sidebar-bg-hover', mix(primary.value, sidebarBase, 0.38))
    root.style.setProperty('--app-sidebar-text', '#ffffff')
    root.style.setProperty('--app-sidebar-active', primary.value)
  }

  async function initTheme() {
    loadLocal()
    applyTheme()
    // 后端覆盖（登录用户）
    try {
      const { data } = await api.get('/users/ui-settings/')
      if (data && typeof data === 'object') {
        mode.value = data.mode || mode.value
        primary.value = data.primary || primary.value
        skin.value = data.skin || skin.value
        wallpaper.value = data.wallpaper || wallpaper.value
        panelOpacity.value = typeof data.panelOpacity === 'number' ? data.panelOpacity : panelOpacity.value
        panelBlur.value = typeof data.panelBlur === 'number' ? data.panelBlur : panelBlur.value
        wallpaperDim.value = typeof data.wallpaperDim === 'number' ? data.wallpaperDim : wallpaperDim.value
        transparentMode.value = !!data.transparentMode
        if (data.hermes_avatar_enabled !== undefined) {
          hermesAvatarEnabled.value = !!data.hermes_avatar_enabled
        }
        if (data.hermes_eye_enabled !== undefined) {
          hermesEyeEnabled.value = !!data.hermes_eye_enabled
        }
        if (data.hermes_eye_style && typeof data.hermes_eye_style === 'string') {
          hermesEyeStyle.value = data.hermes_eye_style
        }
        applyTheme()
      }
    } catch (e) {
      /* 未登录或失败，使用本地缓存 */
    }
  }

  async function save() {
    persist()
    applyTheme()
    try {
      await api.patch('/users/ui-settings/', {
        mode: mode.value,
        primary: primary.value,
        skin: skin.value,
        wallpaper: wallpaper.value,
        panelOpacity: panelOpacity.value,
        panelBlur: panelBlur.value,
        wallpaperDim: wallpaperDim.value,
        transparentMode: transparentMode.value,
        hermes_avatar_enabled: hermesAvatarEnabled.value,
        hermes_eye_enabled: hermesEyeEnabled.value,
        hermes_eye_style: hermesEyeStyle.value,
      })
    } catch (e) {
      /* 离线也可本地生效 */
    }
  }

  // 选择一个皮肤预设
  function setSkin(skinObj) {
    if (!skinObj) return
    skin.value = skinObj.id
    if (skinObj.type === 'gradient') wallpaper.value = skinObj.value || ''
    else if (skinObj.type === 'image') wallpaper.value = skinObj.url || ''
    else wallpaper.value = '' // none
    save()
  }

  // 应用任意背景值（上传自定义壁纸后）
  function setCustomWallpaper(url) {
    skin.value = 'custom'
    wallpaper.value = url
    save()
  }

  function setMode(m) {
    mode.value = m
    save()
  }

  function setPrimary(color) {
    primary.value = color
    save()
  }

  function setPanelOpacity(v) {
    panelOpacity.value = v
    if (!transparentMode.value) lastCustomOpacity = v
    persist()
    applyTheme()
  }

  function setPanelBlur(v) {
    panelBlur.value = v
    if (!transparentMode.value) lastCustomBlur = v
    persist()
    applyTheme()
  }

  function setWallpaperDim(v) {
    wallpaperDim.value = v
    if (!transparentMode.value) lastCustomDim = v
    persist()
    applyTheme()
  }

  function setTransparentMode(v) {
    transparentMode.value = v
    if (v) {
      // 进入「直接显示壁纸」模式：记录当前自定义值后切换为极低透明+高模糊+高暗角
      lastCustomOpacity = panelOpacity.value
      lastCustomBlur = panelBlur.value
      lastCustomDim = wallpaperDim.value
      panelOpacity.value = 0.10
      panelBlur.value = 24
      wallpaperDim.value = 0.45
    } else {
      // 退出时恢复用户之前的自定义值
      panelOpacity.value = lastCustomOpacity
      panelBlur.value = lastCustomBlur
      wallpaperDim.value = lastCustomDim
    }
    persist()
    applyTheme()
  }

  function setHermesAvatarEnabled(v) {
    hermesAvatarEnabled.value = !!v
    save()
  }

  function setHermesEyeEnabled(v) {
    hermesEyeEnabled.value = !!v
    save()
  }

  function setHermesEyeStyle(v) {
    hermesEyeStyle.value = v || DEFAULT_HERMES_EYE_STYLE
    save()
  }

  function reset() {
    mode.value = DEFAULT_MODE
    primary.value = DEFAULT_PRIMARY
    skin.value = ''
    wallpaper.value = ''
    panelOpacity.value = DEFAULT_PANEL_OPACITY
    panelBlur.value = DEFAULT_PANEL_BLUR
    wallpaperDim.value = DEFAULT_WALLPAPER_DIM
    transparentMode.value = false
    lastCustomOpacity = DEFAULT_PANEL_OPACITY
    lastCustomBlur = DEFAULT_PANEL_BLUR
    lastCustomDim = DEFAULT_WALLPAPER_DIM
    save()
  }

  return {
    mode,
    primary,
    skin,
    wallpaper,
    panelOpacity,
    panelBlur,
    wallpaperDim,
    transparentMode,
    hermesAvatarEnabled,
    hermesEyeEnabled,
    hermesEyeStyle,
    setHermesAvatarEnabled,
    setHermesEyeEnabled,
    setHermesEyeStyle,
    initTheme,
    applyTheme,
    save,
    setSkin,
    setCustomWallpaper,
    setMode,
    setPrimary,
    setPanelOpacity,
    setPanelBlur,
    setWallpaperDim,
    setTransparentMode,
    reset,
    findSkin,
    isGradient,
  }
})
