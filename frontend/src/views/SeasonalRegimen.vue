<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import GfIcon from '../components/GfIcon.vue'
import { getSeasonalRegimen } from '../api'

// —— 轮盘静态骨架（颜色/季名先于接口渲染，内容走 API）——
// 顺时针自顶端：春(木·上) → 夏(火·右) → 秋(金·下) → 冬(水·左)
const wheelMeta = [
  { key: 'spring', cn: '春', color: '#5B8C5A', mid: 0, element: '木', organ: '肝' },
  { key: 'summer', cn: '夏', color: '#C0504D', mid: 90, element: '火', organ: '心' },
  { key: 'autumn', cn: '秋', color: '#C8A45C', mid: 180, element: '金', organ: '肺' },
  { key: 'winter', cn: '冬', color: '#3A5A85', mid: 270, element: '水', organ: '肾' },
]

// —— 几何：0°=正上方，顺时针递增 ——
const CX = 130
const CY = 130
const R_OUT = 118
const R_IN = 58
const HALF = 42 // 每扇半角（留 6° 缝隙）

function polar(r: number, deg: number): [number, number] {
  const rad = ((deg - 90) * Math.PI) / 180
  return [CX + r * Math.cos(rad), CY + r * Math.sin(rad)]
}

function sectorPath(mid: number): string {
  const a1 = mid - HALF
  const a2 = mid + HALF
  const [x1o, y1o] = polar(R_OUT, a1)
  const [x2o, y2o] = polar(R_OUT, a2)
  const [x2i, y2i] = polar(R_IN, a2)
  const [x1i, y1i] = polar(R_IN, a1)
  return `M ${x1o} ${y1o} A ${R_OUT} ${R_OUT} 0 0 1 ${x2o} ${y2o} L ${x2i} ${y2i} A ${R_IN} ${R_IN} 0 0 0 ${x1i} ${y1i} Z`
}

const wheelSectors = computed(() =>
  wheelMeta.map((s) => {
    const [lx, ly] = polar((R_IN + R_OUT) / 2, s.mid)
    const [ox, oy] = polar(7, s.mid) // 选中外移向量
    return { ...s, path: sectorPath(s.mid), lx, ly, dx: ox - CX, dy: oy - CY }
  }),
)

// —— 当前季节：默认按今日月份推当季（顺应四时）——
function seasonByMonth(m: number): string {
  if (m >= 3 && m <= 5) return 'spring'
  if (m >= 6 && m <= 8) return 'summer'
  if (m >= 9 && m <= 11) return 'autumn'
  return 'winter'
}

const activeSeason = ref(seasonByMonth(new Date().getMonth() + 1))
const activeMeta = computed(() => wheelMeta.find((s) => s.key === activeSeason.value)!)
const pointerAngle = computed(() => activeMeta.value.mid)

// —— 接口数据（按季缓存，避免重复请求）——
interface Advice { content: string; source: string }
interface SeasonData {
  title: string
  color: string
  element?: string
  organ?: string
  principle: string
  principle_source: string
  quote: string
  advices: Record<string, Advice>
}

const cache = ref<Record<string, SeasonData>>({})
const current = computed<SeasonData | null>(() => cache.value[activeSeason.value] ?? null)
const loading = ref(false)
const error = ref('')
const disclaimer = ref('')
const activeTab = ref('起居')

async function loadSeason(key: string) {
  if (cache.value[key]) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await getSeasonalRegimen(key)
    cache.value[key] = data.data as SeasonData
    if (data.disclaimer) disclaimer.value = data.disclaimer
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '养生数据加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function selectSeason(key: string) {
  activeSeason.value = key
}

watch(activeSeason, (key) => loadSeason(key), { immediate: false })
onMounted(() => loadSeason(activeSeason.value))
</script>

