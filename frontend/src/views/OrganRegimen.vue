<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import GfIcon from '../components/GfIcon.vue'
import { getOrganRegimen } from '../api'

// —— 五脏静态骨架（解剖位置 + 五行，先于接口渲染）——
const organMeta = [
  { key: 'heart', cn: '心', element: '火', color: '#C0504D', pos: { top: '15%', left: '50%' } },
  { key: 'liver', cn: '肝', element: '木', color: '#5B8C5A', pos: { top: '35%', left: '28%' } },
  { key: 'spleen', cn: '脾', element: '土', color: '#C8A45C', pos: { top: '55%', left: '50%' } },
  { key: 'lung', cn: '肺', element: '金', color: '#34505C', pos: { top: '35%', left: '72%' } },
  { key: 'kidney', cn: '肾', element: '水', color: '#1F3A5F', pos: { top: '75%', left: '50%' } },
]

// —— 五行生克 ——
const SHENG = ['木', '火', '土', '金', '水'] // 相生序：木生火→火生土→…→水生木
const EL2ORGAN: Record<string, string> = { 木: 'liver', 火: 'heart', 土: 'spleen', 金: 'lung', 水: 'kidney' }

// SVG 坐标（viewBox 400×500，与百分比定位对齐）
const POS: Record<string, { x: number; y: number }> = {
  heart: { x: 200, y: 75 },
  liver: { x: 112, y: 175 },
  spleen: { x: 200, y: 275 },
  lung: { x: 288, y: 175 },
  kidney: { x: 200, y: 375 },
}
const NODE_R = 47

function shorten(a: { x: number; y: number }, b: { x: number; y: number }, r: number) {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  return { x: a.x + (dx / len) * r, y: a.y + (dy / len) * r }
}

const activeOrgan = ref('')

// 选中脏腑的四条关系：生我 / 我生 / 克我 / 我克
const relationLines = computed(() => {
  const sel = organMeta.find((o) => o.key === activeOrgan.value)
  if (!sel) return []
  const i = SHENG.indexOf(sel.element)
  const defs = [
    { rel: '我生', type: 'sheng', label: '生', from: sel.element, to: SHENG[(i + 1) % 5] },
    { rel: '生我', type: 'sheng', label: '生', from: SHENG[(i + 4) % 5], to: sel.element },
    { rel: '我克', type: 'ke', label: '克', from: sel.element, to: SHENG[(i + 2) % 5] },
    { rel: '克我', type: 'ke', label: '克', from: SHENG[(i + 3) % 5], to: sel.element },
  ]
  return defs.map((d) => {
    const fromKey = EL2ORGAN[d.from]
    const toKey = EL2ORGAN[d.to]
    const s = shorten(POS[fromKey], POS[toKey], NODE_R)
    const e = shorten(POS[toKey], POS[fromKey], NODE_R)
    return {
      ...d,
      fromKey,
      toKey,
      x1: s.x,
      y1: s.y,
      x2: e.x,
      y2: e.y,
      mx: (s.x + e.x) / 2,
      my: (s.y + e.y) / 2,
    }
  })
})

// —— 接口数据（按脏缓存）——
interface NamedItem { name: string; desc: string; source: string }
interface OrganData {
  title: string
  color: string
  element?: string
  function: string
  quote: string
  quote_source: string
  diet: NamedItem[]
  herbal: NamedItem[]
  herbs: string[]
  solar_term: { content: string; source: string }
}

const cache = ref<Record<string, OrganData>>({})
const current = computed<OrganData | null>(() =>
  activeOrgan.value ? cache.value[activeOrgan.value] ?? null : null,
)
const activeMeta = computed(() => organMeta.find((o) => o.key === activeOrgan.value) ?? null)
const loading = ref(false)
const error = ref('')
const disclaimer = ref('')

async function loadOrgan(key: string) {
  if (cache.value[key]) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await getOrganRegimen(key)
    cache.value[key] = data.data as OrganData
    if (data.disclaimer) disclaimer.value = data.disclaimer
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '调养数据加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function selectOrgan(key: string) {
  activeOrgan.value = key
}

watch(activeOrgan, (key) => key && loadOrgan(key))
</script>

