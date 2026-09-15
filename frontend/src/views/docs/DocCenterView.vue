<template>
  <div class="doc-center">
    <div class="doc-sidebar">
      <div class="doc-sidebar-title">文档目录</div>
      <el-menu
        class="doc-menu"
        :default-active="activePath"
        :default-openeds="openedDirs"
      >
        <DocTreeMenu :nodes="tree" @select="selectDoc" />
      </el-menu>
    </div>

    <div class="doc-content">
      <div class="doc-content-header">
        <h2>{{ title || '文档中心' }}</h2>
      </div>
      <div v-loading="loading" class="doc-body markdown-body" v-html="html"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import { getDocContent, getDocTree } from '@/api/docs'
import DocTreeMenu from './DocTreeMenu.vue'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`
      } catch (e) {
        /* 忽略高亮异常，走兜底 */
      }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  }
})

const tree = ref([])
const activePath = ref('')
const openedDirs = ref([])
const html = ref('')
const title = ref('')
const loading = ref(false)

function collect(node, firstFile, dirs) {
  if (node.type === 'dir') {
    dirs.push(node.path)
    node.children.forEach((c) => collect(c, firstFile, dirs))
  } else if (node.type === 'file' && !firstFile.path) {
    firstFile.path = node.path
  }
}

async function selectDoc(path) {
  activePath.value = path
  loading.value = true
  try {
    const res = await getDocContent(path)
    title.value = res.data.title || path
    html.value = md.render(res.data.content || '')
  } catch (e) {
    html.value = '<p style="color:#f56c6c">文档加载失败</p>'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    const res = await getDocTree()
    tree.value = res.data.tree || []
    const firstFile = { path: '' }
    const dirs = []
    tree.value.forEach((n) => collect(n, firstFile, dirs))
    openedDirs.value = dirs
    if (firstFile.path) {
      await selectDoc(firstFile.path)
    }
  } catch (e) {
    tree.value = []
  }
})
</script>

<style lang="scss" scoped>
.doc-center {
  display: flex;
  height: 100%;
  gap: 16px;
}

.doc-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: var(--app-card-bg, #fff);
  border: 1px solid var(--app-border, #e8e8e8);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.doc-sidebar-title {
  padding: 12px 16px;
  font-weight: 600;
  border-bottom: 1px solid var(--app-border, #e8e8e8);
}

.doc-menu {
  flex: 1;
  border-right: none;
  overflow-y: auto;
}

.doc-content {
  flex: 1;
  min-width: 0;
  background: var(--app-card-bg, #fff);
  border: 1px solid var(--app-border, #e8e8e8);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
}

.doc-content-header {
  padding: 16px 24px;
  border-bottom: 1px solid var(--app-border, #e8e8e8);

  h2 {
    margin: 0;
    font-size: 18px;
  }
}

.doc-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}
</style>

<style lang="scss">
/* markdown-it 渲染出的全局样式（v-html 内容不受 scoped 限制） */
.markdown-body {
  line-height: 1.7;
  color: var(--app-text, #303133);

  h1, h2, h3, h4 {
    margin: 1.2em 0 0.6em;
    font-weight: 600;
  }
  h1 { font-size: 1.6em; border-bottom: 1px solid var(--app-border, #e8e8e8); padding-bottom: 0.3em; }
  h2 { font-size: 1.35em; }
  h3 { font-size: 1.15em; }

  p { margin: 0.6em 0; }

  ul, ol { padding-left: 1.6em; margin: 0.6em 0; }

  table {
    border-collapse: collapse;
    width: 100%;
    margin: 0.8em 0;
  }
  th, td {
    border: 1px solid var(--app-border, #e8e8e8);
    padding: 8px 12px;
    text-align: left;
  }
  th { background: var(--app-bg-soft, #f5f5f5); }

  blockquote {
    margin: 0.8em 0;
    padding: 0.4em 1em;
    border-left: 4px solid var(--el-color-primary, #409eff);
    background: var(--app-bg-soft, #f5f5f5);
    color: var(--app-text-secondary, #606266);
  }

  code {
    background: rgba(135, 131, 120, 0.15);
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-family: monospace;
  }

  pre.hljs {
    background: #f6f8fa;
    padding: 14px 16px;
    border-radius: 8px;
    overflow-x: auto;
    margin: 0.8em 0;

    code {
      background: transparent;
      padding: 0;
    }
  }
}
</style>
