<template>
  <div v-if="entityKey" :class="['kg-panel-section', variantClass]">
    <p v-if="expansionHint" class="graph-expansion-hint">
      🔗 知识图谱：{{ expansionHint }}
    </p>
    <div class="kg-panel-card">
      <div class="kg-panel-header">
        <h3>{{ title }}</h3>
        <button
          type="button"
          class="kg-refresh-btn"
          :disabled="loading"
          @click="load">
          {{ loading ? '加载中…' : '刷新' }}
        </button>
      </div>
      <p v-if="enabled === false" class="kg-hint">{{ disabledHint }}</p>
      <p v-else-if="loading" class="kg-hint">正在加载关联关系…</p>
      <p v-else-if="error" class="kg-hint kg-error">{{ error }}</p>
      <template v-else>
        <p v-if="extraHint" class="kg-hint kg-refinement">{{ extraHint }}</p>
        <p v-if="!hasContent && !extraHint" class="kg-hint">
          {{ emptyHint }}
        </p>
        <template v-if="mode === 'testcase-detail' && groupedSections.length">
          <div
            v-for="section in groupedSections"
            :key="section.key"
            class="kg-section">
            <p :class="['kg-section-title', section.key === 'automates' ? 'kg-section-title-automates' : '']">{{ section.title }}</p>
            <div class="kg-relation-list">
              <div
                v-for="(row, idx) in section.rows"
                :key="`${section.key}-${idx}`"
                :class="['kg-relation-row', row.rowVariant === 'covers' ? 'kg-relation-row-covers' : row.rowVariant === 'automates' ? 'kg-relation-row-automates' : '']">
                <span v-if="row.prefix" class="kg-prefix">{{ row.prefix }}</span>
                <span class="kg-rel-type">{{ row.relationLabel }}</span>
                <span class="kg-arrow">→</span>
                <span class="kg-entity-type">{{ row.entityTypeLabel }}</span>
                <router-link
                  v-if="row.linkTo"
                  :to="row.linkTo"
                  class="kg-entity-label kg-link"
                  :title="row.label">
                  {{ row.label }}
                </router-link>
                <span v-else class="kg-entity-label" :title="row.label">{{ row.label }}</span>
                <span
                  v-if="section.key === 'automates' && row.lastExecutionHint"
                  :class="['kg-exec-badge', row.lastExecution?.passed ? 'kg-exec-pass' : 'kg-exec-fail']"
                  :title="row.lastExecution?.error_message || ''">
                  {{ row.lastExecutionHint }}
                </span>
              </div>
            </div>
          </div>
        </template>
        <div v-else-if="displayRows.length > 0" class="kg-relation-list">
          <div
            v-for="(row, idx) in displayRows"
            :key="idx"
            class="kg-relation-row">
            <span v-if="row.prefix" class="kg-prefix">{{ row.prefix }}</span>
            <span class="kg-rel-type">{{ row.relationLabel }}</span>
            <span class="kg-arrow">→</span>
            <span class="kg-entity-type">{{ row.entityTypeLabel }}</span>
            <router-link
              v-if="row.linkTo"
              :to="row.linkTo"
              class="kg-entity-label kg-link"
              :title="row.label">
              {{ row.label }}
            </router-link>
            <span v-else class="kg-entity-label" :title="row.label">{{ row.label }}</span>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getKgStatus, getKgSubgraph } from '@/api/knowledge-graph'
import { buildKgDisplayRows, buildKgTestCaseSections } from '@/utils/kgRelationRows'

const props = defineProps({
  entityKey: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    default: '🔗 关联图谱'
  },
  mode: {
    type: String,
    default: 'outgoing',
    validator: value => ['outgoing', 'provenance-chain', 'derived-incoming', 'testcase-detail'].includes(value)
  },
  emptyHint: {
    type: String,
    default: '暂无图谱数据。'
  },
  extraHint: {
    type: String,
    default: ''
  },
  expansionHint: {
    type: String,
    default: ''
  },
  disabledHint: {
    type: String,
    default: '知识图谱未启用（KNOWLEDGE_GRAPH_ENABLED=false）'
  },
  autoLoad: {
    type: Boolean,
    default: true
  },
  depth: {
    type: Number,
    default: 2
  },
  maxNodes: {
    type: Number,
    default: 80
  },
  /** default：详情页；embedded：KbChat 等内嵌布局 */
  variant: {
    type: String,
    default: 'default',
    validator: value => ['default', 'embedded'].includes(value)
  }
})

const variantClass = computed(() =>
  props.variant === 'embedded' ? 'kg-panel-embedded' : ''
)

const emit = defineEmits(['loaded'])

const loading = ref(false)
const enabled = ref(null)
const error = ref('')
const subgraph = ref(null)

const displayRows = computed(() =>
  props.mode === 'testcase-detail'
    ? []
    : buildKgDisplayRows(subgraph.value, props.entityKey, props.mode)
)

