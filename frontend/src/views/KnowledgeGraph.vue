<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import { Search, InfoFilled } from '@element-plus/icons-vue'
import { getKnowledgeGraph, searchKnowledge, getKnowledgeStats } from '../api'

/* ---------- types（对齐后端 GraphNode / KnowledgeEntry） ---------- */
interface GraphNode { id: string; type: string; label: string; weight: number }
interface GraphLink { source: string; target: string; relation: string }
interface KbEntry {
  id: string
  category: string
  title: string
  source?: any
  original_text?: string
  plain_explanation?: string
  related_diseases?: string[]
  related_syndromes?: string[]
  treatment_method?: string
  formula?: { name?: string } | null
}

/* ---------- 图谱节点类型元信息 ---------- */
const typeMeta: Record<string, { label: string; color: string }> = {
  disease: { label: '病证', color: '#D9534F' },
  treatment: { label: '治法', color: '#5FA8C0' },
  formula: { label: '方剂', color: '#C8A45C' },
  herb: { label: '药材', color: '#5FB3A1' },
  syndrome: { label: '证型', color: '#B08AD9' },
}
const FALLBACK_TYPE = { label: '其他', color: '#8896A6' }
const typeOf = (t: string) => typeMeta[t] || FALLBACK_TYPE
const typeKeys = Object.keys(typeMeta)

/* ---------- 关系配色 ---------- */
const relationColors: Record<string, string> = {
  治法: '#5FA8C0',
  代表方: '#C8A45C',
  主方: '#F59E0B',
  组成: '#5FB3A1',
  证型: '#B08AD9',
  功效: '#36B5A0',
}

/* ---------- KB 类别（理/法/方/药/养生）配色 ---------- */
const kbCatColor: Record<string, string> = {
  理: '#5FA8C0',
  法: '#D9534F',
  方: '#C8A45C',
  药: '#5FB3A1',
  养生: '#B08AD9',
}
const filterTabs = [
  { key: 'all', label: '全部', cat: '' },
  { key: '理', label: '理', cat: '理' },
  { key: '法', label: '法', cat: '法' },
  { key: '方', label: '方', cat: '方' },
  { key: '药', label: '药', cat: '药' },
  { key: '养生', label: '养生', cat: '养生' },
]

/* ---------- 状态 ---------- */
const graphNodes = ref<GraphNode[]>([])
const graphLinks = ref<GraphLink[]>([])
const graphLoading = ref(false)
const graphError = ref('')
const kbTotal = ref(0)

const diseaseOptions = ref<{ label: string; value: string }[]>([])
const selectedDisease = ref('')

/* 聚焦/钻取导航：图谱始终只渲染当前聚焦节点 + 其直接关联（聚焦+上下文），
   节点数恒定 ~17，规避全量 2K+ 节点的“毛球”问题 */
const focusId = ref<string | null>(null)
const trail = ref<string[]>([]) // 面包屑：聚焦路径的祖先节点
const PER_TYPE = 5 // 每种关联类型最多展示数（保证治法/证型/方剂/药材均衡呈现）

const searchQuery = ref('')
const activeFilter = ref('all')
const searchResults = ref<KbEntry[]>([])
const searchTotal = ref(0)
const searchLoading = ref(false)
const searchPage = ref(1)
const PAGE_SIZE = 10

const expandedResultId = ref<string | null>(null)
const detailDialogVisible = ref(false)
const detailEntry = ref<KbEntry | null>(null)

/* ---------- 工具 ---------- */
function sourceStr(s: any): string {
  if (!s) return ''
  if (typeof s === 'string') return s
  return `${s.book || ''}${s.volume ? '·' + s.volume : ''}${s.section ? '·' + s.section : ''}`
}

