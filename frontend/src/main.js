import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import axios from 'axios'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'

import App from './App.vue'
import router from './router'
import i18n from '@/locales'
import './assets/css/global.scss'

// Axios aÃ¥ÂÂºÃ§Â½Â®
axios.defaults.xsrfCookieName = 'csrftoken';
axios.defaults.xsrfHeaderName = 'X-CSRFToken';
axios.defaults.withCredentials = true; // Ã¥ÂÂÃ¨Â®Â¸Ã¨Â·Â¨Ã¨Â¯Â·Ã¥Â¸Â¦ Cookie

const app = createApp(App)

app.use(createPinia())

const userStore = useUserStore()

async function init() {
  // 修复：initAuth 失败时（在登录页拉 /auth/profile/ 拿 401）会触发 axios 401
  //       → userStore.logout() → window.location.href='/login' 死循环。
  // 改为：仅当「有 accessToken 但还没有 user 信息」时尝试拉用户资料；
  //       失败也不要 reload（catch 内不重抛），让守卫决定是否要继续。
  try {
    if (userStore.accessToken && !userStore.user) {
      await userStore.initAuth()
    }
  } catch (error) {
    console.warn('[init] initAuth 失败, 忽略:', error?.message)
  }

  // 初始化主题 / 皮肤 / 壁纸（本地优先，再异步用后端覆盖）
  try {
    await useThemeStore().initTheme()
  } catch (error) {
    // 主题初始化失败不影响主流程
  }

  // 注册所有图标
  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }

  app.use(router)
  app.use(i18n)
  app.use(ElementPlus, {
    locale: zhCn,
  })

  app.mount('#app')
}

init()

