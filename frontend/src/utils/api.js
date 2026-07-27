import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 正在刷新的标志
let isRefreshing = false
// 等待刷新的请求队列
let failedQueue = []

// 处理队列中的请求
const processQueue = (error, token = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })

  failedQueue = []
}

// 请求拦截器
api.interceptors.request.use(
  async (config) => {
    const userStore = useUserStore()

    // FormData 请求必须交给浏览器自动设置 Content-Type（含 boundary）
    if (typeof FormData !== 'undefined' && config?.data instanceof FormData) {
      if (config.headers) {
        delete config.headers['Content-Type']
      }
    }

    // 通用：清理查询参数，避免空值导致后端过滤不生效/报错（适用于所有菜单）
    if (config && config.params && typeof config.params === 'object') {
      const cleaned = {}
      Object.entries(config.params).forEach(([k, v]) => {
        // 去掉 undefined/null/空字符串
        if (v === undefined || v === null) return
        if (typeof v === 'string' && v.trim() === '') return
        // 去掉空数组
        if (Array.isArray(v) && v.length === 0) return
        cleaned[k] = v
      })
      config.params = cleaned
    }

    // auth 端点（登录/注册/刷新）不需要附加 token，
    // 否则 localStorage 里的过期 token 会让 DRF JWTAuthentication
    // 在到达 view 之前就返回 401，导致登录永远失败
    const authEndpoints = [
      '/auth/login/',
      '/auth/register/',
      '/auth/test-register/',
      '/auth/token/refresh/',
    ]
    if (authEndpoints.includes(config.url)) {
      return config
    }

    // 如果有access token
    if (userStore.accessToken) {
      // 检查token是否即将过期（5分钟内）
      if (userStore.isTokenExpiringSoon && !userStore.isTokenExpired) {
        // 如果没有正在刷新，开始刷新
        if (!isRefreshing) {
          isRefreshing = true
          console.log('Token即将过期，开始刷新...')

          try {
            const newToken = await userStore.refreshAccessToken()
            console.log('Token刷新成功')
            processQueue(null, newToken)

            // 更新当前请求的token
            config.headers.Authorization = `Bearer ${newToken}`
          } catch (error) {
            console.error('Token刷新失败:', error)
            processQueue(error, null)
            // 刷新失败会在user store中自动logout
            return Promise.reject(error)
          } finally {
            isRefreshing = false
          }
        } else {
          // 如果正在刷新，将请求加入队列
          console.log('Token正在刷新，请求加入队列等待...')
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject })
          }).then(token => {
            config.headers.Authorization = `Bearer ${token}`
            return config
          }).catch(err => {
            return Promise.reject(err)
          })
        }
      }

      // 使用Bearer token格式
      config.headers.Authorization = `Bearer ${userStore.accessToken}`
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response
  },
  async (error) => {
    const userStore = useUserStore()
    const originalRequest = error.config

    // 如果是401错误且不是刷新token的请求
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 登录/注册端点的 401 不触发 token 刷新逻辑，直接抛出让页面处理
      const authEndpoints = [
        '/auth/login/',
        '/auth/register/',
        '/auth/test-register/',
      ]
      if (authEndpoints.includes(originalRequest.url)) {
        return Promise.reject(error)
      }

      // 如果是logout请求失败，直接清除本地状态不再重试logout，防止死循环
      if (originalRequest.url === '/auth/logout/') {
        console.error('Logout请求401，直接清除本地状态')
        userStore.$patch((state) => {
          state.accessToken = ''
          state.refreshToken = ''
          state.user = null
          state.tokenExpiresAt = 0
        })
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('token_expires_at')
        localStorage.removeItem('user')
        window.location.href = '/login'
        return Promise.reject(error)
      }

      // 如果是刷新token的请求失败
      if (originalRequest.url === '/auth/token/refresh/') {
        console.error('Refresh token失败，跳转登录页')
        await userStore.logout()
        return Promise.reject(error)
      }

      // 如果有refresh token，尝试刷新
      if (userStore.refreshToken && !isRefreshing) {
        originalRequest._retry = true
        isRefreshing = true

        try {
          console.log('收到401响应，尝试刷新token...')
          const newToken = await userStore.refreshAccessToken()
          console.log('Token刷新成功，重试原请求')
          processQueue(null, newToken)

          // 更新当前请求的token
          originalRequest.headers.Authorization = `Bearer ${newToken}`

          // 重试原请求
          return api(originalRequest)
        } catch (refreshError) {
          console.error('Token刷新失败:', refreshError)
          processQueue(refreshError, null)
          await userStore.logout()
          return Promise.reject(refreshError)
        } finally {
          isRefreshing = false
        }
      } else {
        // 没有refresh token，直接退出
        // 修复：避免在应用初始化阶段（main.js 调 initAuth）触发 logout → window.location.href='/login' 死循环。
        // 已经在 /login 页或没有明确用户操作时，仅清本地状态、不再 reload。
        const isOnLoginPage = typeof window !== 'undefined' && window.location.pathname.startsWith('/login')
        if (isOnLoginPage) {
          console.warn('[TestHub] 401 on /login, 仅清本地状态，避免页面刷新死循环')
          userStore.$patch((state) => {
            state.accessToken = ''
            state.refreshToken = ''
            state.user = null
            state.tokenExpiresAt = 0
          })
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          localStorage.removeItem('token_expires_at')
          localStorage.removeItem('user')
          return Promise.reject(error)
        }
        console.error('没有refresh token，跳转登录页')
        await userStore.logout()
      }

      return Promise.reject(error)
    }

    // 其他错误处理
    const contentType = error.response?.headers?.['content-type'] || ''
    const data = error.response?.data
    const isHtml = contentType.includes('text/html') || (typeof data === 'string' && data.trimStart().startsWith('<'))
    const reqUrl = originalRequest?.url || '(unknown)'
    const reqMethod = (originalRequest?.method || 'GET').toUpperCase()

    if (error.response?.status === 401) {
      ElMessage.error('登录已过期，请重新登录')
    } else if (error.response?.status === 404 && originalRequest?.url?.includes('config/dify') && !isHtml) {
      // 获取 Dify 配置无数据时可能返回 404 JSON，由页面自行处理
    } else if (error.response?.status === 404 && originalRequest?.url?.includes('hermes/config/active') && !isHtml) {
      // Hermes 数字人配置未设置时返回 404 JSON，由 HermesChatView 自行展示引导，不弹窗打扰
    } else if (error.response?.status === 404 && isHtml) {
      // 后端返回 HTML 404 页面 → 请求的 URL 路径在后端不存在
      console.warn(`[TestHub] 404 HTML ← ${reqMethod} ${reqUrl}`)
      ElMessage.error(`接口不存在（404）：${reqMethod} ${reqUrl}`)
    } else if (error.response?.status === 502 && isHtml) {
      // 代理上游不可达 → 后端容器可能没启动
      console.warn(`[TestHub] 502 HTML ← ${reqMethod} ${reqUrl}`)
      ElMessage.error(`后端服务不可达（502）：${reqMethod} ${reqUrl}`)
    } else if (error.response?.status === 400 && originalRequest?.url?.includes('test_connection')) {
      // 测试连接失败由配置页展示具体错误（如 Dify 返回 404），不重复弹窗
    } else if (error.response?.status >= 500) {
      console.warn(`[TestHub] ${error.response.status} ← ${reqMethod} ${reqUrl}`, data)
      ElMessage.error(`服务器错误（${error.response.status}），请稍后重试`)
    } else if (data && typeof data === 'object' && data.error) {
      ElMessage.error(data.error)
    } else if (data && typeof data === 'object' && data.detail) {
      ElMessage.error(typeof data.detail === 'string' ? data.detail : '请求失败')
    } else if (data && typeof data === 'object' && typeof data.message === 'string') {
      ElMessage.error(data.message)
    }

    return Promise.reject(error)
  }
)

export default api
