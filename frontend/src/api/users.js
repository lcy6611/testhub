import api from '@/utils/api'

// 获取当前用户界面偏好
export function getUIConfig() {
  return api.get('/users/ui-settings/')
}

// 更新界面偏好（增量合并）
export function updateUIConfig(data) {
  return api.patch('/users/ui-settings/', data)
}

// 上传自定义壁纸，返回 { url, name }
export function uploadWallpaper(formData) {
  return api.post('/users/wallpaper/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