<template>
  <div class="seasonal-page">
    <h2 class="page-title">四时养生</h2>
    <p class="page-subtitle">顺应四时节律，调和阴阳气血 · 据《本草纲目》四时用药例</p>

    <div class="seasonal-layout">
      <!-- 左：径向四季轮盘 -->
      <div class="wheel-section">
        <svg class="season-wheel" viewBox="0 0 260 260" role="group" aria-label="四季养生轮盘">
          <!-- 外环装饰 -->
          <circle :cx="CX" :cy="CY" :r="R_OUT + 6" class="wheel-ring" />
          <!-- 四季扇形 -->
          <g
            v-for="s in wheelSectors"
            :key="s.key"
            class="sector-group"
            :class="{ active: activeSeason === s.key }"
            :style="activeSeason === s.key ? { transform: `translate(${s.dx * 0.06}px, ${s.dy * 0.06}px)` } : {}"
            @click="selectSeason(s.key)"
          >
            <path
              :d="s.path"
              class="sector-path"
              :style="{ fill: s.color, fillOpacity: activeSeason === s.key ? 1 : 0.14, stroke: s.color }"
            />
            <text
              :x="s.lx"
              :y="s.ly"
              class="sector-label"
              :style="{ fill: activeSeason === s.key ? '#FBF7EE' : s.color }"
            >{{ s.cn }}</text>
          </g>
          <!-- 中心指针（旋转指向当季）-->
          <g
            class="pointer"
            :style="{ transform: `rotate(${pointerAngle}deg)`, transformOrigin: `${CX}px ${CY}px` }"
          >
            <polygon
              :points="`${CX - 7},${CY} ${CX + 7},${CY} ${CX},${CY - R_IN + 6}`"
              :style="{ fill: activeMeta.color }"
            />
          </g>
          <!-- 中心圆 -->
          <circle :cx="CX" :cy="CY" :r="R_IN - 14" class="wheel-hub" />
          <text :x="CX" :y="CY - 4" class="hub-season" :style="{ fill: activeMeta.color }">
            {{ activeMeta.cn }}
          </text>
          <text :x="CX" :y="CY + 16" class="hub-meta">{{ activeMeta.element }}·{{ activeMeta.organ }}</text>
        </svg>
        <p class="wheel-hint">点击四季查看当季养生 · 已自动定位当令</p>
      </div>

      <!-- 右：养生详情 -->
      <div class="detail-section">
        <!-- 加载/错误态 -->
        <div v-if="loading && !current" class="state-block">
          <span class="loading-dot" /> 正在调取「{{ activeMeta.cn }}季」养生方……
        </div>
        <el-alert
          v-else-if="error && !current"
          :title="error"
          type="error"
          :closable="false"
          show-icon
        />

        <template v-if="current">
          <!-- 内经四气调神原则 -->
          <el-card class="principle-card" :style="{ borderLeftColor: activeMeta.color }">
            <div class="principle-head" :style="{ color: activeMeta.color }">{{ current.title }}</div>
            <div class="principle-text">「{{ current.principle }}」</div>
            <div class="principle-source">—— {{ current.principle_source }}</div>
          </el-card>

          <!-- 李时珍论养生 引文 -->
          <div class="lsz-quote" :style="{ borderColor: activeMeta.color }">
            <div class="lsz-seal" :style="{ background: activeMeta.color }">李时珍曰</div>
            <p class="lsz-text">{{ current.quote }}</p>
          </div>

          <!-- 起居 / 膳食 / 情志 / 功法 -->
          <el-tabs v-model="activeTab" class="season-tabs">
            <el-tab-pane
              v-for="(adv, name) in current.advices"
              :key="name"
              :name="String(name)"
            >
              <template #label>
                <span class="tab-label">
                  <span class="tab-seal" :style="{ borderColor: activeMeta.color, color: activeMeta.color }">
                    {{ String(name).charAt(0) }}
                  </span>
                  {{ name }}
                </span>
              </template>
              <div class="tab-content">
                <p class="content-text">{{ adv.content }}</p>
                <div class="source-tag">
                  <GfIcon name="book" :size="14" class="source-icon" />
                  {{ adv.source }}
                </div>
              </div>
            </el-tab-pane>
          </el-tabs>

          <p v-if="disclaimer" class="regimen-disclaimer">{{ disclaimer }}</p>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.seasonal-page {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.seasonal-layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  grid-template-rows: minmax(0, 1fr);
  gap: 32px;
  margin-top: 24px;
  align-items: start;
  flex: 1;
  min-height: 0;
}

.detail-section {
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  height: 100%;
}

/* —— 径向轮盘 —— */
.wheel-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: sticky;
  top: 0;
}

.season-wheel {
  width: 340px;
  height: 340px;
  user-select: none;
}

.wheel-ring {
  fill: var(--paper-card);
  stroke: var(--border-paper);
  stroke-width: 1;
}

.sector-group {
  cursor: pointer;
  transition: transform 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}

.sector-path {
  stroke-width: 1.5;
  transition: fill-opacity 0.4s ease;
}

.sector-group:hover .sector-path {
  fill-opacity: 0.4 !important;
}

.sector-label {
  font-family: var(--font-serif);
  font-size: 34px;
  font-weight: 700;
  text-anchor: middle;
  dominant-baseline: central;
  pointer-events: none;
  transition: fill 0.4s ease;
}

.pointer {
  transition: transform 0.55s cubic-bezier(0.22, 1, 0.36, 1);
}

.pointer polygon {
  opacity: 0.85;
}

.wheel-hub {
  fill: var(--paper-card);
  stroke: var(--border-paper);
  stroke-width: 1.5;
}

.hub-season {
  font-family: var(--font-serif);
  font-size: 30px;
  font-weight: 700;
  text-anchor: middle;
  dominant-baseline: central;
}

.hub-meta {
  font-size: 12px;
  fill: var(--ink-2);
  text-anchor: middle;
  dominant-baseline: central;
  letter-spacing: 1px;
}

.wheel-hint {
  margin-top: 14px;
  font-size: 12px;
  color: var(--ink-2);
}

/* —— 详情 —— */
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

.principle-card {
  border-left: 4px solid;
  margin-bottom: 16px;
}

.principle-head {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 10px;
}

.principle-text {
  font-size: 16px;
  color: var(--ink);
  line-height: 1.9;
}

.principle-source {
  font-size: 12px;
  color: var(--ink-2);
  text-align: right;
  margin-top: 8px;
}

/* 李时珍引文 */
.lsz-quote {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  margin-bottom: 20px;
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
  line-height: 1.2;
}

.lsz-text {
  font-family: var(--font-serif);
  font-size: 15px;
  color: var(--ink);
  line-height: 1.8;
  font-style: italic;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.tab-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: 1px solid;
  border-radius: 4px;
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 700;
}

.tab-content {
  padding-top: 6px;
}

.content-text {
  font-size: 15px;
  line-height: 1.95;
  color: var(--ink);
}

.source-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 16px;
  padding: 6px 12px;
  background: #fff8e1;
  border-radius: 20px;
  font-size: 12px;
  color: var(--gold);
}

.source-icon {
  flex-shrink: 0;
}

.regimen-disclaimer {
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-paper);
  font-size: 12px;
  color: var(--ink-2);
  line-height: 1.6;
}

@media (max-width: 768px) {
  .seasonal-layout {
    grid-template-columns: 1fr;
    grid-template-rows: none;
    flex: none;
    min-height: 0;
  }
  .wheel-section {
    position: static;
  }
  .detail-section {
    overflow: visible;
    padding-right: 0;
    height: auto;
  }
}
</style>
