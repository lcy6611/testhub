import { createI18n } from 'vue-i18n'
import zhCnMonitor from './lang/zh-cn/monitor.js'
import enMonitor from './lang/en/monitor.js'
import zhCnDefectsOss from './lang/zh-cn/defects_oss.js'
import enDefectsOss from './lang/en/defects_oss.js'
import zhCnMcp from './lang/zh-cn/mcp.js'
import enMcp from './lang/en/mcp.js'

// 仅注册「监控中心」「缺陷(开源对比)」与「MCP 控制台」模块的国际化文案（其余模块当前未接入 i18n，保持最小侵入）。
// 命名空间 monitor / defects_oss / mcp 与源项目 locales 结构一致（t('mcp.tabTools') 等）。
const messages = {
  'zh-cn': {
    monitor: zhCnMonitor,
    defects_oss: zhCnDefectsOss,
    mcp: zhCnMcp,
    common: { refresh: '刷新', actions: '操作' },
  },
  'en': {
    monitor: enMonitor,
    defects_oss: enDefectsOss,
    mcp: enMcp,
    common: { refresh: 'Refresh', actions: 'Actions' },
  },
}

const i18n = createI18n({
  legacy: false, // 必须 false 才能使用 Composition API 的 useI18n()
  locale: 'zh-cn',
  fallbackLocale: 'zh-cn',
  globalInjection: true,
  messages,
  missingWarn: false,
  fallbackWarn: false,
})

export default i18n