<template>
  <div class="organ-page">
    <h2 class="page-title">五脏调养</h2>
    <p class="page-subtitle">心肝脾肺肾五脏调护 · 据五行生克 · 食疗药膳养生</p>

    <div class="organ-layout">
      <!-- 左：人体五脏图 + 五行生克关系线 -->
      <div class="body-section">
        <div class="body-map">
          <svg class="body-lines" viewBox="0 0 400 500">
            <defs>
              <marker id="arrow-sheng" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0 L10 5 L0 10 z" fill="#3E9A85" />
              </marker>
              <marker id="arrow-ke" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M0 0 L10 5 L0 10 z" fill="#9A2D2D" />
              </marker>
            </defs>
            <template v-for="(l, i) in relationLines" :key="i">
              <line
                :x1="l.x1" :y1="l.y1" :x2="l.x2" :y2="l.y2"
                :class="['rel-line', l.type]"
                :marker-end="`url(#arrow-${l.type})`"
              />
              <g class="rel-label">
                <circle :cx="l.mx" :cy="l.my" r="11" :class="l.type" />
                <text :x="l.mx" :y="l.my">{{ l.label }}</text>
              </g>
            </template>
          </svg>
          <div
            v-for="organ in organMeta"
            :key="organ.key"
            class="organ-btn"
            :class="{
              active: activeOrgan === organ.key,
              related: activeOrgan && activeOrgan !== organ.key,
            }"
            :style="{ top: organ.pos.top, left: organ.pos.left, '--organ-color': organ.color }"
            @click="selectOrgan(organ.key)"
          >
            <span class="organ-seal">{{ organ.cn }}</span>
            <span class="organ-element">{{ organ.element }}</span>
          </div>
        </div>
        <div class="map-legend">
          <span class="lg-item"><span class="lg-line sheng" />相生</span>
          <span class="lg-item"><span class="lg-line ke" />相克</span>
          <span class="lg-hint">点击脏腑查看调养方案与五行生克</span>
        </div>
      </div>

      <!-- 右：详情 -->
      <div class="detail-section">
        <!-- 加载/错误 -->
        <div v-if="loading && !current" class="state-block">
          <span class="loading-dot" /> 正在调取「{{ activeMeta?.cn }}」调养方……
        </div>
        <el-alert
          v-else-if="error && !current"
          :title="error"
          type="error"
          :closable="false"
          show-icon
        />

        <el-card
          v-else-if="current && activeMeta"
          class="organ-card"
          :style="{ borderTopColor: activeMeta.color }"
        >
          <template #header>
            <div class="card-header">
              <span class="organ-big-seal" :style="{ background: activeMeta.color }">{{ activeMeta.cn }}</span>
              <div>
                <h3>{{ current.title }}<span class="el-badge" :style="{ color: activeMeta.color }">　{{ activeMeta.element }}</span></h3>
                <p class="organ-func">{{ current.function }}</p>
              </div>
            </div>
          </template>

          <!-- 经典引文 -->
          <div class="lsz-quote" :style="{ borderColor: activeMeta.color }">
            <div class="lsz-seal" :style="{ background: activeMeta.color }">经典</div>
            <div>
              <p class="lsz-text">{{ current.quote }}</p>
              <p class="lsz-source">—— {{ current.quote_source }}</p>
            </div>
          </div>

          <!-- 食疗 -->
          <h4 class="section-title">食疗</h4>
          <div v-for="(d, i) in current.diet" :key="'d' + i" class="diet-item">
            <div class="diet-name">{{ d.name }}</div>
            <div class="diet-desc">{{ d.desc }}</div>
            <div class="source-tag"><GfIcon name="book" :size="13" /> {{ d.source }}</div>
          </div>

          <!-- 药膳 -->
          <h4 class="section-title">药膳</h4>
          <div v-for="(h, i) in current.herbal" :key="'h' + i" class="diet-item">
            <div class="diet-name">{{ h.name }}</div>
            <div class="diet-desc">{{ h.desc }}</div>
            <div class="source-tag"><GfIcon name="book" :size="13" /> {{ h.source }}</div>
          </div>

          <!-- 常用药材 -->
          <h4 class="section-title">常用调养药材</h4>
          <div class="herb-tags">
            <el-tag
              v-for="herb in current.herbs"
              :key="herb"
              :color="activeMeta.color"
              effect="dark"
              round
            >{{ herb }}</el-tag>
          </div>

          <!-- 节气养生 -->
          <h4 class="section-title">节气养生</h4>
          <div class="solar-block" :style="{ borderLeftColor: activeMeta.color }">
            <p class="content-text">{{ current.solar_term.content }}</p>
            <div class="source-tag"><GfIcon name="book" :size="13" /> {{ current.solar_term.source }}</div>
          </div>

          <p v-if="disclaimer" class="regimen-disclaimer">{{ disclaimer }}</p>
        </el-card>

        <!-- 未选择 -->
        <div v-else class="placeholder-section">
          <div class="placeholder-content">
            <div class="placeholder-icon"><GfIcon name="organ" :size="64" /></div>
            <p>请点击左侧脏腑印章</p>
            <p>查看对应的调养方案与五行生克关系</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.organ-page {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.organ-layout {
  display: grid;
  grid-template-columns: 400px 1fr;
  grid-template-rows: minmax(0, 1fr);
  gap: 32px;
  margin-top: 24px;
  flex: 1;
  min-height: 0;
}

/* —— 五脏图 —— */
.body-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: sticky;
  top: 0;
}

