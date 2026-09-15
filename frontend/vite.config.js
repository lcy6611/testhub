import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  css: {
    preprocessorOptions: {
      scss: {
        silenceDeprecations: ['legacy-js-api'],
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    // 允许 Docker 网络内其他容器（如 UI 自动化 backend 容器）通过服务名访问前端
    allowedHosts: true,
    // 本地开发默认 8001；Docker 下通过环境变量 VITE_PROXY_TARGET 指向 backend:8000
    proxy: (() => {
      const target = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8001'
      return {
        // Vite 的 proxy key 是“路径前缀”，不是正则；用 '^/api/' 会导致不生效，
        // 从而 /api 请求落回前端并返回 HTML（触发你看到的红色错误提示）。
        // 只代理 /api/（不能写成 /api，否则会把 /api-testing 等前端路由也误代理到后端）
        '/api/': { target, changeOrigin: true, secure: false },
        '/media/': { target, changeOrigin: true, secure: false },
        // WebSocket：必须显式 ws: true，否则浏览器 ws:// 同源连接无法升级到后端
        // （app-automation / performance-testing 的实时推送都挂在 /ws/ 下）
        '/ws/': { target, changeOrigin: true, secure: false, ws: true },
      }
    })(),
    historyApiFallback: {
      index: '/index.html',
    },
  },
  // curlconverter 依赖的 web-tree-sitter 在浏览器侧会使用 top-level await，
  // 因此需要把构建 target 提升到 esnext 以避免生产构建失败。
  esbuild: {
    target: 'esnext',
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    target: 'esnext',
  },
  optimizeDeps: {
    include: [
      'monaco-editor',
      'curlconverter',
      // pixi.js@6 + pixi-live2d-display@0.4 在 ESM 互操作下会触发
      // "does not provide an export named 'PIXI'"，必须显式预构建走 CJS 桥接
      'pixi.js',
      'pixi-live2d-display/cubism4',
      'pixi-live2d-display/cubism2',
      // 必须把 vue 显式 include，否则 vite 重新扫描依赖时会把 vue/reactivity 拆 chunk，
      // 引发 "RefImpl is not a constructor" 错误
      'vue',
      '@vue/runtime-core',
      '@vue/runtime-dom',
      'vue > @vue/reactivity',
    ],
    esbuildOptions: {
      target: 'esnext',
    },
  }
})