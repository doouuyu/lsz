<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import GfIcon from '../components/GfIcon.vue'
import { getKnowledgeStats } from '../api'

const router = useRouter()

const features = [
  { path: '/diagnose', icon: 'diagnose', title: '仿真辨证', desc: '智能四诊合参，八步思维链辨证分析' },
  { path: '/regimen/seasonal', icon: 'seasonal', title: '四时养生', desc: '春夏秋冬养生指导，顺应天时' },
  { path: '/regimen/organ', icon: 'organ', title: '五脏调养', desc: '心肝脾肺肾调养方案，食疗药膳' },
  { path: '/chronic', icon: 'chronic', title: '慢病助手', desc: '老年慢病一键辨证，基层适配' },
  { path: '/knowledge', icon: 'knowledge', title: '知识图谱', desc: '知识条目检索，可视化关系网络' },
]

const stats = ref([
  { label: '知识条目', value: 2000, suffix: '+' },
  { label: '覆盖病证', value: 16, suffix: '' },
  { label: '药材收录', value: 1477, suffix: '' },
  { label: '文献溯源', value: 98, suffix: '%' },
])

const animatedValues = ref(stats.value.map(() => 0))

function animateStats() {
  stats.value.forEach((stat, i) => {
    const target = stat.value
    const duration = 1500
    const step = target / (duration / 16)
    const timer = setInterval(() => {
      animatedValues.value[i] = Math.min(animatedValues.value[i] + step, target)
      if (animatedValues.value[i] >= target) {
        animatedValues.value[i] = target
        clearInterval(timer)
      }
    }, 16)
  })
}

onMounted(async () => {
  try {
    const res = await getKnowledgeStats()
    const d = res.data
    const total = d.total || 2000
    const diseaseCount = Object.keys(d.by_category || {}).length > 0 ? 16 : 15
    stats.value = [
      { label: '知识条目', value: total, suffix: '' },
      { label: '覆盖病证', value: diseaseCount, suffix: '' },
      { label: '药材收录', value: 1477, suffix: '' },
      { label: '文献溯源', value: 98, suffix: '%' },
    ]
  } catch {
    // 后端不可用时保持默认值
  }
  animateStats()
})

const archLayers = [
  { label: '经典文献', desc: '《本草纲目》1477个药材条目', icon: 'book' },
  { label: '向量化', desc: '语义嵌入 + BM25混合索引', icon: 'vector' },
  { label: 'RAG引擎', desc: '检索增强生成，知识溯源', icon: 'engine' },
  { label: '辨证输出', desc: '八步思维链结构化诊断', icon: 'output' },
]
</script>

<template>
  <div class="dashboard">
    <!-- Hero区（古籍面） -->
    <section class="hero">
      <div class="hero-stamp">本草</div>
      <h1 class="hero-title">传承千年智慧 · 赋能现代医疗</h1>
      <p class="hero-subtitle">基于检索增强生成的李时珍老年病智能辨证系统</p>
    </section>

    <!-- 架构流程图（藏青数据面） -->
    <section class="arch-flow navy-surface">
      <div class="arch-flow-title">平台技术架构</div>
      <div class="arch-track">
        <template v-for="(layer, i) in archLayers" :key="i">
          <div class="arch-item">
            <div class="arch-icon"><GfIcon :name="layer.icon" :size="30" /></div>
            <div class="arch-label">{{ layer.label }}</div>
            <div class="arch-desc">{{ layer.desc }}</div>
          </div>
          <div v-if="i < archLayers.length - 1" class="arch-arrow">
            <GfIcon name="arrow" :size="22" />
          </div>
        </template>
      </div>
    </section>

    <!-- 功能入口（古籍面） -->
    <section class="features">
      <div
        v-for="feat in features"
        :key="feat.path"
        class="feature-card card"
        @click="router.push(feat.path)"
      >
        <div class="feature-icon"><GfIcon :name="feat.icon" :size="34" /></div>
        <h3 class="feature-title">{{ feat.title }}</h3>
        <p class="feature-desc">{{ feat.desc }}</p>
      </div>
    </section>

    <!-- 数据统计（藏青数据面） -->
    <section class="stats-bar navy-surface">
      <div v-for="(stat, i) in stats" :key="i" class="stat-item">
        <div class="stat-value tnum">
          {{ Math.floor(animatedValues[i]) }}<span class="stat-suffix">{{ stat.suffix }}</span>
        </div>
        <div class="stat-label">{{ stat.label }}</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.dashboard {
  max-width: 1200px;
  margin: 0 auto;
}