/* ---------- 图谱加载 ---------- */
async function loadGraph(disease = '') {
  graphLoading.value = true
  graphError.value = ''
  try {
    // 聚焦病证用更小的 max_entries → 该病为中心的清晰子图；总览适度铺开
    const { data } = await getKnowledgeGraph(disease || undefined, disease ? 35 : 80)
    graphNodes.value = data.nodes || []
    graphLinks.value = data.links || []
    // 仅在总览（无病证过滤）时刷新病证下拉项 + 默认聚焦，保持其稳定
    if (!disease) {
      const diseases = graphNodes.value
        .filter((n) => n.type === 'disease')
        .sort((a, b) => b.weight - a.weight)
      diseaseOptions.value = diseases.map((n) => ({ label: `${n.label}（${n.weight}）`, value: n.label }))
    }
    // 选了病证→聚焦该病子图；否则→总览病证环（focus 为空）
    trail.value = []
    if (disease) {
      focusId.value = disease
      drillToSearch(disease)
    } else {
      focusId.value = null
    }
    nextTick(() => renderChart())
  } catch (e: any) {
    graphError.value = e?.response?.data?.detail || '图谱加载失败，请确认后端已启动'
  } finally {
    graphLoading.value = false
  }
}

/* ---------- 检索 ---------- */
async function runSearch() {
  searchLoading.value = true
  try {
    const cat = filterTabs.find((t) => t.key === activeFilter.value)?.cat || undefined
    const { data } = await searchKnowledge(searchQuery.value.trim(), cat, searchPage.value, PAGE_SIZE)
    searchResults.value = data.items || []
    searchTotal.value = data.total || 0
    expandedResultId.value = null
    // 结果区滚回顶部，避免翻页后停留在底部
    nextTick(() => { resultsListRef.value?.scrollTo({ top: 0 }) })
  } catch {
    searchResults.value = []
    searchTotal.value = 0
  } finally {
    searchLoading.value = false
  }
}

// 新查询/换筛选时回到第 1 页后再检索
function resetAndSearch() {
  searchPage.value = 1
  runSearch()
}
function onPageChange(p: number) {
  searchPage.value = p
  runSearch()
}

let searchTimer: ReturnType<typeof setTimeout> | null = null
// 覆盖手动输入与点击节点的程序化赋值，统一走防抖检索（并重置到第1页）
watch(searchQuery, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(resetAndSearch, 300)
})

/* ---------- DOM refs ---------- */
const resultsListRef = ref<HTMLDivElement | null>(null)

/* ---------- ECharts ---------- */
const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

/* ---------- 聚焦子图（中心节点 + 直接关联，按类型/权重排序并截断） ---------- */
interface EgoNeighbor { node: GraphNode; relation: string }
interface Ego { focus: GraphNode | null; shown: EgoNeighbor[]; hidden: number }

function computeEgo(id: string | null): Ego {
  if (!id) return { focus: null, shown: [], hidden: 0 }
  const map = new Map(graphNodes.value.map((n) => [n.id, n]))
  const focus = map.get(id) || null
  if (!focus) return { focus: null, shown: [], hidden: 0 }
  const seen = new Set<string>()
  const nb: EgoNeighbor[] = []
  for (const l of graphLinks.value) {
    let other = ''
    if (l.source === id) other = l.target
    else if (l.target === id) other = l.source
    else continue
    const node = map.get(other)
    if (!node || seen.has(other)) continue
    seen.add(other)
    nb.push({ node, relation: l.relation })
  }
  // 按类型分组，每类取权重最高的 PER_TYPE 个 → 均衡呈现，并按类型成弧排布
  const byType = new Map<string, EgoNeighbor[]>()
  for (const x of nb) {
    if (!byType.has(x.node.type)) byType.set(x.node.type, [])
    byType.get(x.node.type)!.push(x)
  }
  const orderedTypes = [...typeKeys, ...[...byType.keys()].filter((t) => !typeKeys.includes(t))]
  const shown: EgoNeighbor[] = []
  let hidden = 0
  for (const t of orderedTypes) {
    const arr = (byType.get(t) || []).sort((a, b) => b.node.weight - a.node.weight)
    shown.push(...arr.slice(0, PER_TYPE))
    hidden += Math.max(0, arr.length - PER_TYPE)
  }
  return { focus, shown, hidden }
}

const ego = computed(() => computeEgo(focusId.value))

function neighborSize(weight: number): number {
  return Math.max(20, Math.min(46, 16 + 5 * Math.sqrt(weight)))
}

function buildOption() {
  // focus 为空 → 总览（顶部病证环，点击展开）；否则 → 聚焦子图
  return focusId.value ? buildEgoOption() : buildOverviewOption()
}