const groupedSections = computed(() => {
  if (props.mode !== 'testcase-detail') return []
  return buildKgTestCaseSections(subgraph.value, props.entityKey)
})

const hasContent = computed(() =>
  props.mode === 'testcase-detail'
    ? groupedSections.value.length > 0
    : displayRows.value.length > 0
)

async function load() {
  if (!props.entityKey) return
  loading.value = true
  error.value = ''
  try {
    const statusResp = await getKgStatus(props.entityKey)
    enabled.value = statusResp.data?.enabled !== false
    if (!enabled.value) {
      subgraph.value = null
      emit('loaded', null)
      return
    }
    const resp = await getKgSubgraph(props.entityKey, {
      depth: props.depth,
      max_nodes: props.maxNodes
    })
    subgraph.value = resp.data
    if (!resp.data?.root && resp.data?.detail) {
      error.value = resp.data.detail
    }
    emit('loaded', resp.data)
  } catch (e) {
    error.value = e.response?.data?.detail || '加载关联图谱失败'
    subgraph.value = null
    emit('loaded', null)
  } finally {
    loading.value = false
  }
}

watch(
  () => props.entityKey,
  key => {
    if (key && props.autoLoad) {
      load()
    }
  },
  { immediate: true }
)

defineExpose({ load, refresh: load, subgraph, displayRows })
</script>

<style scoped>
.kg-panel-section {
  margin-top: 20px;
  margin-bottom: 20px;
}
.graph-expansion-hint {
  margin: 0 0 12px;
  padding: 8px 12px;
  font-size: 13px;
  color: #1e40af;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  line-height: 1.5;
}
.kg-panel-card {
  background: #f8fafc;
  border: 1px solid #dbeafe;
  border-radius: 10px;
  padding: 16px 20px;
}
.kg-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.kg-panel-header h3 {
  margin: 0;
  font-size: 1rem;
  color: #1e293b;
}
.kg-refresh-btn {
  padding: 4px 12px;
  font-size: 13px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #fff;
  cursor: pointer;
}
.kg-refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.kg-hint {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.kg-hint.kg-error {
  color: #b91c1c;
}
.kg-hint.kg-refinement {
  color: #7c3aed;
  background: #f5f3ff;
  padding: 8px 10px;
  border-radius: 6px;
  margin-bottom: 8px;
}
.kg-relation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.kg-relation-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
}
.kg-relation-row-covers {
  background: #f0fdf4;
  border-color: #bbf7d0;
}
.kg-relation-row-automates {
  background: #fff7ed;
  border-color: #fed7aa;
}
.kg-section {
  margin-bottom: 14px;
}
.kg-section:last-child {
  margin-bottom: 0;
}
.kg-section-title {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  letter-spacing: 0.02em;
}
.kg-section:first-child .kg-section-title {
  color: #15803d;
}
.kg-section-title-automates {
  color: #c2410c;
}
.kg-exec-badge {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}
.kg-exec-pass {
  background: #dcfce7;
  color: #166534;
}
.kg-exec-fail {
  background: #fee2e2;
  color: #b91c1c;
}
.kg-prefix {
  color: #64748b;
  font-size: 12px;
}
.kg-rel-type {
  padding: 2px 8px;
  background: #e0e7ff;
  color: #3730a3;
  border-radius: 4px;
  font-size: 12px;
}
.kg-arrow {
  color: #94a3b8;
}
.kg-entity-type {
  color: #475569;
  font-size: 12px;
}
.kg-entity-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #0f172a;
}
.kg-link {
  color: #2563eb;
  text-decoration: none;
}
.kg-link:hover {
  text-decoration: underline;
}
.kg-panel-section.kg-panel-embedded {
  flex-shrink: 0;
  margin-top: 0;
  margin-bottom: 0;
  padding: 0 16px 8px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}
.kg-panel-embedded .kg-panel-card {
  padding: 10px 14px;
  border-radius: 8px;
}
.kg-panel-embedded .kg-panel-header {
  margin-bottom: 8px;
}
.kg-panel-embedded .kg-panel-header h3 {
  font-size: 13px;
  color: #1e40af;
}
.kg-panel-embedded .kg-refresh-btn {
  padding: 2px 10px;
  border-color: #93c5fd;
  color: #2563eb;
  border-radius: 4px;
  font-size: 12px;
}
.kg-panel-embedded .kg-hint {
  font-size: 12px;
}
.kg-panel-embedded .kg-relation-list {
  gap: 6px;
}
.kg-panel-embedded .kg-relation-row {
  gap: 6px;
  padding: 6px 8px;
  font-size: 12px;
}
.kg-panel-embedded .kg-prefix {
  font-size: 11px;
}
.kg-panel-embedded .kg-rel-type {
  padding: 1px 6px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
}
.kg-panel-embedded .kg-entity-type {
  font-size: 11px;
}
</style>
