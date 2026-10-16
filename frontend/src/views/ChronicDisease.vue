<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Download } from '@element-plus/icons-vue'
import GfIcon from '../components/GfIcon.vue'
import { getChronicDiseases, quickDiagnose } from '../api'

// —— 病种清单（来自 /chronic/diseases）——
interface DiseaseMeta { key: string; tcmName: string; symptoms: string[] }
const diseases = ref<DiseaseMeta[]>([])
const diseasesLoading = ref(false)
const diseasesError = ref('')

const selectedDisease = ref('')
const selectedSymptoms = ref<string[]>([])

const currentDisease = computed(() => diseases.value.find((d) => d.key === selectedDisease.value))

async function loadDiseases() {
  diseasesLoading.value = true
  diseasesError.value = ''
  try {
    const { data } = await getChronicDiseases()
    diseases.value = Object.entries(data as Record<string, any>).map(([key, cfg]) => ({
      key,
      tcmName: cfg.tcm_name || key,
      symptoms: cfg.common_symptoms || [],
    }))
  } catch (e: any) {
    diseasesError.value = e?.response?.data?.detail || '病种清单加载失败，请确认后端已启动'
  } finally {
    diseasesLoading.value = false
  }
}
onMounted(loadDiseases)

function pickDisease(key: string) {
  selectedDisease.value = key
  selectedSymptoms.value = []
  result.value = null
  resultError.value = ''
}

// —— 一键辨证 ——
interface KnowledgeSource {
  id: string
  category?: string
  title: string
  source?: any
  original_text?: string
  plain_explanation?: string
}
interface QuickResult {
  disease: string
  syndrome: string
  treatment: string
  plan: Record<string, string>
  sources: KnowledgeSource[]
  disclaimer: string
}

const result = ref<QuickResult | null>(null)
const loading = ref(false)
const resultError = ref('')