function buildOverviewOption() {
  const diseases = graphNodes.value
    .filter((n) => n.type === 'disease')
    .sort((a, b) => b.weight - a.weight)
    .slice(0, 12)
  const R = 230
  const n = diseases.length || 1
  const meta = typeMeta.disease
  const data = diseases.map((d, i) => {
    const ang = (-90 + (360 / n) * i) * (Math.PI / 180)
    const x = R * Math.cos(ang)
    const y = R * Math.sin(ang)
    const pos = Math.abs(x) < 50 ? (y < 0 ? 'top' : 'bottom') : x >= 0 ? 'right' : 'left'
    return {
      id: d.id,
      name: d.label,
      x,
      y,
      symbolSize: Math.max(26, Math.min(62, 20 + 6 * Math.sqrt(d.weight))),
      itemStyle: { color: meta.color, borderColor: 'rgba(251,247,238,0.25)', borderWidth: 1, shadowColor: meta.color, shadowBlur: 12 },
      label: {
        show: true,
        position: pos,
        color: '#EAF0F6',
        fontSize: 12,
        fontWeight: 600,
        formatter: (p: any) => (p.name.length > 8 ? p.name.slice(0, 8) + '…' : p.name),
      },
    }
  })
  return {
    tooltip: {
      trigger: 'item' as const,
      formatter: (p: any) => {
        const node = graphNodes.value.find((x) => x.id === p.data?.id)
        if (!node) return ''
        return `<b>${node.label}</b> <span style="color:${meta.color};font-size:12px">病证</span><div style="font-size:11px;color:#9FB2C8;margin-top:4px">被 ${node.weight} 条知识引用 · 点击展开知识网络</div>`
      },
    },
    animationDuration: 480,
    animationDurationUpdate: 480,
    animationEasingUpdate: 'cubicInOut' as const,
    series: [{ type: 'graph', layout: 'none', roam: true, draggable: false, data, links: [] }],
  }
}

function buildEgoOption() {
  const e = ego.value
  if (!e.focus) return { series: [] }

  const R = 260
  const n = e.shown.length || 1
  const fmeta = typeOf(e.focus.type)

  const eNodes: any[] = [
    {
      id: e.focus.id,
      name: e.focus.label,
      x: 0,
      y: 0,
      symbolSize: 62,
      itemStyle: { color: fmeta.color, borderColor: '#FBF7EE', borderWidth: 2.5, shadowColor: fmeta.color, shadowBlur: 26 },
      label: {
        show: true,
        position: 'inside',
        color: '#fff',
        fontWeight: 700,
        fontSize: 13,
        formatter: (p: any) => (p.name.length > 5 ? p.name.slice(0, 5) + '…' : p.name),
      },
      z: 10,
    },
  ]
  const eLinks: any[] = []

  e.shown.forEach((it, i) => {
    const ang = (-90 + (360 / n) * i) * (Math.PI / 180)
    const x = R * Math.cos(ang)
    const y = R * Math.sin(ang)
    const meta = typeOf(it.node.type)
    const pos = Math.abs(x) < 50 ? (y < 0 ? 'top' : 'bottom') : x >= 0 ? 'right' : 'left'
    eNodes.push({
      id: it.node.id,
      name: it.node.label,
      x,
      y,
      symbolSize: neighborSize(it.node.weight),
      itemStyle: { color: meta.color, borderColor: 'rgba(251,247,238,0.22)', borderWidth: 1 },
      label: {
        show: true,
        position: pos,
        color: '#D7E2EE',
        fontSize: 12,
        formatter: (p: any) => (p.name.length > 9 ? p.name.slice(0, 9) + '…' : p.name),
      },
    })
    eLinks.push({
      source: e.focus!.id,
      target: it.node.id,
      label: {
        show: true,
        formatter: it.relation,
        fontSize: 10,
        color: '#AFC0D4',
        backgroundColor: 'rgba(16,29,47,0.72)',
        padding: [1, 4],
        borderRadius: 3,
      },
      lineStyle: { color: relationColors[it.relation] || '#7C8BA0', width: 1.6, opacity: 0.5, curveness: 0 },
    })
  })

  return {
    tooltip: {
      trigger: 'item' as const,
      formatter: (p: any) => {
        if (p.dataType !== 'node') return ''
        const node = graphNodes.value.find((x) => x.id === p.data.id)
        if (!node) return ''
        const meta = typeOf(node.type)
        const isFocus = node.id === focusId.value
        return `<div style="max-width:240px"><b><span style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${meta.color};margin-right:6px"></span>${node.label}</b><span style="color:${meta.color};font-size:12px;margin-left:6px">${meta.label}</span><div style="font-size:11px;color:#9FB2C8;margin-top:4px">被 ${node.weight} 条知识引用 · ${isFocus ? '点击查看相关条目' : '点击聚焦此节点'}</div></div>`
      },
    },
    animationDuration: 480,
    animationDurationUpdate: 480,
    animationEasingUpdate: 'cubicInOut' as const,
    series: [
      {
        type: 'graph',
        layout: 'none',
        roam: true,
        draggable: false,
        data: eNodes,
        links: eLinks,
        lineStyle: { curveness: 0 },
        emphasis: { scale: 1.1, focus: 'adjacency' as const, lineStyle: { width: 2.6, opacity: 0.95 } },
      },
    ],
  }
}

