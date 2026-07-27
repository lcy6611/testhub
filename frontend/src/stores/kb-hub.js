import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getKbHubConfig,
  switchEngine,
  getProjectKbs,
  getKbHubOverview,
} from '@/api/kb-hub'

// 知识中枢 store（2026-07-23 重构）
// 引擎不再是「全局单一值」驱动一切，改为：
//   - defaultEngine：默认回退引擎（KnowledgeHubConfig.engine）
//   - 按项目自动判定：调 getProjectKbs(projectId) 看 Dify 绑定还是本地 KB
// 单一真相源：defaultEngine 仍由配置页（KnowledgeHubConfigView）写入；
// 其它页面只读 loadDefaultEngine，不直接 setEngine。
export const useKbHubStore = defineStore('kb-hub', () => {
  // 默认回退引擎（dify | native）；仅在没有项目特定配置时生效
  const defaultEngine = ref('dify')
  const defaultEngineLoaded = ref(false)
  const loading = ref(false)

  const engineDisplay = computed(() =>
    defaultEngine.value === 'dify' ? 'Dify 知识库' : '自建知识中枢（Native）',
  )
  const engineType = computed(() =>
    defaultEngine.value === 'dify' ? 'success' : 'warning',
  )

  // 当前加载的项目级 KB 缓存：{ projectId: { engine, items, reason, kb_count } }
  const projectKbsCache = ref({})

  // 知识中枢首页统计：{ kb_total, doc_total, chunk_total, source_total, ... }
  const overview = ref(null)

  async function loadDefaultEngine(force = false) {
    if (defaultEngineLoaded.value && !force) return defaultEngine.value
    loading.value = true
    try {
      const { data } = await getKbHubConfig()
      if (data?.engine) defaultEngine.value = data.engine
      defaultEngineLoaded.value = true
    } catch (e) {
      console.warn('加载知识中枢默认引擎失败:', e)
    } finally {
      loading.value = false
    }
    return defaultEngine.value
  }

  // 切换默认引擎（写入口）
  async function setDefaultEngine(val) {
    try {
      await switchEngine(val)
      defaultEngine.value = val
      defaultEngineLoaded.value = true
      return true
    } catch (e) {
      console.error('切换知识中枢默认引擎失败:', e)
      return false
    }
  }

  // 按项目加载可用 KB 列表（自动判定引擎）
  // 返回 { engine, reason, items, kb_count }
  async function loadProjectKbs(projectId, force = false) {
    if (!projectId) return null
    if (!force && projectKbsCache.value[projectId]) {
      return projectKbsCache.value[projectId]
    }
    try {
      const { data } = await getProjectKbs(projectId)
      projectKbsCache.value[projectId] = data
      return data
    } catch (e) {
      console.error('加载项目可用知识库失败:', e)
      return null
    }
  }

  function clearProjectKbsCache(projectId) {
    if (projectId) delete projectKbsCache.value[projectId]
    else projectKbsCache.value = {}
  }

  async function loadOverview(force = false) {
    if (overview.value && !force) return overview.value
    try {
      const { data } = await getKbHubOverview()
      overview.value = data
      return data
    } catch (e) {
      console.error('加载知识中枢概览失败:', e)
      return null
    }
  }

  return {
    defaultEngine,
    defaultEngineLoaded,
    loading,
    engineDisplay,
    engineType,
    projectKbsCache,
    overview,
    loadDefaultEngine,
    setDefaultEngine,
    loadProjectKbs,
    clearProjectKbsCache,
    loadOverview,
  }
})