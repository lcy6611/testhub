<template>
  <div class="appearance-page">
    <div class="page-container">
      <div class="page-header">
        <div class="page-title">外观与皮肤设置</div>
        <div>
          <el-button @click="onReset">恢复默认</el-button>
          <el-button type="primary" @click="onSave">保存设置</el-button>
        </div>
      </div>

      <!-- 实时预览 -->
      <el-card class="preview-card" :body-style="{ padding: '0' }">
        <div class="preview-box" :style="previewStyle">
          <div class="preview-bar">
            <span class="preview-dot"></span>
            <span class="preview-dot"></span>
            <span class="preview-dot"></span>
            <span class="preview-title">TestHub</span>
          </div>
          <div class="preview-content">
            <el-button type="primary" size="small">主按钮</el-button>
            <el-button size="small">次按钮</el-button>
            <span class="preview-text">主题模式：{{ themeStore.mode === 'dark' ? '暗色' : '亮色' }} ｜ 主题色：{{ themeStore.primary }}</span>
          </div>
        </div>
      </el-card>

      <!-- 首页标题自定义 -->
      <el-card class="block-card home-title-card">
        <template #header>
          <div class="skin-header">
            <span>首页标题</span>
            <el-button size="small" @click="onResetHomeTitle">恢复默认文案</el-button>
          </div>
        </template>

        <div class="effect-row">
          <div class="effect-label">主标题</div>
          <el-input
            v-model="homeTitleDraft"
            maxlength="40"
            show-word-limit
            clearable
            placeholder="留空则首页不显示主标题"
            @change="commitHomeTitle"
            @clear="commitHomeTitle"
          />
        </div>

        <div class="effect-row">
          <div class="effect-label">副标题</div>
          <el-input
            v-model="homeSubtitleDraft"
            maxlength="60"
            show-word-limit
            clearable
            placeholder="留空则首页不显示副标题"
            @change="commitHomeSubtitle"
            @clear="commitHomeSubtitle"
          />
        </div>

        <div class="home-title-hint">
          <span class="hint-label">首页预览：</span>
          <div class="hint-preview">
            <div class="hint-h1">{{ homeTitleDraft || '（不显示主标题）' }}</div>
            <div class="hint-p2">{{ homeSubtitleDraft || '（不显示副标题）' }}</div>
          </div>
        </div>
        <div class="hint-tip">输入后按回车或点击别处即生效；留空表示首页不展示该行。</div>
      </el-card>

      <el-row :gutter="20">
        <!-- 主题模式 + 主题色 -->
        <el-col :span="8">
          <el-card class="block-card">
            <template #header>主题模式</template>
            <el-radio-group :model-value="themeStore.mode" @change="onModeChange">
              <el-radio-button label="light">☀️ 亮色</el-radio-button>
              <el-radio-button label="dark">🌙 暗色</el-radio-button>
            </el-radio-group>

            <div class="block-title">主题色</div>
            <div class="color-grid">
              <div
                v-for="c in primaryPresets"
                :key="c"
                class="color-dot"
                :style="{ background: c }"
                :class="{ active: themeStore.primary.toLowerCase() === c.toLowerCase() }"
                @click="onPrimary(c)"
              ></div>
            </div>
            <div class="color-picker-row">
              <span class="color-picker-label">自定义：</span>
              <el-color-picker :model-value="themeStore.primary" @change="onPrimary" />
            </div>
          </el-card>
        </el-col>

        <!-- 皮肤 / 壁纸 -->
        <el-col :span="16">
          <el-card class="block-card">
            <template #header>
              <div class="skin-header">
                <span>皮肤 / 壁纸</span>
                <el-upload
                  class="upload-btn"
                  :http-request="handleUpload"
                  :show-file-list="false"
                  accept="image/*"
                >
                  <el-button size="small" type="primary" plain>上传自定义壁纸</el-button>
                </el-upload>
              </div>
            </template>

            <el-tabs v-model="activeCat">
              <el-tab-pane label="全部" name="all" />
              <el-tab-pane
                v-for="cat in SKIN_CATEGORIES"
                :key="cat.key"
                :label="cat.icon + ' ' + cat.name"
                :name="cat.key"
              />
            </el-tabs>

            <div class="skin-grid">
              <div
                v-for="s in filteredSkins"
                :key="s.id"
                class="skin-card"
                :class="{ active: themeStore.skin === s.id }"
                @click="selectSkin(s)"
              >
                <div class="skin-thumb" :style="thumbStyle(s)">
                  <span v-if="s.type === 'none'" class="skin-none">纯色</span>
                  <span v-if="themeStore.skin === s.id" class="skin-check">✓</span>
                </div>
                <div class="skin-name">{{ s.name }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 壁纸显示效果 -->
      <el-row :gutter="20" style="margin-top: 20px;">
        <el-col :span="24">
          <el-card class="block-card">
            <template #header>
              <div class="skin-header">
                <span>壁纸显示效果</span>
                <el-switch
                  :model-value="themeStore.transparentMode"
                  active-text="直接显示壁纸"
                  inactive-text="正常面板"
                  @input="onTransparentMode"
                  @change="onTransparentMode"
                />
              </div>
            </template>

            <div class="effect-row">
              <div class="effect-label">面板透明度</div>
              <el-slider
                :model-value="themeStore.panelOpacity"
                :min="0"
                :max="1"
                :step="0.01"
                style="flex: 1;"
                @input="onOpacityChange"
                @change="onOpacityChange"
              />
              <el-input-number
                :model-value="themeStore.panelOpacity"
                :min="0"
                :max="1"
                :step="0.01"
                :precision="2"
                size="small"
                style="width: 90px; margin-left: 12px;"
                @input="onOpacityChange"
                @change="onOpacityChange"
              />
            </div>

            <div class="effect-row">
              <div class="effect-label">面板模糊</div>
              <el-slider
                :model-value="themeStore.panelBlur"
                :min="0"
                :max="30"
                :step="1"
                style="flex: 1;"
                @input="onBlurChange"
                @change="onBlurChange"
              />
              <span class="effect-unit">{{ themeStore.panelBlur }}px</span>
            </div>

            <div class="effect-row">
              <div class="effect-label">壁纸暗角</div>
              <el-slider
                :model-value="themeStore.wallpaperDim"
                :min="0"
                :max="0.8"
                :step="0.01"
                style="flex: 1;"
                @input="onDimChange"
                @change="onDimChange"
              />
              <el-input-number
                :model-value="themeStore.wallpaperDim"
                :min="0"
                :max="0.8"
                :step="0.01"
                :precision="2"
                size="small"
                style="width: 90px; margin-left: 12px;"
                @input="onDimChange"
                @change="onDimChange"
              />
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { DEFAULT_HOME_SUBTITLE, DEFAULT_HOME_TITLE, useThemeStore } from '@/stores/theme'
import { SKIN_CATEGORIES, SKINS } from '@/theme/skins'
import { uploadWallpaper } from '@/api/users'

const themeStore = useThemeStore()
const activeCat = ref('all')

// 首页标题：用本地草案编辑，失焦/回车再提交，避免每敲一个字就打一次接口
const homeTitleDraft = ref(themeStore.homeTitle)
const homeSubtitleDraft = ref(themeStore.homeSubtitle)
watch(() => themeStore.homeTitle, (v) => { homeTitleDraft.value = v })
watch(() => themeStore.homeSubtitle, (v) => { homeSubtitleDraft.value = v })

function commitHomeTitle() {
  themeStore.setHomeTitle((homeTitleDraft.value || '').trim())
}
function commitHomeSubtitle() {
  themeStore.setHomeSubtitle((homeSubtitleDraft.value || '').trim())
}
function onResetHomeTitle() {
  themeStore.setHomeTitle(DEFAULT_HOME_TITLE)
  themeStore.setHomeSubtitle(DEFAULT_HOME_SUBTITLE)
  ElMessage.success('首页标题已恢复默认')
}

const primaryPresets = [
  '#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#9b59b6',
  '#1abc9c', '#34495e', '#ff7a45', '#722ed1', '#13c2c2',
]

const filteredSkins = computed(() => {
  if (activeCat.value === 'all') return SKINS
  return SKINS.filter((s) => s.category === activeCat.value)
})

function thumbStyle(s) {
  if (s.type === 'image') {
    return {
      backgroundImage: `url("${s.url}")`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    }
  }
  if (s.type === 'gradient') return { background: s.value }
  return { background: 'linear-gradient(135deg, #e0eafc 0%, #cfdef3 100%)' }
}

const previewStyle = computed(() => {
  const wp = themeStore.wallpaper
  if (!wp) {
    return { background: themeStore.mode === 'dark' ? '#1d1e1f' : '#f5f7fa' }
  }
  return {
    backgroundImage: themeStore.isGradient(wp) ? wp : `url("${wp}")`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
  }
})

function onModeChange(v) {
  themeStore.setMode(v)
}
function onPrimary(c) {
  if (c) themeStore.setPrimary(c)
}
function selectSkin(s) {
  themeStore.setSkin(s)
}
function onOpacityChange(v) {
  if (v === undefined || v === null) return
  themeStore.setPanelOpacity(v)
}
function onBlurChange(v) {
  if (v === undefined || v === null) return
  themeStore.setPanelBlur(v)
}
function onDimChange(v) {
  if (v === undefined || v === null) return
  themeStore.setWallpaperDim(v)
}
function onTransparentMode(v) {
  themeStore.setTransparentMode(v)
}
function onSave() {
  themeStore.save()
  ElMessage.success('外观设置已保存')
}
function onReset() {
  themeStore.reset()
  ElMessage.success('已恢复默认外观')
}

async function handleUpload(option) {
  const fd = new FormData()
  fd.append('file', option.file)
  try {
    const { data } = await uploadWallpaper(fd)
    themeStore.setCustomWallpaper(data.url)
    ElMessage.success('自定义壁纸已应用')
    option.onSuccess()
  } catch (e) {
    ElMessage.error('上传失败，请重试')
    option.onError(e)
  }
}
</script>

<style lang="scss" scoped>
.preview-card {
  margin-bottom: 20px;
}

.preview-box {
  height: 170px;
  padding: 16px;
  color: #fff;
  position: relative;
  overflow: hidden;

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.25);
  }
}

