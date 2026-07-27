<template>
  <div class="knowledge-hub-home">
    <!-- 顶部欢迎条 -->
    <div class="hero">
      <div class="hero-left">
        <h1>🧠 知识中枢</h1>
        <p class="subtitle">
          知识中枢按项目隔离，让 AI 用例生成、Agent 检索、智能问答围绕同一份业务知识库运转。
          支持 <strong>本地自建 KB</strong> 与 <strong>Dify 知识库</strong> 双引擎，可接入飞书、Confluence、Notion 等外部数据源。
        </p>
      </div>
      <div class="hero-right">
        <el-dropdown
          class="engine-switcher"
          trigger="click"
          @command="handleSwitchEngine"
        >
          <span class="engine-btn" :class="'engine-' + kbHubStore.defaultEngine">
            <el-icon><Connection /></el-icon>
            <span class="engine-btn-text">默认回退引擎：{{ kbHubStore.engineDisplay }}</span>
            <el-icon class="caret"><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="dify" :disabled="kbHubStore.defaultEngine === 'dify'">
                <el-icon><Link /></el-icon> Dify 知识库
              </el-dropdown-item>
              <el-dropdown-item command="native" :disabled="kbHubStore.defaultEngine === 'native'">
                <el-icon><Files /></el-icon> 自建知识中枢
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- 概览统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card" v-for="item in statCards" :key="item.key" @click="item.to && router.push(item.to)">
        <div class="stat-label">{{ item.label }}</div>
        <div class="stat-value">{{ item.value }}</div>
        <div class="stat-hint">{{ item.hint }}</div>
      </div>
    </div>

    <!-- 4 个子模块入口 -->
    <h2 class="section-title">功能入口</h2>
    <div class="entry-grid">
      <el-card v-for="entry in entries" :key="entry.path" class="entry-card" shadow="hover" @click="router.push(entry.path)">
        <div class="entry-icon">{{ entry.icon }}</div>
        <div class="entry-title">{{ entry.title }}</div>
        <div class="entry-desc">{{ entry.desc }}</div>
      </el-card>
    </div>

    <!-- 操作手册摘要 -->
    <h2 class="section-title">使用建议</h2>
    <el-alert type="info" :closable="false" class="manual-alert">
      <template #title>三步让 AI 用例自动用上知识库</template>
      <ol class="manual-steps">
        <li><strong>① 让项目上知识库</strong>：在「项目管理」中为项目勾选「知识库」模块。</li>
        <li><strong>② 添加知识源并同步</strong>：在「知识库管理」外部数据源页签接入飞书/Confluence，或在「Dify 知识库」页签绑定 Dify 数据集。</li>
        <li><strong>③ 启用知识库</strong>：在 AI 用例生成页勾选「启用知识库（业务大脑）」，系统会按项目自动选择 Dify 或本地 KB 检索。</li>
      </ol>
      <el-button type="primary" link @click="router.push('/configuration/knowledge-hub/manual')">
        查看完整操作手册 →
      </el-button>
    </el-alert>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useKbHubStore } from '@/stores/kb-hub'
import { ElMessage } from 'element-plus'
import { Connection, Link, Files, ArrowDown } from '@element-plus/icons-vue'

const router = useRouter()
const kbHubStore = useKbHubStore()

// Hero 右上角：引擎切换下拉（2026-07-24 按陛下要求移到此处）
const handleSwitchEngine = async (engine) => {
  if (engine === kbHubStore.defaultEngine) return
  const ok = await kbHubStore.setDefaultEngine(engine)
  if (ok) {
    ElMessage.success('已切换默认回退引擎为 ' + (engine === 'dify' ? 'Dify 知识库' : '自建知识中枢'))
    kbHubStore.clearProjectKbsCache()
  } else {
    ElMessage.error('切换失败')
  }
}