.body-map {
  position: relative;
  width: 400px;
  height: 500px;
  background: var(--paper-card);
  border: 1px solid var(--border-paper);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

.body-lines {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.rel-line {
  stroke-width: 2;
  transition: opacity 0.3s;
}
.rel-line.sheng { stroke: #3E9A85; }
.rel-line.ke { stroke: #9A2D2D; stroke-dasharray: 6 5; }

.rel-label circle {
  stroke: var(--paper-card);
  stroke-width: 2;
}
.rel-label circle.sheng { fill: #3E9A85; }
.rel-label circle.ke { fill: #9A2D2D; }
.rel-label text {
  font-family: var(--font-serif);
  font-size: 12px;
  font-weight: 700;
  fill: #fff;
  text-anchor: middle;
  dominant-baseline: central;
}

.organ-btn {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: var(--paper-card);
  border: 2px solid var(--border-paper);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  z-index: 2;
}

.organ-seal {
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 700;
  color: var(--organ-color);
  line-height: 1;
  transition: color 0.3s ease;
}

.organ-element {
  font-size: 11px;
  color: var(--ink-2);
  margin-top: 2px;
  transition: color 0.3s ease;
}

.organ-btn.related {
  border-color: var(--organ-color);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--organ-color) 18%, transparent);
}

.organ-btn:hover,
.organ-btn.active {
  border-color: var(--organ-color);
  background: var(--organ-color);
  transform: translate(-50%, -50%) scale(1.12);
  box-shadow: 0 6px 18px rgba(31, 27, 22, 0.22);
}

.organ-btn:hover .organ-seal,
.organ-btn.active .organ-seal,
.organ-btn:hover .organ-element,
.organ-btn.active .organ-element {
  color: #fbf7ee;
}

.map-legend {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 14px;
  font-size: 12px;
  color: var(--ink-2);
  flex-wrap: wrap;
  justify-content: center;
}
.lg-item { display: inline-flex; align-items: center; gap: 6px; }
.lg-line { width: 22px; height: 0; border-top-width: 2px; border-top-style: solid; }
.lg-line.sheng { border-color: #3E9A85; }
.lg-line.ke { border-color: #9A2D2D; border-top-style: dashed; }
.lg-hint { color: var(--ink-3, var(--ink-2)); }

/* —— 详情 —— */
.detail-section {
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  height: 100%;
}

.state-block {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 32px 4px;
  color: var(--ink-2);
  font-size: 14px;
}
.loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--cinnabar, #9a2d2d);
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.organ-card {
  border-top: 4px solid;
  background: var(--paper-card);
}

.card-header { display: flex; align-items: center; gap: 14px; }

.organ-big-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 10px;
  color: #fbf7ee;
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  box-shadow: inset 0 0 0 1px rgba(251, 247, 238, 0.3);
  flex-shrink: 0;
}

.card-header h3 { font-size: 20px; color: var(--ink); }
.el-badge { font-size: 14px; font-weight: 400; }
.organ-func { font-size: 14px; color: var(--ink-2); margin-top: 4px; line-height: 1.6; }

/* 经典引文 */
.lsz-quote {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  margin: 16px 0 4px;
  background: #fff8e1;
  border-left: 3px solid;
  border-radius: var(--radius);
}
.lsz-seal {
  flex-shrink: 0;
  font-family: var(--font-serif);
  font-size: 13px;
  font-weight: 700;
  color: #fbf7ee;
  padding: 6px 8px;
  border-radius: 4px;
  writing-mode: vertical-rl;
  letter-spacing: 2px;
}
.lsz-text { font-family: var(--font-serif); font-size: 15px; color: var(--ink); line-height: 1.8; font-style: italic; }
.lsz-source { font-size: 12px; color: var(--ink-2); margin-top: 4px; }

.section-title {
  font-size: 16px;
  color: var(--ink);
  margin: 22px 0 12px;
  padding-left: 10px;
  border-left: 3px solid var(--gold);
}

.diet-item {
  padding: 12px 14px;
  background: var(--paper-sunken);
  border-radius: var(--radius-sm);
  margin-bottom: 10px;
}
.diet-name { font-weight: 600; color: var(--ink); margin-bottom: 4px; }
.diet-desc { font-size: 14px; color: var(--ink-2); line-height: 1.7; }

.source-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--cinnabar);
  margin-top: 6px;
}

.herb-tags { display: flex; flex-wrap: wrap; gap: 8px; }

.solar-block {
  padding: 12px 14px;
  background: var(--paper-sunken);
  border-left: 3px solid;
  border-radius: var(--radius-sm);
}
.content-text { font-size: 14px; line-height: 1.8; color: var(--ink); }

.regimen-disclaimer {
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-paper);
  font-size: 12px;
  color: var(--ink-2);
  line-height: 1.6;
}

.placeholder-section {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}
.placeholder-content { text-align: center; color: var(--ink-2); line-height: 1.9; }
.placeholder-icon { color: var(--gold); opacity: 0.7; margin-bottom: 16px; }

@media (max-width: 768px) {
  .organ-layout {
    grid-template-columns: 1fr;
    grid-template-rows: none;
    flex: none;
    min-height: 0;
  }
  .body-section { position: static; }
  .detail-section { overflow: visible; padding-right: 0; height: auto; }
  .body-map { width: 100%; max-width: 360px; }
}
</style>