function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
    chartInstance.on('click', (params: any) => {
      if (params.dataType !== 'node') return
      const id = params.data.id as string
      if (id === focusId.value) drillToSearch(id) // 点中心：刷新右侧条目
      else pivotTo(id) // 点邻居：以其为新中心
    })
  }
  chartInstance.setOption(buildOption(), true)
}

/* ---------- 聚焦导航 ---------- */
function drillToSearch(id: string) {
  const node = graphNodes.value.find((n) => n.id === id)
  if (!node) return
  activeFilter.value = 'all'
  searchQuery.value = node.label
}
function setFocus(id: string, drill = true) {
  focusId.value = id
  if (drill) drillToSearch(id)
  nextTick(() => renderChart())
}
function pivotTo(id: string) {
  if (focusId.value && focusId.value !== id) trail.value.push(focusId.value)
  setFocus(id)
}
function focusCrumb(i: number) {
  const id = trail.value[i]
  trail.value = trail.value.slice(0, i)
  setFocus(id, false)
}
function resetFocus() {
  trail.value = []
  focusId.value = null // 回到总览病证环
  nextTick(() => renderChart())
}
function crumbLabel(id: string): string {
  return id.length > 6 ? id.slice(0, 6) + '…' : id
}

function handleResize() {
  chartInstance?.resize()
}

/* ---------- 交互 ---------- */
function onFilterClick(key: string) {
  if (activeFilter.value === key) return
  activeFilter.value = key
  resetAndSearch()
}
function onResultClick(item: KbEntry) {
  expandedResultId.value = expandedResultId.value === item.id ? null : item.id
}
function showDetail(item: KbEntry) {
  detailEntry.value = item
  detailDialogVisible.value = true
}
function kbBadgeStyle(cat: string) {
  const c = kbCatColor[cat] || '#8896A6'
  return { backgroundColor: c + '18', color: c, border: `1px solid ${c}40` }
}

watch(selectedDisease, (d) => loadGraph(d))