.preview-bar {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: 6px;

  .preview-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.8);
  }

  .preview-title {
    margin-left: 8px;
    font-weight: 600;
  }
}

.preview-content {
  position: relative;
  z-index: 2;
  margin-top: 40px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;

  .preview-text {
    text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5);
    font-size: 13px;
  }
}

.block-title {
  margin: 18px 0 10px;
  font-weight: 600;
  color: var(--app-text, #303133);
}

.color-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;

  .color-dot {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    cursor: pointer;
    border: 2px solid transparent;
    transition: transform 0.15s;

    &:hover {
      transform: scale(1.1);
    }

    &.active {
      border-color: var(--el-text-color-primary);
      box-shadow: 0 0 0 2px var(--el-bg-color), 0 0 0 4px currentColor;
    }
  }
}

.color-picker-row {
  margin-top: 14px;
  display: flex;
  align-items: center;

  .color-picker-label {
    font-size: 13px;
    color: var(--app-text-secondary, #909399);
    margin-right: 8px;
  }
}

.home-title-card {
  margin-bottom: 20px;
}

.home-title-hint {
  display: flex;
  align-items: flex-start;
  margin-top: 4px;

  .hint-label {
    width: 90px;
    font-size: 13px;
    color: var(--app-text-secondary, #909399);
    flex-shrink: 0;
    line-height: 34px;
  }

  .hint-preview {
    flex: 1;
    border: 1px dashed var(--el-border-color, #dcdfe6);
    border-radius: 8px;
    padding: 12px 16px;
    text-align: center;
    background: var(--el-fill-color-lighter, #fafafa);

    .hint-h1 {
      font-size: 22px;
      font-weight: 700;
      color: var(--app-text, #303133);
      letter-spacing: 1px;
    }

    .hint-p2 {
      margin-top: 6px;
      font-size: 13px;
      color: var(--app-text-secondary, #909399);
    }
  }
}

.hint-tip {
  margin-top: 8px;
  padding-left: 90px;
  font-size: 12px;
  color: var(--app-text-secondary, #909399);
}

.skin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.effect-row {
  display: flex;
  align-items: center;
  margin-bottom: 16px;

  &:last-child {
    margin-bottom: 0;
  }

  .effect-label {
    width: 90px;
    font-size: 13px;
    color: var(--app-text-secondary, #909399);
    flex-shrink: 0;
  }

  .effect-unit {
    width: 50px;
    text-align: right;
    font-size: 13px;
    color: var(--app-text-secondary, #909399);
    flex-shrink: 0;
    margin-left: 12px;
  }
}

.skin-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-top: 4px;
}

.skin-card {
  cursor: pointer;

  .skin-thumb {
    height: 86px;
    border-radius: 8px;
    border: 2px solid transparent;
    position: relative;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform 0.15s;

    .skin-none {
      color: var(--el-text-color-regular);
      font-size: 12px;
      background: var(--el-fill-color);
      padding: 2px 8px;
      border-radius: 10px;
    }

    .skin-check {
      position: absolute;
      right: 6px;
      top: 6px;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: #67c23a;
      color: #fff;
      font-size: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
  }

  .skin-name {
    text-align: center;
    font-size: 12px;
    margin-top: 6px;
    color: var(--app-text, #303133);
  }

  &:hover .skin-thumb {
    transform: translateY(-3px);
  }

  &.active .skin-thumb {
    border-color: var(--el-color-primary);
    box-shadow: 0 0 0 2px var(--el-color-primary);
  }
}
</style>
