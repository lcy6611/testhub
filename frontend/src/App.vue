<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const route = useRoute()

onMounted(() => {
  // 修复：initAuth 失败时（在登录页）会触发 axios 401 → logout → window.location.href='/login' 死循环。
  // 仅在「非登录页」才调 initAuth（守卫里的 initAuth 已经覆盖首次进入）。
  if (!route.path.startsWith('/login')) {
    userStore.initAuth()
  }
})
</script>

<style>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 
    'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  height: 100vh;
  width: 100vw;
}
</style>