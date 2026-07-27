// 内置皮肤 / 壁纸预设
// - type === 'image'    : 使用 url 指向 public/wallpapers 下的真实图片
// - type === 'gradient' : 使用纯 CSS 渐变（value 直接作为 background-image）
// - type === 'none'     : 无壁纸，使用纯色背景

export const SKIN_CATEGORIES = [
  { key: 'landscape', name: '风景', icon: '🏞️' },
  { key: 'game', name: '游戏', icon: '🎮' },
  { key: 'car', name: '汽车', icon: '🚗' },
  { key: 'abstract', name: '抽象', icon: '🌀' },
  { key: 'minimal', name: '简约', icon: '⬜' },
  { key: 'gradient', name: '渐变', icon: '🌈' },
]

export const SKINS = [
  { id: 'none', name: '无壁纸（纯色）', category: 'minimal', type: 'none' },

  // 风景
  { id: 'landscape-1', name: '山湖晨曦', category: 'landscape', type: 'image', url: '/wallpapers/landscape-1.png' },
  { id: 'landscape-2', name: '森林薄雾', category: 'landscape', type: 'image', url: '/wallpapers/landscape-2.png' },

  // 游戏
  { id: 'game-1', name: '赛博都市', category: 'game', type: 'image', url: '/wallpapers/game-1.png' },
  { id: 'game-2', name: '奇幻大陆', category: 'game', type: 'image', url: '/wallpapers/game-2.png' },

  // 汽车
  { id: 'car-1', name: '公路飞驰', category: 'car', type: 'image', url: '/wallpapers/car-1.png' },
  { id: 'car-2', name: '都市夜驾', category: 'car', type: 'image', url: '/wallpapers/car-2.png' },

  // 抽象
  { id: 'abstract-1', name: '极光流体', category: 'abstract', type: 'image', url: '/wallpapers/abstract-1.png' },
  { id: 'abstract-2', name: '几何光影', category: 'abstract', type: 'image', url: '/wallpapers/abstract-2.png' },

  // 简约
  { id: 'minimal-1', name: '极简灰白', category: 'minimal', type: 'gradient', value: 'linear-gradient(135deg, #e0eafc 0%, #cfdef3 100%)' },

  // 渐变
  { id: 'gradient-1', name: '紫粉晚霞', category: 'gradient', type: 'gradient', value: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' },
  { id: 'gradient-2', name: '橙蓝日落', category: 'gradient', type: 'gradient', value: 'linear-gradient(135deg, #ff9a9e 0%, #fad0c4 50%, #a18cd1 100%)' },
  { id: 'gradient-3', name: '深海蓝绿', category: 'gradient', type: 'gradient', value: 'linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%)' },
  { id: 'gradient-4', name: '墨绿森林', category: 'gradient', type: 'gradient', value: 'linear-gradient(135deg, #134e5e 0%, #71b280 100%)' },
]

export const DEFAULT_PRIMARY = '#409eff'

export function findSkin(id) {
  return SKINS.find((s) => s.id === id) || null
}