/* Hero */
.hero {
  text-align: center;
  padding: 40px 0 28px;
  position: relative;
}

.hero-stamp {
  display: inline-block;
  font-family: var(--font-serif);
  font-size: 14px;
  letter-spacing: 4px;
  color: var(--cinnabar);
  border: 1.5px solid var(--cinnabar);
  border-radius: 6px;
  padding: 3px 12px;
  margin-bottom: 16px;
  opacity: 0.85;
}

.hero-title {
  font-size: 36px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 12px;
  letter-spacing: 2px;
}

.hero-title::after {
  content: '';
  display: block;
  width: 80px;
  height: 3px;
  background: var(--gold);
  margin: 16px auto 0;
  border-radius: 2px;
}

.hero-subtitle {
  font-size: 16px;
  color: var(--ink-2);
}

/* 架构流程（藏青） */
.arch-flow {
  margin-top: 28px;
  padding: 28px 32px;
}

.arch-flow-title {
  font-family: var(--font-serif);
  font-size: 15px;
  letter-spacing: 3px;
  color: var(--gold);
  text-align: center;
  margin-bottom: 20px;
}

.arch-track {
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.arch-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0 18px;
  flex: 1;
  max-width: 200px;
}

.arch-icon {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: rgba(200, 164, 92, 0.12);
  border: 1px solid rgba(200, 164, 92, 0.35);
  color: var(--gold);
  margin-bottom: 10px;
}

.arch-label {
  font-size: 16px;
  font-weight: 600;
  color: var(--on-navy);
}

.arch-desc {
  font-size: 12px;
  color: var(--on-navy-2);
  margin-top: 4px;
  text-align: center;
  line-height: 1.5;
}

.arch-arrow {
  color: var(--gold);
  margin-top: 18px;
  flex-shrink: 0;
}

/* 功能卡片 */
.features {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-top: 28px;
}

.feature-card {
  text-align: center;
  cursor: pointer;
  padding: 28px 16px;
}

.feature-card:hover {
  border-color: var(--gold);
}

.feature-icon {
  width: 60px;
  height: 60px;
  margin: 0 auto 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--paper-sunken);
  color: var(--cinnabar);
}

.feature-title {
  font-size: 17px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 8px;
}

.feature-desc {
  font-size: 13px;
  color: var(--ink-2);
  line-height: 1.6;
}

/* 数据统计（藏青） */
.stats-bar {
  display: flex;
  justify-content: space-around;
  margin-top: 28px;
  padding: 26px;
}

.stat-item { text-align: center; }

.stat-value {
  font-family: var(--font-serif);
  font-size: 34px;
  font-weight: 700;
  color: var(--gold);
}

.stat-suffix { font-size: 20px; margin-left: 2px; }

.stat-label {
  font-size: 14px;
  color: var(--on-navy-2);
  margin-top: 4px;
}

@media (max-width: 768px) {
  .features { grid-template-columns: repeat(2, 1fr); }
  .arch-track { flex-direction: column; align-items: center; gap: 8px; }
  .arch-item { max-width: none; }
  .arch-arrow { transform: rotate(90deg); margin: 0; }
  .stats-bar { flex-wrap: wrap; gap: 16px; }
  .stat-item { flex: 0 0 40%; }
}
</style>