async function handleGenerate() {
  if (!selectedDisease.value || selectedSymptoms.value.length === 0) return
  loading.value = true
  resultError.value = ''
  result.value = null
  try {
    const { data } = await quickDiagnose(selectedDisease.value, selectedSymptoms.value)
    result.value = data as QuickResult
  } catch (e: any) {
    resultError.value = e?.response?.data?.detail || '辨证生成失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

// plan 四维 → 印章卡（按固定顺序，仅显示后端给出的项）
const CARE_SEALS = [
  { key: '食疗', seal: '膳', label: '食疗建议' },
  { key: '起居', seal: '居', label: '起居调护' },
  { key: '功法', seal: '功', label: '简易功法' },
  { key: '用药提示', seal: '药', label: '用药提示' },
  { key: '随访提醒', seal: '访', label: '随访提醒' },
]
const careItems = computed(() =>
  result.value
    ? CARE_SEALS.filter((c) => result.value!.plan?.[c.key]).map((c) => ({
        ...c,
        text: result.value!.plan[c.key],
      }))
    : [],
)

// —— 文献溯源弹窗 ——
function sourceStr(s: any): string {
  if (!s) return ''
  if (typeof s === 'string') return s
  return `${s.book || ''}${s.volume ? '·' + s.volume : ''}${s.section ? '·' + s.section : ''}`
}
const sourceDialogVisible = ref(false)
const activeSource = ref<KnowledgeSource | null>(null)
function openSource(src: KnowledgeSource) {
  activeSource.value = src
  sourceDialogVisible.value = true
}

// —— 一键报告（客户端打印 → 另存 PDF）——
function exportReport() {
  const r = result.value
  const d = currentDisease.value
  if (!r || !d) return
  const today = new Date().toISOString().slice(0, 10)
  const care = CARE_SEALS.filter((c) => r.plan?.[c.key])
    .map((c) => `<li><b>${c.label}：</b>${r.plan[c.key]}</li>`)
    .join('')
  const evidence =
    (r.sources || [])
      .map(
        (s) =>
          `<li>${s.title}　<em>${sourceStr(s.source)}</em>${
            s.original_text ? `<div class="orig">「${s.original_text}」</div>` : ''
          }</li>`,
      )
      .join('') || '<li>—</li>'
  const html = `<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<title>李时珍智能医师·慢病调护报告</title><style>
  body{font-family:"Songti SC","STSong",serif;color:#1F3A5F;margin:40px;line-height:1.7}
  h1{text-align:center;border-bottom:3px solid #C8A45C;padding-bottom:12px}
  .meta{color:#888;font-size:12px;text-align:center;margin-bottom:24px}
  h2{color:#9A2D2D;font-size:16px;border-left:4px solid #C8A45C;padding-left:8px;margin-top:22px}
  .syn{font-size:20px;color:#9A2D2D;font-weight:700}
  ul{padding-left:20px} li{margin:6px 0}
  .orig{color:#5C5345;font-size:13px;margin:4px 0 4px 0}
  .disclaimer{margin-top:32px;padding:12px;background:#F5F6F8;font-size:12px;color:#666}
  .sign{text-align:right;margin-top:24px;color:#1F3A5F}
</style></head><body>
  <h1>李时珍智能医师 · 慢病中医调护报告</h1>
  <div class="meta">病种：${d.key}（中医：${d.tcmName}）　日期：${today}</div>
  <h2>主诉症状</h2><p>${selectedSymptoms.value.join('、') || '—'}</p>
  <h2>辨证分型</h2><p class="syn">${r.syndrome || '—'}</p>
  <h2>治法</h2><p>${r.treatment || '—'}</p>
  <h2>调护方案</h2><ul>${care || '<li>—</li>'}</ul>
  <h2>文献依据</h2><ul>${evidence}</ul>
  <div class="disclaimer">${r.disclaimer || '本方案为学术研究与辅助参考，不替代执业医师面诊。'}</div>
  <div class="sign">李时珍智能医师 · 湖北时珍实验室</div>
</body></html>`
  const w = window.open('', '_blank', 'width=820,height=920')
  if (!w) return
  w.document.write(html)
  w.document.close()
  w.focus()
  setTimeout(() => w.print(), 300)
}
</script>

<template>
  <div class="chronic-page">
    <h2 class="page-title">基层老年慢病管理助手</h2>
    <p class="page-subtitle">一键辨证 · 据症状鉴别证型 · 文献溯源 · 一键报告</p>

    <div class="chronic-layout">
      <!-- 第1步 选择病种 -->
      <div class="step-section">
        <div class="step-header"><span class="seal-no">1</span><span>选择病种</span></div>

        <div v-if="diseasesLoading" class="state-block"><span class="loading-dot" /> 正在加载病种清单……</div>
        <el-alert v-else-if="diseasesError" :title="diseasesError" type="error" :closable="false" show-icon />

        <div v-else class="disease-grid">
          <div
            v-for="d in diseases"
            :key="d.key"
            class="disease-btn"
            :class="{ active: selectedDisease === d.key }"
            @click="pickDisease(d.key)"
          >
            <div class="disease-seal">{{ d.tcmName }}</div>
            <div class="disease-name">{{ d.key }}</div>
          </div>
        </div>
      </div>

      <!-- 第2步 勾选症状 -->
      <div class="step-section" v-if="currentDisease">
        <div class="step-header"><span class="seal-no">2</span><span>勾选您的症状</span></div>
        <el-checkbox-group v-model="selectedSymptoms" class="symptom-grid">
          <el-checkbox
            v-for="s in currentDisease.symptoms"
            :key="s"
            :value="s"
            :label="s"
            size="large"
            border
          />
        </el-checkbox-group>
      </div>

      <!-- 一键生成 -->
      <div class="generate-section" v-if="currentDisease && selectedSymptoms.length > 0">
        <button class="btn-cinnabar generate-btn" :disabled="loading" @click="handleGenerate">
          {{ loading ? '正在辨证生成…' : '一键生成调护方案' }}
        </button>
      </div>

      <el-alert
        v-if="resultError"
        :title="resultError"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />

      <!-- 结果 -->
      <transition name="slide-up">
        <div v-if="result" class="result-section">
          <el-card class="result-card">
            <template #header>
              <div class="result-header">
                <h3>{{ currentDisease?.key }} · 中医调护方案</h3>
                <el-button type="primary" size="small" @click="exportReport">
                  <el-icon><Download /></el-icon>
                  导出报告
                </el-button>
              </div>
            </template>

            <div class="result-grid">
              <div class="result-item">
                <div class="result-label">辨证分型</div>
                <div class="result-value syndrome">{{ result.syndrome }}</div>
              </div>
              <div class="result-item">
                <div class="result-label">治法</div>
                <div class="result-value">{{ result.treatment }}</div>
              </div>
            </div>

            <el-divider />

            <div class="care-sections">
              <div v-for="c in careItems" :key="c.seal" class="care-item">
                <h4><span class="mini-seal">{{ c.seal }}</span>{{ c.label }}</h4>
                <p>{{ c.text }}</p>
              </div>
            </div>

            <!-- 真实文献溯源 -->
            <h4 class="evidence-title">文献依据 · 知识库溯源</h4>
            <div v-if="result.sources && result.sources.length" class="evidence-list">
              <div
                v-for="src in result.sources"
                :key="src.id"
                class="evidence-card"
                @click="openSource(src)"
              >
                <div class="evidence-head">
                  <GfIcon name="book" :size="14" />
                  <span class="evidence-name">{{ src.title }}</span>
                  <span v-if="src.category" class="evidence-cat">{{ src.category }}</span>
                </div>
                <div class="evidence-src">{{ sourceStr(src.source) }}</div>
              </div>
            </div>
            <p v-else class="evidence-empty">暂无匹配的知识库文献条目。</p>

            <el-alert
              :title="result.disclaimer || '本方案为学术研究与辅助参考，不替代执业医师面诊。'"
              type="warning"
              show-icon
              :closable="false"
              class="disclaimer"
            />
          </el-card>
        </div>
      </transition>
    </div>

    <!-- 溯源原文弹窗 -->
    <el-dialog v-model="sourceDialogVisible" title="文献溯源" width="560px">
      <div v-if="activeSource" class="source-detail">
        <h3 class="sd-title">{{ activeSource.title }}</h3>
        <div class="sd-source"><GfIcon name="book" :size="14" /> {{ sourceStr(activeSource.source) }}</div>
        <div v-if="activeSource.original_text" class="sd-block">
          <div class="sd-label">原文摘录</div>
          <p class="sd-orig">「{{ activeSource.original_text }}」</p>
        </div>
        <div v-if="activeSource.plain_explanation" class="sd-block">
          <div class="sd-label">白话释义</div>
          <p class="sd-plain">{{ activeSource.plain_explanation }}</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.chronic-page {
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.chronic-layout {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin-top: 24px;
  padding-right: 4px;
}

.step-section { margin-bottom: 24px; }

.step-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--ink);
  margin-bottom: 16px;
}

.state-block {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 2px;
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

/* 病种选择 */
.disease-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }

.disease-btn {
  background: var(--paper-card);
  border: 2px solid var(--border-paper);
  border-radius: var(--radius);
  padding: 18px 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
}
.disease-btn:hover { border-color: var(--gold); transform: translateY(-2px); }
.disease-btn.active { border-color: var(--cinnabar); background: rgba(154, 45, 45, 0.06); }

.disease-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 46px;
  height: 46px;
  margin-bottom: 8px;
  border-radius: 9px;
  background: var(--cinnabar);
  color: #fbf7ee;
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -1px;
  box-shadow: inset 0 0 0 1px rgba(251, 247, 238, 0.3);
}
.disease-name { font-size: 15px; font-weight: 600; color: var(--ink); }