onMounted(async () => {
  try {
    const { data } = await getKnowledgeStats()
    kbTotal.value = data.total || 0
  } catch { /* 忽略 */ }
  await nextTick()
  loadGraph()
  runSearch()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<template>
  <div class="kg-page">
    <!-- header -->
    <div class="kg-header">
      <h1 class="page-title">
        知识库与知识图谱
        <span class="page-subtitle">
          基于《本草纲目》等经典文献的中医知识网络
          <template v-if="kbTotal"> · 全库 {{ kbTotal }} 条</template>
          <template v-if="ego.focus"> · 聚焦「{{ ego.focus.label }}」· {{ ego.shown.length }} 个直接关联<template v-if="ego.hidden"> (+{{ ego.hidden }})</template></template>
          <template v-else-if="diseaseOptions.length"> · 总览 {{ diseaseOptions.length }} 个病证</template>
        </span>
      </h1>
    </div>

    <!-- toolbar -->
    <div class="kg-toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          placeholder="语义检索：输入症状、药材、方剂、证型…"
          :prefix-icon="Search"
          clearable
          class="search-input"
          size="large"
        />
        <el-select v-model="selectedDisease" placeholder="聚焦病证" clearable class="disease-select" size="large" filterable>
          <el-option v-for="opt in diseaseOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
      </div>
      <div class="toolbar-filters">
        <span
          v-for="tab in filterTabs"
          :key="tab.key"
          :class="['filter-pill', { active: activeFilter === tab.key }]"
          @click="onFilterClick(tab.key)"
        >{{ tab.label }}</span>
      </div>
    </div>

    <!-- body -->
    <div class="kg-body">
      <!-- graph -->
      <div class="kg-graph-panel navy-surface">
        <!-- 面包屑导航 -->
        <div v-if="ego.focus" class="graph-breadcrumb">
          <button class="crumb reset" @click="resetFocus">总览</button>
          <template v-for="(c, i) in trail" :key="c">
            <span class="crumb-sep">›</span>
            <button class="crumb" @click="focusCrumb(i)">{{ crumbLabel(c) }}</button>
          </template>
          <span class="crumb-sep">›</span>
          <span class="crumb current">{{ ego.focus.label }}</span>
          <span class="crumb-hint">点邻接节点聚焦展开 · 点中心看条目</span>
        </div>
        <!-- 总览态提示 -->
        <div v-else-if="graphNodes.length" class="graph-breadcrumb">
          <span class="crumb-hint" style="margin-left: 0">点击病证节点，展开其「治法 · 方剂 · 药材 · 证型」知识网络</span>
        </div>

        <div ref="chartRef" class="graph-container" />

        <div v-if="graphLoading" class="graph-overlay"><span class="loading-dot" /> 正在构建知识图谱…</div>
        <div v-else-if="graphError" class="graph-overlay err">{{ graphError }}</div>
        <div v-else-if="!graphNodes.length" class="graph-overlay">该病证暂无图谱数据</div>

        <!-- 图例 -->
        <div class="graph-legend">
          <span v-for="k in typeKeys" :key="k" class="lg-chip"><i :style="{ background: typeMeta[k].color }" />{{ typeMeta[k].label }}</span>
        </div>
        <div class="graph-watermark">李时珍智能医师 · 知识图谱</div>
      </div>

      <!-- results -->
      <div class="kg-results-panel">
        <div class="results-header">
          <span class="results-title">
            {{ searchQuery.trim() ? `「${searchQuery.trim()}」相关条目` : '检索结果' }}
          </span>
          <span class="results-count">共 {{ searchTotal }} 条</span>
        </div>

        <div ref="resultsListRef" class="results-list">
          <div v-if="searchLoading" class="results-loading"><span class="loading-dot" /> 检索中…</div>

          <div
            v-for="item in searchResults"
            :key="item.id"
            :class="['result-card card', { expanded: expandedResultId === item.id }]"
            @click="onResultClick(item)"
          >
            <div class="result-top">
              <span class="result-title">{{ item.title }}</span>
              <span class="result-badge" :style="kbBadgeStyle(item.category)">{{ item.category }}</span>
            </div>
            <div class="result-source">{{ sourceStr(item.source) }}</div>
            <div class="result-excerpt">{{ (item.plain_explanation || item.original_text || '').slice(0, 64) }}{{ (item.plain_explanation || item.original_text || '').length > 64 ? '…' : '' }}</div>

            <transition name="slide-detail">
              <div v-if="expandedResultId === item.id" class="result-detail">
                <p v-if="item.original_text" class="rd-orig">「{{ item.original_text.slice(0, 160) }}{{ item.original_text.length > 160 ? '…' : '' }}」</p>
                <p v-if="item.plain_explanation" class="rd-plain">{{ item.plain_explanation }}</p>
                <el-button size="small" type="primary" :icon="InfoFilled" @click.stop="showDetail(item)">查看完整条目</el-button>
              </div>
            </transition>
          </div>

          <div v-if="!searchLoading && searchResults.length === 0" class="results-empty">
            <el-empty description="未找到匹配的知识条目" :image-size="80" />
          </div>
        </div>

        <div v-if="searchTotal > PAGE_SIZE" class="results-pager">
          <el-pagination
            background
            layout="prev, pager, next"
            :total="searchTotal"
            :page-size="PAGE_SIZE"
            :current-page="searchPage"
            :pager-count="5"
            @current-change="onPageChange"
          />
        </div>
      </div>
    </div>

    <!-- detail dialog -->
    <el-dialog v-model="detailDialogVisible" :title="detailEntry?.title" width="560px" class="detail-dialog">
      <div v-if="detailEntry" class="detail-content">
        <div class="detail-meta">
          <span class="result-badge" :style="kbBadgeStyle(detailEntry.category)">{{ detailEntry.category }}</span>
          <span class="detail-source">{{ sourceStr(detailEntry.source) }}</span>
        </div>
        <div v-if="detailEntry.original_text" class="detail-block">
          <div class="detail-label">原文摘录</div>
          <p class="detail-orig">「{{ detailEntry.original_text }}」</p>
        </div>
        <div v-if="detailEntry.plain_explanation" class="detail-block">
          <div class="detail-label">白话释义</div>
          <p class="detail-text">{{ detailEntry.plain_explanation }}</p>
        </div>
        <div
          v-if="(detailEntry.related_diseases?.length || detailEntry.related_syndromes?.length || detailEntry.treatment_method || detailEntry.formula?.name)"
          class="detail-relations"
        >
          <h4>关联知识</h4>
          <div class="relation-tags">
            <el-tag v-for="d in detailEntry.related_diseases || []" :key="'d' + d" size="small" :style="kbBadgeStyle('法')" class="relation-tag">病证 · {{ d }}</el-tag>
            <el-tag v-for="s in detailEntry.related_syndromes || []" :key="'s' + s" size="small" :style="kbBadgeStyle('养生')" class="relation-tag">证型 · {{ s }}</el-tag>
            <el-tag v-if="detailEntry.treatment_method" size="small" :style="kbBadgeStyle('理')" class="relation-tag">治法 · {{ detailEntry.treatment_method }}</el-tag>
            <el-tag v-if="detailEntry.formula?.name" size="small" :style="kbBadgeStyle('方')" class="relation-tag">方剂 · {{ detailEntry.formula.name }}</el-tag>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.kg-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  min-height: 600px;
}

.kg-header { flex-shrink: 0; }
.kg-header .page-title { margin-bottom: 0; display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap; }

/* toolbar */
.kg-toolbar { flex-shrink: 0; display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.toolbar-left { display: flex; gap: 12px; flex: 1; min-width: 320px; }
.search-input { flex: 1; max-width: 440px; }
.search-input :deep(.el-input__wrapper) { border-radius: 20px; box-shadow: 0 2px 8px rgba(31, 58, 95, 0.06); }
.search-input :deep(.el-input__wrapper:focus-within) { box-shadow: 0 2px 12px rgba(31, 58, 95, 0.12); }
.disease-select { width: 160px; }
.disease-select :deep(.el-input__wrapper) { border-radius: 20px; }

.toolbar-filters { display: flex; gap: 8px; flex-shrink: 0; }
.filter-pill {
  padding: 6px 18px;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.25s;
  background: var(--paper-card);
  color: var(--ink-2);
  border: 1px solid #e5e7eb;
  user-select: none;
}
.filter-pill:hover { color: var(--ink); border-color: var(--gold); background: rgba(31, 58, 95, 0.04); }
.filter-pill.active { background: var(--ink); color: white; border-color: var(--ink); box-shadow: 0 2px 8px rgba(31, 58, 95, 0.2); }

/* body */
.kg-body { flex: 1; display: flex; gap: 16px; min-height: 0; }

/* graph */
.kg-graph-panel { flex: 65; position: relative; overflow: hidden; padding: 0; border-radius: var(--radius); }
.graph-container { width: 100%; height: 100%; min-height: 500px; }
.graph-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: #9fb2c8;
  font-size: 14px;
  pointer-events: none;
}
.graph-overlay.err { color: #e8a0a0; }
.graph-watermark { position: absolute; bottom: 12px; right: 16px; font-size: 11px; color: rgba(234, 240, 246, 0.25); pointer-events: none; letter-spacing: 1px; }

/* 面包屑导航 */
.graph-breadcrumb {
  position: absolute;
  top: 12px;
  left: 14px;
  right: 14px;
  z-index: 3;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
}
.crumb {
  background: rgba(36, 64, 95, 0.7);
  color: #d7e2ee;
  border: 1px solid rgba(159, 178, 200, 0.25);
  border-radius: 12px;
  padding: 3px 11px;
  cursor: pointer;
  font-size: 12px;
  font-family: var(--font-sans);
  transition: all 0.2s;
}
.crumb:hover { background: rgba(95, 168, 192, 0.35); color: #fff; }
.crumb.reset { color: #d9b877; border-color: rgba(200, 164, 92, 0.45); }
.crumb.current { background: #9a2d2d; color: #fbf7ee; border-color: transparent; cursor: default; font-weight: 600; }
.crumb.current:hover { background: #9a2d2d; }
.crumb-sep { color: rgba(159, 178, 200, 0.5); }
.crumb-hint { margin-left: auto; color: rgba(159, 178, 200, 0.5); font-size: 11px; }

/* 图例 */
.graph-legend {
  position: absolute;
  bottom: 12px;
  left: 16px;
  z-index: 3;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  pointer-events: none;
}
.lg-chip { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: #9fb2c8; }
.lg-chip i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }

.loading-dot { width: 8px; height: 8px; border-radius: 50%; background: #5fb3a1; animation: pulse 1s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1.2); } }

/* results */
.kg-results-panel { flex: 35; display: flex; flex-direction: column; min-height: 0; }
.results-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-shrink: 0; }
.results-title { font-size: 16px; font-weight: 600; color: var(--ink); }
.results-count { font-size: 12px; color: var(--ink-2); background: var(--paper-sunken); padding: 2px 10px; border-radius: 10px; }

.results-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding-right: 4px; }
.results-loading { display: flex; align-items: center; gap: 8px; color: var(--ink-2); font-size: 13px; padding: 12px 2px; }

.result-card { padding: 14px 16px; cursor: pointer; border-radius: var(--radius-sm); border: 1px solid transparent; transition: all 0.25s; }
.result-card:hover { transform: translateY(-1px); border-color: rgba(31, 58, 95, 0.1); }
.result-card.expanded { border-color: var(--gold); }

.result-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.result-title { font-size: 15px; font-weight: 600; color: var(--ink); }
.result-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 500; white-space: nowrap; }
.result-source { font-size: 11px; color: var(--ink-2); margin-bottom: 6px; }
.result-excerpt { font-size: 13px; color: var(--ink-2); line-height: 1.6; }

.result-detail { margin-top: 12px; padding-top: 12px; border-top: 1px dashed #e5e7eb; }
.rd-orig { font-family: var(--font-serif); font-size: 13px; line-height: 1.8; color: var(--ink); background: var(--paper-sunken); padding: 10px 12px; border-radius: var(--radius-sm); margin-bottom: 8px; }
.rd-plain { font-size: 13px; line-height: 1.8; color: var(--ink-2); margin-bottom: 10px; }

.slide-detail-enter-active, .slide-detail-leave-active { transition: all 0.3s ease; overflow: hidden; }
.slide-detail-enter-from, .slide-detail-leave-to { opacity: 0; max-height: 0; }
.slide-detail-enter-to, .slide-detail-leave-from { opacity: 1; max-height: 400px; }

.results-empty { flex: 1; display: flex; align-items: center; justify-content: center; }

.results-pager { flex-shrink: 0; display: flex; justify-content: center; padding-top: 12px; margin-top: 4px; border-top: 1px solid rgba(31, 58, 95, 0.06); }

/* dialog */
.detail-meta { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.detail-source { font-size: 12px; color: var(--ink-2); }
.detail-block { margin-bottom: 14px; }
.detail-label { font-size: 12px; color: var(--ink-2); margin-bottom: 6px; padding-left: 8px; border-left: 3px solid var(--gold); }
.detail-orig { font-family: var(--font-serif); font-size: 15px; line-height: 1.9; color: var(--ink); background: var(--paper-sunken); padding: 12px 14px; border-radius: var(--radius-sm); }
.detail-text { font-size: 14px; line-height: 1.9; color: var(--ink); }
.detail-relations h4 { font-size: 14px; font-weight: 600; color: var(--ink); margin: 16px 0 10px; }
.relation-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.relation-tag { font-size: 12px; }

@media (max-width: 900px) {
  .kg-body { flex-direction: column; }
  .kg-graph-panel { flex: none; height: 420px; }
  .kg-results-panel { flex: none; }
}
</style>