const statCards = computed(() => [
  { key: 'kb_total', label: '本地知识库', value: overview.value?.kb_total ?? '—', hint: '已发布 ' + (overview.value?.kb_published ?? 0), to: '/configuration/knowledge-hub/kbs' },
  { key: 'doc_total', label: '知识库文档', value: overview.value?.doc_total ?? '—', hint: '已解析 ' + (overview.value?.doc_parsed ?? 0), to: '/configuration/knowledge-hub/documents' },
  { key: 'chunk_total', label: '向量化分块', value: overview.value?.chunk_total ?? '—', hint: '可供检索', to: '/configuration/knowledge-hub/documents' },
  { key: 'source_total', label: '外部数据源', value: overview.value?.source_total ?? '—', hint: '飞书/Confluence/Notion', to: '/configuration/knowledge-hub/kbs' },
  { key: 'binding_total', label: '项目绑定关系', value: (overview.value?.kb_binding_total ?? 0) + (overview.value?.doc_binding_total ?? 0) + (overview.value?.dify_binding_total ?? 0), hint: 'KB 共享 + 文档共享 + Dify 绑定', to: '/configuration/knowledge-hub/kbs' },
  { key: 'qa', label: '知识问答', value: '→', hint: '直接检索知识库', to: '/configuration/knowledge-hub/qa' },
])

const overview = ref(null)
onMounted(async () => {
  await kbHubStore.loadDefaultEngine()
  overview.value = await kbHubStore.loadOverview()
})

const entries = [
  { icon: '🗂️', title: '知识库管理', desc: '两页签：①外部数据源（飞书/Confluence/Notion）②Dify 知识库绑定', path: '/configuration/knowledge-hub/kbs' },
  { icon: '📄', title: '文档管理', desc: 'PDF/Word/Markdown 上传 + 文档级多项目共享 + 一键抽取', path: '/configuration/knowledge-hub/documents' },
  { icon: '💬', title: '知识问答', desc: 'AI 评测师直接检索知识库（无需 Dify 工作流）', path: '/configuration/knowledge-hub/qa' },
  { icon: '⚙️', title: '中枢配置', desc: '5 项配置：文档解析 / Embedding / Rerank / 抽取 / 视觉', path: '/configuration/knowledge-hub/config' },
  { icon: '📘', title: '操作手册', desc: '新建知识中枢的 5 个子功能详解', path: '/configuration/knowledge-hub/manual' },
]
</script>

<style scoped>
.knowledge-hub-home {
  padding: 24px;
  max-width: 1280px;
  margin: 0 auto;
}
.hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
  gap: 24px;
}
.hero h1 { margin: 0 0 12px; font-size: 28px; }
.subtitle { margin: 0; line-height: 1.7; opacity: 0.95; max-width: 760px; }
.hero-right { flex-shrink: 0; }

/* Hero 右上角引擎切换按钮（2026-07-24 按陛下要求放这里） */
.engine-switcher { display: inline-block; }
.engine-switcher :deep(.el-dropdown__caret-button) { display: none !important; }
.engine-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 500;
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.35);
  cursor: pointer;
  transition: all 0.18s;
  white-space: nowrap;
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  line-height: 1.5;
}
.engine-btn:hover {
  background: rgba(255, 255, 255, 0.35);
  border-color: rgba(255, 255, 255, 0.55);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
.engine-btn .el-icon { font-size: 14px; }
.engine-btn .caret { font-size: 11px; opacity: 0.85; }
.engine-btn-text { font-weight: 500; }
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}
.stat-card {
  background: #fff;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  cursor: pointer;
  transition: all 0.2s;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  border-color: #409eff;
}
.stat-label { color: #909399; font-size: 12px; margin-bottom: 6px; }
.stat-value { font-size: 26px; font-weight: bold; color: #303133; }
.stat-hint { color: #909399; font-size: 11px; margin-top: 4px; }
.section-title { font-size: 18px; margin: 24px 0 12px; color: #303133; }
.entry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}
.entry-card { cursor: pointer; transition: transform 0.2s; }
.entry-card:hover { transform: translateY(-2px); }
.entry-icon { font-size: 32px; margin-bottom: 8px; }
.entry-title { font-size: 16px; font-weight: bold; margin-bottom: 4px; color: #303133; }
.entry-desc { font-size: 12px; color: #909399; line-height: 1.5; }
.manual-alert { margin-top: 12px; }
.manual-steps { margin: 12px 0; padding-left: 24px; line-height: 1.9; color: #606266; }
.manual-steps li { margin-bottom: 4px; }
</style>