/* 症状勾选 */
.symptom-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }

/* 生成按钮 */
.generate-section { text-align: center; margin: 24px 0; }
.generate-btn {
  min-width: 300px;
  height: 52px;
  font-size: 18px;
  font-weight: 600;
  border-radius: 26px;
}
.generate-btn:disabled { opacity: 0.7; cursor: not-allowed; }

/* 结果 */
.result-card { background: var(--paper-card); }
.result-header { display: flex; justify-content: space-between; align-items: center; }
.result-header h3 { color: var(--ink); }

.result-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.result-item { padding: 14px; background: var(--paper-sunken); border-radius: var(--radius-sm); }
.result-label { font-size: 12px; color: var(--ink-2); margin-bottom: 4px; }
.result-value { font-size: 16px; font-weight: 600; color: var(--ink); }
.result-value.syndrome { color: var(--cinnabar); font-family: var(--font-serif); font-size: 22px; }

.care-sections { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.care-item { padding: 16px; background: var(--paper-sunken); border-radius: var(--radius-sm); }
.care-item h4 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  color: var(--ink);
  margin-bottom: 8px;
}
.mini-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--cinnabar);
  color: #fbf7ee;
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
.care-item p { font-size: 14px; line-height: 1.7; color: var(--ink-2); }

/* 文献溯源 */
.evidence-title {
  font-size: 15px;
  color: var(--ink);
  margin: 22px 0 12px;
  padding-left: 10px;
  border-left: 3px solid var(--gold);
}
.evidence-list { display: flex; flex-direction: column; gap: 10px; }
.evidence-card {
  padding: 12px 14px;
  background: var(--paper-sunken);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-paper);
  cursor: pointer;
  transition: all 0.2s ease;
}
.evidence-card:hover { border-color: var(--gold); transform: translateX(2px); box-shadow: 0 2px 10px rgba(31, 27, 22, 0.08); }
.evidence-head { display: flex; align-items: center; gap: 7px; color: var(--cinnabar); }
.evidence-name { font-weight: 600; color: var(--ink); }
.evidence-cat {
  margin-left: auto;
  font-size: 11px;
  color: var(--gold);
  border: 1px solid var(--gold);
  border-radius: 10px;
  padding: 0 8px;
}
.evidence-src { font-size: 12px; color: var(--ink-2); margin-top: 5px; padding-left: 21px; }
.evidence-empty { font-size: 13px; color: var(--ink-2); padding: 8px 2px; }

.disclaimer { margin-top: 18px; }

/* 溯源弹窗 */
.sd-title { font-family: var(--font-serif); font-size: 18px; color: var(--ink); }
.sd-source { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--cinnabar); margin: 8px 0 14px; }
.sd-block { margin-bottom: 14px; }
.sd-label { font-size: 12px; color: var(--ink-2); margin-bottom: 6px; padding-left: 8px; border-left: 3px solid var(--gold); }
.sd-orig { font-family: var(--font-serif); font-size: 15px; line-height: 1.9; color: var(--ink); background: var(--paper-sunken); padding: 12px 14px; border-radius: var(--radius-sm); }
.sd-plain { font-size: 14px; line-height: 1.8; color: var(--ink-2); }

.slide-up-enter-active { transition: all 0.5s ease; }
.slide-up-enter-from { opacity: 0; transform: translateY(30px); }

@media (max-width: 768px) {
  .chronic-layout { flex: none; min-height: 0; overflow: visible; padding-right: 0; }
  .disease-grid { grid-template-columns: repeat(3, 1fr); }
  .symptom-grid { grid-template-columns: repeat(2, 1fr); }
  .care-sections { grid-template-columns: 1fr; }
}
</style>
