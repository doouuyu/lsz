<script setup lang="ts">
import { ref, reactive, nextTick, onMounted, onBeforeUnmount, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import GfIcon from '../components/GfIcon.vue'
import { inquiry, diagnose, getKnowledgeEntry, generateReport, apiOrigin } from '../api'

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
// 脉案条目作答快照：主诉为纯文本，问诊卡为各控件状态（供回退改答时还原）
type AnswerSnapshot =
  | { kind: 'chief'; text: string }
  | { kind: 'card'; single: string; multi: string[]; slider: number; supp: string }

// 脉案条目：与 accumulated 数组 1:1 对应；question 为该条所答的问题（主诉为 null）
interface CaseEntry {
  id: number
  label: string            // 维度标签（主诉 / 寒热 / 睡眠 …）
  summary: string          // 在脉案中显示的作答文本
  question: InquiryQuestion | null
  answer: AnswerSnapshot
}

interface Candidate { name: string; score: number }
interface Evidence { text: string; source: string; entry_id?: string }
interface Herb { herb: string; dosage: string; role: string; reason: string }

interface InquiryOption { label: string; value: string }
interface InquiryQuestion {
  key: string
  question: string
  type: 'single' | 'multi' | 'slider' | 'text'
  options: InquiryOption[]
  min: number
  max: number
  min_label: string
  max_label: string
  unit: string
}

interface ViewModel {
  summary: string
  location: { 病位: string[]; 病性: string[]; 气血津液: string }
  primary: string
  concurrent: string[]
  confidence: number
  candidates: Candidate[]
  evidence: Evidence[]
  treatment: string
  formula: { name: string; modification: string; herbs: Herb[] }
  care: { contraindication: string; diet: string; lifestyle: string; exercise: string }
  disclaimer: string
}

/* ------------------------------------------------------------------ */
/*  State                                                             */
/* ------------------------------------------------------------------ */
const chiefDraft = ref('')               // 主诉录入草稿
const isSending = ref(false)             // 提交/请求进行中
const thinking = ref(false)              // 李时珍正在斟酌下一问

const sessionId = ref<string | null>(null)
const accumulated = ref<string[]>([])    // 累计作答文本，与 caseRecord 1:1
// 完整问答记录：user=主诉/回答，assistant=系统已问出的问题；供后端连贯追问
const inquiryHistory = ref<{ role: 'user' | 'assistant'; content: string }[]>([])
const caseRecord = ref<CaseEntry[]>([])  // 脉案：主诉 + 历次问诊作答
let entryIdCounter = 0
// 仅作防死循环兜底：是否充分由模型(ready)判断，正常不会触达此上限
const MAX_INQUIRY_ROUNDS = 12
const phase = ref<'collecting' | 'diagnosing' | 'done'>('collecting')

// 已采集的问诊项数（不含主诉）——回溯式计数，绝不预告还剩几问
const answeredCount = computed(() => Math.max(0, caseRecord.value.length - 1))

// 右舞台当前形态：主诉录入 / 引导问诊 / 斟酌 / 决断辨证 / 八步结果
const rightStage = computed<'intake' | 'inquiry' | 'thinking' | 'diagnosing' | 'result'>(() => {
  if (phase.value === 'done') return 'result'
  // 辨证途中：结果未出时放决断过场，结果一出即切到八步（让分步动画可见）
  if (phase.value === 'diagnosing') return vm.value ? 'result' : 'diagnosing'
  if (activeQuestion.value) return 'inquiry'
  if (caseRecord.value.length === 0) return 'intake'
  return 'thinking'
})
// 问诊/录入为宣纸古籍面；辨证/结果翻入藏青数据面
const stageIsDark = computed(() => rightStage.value === 'diagnosing' || rightStage.value === 'result')
// 脉案条目是否可点回退（辨证/斟酌途中锁定，避免竞态）
const canEditCase = computed(() => !isSending.value && !thinking.value && phase.value !== 'diagnosing')

/* 结构化问诊卡片 */
const activeQuestion = ref<InquiryQuestion | null>(null)
const answerSingle = ref('')
const answerMulti = ref<string[]>([])
const answerSlider = ref(0)
const answerSupplement = ref('')

function setActiveQuestion(q: InquiryQuestion | null) {
  activeQuestion.value = q
  answerSingle.value = ''
  answerMulti.value = []
  answerSlider.value = q ? Math.round((q.min + q.max) / 2) : 0
  answerSupplement.value = ''
}

const canSubmitCard = computed(() => {
  const q = activeQuestion.value
  if (!q) return false
  if (q.type === 'single') return !!answerSingle.value || !!answerSupplement.value.trim()
  if (q.type === 'multi') return answerMulti.value.length > 0 || !!answerSupplement.value.trim()
  if (q.type === 'slider') return true
  return !!answerSupplement.value.trim()
})

const vm = ref<ViewModel | null>(null)
const rawSources = ref<any[]>([])
const reporting = ref(false)

const radarChartRef = ref<HTMLElement | null>(null)
const diagnosisPanelRef = ref<HTMLElement | null>(null)
let radarChartInstance: echarts.ECharts | null = null

const diagnosisSteps = reactive<{ step: number; title: string; visible: boolean }[]>([
  { step: 1, title: '症状归纳', visible: false },
  { step: 2, title: '病位病性', visible: false },
  { step: 3, title: '证型推断', visible: false },
  { step: 4, title: '经典依据', visible: false },
  { step: 5, title: '治法', visible: false },
  { step: 6, title: '推荐方药', visible: false },
  { step: 7, title: '调护建议', visible: false },
  { step: 8, title: '免责声明', visible: false },
])

/* 溯源弹窗 */
const sourceDialogVisible = ref(false)
const sourceLoading = ref(false)
const activeSource = ref<{ title: string; sourceStr: string; original: string; plain: string } | null>(null)

const tongueInputRef = ref<HTMLInputElement | null>(null)

/* ------------------------------------------------------------------ */
/*  角色自适应（页面内自管，决定辨证结果的语言风格与详细度）          */
/* ------------------------------------------------------------------ */
type Role = 'doctor' | 'patient' | 'researcher'

const ROLES: { value: Role; label: string; desc: string }[] = [
  { value: 'doctor', label: '医生', desc: '专业术语 · 完整方药剂量 · 君臣佐使配伍' },
  { value: 'patient', label: '患者', desc: '通俗白话 · 侧重食疗起居 · 弱化处方剂量' },
  { value: 'researcher', label: '研究者', desc: '文献引证 · 理论溯源 · 内联经典原文' },
]
function roleLabel(r: Role | null): string {
  return ROLES.find((x) => x.value === r)?.label ?? ''
}

const role = ref<Role>('doctor')                 // 当前选定视角（决定下一次辨证的语言）
const resultRole = ref<Role | null>(null)        // 当前结果实际按哪个视角生成
const lastFullSymptoms = ref('')                 // 缓存完整四诊信息，供切换视角时免重复问诊
const bannerDismissed = ref(false)               // 用户是否已选择"仅切换显示"
const reinterpreting = ref(false)                // 重新解读进行中

const showDosage = computed(() => role.value !== 'patient')          // 患者弱化处方剂量
const evidenceInline = computed(() => role.value === 'researcher')   // 研究者直接展开文献

// 结果已生成、但当前视角与结果生成时的视角不一致 → 文字风格存在"漂移"
const roleDrifted = computed(
  () => phase.value === 'done' && !!resultRole.value && role.value !== resultRole.value,
)
const showRoleBanner = computed(() => roleDrifted.value && !bannerDismissed.value)

// 每次切换视角都重置"仅切换显示"的忽略状态，使提示能再次出现
watch(role, () => {
  bannerDismissed.value = false
})

/** 用缓存的四诊信息，按当前视角重新解读——不重新问诊，仅重跑一次辨证 */
async function reInterpret() {
  if (!lastFullSymptoms.value || reinterpreting.value) return
  const target = role.value
  reinterpreting.value = true
  try {
    const { data } = await diagnose(lastFullSymptoms.value, target, sessionId.value, true)
    if (data.session_id) sessionId.value = data.session_id
    if (data.result?._error) ElMessage.warning('模型暂不可用，已返回兜底结构')
    vm.value = adapt(data.result || {})
    rawSources.value = data.sources || []
    resultRole.value = target
    bannerDismissed.value = false
    await nextTick()
    if (vm.value && vm.value.candidates.length >= 3) initRadarChart()
    ElMessage.success(`已按「${roleLabel(target)}」视角重新解读本次辨证。`)
  } catch (e: any) {
    ElMessage.error('重新解读失败：' + (e?.message || '网络错误'))
  } finally {
    reinterpreting.value = false
  }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */
function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}

function normScore(s: number): number {
  if (s == null || isNaN(s)) return 0
  return s <= 1 ? Math.round(s * 100) : Math.round(s)
}

function sourceStr(s: any): string {
  if (!s) return ''
  if (typeof s === 'string') return s
  return `${s.book || ''}${s.volume ? '·' + s.volume : ''}${s.section ? '·' + s.section : ''}`
}

/* ------------------------------------------------------------------ */
/*  适配层：后端 8 步 JSON → 视图模型                                  */
/* ------------------------------------------------------------------ */
function adapt(result: any): ViewModel {
  const s2 = result.step2_location_nature || {}
  const s3 = result.step3_syndrome || {}
  const s6 = result.step6_formula || {}
  const s7 = result.step7_care || {}
  const candidates: Candidate[] = (s3.syndrome_candidates || []).map((c: any) => ({
    name: c.name,
    score: normScore(c.score),
  }))
  return {
    summary: result.step1_symptom_summary || '',
    location: {
      病位: s2.病位 || [],
      病性: s2.病性 || [],
      气血津液: s2.气血津液 || '',
    },
    primary: s3.主证 || '待辨证',
    concurrent: s3.兼证 || [],
    confidence: normScore(s3.confidence),
    candidates,
    evidence: result.step4_classic_evidence || [],
    treatment: result.step5_treatment || '',
    formula: {
      name: s6.name || '',
      modification: s6.modification || '',
      herbs: (s6.composition || []).map((h: any) => ({
        herb: h.herb || '',
        dosage: h.dosage || '',
        role: h.role || '',
        reason: h.reason || '',
      })),
    },
    care: {
      contraindication: s7.contraindication || '',
      diet: s7.diet || '',
      lifestyle: s7.lifestyle || '',
      exercise: s7.exercise || '',
    },
    disclaimer: result.step8_disclaimer || '本结果为学术研究与辅助参考，不替代执业医师面诊。',
  }
}

/* 君臣佐使分组 */
const junHerbs = computed(() => vm.value?.formula.herbs.filter((h) => h.role.includes('君')) || [])
const chenHerbs = computed(() => vm.value?.formula.herbs.filter((h) => h.role.includes('臣')) || [])
const zuoHerbs = computed(() => vm.value?.formula.herbs.filter((h) => h.role.includes('佐')) || [])
const shiHerbs = computed(() => vm.value?.formula.herbs.filter((h) => h.role.includes('使')) || [])
const otherHerbs = computed(
  () => vm.value?.formula.herbs.filter((h) => !/[君臣佐使]/.test(h.role)) || [],
)

const careItems = computed(() => {
  const c = vm.value?.care
  if (!c) return []
  return [
    { seal: '忌', label: '用药禁忌', text: c.contraindication },
    { seal: '食', label: '食疗建议', text: c.diet },
    { seal: '居', label: '起居调护', text: c.lifestyle },
    { seal: '功', label: '简易功法', text: c.exercise },
  ].filter((i) => i.text)
})

/* 问诊卡片：已选项数（多选用）与提示文案 */
const multiCount = computed(() => answerMulti.value.length)
const cardHint = computed(() => {
  const q = activeQuestion.value
  if (!q) return ''
  if (q.type === 'single') return '请选择一项，可在下方补充'
  if (q.type === 'multi') return '可多选，凡符合的都点上'
  if (q.type === 'slider') return '拖动评估程度'
  return '请在下方简要描述'
})

/* 脉案头部状态文案 */
const statusText = computed(() => {
  if (phase.value === 'done') return '辨证已完成'
  if (phase.value === 'diagnosing') return '四诊已明 · 辨证中'
  if (thinking.value) return '李时珍正在斟酌…'
  if (answeredCount.value > 0) return `已采集 ${answeredCount.value} 项`
  return '待录主诉'
})

/* 置信度分档：用于结果摘要的文字标签与配色 */
const confidenceLevel = computed(() => {
  const v = vm.value?.confidence ?? 0
  if (v >= 75) return { label: '高', cls: 'high' }
  if (v >= 50) return { label: '中', cls: 'mid' }
  return { label: '参考', cls: 'low' }
})

/* ------------------------------------------------------------------ */
/*  会话流（Flow B：先 inquiry 追问，ready 后 diagnose）              */
/*  脉案版：一次只呈现此刻一问，作答凝成可回退的脉案条目              */
/* ------------------------------------------------------------------ */
/** 常见主诉快选：点击即并入主诉草稿 */
const COMMON_COMPLAINTS = ['头晕', '失眠多梦', '乏力气短', '口干多饮', '心悸', '腰膝酸软', '便秘', '咳嗽痰多']
function pickComplaint(c: string) {
  const cur = chiefDraft.value.trim()
  if (cur.includes(c)) return
  chiefDraft.value = cur ? `${cur}、${c}` : c
}

/** 主诉录入 → 开始坐诊 */
function startConsult() {
  const text = chiefDraft.value.trim()
  if (!text || isSending.value) return
  submitAnswer(text, '主诉', null, { kind: 'chief', text })
  chiefDraft.value = ''
}

/** 问诊卡片提交：把选项 + 补充拼成作答文本 */
function submitCard() {
  const q = activeQuestion.value
  if (!q || !canSubmitCard.value || isSending.value) return
  const parts: string[] = []
  if (q.type === 'single' && answerSingle.value) parts.push(answerSingle.value)
  if (q.type === 'multi' && answerMulti.value.length) parts.push(answerMulti.value.join('、'))
  if (q.type === 'slider') parts.push(`${q.key || '程度'}：${answerSlider.value}${q.unit || ''}`)
  if (answerSupplement.value.trim()) parts.push(answerSupplement.value.trim())
  const snapshot: AnswerSnapshot = {
    kind: 'card',
    single: answerSingle.value,
    multi: [...answerMulti.value],
    slider: answerSlider.value,
    supp: answerSupplement.value.trim(),
  }
  submitAnswer(parts.join('；'), q.key || '问诊', q, snapshot)
}

/** 跳过当前问题（说不清） */
function skipQuestion() {
  const q = activeQuestion.value
  if (!q || isSending.value) return
  submitAnswer('这一项不太清楚', q.key || '问诊', q, { kind: 'card', single: '', multi: [], slider: q.min, supp: '' })
}

/** 共享：把一次作答写入脉案 → 累计 → 取下一问 / 决断辨证 */
async function submitAnswer(text: string, label: string, answered: InquiryQuestion | null, snapshot: AnswerSnapshot) {
  isSending.value = true
  caseRecord.value.push({ id: ++entryIdCounter, label, summary: text, question: answered, answer: snapshot })
  accumulated.value.push(text)
  // 历史保持「完整问答对」：先记下刚答的这一问，再记答案；待问的问题不入历史，便于回退截断
  if (answered) inquiryHistory.value.push({ role: 'assistant', content: answered.question })
  inquiryHistory.value.push({ role: 'user', content: text })
  setActiveQuestion(null)

  const fullSymptoms = accumulated.value.join('；')
  try {
    thinking.value = true
    const { data } = await inquiry(fullSymptoms, sessionId.value, inquiryHistory.value)
    if (data.session_id) sessionId.value = data.session_id
    thinking.value = false

    // 充分性只认模型明确 ready；MAX 仅防死循环。
    // 关键：未就绪就继续追问，绝不因「没拿到问题」而误入辨证。
    const hitMax = answeredCount.value >= MAX_INQUIRY_ROUNDS
    const q: InquiryQuestion | undefined = data.questions?.[0]
    if (!data.ready && !hitMax && q) {
      await delay(220)
      setActiveQuestion(q)
      isSending.value = false
    } else {
      // 决断式收束：四诊已明 → 过场 → 辨证
      phase.value = 'diagnosing'
      await delay(900)
      await runDiagnose(fullSymptoms)
    }
  } catch (e: any) {
    thinking.value = false
    isSending.value = false
    ElMessage.error('问诊请求失败：' + (e?.message || '网络错误'))
  }
}

async function runDiagnose(fullSymptoms: string) {
  phase.value = 'diagnosing'
  lastFullSymptoms.value = fullSymptoms
  try {
    const { data } = await diagnose(fullSymptoms, role.value, sessionId.value, true)
    if (data.session_id) sessionId.value = data.session_id

    if (data.need_more && data.questions?.length) {
      // 理论上 skip_inquiry=true 不会触发；防御性处理：退回问诊补问
      phase.value = 'collecting'
      isSending.value = false
      await delay(200)
      const q = data.questions[0]
      if (typeof q === 'object' && q?.question) setActiveQuestion(q)
      return
    }

    if (data.result?._error) {
      ElMessage.warning('模型暂不可用，已返回兜底结构')
    }
    vm.value = adapt(data.result || {})
    rawSources.value = data.sources || []
    resultRole.value = role.value
    bannerDismissed.value = false
    await startStepAnimation()
    phase.value = 'done'
    isSending.value = false
  } catch (e: any) {
    phase.value = 'collecting'
    isSending.value = false
    ElMessage.error('辨证请求失败：' + (e?.message || '网络错误'))
  }
}

/** 清空辨证结果（回退改答时调用） */
function clearResult() {
  vm.value = null
  rawSources.value = []
  resultRole.value = null
  lastFullSymptoms.value = ''
  bannerDismissed.value = false
  diagnosisSteps.forEach((s) => (s.visible = false))
  radarChartInstance?.dispose()
  radarChartInstance = null
}

/** 回退到脉案第 index 条重新作答：截断其后的一切，后续问题顺势重问 */
function reopenEntry(index: number) {
  if (!canEditCase.value || index < 0 || index >= caseRecord.value.length) return
  const entry = caseRecord.value[index]
  if (phase.value === 'done' || vm.value) clearResult()
  phase.value = 'collecting'

  // 截断脉案与累计作答（含本条）
  caseRecord.value.splice(index)
  accumulated.value.splice(index)
  // 历史：主诉占 1 项，其后每条问诊占「问+答」2 项 → 保留 index 条之前的内容
  inquiryHistory.value.splice(index === 0 ? 0 : 2 * index - 1)

  if (index === 0) {
    // 回到主诉录入，草稿回填
    chiefDraft.value = entry.answer.kind === 'chief' ? entry.answer.text : entry.summary
    setActiveQuestion(null)
  } else {
    // 重新打开该问诊卡，回填上次作答
    activeQuestion.value = entry.question
    const s = entry.answer
    answerSingle.value = s.kind === 'card' ? s.single : ''
    answerMulti.value = s.kind === 'card' ? [...s.multi] : []
    answerSlider.value = s.kind === 'card' ? s.slider : (entry.question?.min ?? 0)
    answerSupplement.value = s.kind === 'card' ? s.supp : ''
  }
}

/** 上一问：回退到最近一条已答脉案 */
function goPrevQuestion() {
  if (!canEditCase.value || caseRecord.value.length === 0) return
  reopenEntry(caseRecord.value.length - 1)
}

/** 问诊卡片键盘提交：Ctrl/⌘+Enter 始终提交；补充框外的普通回车也提交 */
function handleCardKeydown(e: KeyboardEvent) {
  if (e.isComposing || (e as any).keyCode === 229) return
  if (e.key !== 'Enter') return
  const inTextarea = (e.target as HTMLElement)?.tagName === 'TEXTAREA'
  const combo = e.metaKey || e.ctrlKey
  if (combo || (!inTextarea && !e.shiftKey)) {
    e.preventDefault()
    submitCard()
  }
}

function resetSession() {
  accumulated.value = []
  inquiryHistory.value = []
  caseRecord.value = []
  chiefDraft.value = ''
  sessionId.value = null
  setActiveQuestion(null)
  phase.value = 'collecting'
  thinking.value = false
  isSending.value = false
  clearResult()
}

/* ------------------------------------------------------------------ */
/*  分步动画                                                          */
/* ------------------------------------------------------------------ */
function scrollDiagToBottom() {
  const el = diagnosisPanelRef.value
  if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
}

async function startStepAnimation() {
  for (let i = 0; i < diagnosisSteps.length; i++) {
    await delay(300)
    diagnosisSteps[i].visible = true
    if (i === 2) {
      await nextTick()
      await delay(100)
      initRadarChart()
    }
    await nextTick()
    scrollDiagToBottom()
  }
}

/* ------------------------------------------------------------------ */
/*  证型雷达                                                          */
/* ------------------------------------------------------------------ */
function initRadarChart() {
  if (!radarChartRef.value || !vm.value) return
  const cands = vm.value.candidates
  if (cands.length < 3) return // 候选过少不画雷达，仅显示条形

  radarChartInstance = echarts.init(radarChartRef.value)
  const option: echarts.EChartsOption = {
    animation: true,
    animationDuration: 1200,
    animationEasing: 'cubicOut' as const,
    tooltip: { trigger: 'item' },
    radar: {
      indicator: cands.map((c) => ({ name: c.name, max: 100 })),
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#34505C', fontSize: 12, fontWeight: 'bold' },
      splitArea: {
        areaStyle: { color: ['rgba(200,164,92,0.05)', 'rgba(200,164,92,0.1)', 'rgba(200,164,92,0.05)', 'rgba(200,164,92,0.1)'] },
      },
      axisLine: { lineStyle: { color: 'rgba(31,27,22,0.14)' } },
      splitLine: { lineStyle: { color: 'rgba(31,27,22,0.1)' } },
    },
    series: [
      {
        type: 'radar',
        symbol: 'circle',
        symbolSize: 6,
        data: [
          {
            value: cands.map((c) => c.score),
            name: '证型匹配度',
            areaStyle: { color: 'rgba(200,164,92,0.3)' },
            lineStyle: { color: '#C8A45C', width: 2 },
            itemStyle: { color: '#C8A45C', borderColor: '#FBF7EE', borderWidth: 2 },
          },
        ],
      },
    ],
  }
  radarChartInstance.setOption(option)
}

function handleResize() {
  radarChartInstance?.resize()
}

/* ------------------------------------------------------------------ */
/*  溯源弹窗                                                          */
/* ------------------------------------------------------------------ */
async function openSource(ev: Evidence) {
  sourceDialogVisible.value = true
  if (ev.entry_id) {
    sourceLoading.value = true
    activeSource.value = null
    try {
      const { data } = await getKnowledgeEntry(ev.entry_id)
      activeSource.value = {
        title: data.title || ev.entry_id,
        sourceStr: sourceStr(data.source),
        original: data.original_text || ev.text || '',
        plain: data.plain_explanation || '',
      }
    } catch {
      activeSource.value = { title: '引证', sourceStr: ev.source || '', original: ev.text || '', plain: '' }
    } finally {
      sourceLoading.value = false
    }
  } else {
    activeSource.value = { title: '引证', sourceStr: ev.source || '', original: ev.text || '', plain: '' }
  }
}

/* ------------------------------------------------------------------ */
/*  PDF 报告导出                                                      */
/* ------------------------------------------------------------------ */
async function exportReport() {
  if (!sessionId.value) return
  reporting.value = true
  try {
    const { data } = await generateReport(sessionId.value)
    const url = apiOrigin + data.download_url
    const isPdf = /\.pdf(\?|$)/i.test(data.download_url)
    if (isPdf) {
      // 后端已产出矢量 PDF → 真·一键下载到本地
      try {
        const resp = await fetch(url)
        const blob = await resp.blob()
        const objUrl = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = objUrl
        a.download = `${data.report_id || '李时珍诊疗报告'}.pdf`
        document.body.appendChild(a)
        a.click()
        a.remove()
        setTimeout(() => URL.revokeObjectURL(objUrl), 4000)
        ElMessage.success('PDF 报告已下载')
      } catch {
        window.open(url, '_blank') // 下载受限时兜底：在浏览器中打开 PDF
        ElMessage.success('报告 PDF 已在新标签打开，可在阅读器中保存')
      }
    } else {
      // 降级 HTML：打开后用页内「下载 / 打印 PDF」按钮另存
      window.open(url, '_blank')
      ElMessage.success('报告已打开，点右上角「下载 / 打印 PDF」即可另存')
    }
  } catch (e: any) {
    ElMessage.error('报告生成失败：' + (e?.message || '网络错误'))
  } finally {
    reporting.value = false
  }
}

/* ------------------------------------------------------------------ */
/*  多模态占位                                                        */
/* ------------------------------------------------------------------ */
function onTongueClick() {
  tongueInputRef.value?.click()
}
function onTongueChange() {
  ElMessage.info('舌象智能识别即将上线，已记录图像作为辅助参考')
  if (tongueInputRef.value) tongueInputRef.value.value = ''
}
function onMicClick() {
  ElMessage.info('语音输入即将上线，请先使用文字描述')
}

/* ------------------------------------------------------------------ */
/*  Lifecycle                                                         */
/* ------------------------------------------------------------------ */
onMounted(() => {
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  radarChartInstance?.dispose()
})
</script>

<template>
  <div class="diagnose-page">
    <!-- Page header -->
    <div class="page-header">
      <div>
        <h1 class="page-title" style="margin-bottom: 4px">仿真辨证</h1>
        <p class="page-subtitle">四诊合参 · 八步思维链 · 文献溯源</p>
      </div>
      <div class="page-header-actions">
        <div class="role-switch" role="group" aria-label="选择回答视角">
          <el-tooltip placement="bottom-end" :effect="'light'" :show-after="120">
            <template #content>
              <div class="role-tip">
                <div class="role-tip-title">切换视角＝切换回答风格</div>
                <div
                  v-for="r in ROLES"
                  :key="r.value"
                  class="role-tip-row"
                  :class="{ active: r.value === role }"
                >
                  <b>{{ r.label }}</b><span>{{ r.desc }}</span>
                </div>
                <div class="role-tip-note">辨证完成后切换，可一键按新视角重新解读，无需重复问诊。</div>
              </div>
            </template>
            <span class="role-switch-hint" aria-label="视角说明">视角 ⓘ</span>
          </el-tooltip>
          <el-segmented
            v-model="role"
            :options="ROLES.map((r) => ({ label: r.label, value: r.value }))"
            size="small"
            class="role-segmented"
          />
        </div>
        <el-popconfirm
          v-if="phase !== 'collecting' || caseRecord.length > 0"
          title="将清空当前问诊与辨证结果，重新开始？"
          confirm-button-text="重新辨证"
          cancel-button-text="取消"
          :width="248"
          @confirm="resetSession"
        >
          <template #reference>
            <el-button plain size="small" :disabled="phase === 'diagnosing'">重新辨证</el-button>
          </template>
        </el-popconfirm>
      </div>
    </div>

    <!-- Main layout -->
    <div class="diagnose-layout">
      <!-- ============ LEFT: 脉案（已述）============ -->
      <aside class="case-panel">
        <div class="case-header">
          <div class="case-header-seal">案</div>
          <div class="case-header-info">
            <span class="case-header-name">脉案</span>
            <span class="case-header-status">
              <span class="status-dot" :class="{ active: thinking || phase === 'diagnosing' }"></span>
              {{ statusText }}
            </span>
          </div>
        </div>

        <div class="case-body">
          <div v-if="!caseRecord.length" class="case-empty">
            <GfIcon name="book" :size="40" />
            <p>请在右侧描述主诉<br />问诊所得将逐条记入此脉案</p>
          </div>

          <TransitionGroup v-else name="case-item" tag="ul" class="case-list">
            <li
              v-for="(e, i) in caseRecord"
              :key="e.id"
              class="case-entry"
              :class="{ chief: i === 0, editable: canEditCase }"
              @click="reopenEntry(i)"
            >
              <div class="case-entry-head">
                <span class="case-entry-label" :class="{ 'is-chief': i === 0 }">{{ e.label }}</span>
                <span v-if="canEditCase" class="case-entry-edit"><GfIcon name="back" :size="12" />改</span>
              </div>
              <p class="case-entry-text">{{ e.summary }}</p>
            </li>
          </TransitionGroup>
        </div>

        <div class="case-foot">四诊合参 · 已采集 {{ answeredCount }} 项</div>
      </aside>

      <!-- ============ RIGHT: 问诊台 / 辨证台 ============ -->
      <section
        ref="diagnosisPanelRef"
        class="stage-panel"
        :class="stageIsDark ? 'is-dark' : 'is-light'"
      >
        <!-- 主诉录入 -->
        <div v-if="rightStage === 'intake'" class="intake-stage">
          <div class="intake-seal">李</div>
          <h2 class="intake-greet">请说说您最主要的不适</h2>
          <p class="intake-sub">如同坐诊：先讲主诉，李时珍再一步步为您问诊</p>
          <el-input
            v-model="chiefDraft"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 6 }"
            placeholder="例如：近一个月头晕乏力、怕冷、夜里睡不好…"
            resize="none"
            class="intake-input"
          />
          <div class="intake-chips">
            <span class="intake-chips-label">常见主诉</span>
            <button v-for="c in COMMON_COMPLAINTS" :key="c" class="intake-chip" @click="pickComplaint(c)">{{ c }}</button>
          </div>
          <div class="intake-actions">
            <div class="intake-modal">
              <button class="io-btn" title="语音输入（即将上线）" aria-label="语音输入" @click="onMicClick"><GfIcon name="mic" :size="18" /></button>
              <button class="io-btn" title="舌象上传（多模态）" aria-label="舌象上传" @click="onTongueClick"><GfIcon name="camera" :size="18" /></button>
            </div>
            <button class="btn-cinnabar intake-cta" :disabled="!chiefDraft.trim() || isSending" @click="startConsult">
              请李时珍辨证 →
            </button>
          </div>
        </div>

        <!-- 引导问诊：一问一卡 -->
        <div
          v-else-if="rightStage === 'inquiry' && activeQuestion"
          class="inquiry-stage"
          @keydown="handleCardKeydown"
        >
          <div class="inquiry-ask">
            <span class="inquiry-ask-by">李时珍 问</span>
            <span class="inquiry-ask-no">第 {{ answeredCount + 1 }} 问</span>
          </div>
          <h2 class="inquiry-question">{{ activeQuestion.question }}</h2>
          <p class="inquiry-stage-hint">{{ cardHint }}</p>

          <el-radio-group v-if="activeQuestion.type === 'single'" v-model="answerSingle" class="opt-group big">
            <el-radio-button v-for="o in activeQuestion.options" :key="o.value" :value="o.value">{{ o.label }}</el-radio-button>
          </el-radio-group>

          <el-checkbox-group v-else-if="activeQuestion.type === 'multi'" v-model="answerMulti" class="opt-group big">
            <el-checkbox-button v-for="o in activeQuestion.options" :key="o.value" :value="o.value">{{ o.label }}</el-checkbox-button>
          </el-checkbox-group>

          <div v-else-if="activeQuestion.type === 'slider'" class="slider-wrap">
            <span class="slider-end">{{ activeQuestion.min_label }}</span>
            <el-slider v-model="answerSlider" :min="activeQuestion.min" :max="activeQuestion.max" show-stops class="slider-ctl" />
            <span class="slider-end">{{ activeQuestion.max_label }}</span>
            <span class="slider-val">{{ answerSlider }}{{ activeQuestion.unit }}</span>
          </div>

          <el-input
            v-model="answerSupplement"
            type="textarea"
            :autosize="{ minRows: 1, maxRows: 3 }"
            placeholder="补充说明（选填）"
            resize="none"
            class="supp-input"
          />

          <div class="inquiry-stage-actions">
            <button class="link-btn" :disabled="!caseRecord.length || !canEditCase" @click="goPrevQuestion">← 上一问</button>
            <div class="inquiry-stage-right">
              <button class="link-btn" :disabled="isSending" @click="skipQuestion">说不清 · 跳过</button>
              <span v-if="activeQuestion.type === 'multi' && multiCount" class="multi-count">已选 {{ multiCount }} 项</span>
              <button class="btn-cinnabar inquiry-submit" :disabled="!canSubmitCard || isSending" @click="submitCard">作答 →</button>
            </div>
          </div>
        </div>

        <!-- 斟酌下一问 -->
        <div v-else-if="rightStage === 'thinking'" class="ponder-stage">
          <div class="ponder-seal">李</div>
          <div class="typing-dots"><span></span><span></span><span></span></div>
          <p class="ponder-text">李时珍正斟酌下一问…</p>
        </div>

        <!-- 决断辨证过场 -->
        <div v-else-if="rightStage === 'diagnosing'" class="diagnose-transition">
          <div class="placeholder-icon pulsing"><GfIcon name="engine" :size="64" /></div>
          <h3>四诊已明 · 胸有定见</h3>
          <p>检索经典文献 · 推演理法方药</p>
        </div>

        <div v-else-if="vm" class="diagnosis-steps">
          <!-- 结果摘要条：辨证完成后置顶常驻，速览主证 + 操作 -->
          <Transition name="step-slide">
            <div v-if="phase === 'done'" class="result-summary-bar">
              <div class="rsb-main">
                <span class="rsb-label">主证</span>
                <span class="rsb-syndrome">{{ vm.primary }}</span>
                <span v-if="vm.confidence" class="rsb-conf" :class="confidenceLevel.cls">
                  置信 {{ vm.confidence }}% · {{ confidenceLevel.label }}
                </span>
                <span v-if="resultRole" class="rsb-perspective">{{ roleLabel(resultRole) }}视角</span>
              </div>
              <div class="rsb-actions">
                <button class="rsb-btn" :disabled="reporting" @click="exportReport">
                  <GfIcon name="report" :size="15" />
                  {{ reporting ? '生成中…' : '生成报告' }}
                </button>
                <el-popconfirm
                  title="将清空当前结果，重新开始？"
                  confirm-button-text="重新辨证"
                  cancel-button-text="取消"
                  :width="220"
                  @confirm="resetSession"
                >
                  <template #reference>
                    <button class="rsb-btn ghost">重新辨证</button>
                  </template>
                </el-popconfirm>
              </div>
            </div>
          </Transition>

          <!-- 视角漂移提示：结果生成后用户切换了视角 -->
          <Transition name="step-slide">
            <div v-if="showRoleBanner" class="role-drift-banner">
              <div class="rdb-text">
                <GfIcon name="engine" :size="16" class="rdb-icon" />
                <span>
                  已切换到「<b>{{ roleLabel(role) }}</b>」视角，当前结果仍按「{{ roleLabel(resultRole) }}」措辞生成。
                </span>
              </div>
              <div class="rdb-actions">
                <button class="rdb-btn primary" :disabled="reinterpreting" @click="reInterpret">
                  {{ reinterpreting ? '重新解读中…' : `按${roleLabel(role)}视角重新解读` }}
                </button>
                <button class="rdb-btn ghost" :disabled="reinterpreting" @click="bannerDismissed = true">
                  仅切换显示
                </button>
              </div>
            </div>
          </Transition>

          <!-- Step 1 -->
          <Transition name="step-slide">
            <div v-if="diagnosisSteps[0].visible" class="step-card">
              <div class="step-badge">1</div>
              <div class="step-content">
                <h3 class="step-title">{{ diagnosisSteps[0].title }}</h3>
                <p class="summary-text">{{ vm.summary }}</p>
              </div>
            </div>
          </Transition>

          <!-- Step 2 -->
          <Transition name="step-slide">
            <div v-if="diagnosisSteps[1].visible" class="step-card">
              <div class="step-badge">2</div>
              <div class="step-content">
                <h3 class="step-title">{{ diagnosisSteps[1].title }}</h3>
                <div class="nature-block" v-if="vm.location.病位.length">
                  <span class="nature-label">病位</span>
                  <el-tag v-for="(x, i) in vm.location.病位" :key="'w' + i" class="symptom-tag" effect="plain" round>{{ x }}</el-tag>
                </div>
                <div class="nature-block" v-if="vm.location.病性.length">
                  <span class="nature-label">病性</span>
                  <el-tag v-for="(x, i) in vm.location.病性" :key="'n' + i" class="symptom-tag" effect="plain" round>{{ x }}</el-tag>
                </div>
                <div class="nature-block" v-if="vm.location.气血津液">
                  <span class="nature-label">气血津液</span>
                  <span class="nature-text">{{ vm.location.气血津液 }}</span>
                </div>
              </div>
            </div>
          </Transition>

          <!-- Step 3 -->
          <Transition name="step-slide">
            <div v-if="diagnosisSteps[2].visible" class="step-card">
              <div class="step-badge">3</div>
              <div class="step-content">
                <h3 class="step-title">{{ diagnosisSteps[2].title }}</h3>
                <div class="syndrome-section">
                  <div class="syndrome-primary">
                    <span class="syndrome-label">主证型</span>
                    <span class="syndrome-value">{{ vm.primary }}</span>
                    <span v-if="vm.confidence" class="syndrome-conf">置信度 {{ vm.confidence }}%</span>
                  </div>
                  <div v-if="vm.concurrent.length" class="concurrent-row">
                    <span class="nature-label">兼证</span>
                    <el-tag v-for="(c, i) in vm.concurrent" :key="i" class="symptom-tag" effect="plain" round>{{ c }}</el-tag>
                  </div>
                  <div v-if="vm.candidates.length >= 3" ref="radarChartRef" class="radar-chart"></div>
                  <div class="syndrome-list">
                    <div v-for="(sd, i) in vm.candidates" :key="i" class="syndrome-bar-row">
                      <span class="syndrome-name">{{ sd.name }}</span>
                      <div class="syndrome-bar-track">
                        <div class="syndrome-bar-fill" :style="{ width: sd.score + '%' }"></div>
                      </div>
                      <span class="syndrome-score">{{ sd.score }}%</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Transition>

          <!-- Step 4 -->
          <Transition name="step-slide">
            <div v-if="diagnosisSteps[3].visible" class="step-card">
              <div class="step-badge">4</div>
              <div class="step-content">
                <h3 class="step-title">{{ diagnosisSteps[3].title }}</h3>
                <div v-if="vm.evidence.length" class="sources-list">
                  <div v-for="(src, i) in vm.evidence" :key="i" class="source-item" @click="openSource(src)">
                    <span class="source-icon"><GfIcon name="book" :size="20" /></span>
                    <div class="source-info">
                      <span class="source-book">{{ src.source || '点击查看出处' }}</span>
                      <span v-if="evidenceInline && src.text" class="source-quote-inline">「{{ src.text }}」</span>
                    </div>
                    <GfIcon name="arrow" :size="16" class="source-arrow" />
                  </div>
                </div>
                <p v-else class="summary-text muted">本次辨证未匹配到知识库引证条目。</p>
              </div>
            </div>
          </Transition>

          <!-- Step 5 -->
          <Transition name="step-slide">
            <div v-if="diagnosisSteps[4].visible" class="step-card">
              <div class="step-badge">5</div>
              <div class="step-content">
                <h3 class="step-title">{{ diagnosisSteps[4].title }}</h3>
                <div class="treatment-text">
                  <span class="treatment-principle">{{ vm.treatment }}</span>
                </div>
              </div>
            </div>
          </Transition>

          <!-- Step 6 -->
          <Transition name="step-slide">
            <div v-if="diagnosisSteps[5].visible" class="step-card">
              <div class="step-badge">6</div>
              <div class="step-content">
                <h3 class="step-title">{{ diagnosisSteps[5].title }}</h3>
                <div class="formula-header" v-if="vm.formula.name">
                  <span class="formula-name">{{ vm.formula.name }}</span>
                </div>

                <!-- 患者模式：弱化处方，仅列药名 -->
                <template v-if="!showDosage">
                  <div class="patient-herbs">
                    <el-tag v-for="h in vm.formula.herbs" :key="h.herb" class="symptom-tag" effect="plain" round>{{ h.herb }}</el-tag>
                  </div>
                  <p class="summary-text muted">具体方药剂量请遵执业中医师面诊后开具。</p>
                </template>

                <!-- 医生 / 研究者：完整君臣佐使 -->
                <template v-else>
                  <div class="formula-layout">
                    <div v-if="junHerbs.length" class="herb-section">
                      <div class="herb-section-label" style="color: var(--gold)">君药</div>
                      <div class="herb-cards">
                        <div v-for="h in junHerbs" :key="h.herb" class="herb-card jun">
                          <div class="herb-name">{{ h.herb }}</div>
                          <div class="herb-dosage">{{ h.dosage }}</div>
                          <div class="herb-effect">{{ h.reason }}</div>
                        </div>
                      </div>
                    </div>
                    <div v-if="chenHerbs.length" class="herb-section">
                      <div class="herb-section-label" style="color: var(--dai-qing)">臣药</div>
                      <div class="herb-cards">
                        <div v-for="h in chenHerbs" :key="h.herb" class="herb-card chen">
                          <div class="herb-name">{{ h.herb }}</div>
                          <div class="herb-dosage">{{ h.dosage }}</div>
                          <div class="herb-effect">{{ h.reason }}</div>
                        </div>
                      </div>
                    </div>
                    <div v-if="zuoHerbs.length" class="herb-section">
                      <div class="herb-section-label" style="color: var(--jade)">佐药</div>
                      <div class="herb-cards">
                        <div v-for="h in zuoHerbs" :key="h.herb" class="herb-card zuo">
                          <div class="herb-name">{{ h.herb }}</div>
                          <div class="herb-dosage">{{ h.dosage }}</div>
                          <div class="herb-effect">{{ h.reason }}</div>
                        </div>
                      </div>
                    </div>
                    <div v-if="shiHerbs.length || otherHerbs.length" class="herb-section">
                      <div class="herb-section-label" style="color: var(--ink-3)">使药</div>
                      <div class="herb-cards">
                        <div v-for="h in [...shiHerbs, ...otherHerbs]" :key="h.herb" class="herb-card shi">
                          <div class="herb-name">{{ h.herb }}</div>
                          <div class="herb-dosage">{{ h.dosage }}</div>
                          <div class="herb-effect">{{ h.reason }}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <p v-if="vm.formula.modification" class="modification-text">
                    <span class="nature-label">随症加减</span>{{ vm.formula.modification }}
                  </p>
                </template>
              </div>
            </div>
          </Transition>

          <!-- Step 7 -->
          <Transition name="step-slide">
            <div v-if="diagnosisSteps[6].visible" class="step-card">
              <div class="step-badge">7</div>
              <div class="step-content">
                <h3 class="step-title">{{ diagnosisSteps[6].title }}</h3>
                <div class="care-grid">
                  <div v-for="c in careItems" :key="c.seal" class="care-block">
                    <h4><span class="mini-seal">{{ c.seal }}</span>{{ c.label }}</h4>
                    <p>{{ c.text }}</p>
                  </div>
                </div>
              </div>
            </div>
          </Transition>

          <!-- Step 8 -->
          <Transition name="step-slide">
            <div v-if="diagnosisSteps[7].visible" class="step-card disclaimer-card">
              <div class="step-badge disclaimer-badge">8</div>
              <div class="step-content">
                <h3 class="step-title">{{ diagnosisSteps[7].title }}</h3>
                <p class="disclaimer-text">{{ vm.disclaimer }}</p>
                <button class="btn-cinnabar report-btn" :disabled="reporting" @click="exportReport">
                  <GfIcon name="report" :size="18" />
                  {{ reporting ? '正在生成…' : '生成诊疗报告' }}
                </button>
              </div>
            </div>
          </Transition>
        </div>

        <input ref="tongueInputRef" type="file" accept="image/*" hidden @change="onTongueChange" />
      </section>
    </div>

    <!-- ============ Source Detail Dialog ============ -->
    <el-dialog
      v-model="sourceDialogVisible"
      :title="activeSource?.title ?? '文献出处'"
      width="560px"
      class="source-dialog"
      destroy-on-close
    >
      <div v-loading="sourceLoading" class="source-dialog-body">
        <template v-if="activeSource">
          <div class="source-meta">
            <el-tag type="info" size="small" effect="plain">{{ activeSource.sourceStr || '出处待校' }}</el-tag>
          </div>
          <blockquote v-if="activeSource.original" class="source-quote">「{{ activeSource.original }}」</blockquote>
          <p v-if="activeSource.plain" class="source-plain">{{ activeSource.plain }}</p>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
/* ================================================================== */
/*  PAGE LAYOUT                                                        */
/* ================================================================== */
.diagnose-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 20px;
}

.diagnose-layout {
  display: flex;
  gap: 20px;
  flex: 1;
  /* 充满剩余高度；矮屏低于此值时由 .app-main 滚动，避免面板被压扁 */
  min-height: 600px;
}

/* ================================================================== */
/*  LEFT: 脉案 PANEL — 宣纸古籍面                                      */
/* ================================================================== */
.case-panel {
  width: 34%;
  min-width: 300px;
  max-width: 400px;
  background: var(--paper-card);
  border: 1px solid var(--border-paper);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.case-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 15px 18px;
  background: linear-gradient(135deg, var(--navy) 0%, var(--navy-card) 100%);
  color: #fff;
  flex-shrink: 0;
}
.case-header-seal {
  width: 38px; height: 38px; border-radius: 8px;
  background: var(--cinnabar); color: #FBF7EE;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-serif); font-weight: 700; font-size: 20px;
  box-shadow: inset 0 0 0 1px rgba(251, 247, 238, 0.35);
  flex-shrink: 0;
}
.case-header-info { display: flex; flex-direction: column; }
.case-header-name { font-family: var(--font-serif); font-weight: 700; font-size: 17px; letter-spacing: 2px; color: var(--gold); }
.case-header-status { font-size: 12px; opacity: 0.85; display: flex; align-items: center; gap: 5px; }

.status-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--jade); display: inline-block; }
.status-dot.active { animation: pulse-dot 1s infinite; }
@keyframes pulse-dot { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

.case-body { flex: 1; overflow-y: auto; padding: 16px; background: var(--paper); }

.case-empty {
  height: 100%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 14px; color: var(--ink-3); text-align: center;
}
.case-empty svg { color: var(--gold); opacity: 0.55; }
.case-empty p { font-size: 13px; line-height: 1.9; }

.case-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }

.case-entry {
  padding: 11px 14px;
  background: var(--paper-card);
  border: 1px solid var(--border-paper);
  border-left: 3px solid var(--gold-soft);
  border-radius: var(--radius-sm);
  transition: all 0.18s ease;
}
.case-entry.chief { border-left-color: var(--cinnabar); background: linear-gradient(180deg, rgba(154, 45, 45, 0.05), var(--paper-card)); }
.case-entry.editable { cursor: pointer; }
.case-entry.editable:hover { border-color: var(--gold); box-shadow: 0 2px 10px rgba(11, 22, 38, 0.08); transform: translateX(2px); }
.case-entry.editable:hover .case-entry-edit { opacity: 1; }

.case-entry-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.case-entry-label { font-size: 12px; font-weight: 700; color: var(--dai-qing); font-family: var(--font-serif); letter-spacing: 1px; }
.case-entry-label.is-chief { color: #FBF7EE; background: var(--cinnabar); padding: 1px 10px; border-radius: 5px; }
.case-entry-edit { display: inline-flex; align-items: center; gap: 2px; font-size: 11px; color: var(--ink-3); opacity: 0; transition: opacity 0.18s; }
.case-entry-text { margin: 0; font-size: 14px; color: var(--ink); line-height: 1.6; word-break: break-word; }

.case-foot {
  flex-shrink: 0; padding: 10px 16px; text-align: center;
  font-size: 12px; color: var(--ink-3);
  border-top: 1px solid var(--border-paper); background: var(--paper-card);
  font-variant-numeric: tabular-nums;
}

.case-item-enter-active { transition: all 0.32s cubic-bezier(0.22, 1, 0.36, 1); }
.case-item-enter-from { opacity: 0; transform: translateY(-8px); }

/* ================================================================== */
/*  RIGHT: 问诊台 / 辨证台 — 双表面（问诊宣纸 · 辨证藏青）            */
/* ================================================================== */
.stage-panel {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  border-radius: var(--radius);
  transition: background 0.5s ease;
}
.stage-panel.is-light {
  background: var(--paper-card);
  border: 1px solid var(--border-paper);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
}
.stage-panel.is-dark {
  padding: 18px;
  background:
    radial-gradient(circle at 18% 0%, rgba(95, 179, 161, 0.10), transparent 45%),
    linear-gradient(160deg, var(--navy) 0%, var(--navy-2) 100%);
  box-shadow: var(--shadow-navy);
}

@keyframes stage-in { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }

/* ---- 主诉录入 ---- */
.intake-stage {
  flex: 1;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center; padding: 40px 48px;
  max-width: 600px; width: 100%; margin: 0 auto;
  animation: stage-in 0.4s ease;
}
.intake-seal {
  width: 60px; height: 60px; border-radius: 14px;
  background: linear-gradient(135deg, var(--gold) 0%, var(--gold-soft) 100%);
  color: #1F1B16; display: flex; align-items: center; justify-content: center;
  font-family: var(--font-serif); font-weight: 700; font-size: 30px;
  margin-bottom: 18px; box-shadow: 0 6px 18px rgba(200, 164, 92, 0.3);
}
.intake-greet { font-family: var(--font-serif); font-size: 24px; color: var(--ink); margin: 0 0 8px; letter-spacing: 1px; }
.intake-sub { font-size: 14px; color: var(--ink-2); margin: 0 0 22px; }
.intake-input { width: 100%; margin-bottom: 16px; }
.intake-input :deep(.el-textarea__inner) {
  border-radius: 14px; padding: 14px 16px; font-size: 16px; line-height: 1.7;
  border: 1px solid var(--border-paper); background: var(--paper);
}
.intake-input :deep(.el-textarea__inner:focus) { border-color: var(--gold); box-shadow: 0 0 0 2px rgba(200, 164, 92, 0.18); }

.intake-chips { display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 8px; width: 100%; margin-bottom: 24px; }
.intake-chips-label { font-size: 12px; color: var(--ink-3); margin-right: 2px; }
.intake-chip {
  padding: 6px 14px; border-radius: 16px;
  border: 1px dashed var(--gold-soft); background: transparent;
  color: var(--ink-2); font-size: 13px; cursor: pointer; transition: all 0.18s;
}
.intake-chip:hover { border-style: solid; border-color: var(--cinnabar); color: var(--cinnabar); background: rgba(154, 45, 45, 0.05); }

.intake-actions { display: flex; align-items: center; justify-content: space-between; width: 100%; gap: 12px; }
.intake-modal { display: flex; gap: 8px; }
.intake-cta { padding: 12px 32px; font-size: 16px; }
.intake-cta:disabled { opacity: 0.5; cursor: not-allowed; }

/* ---- 引导问诊：一问一卡 ---- */
.inquiry-stage {
  flex: 1;
  display: flex; flex-direction: column;
  padding: 40px 48px; max-width: 660px; width: 100%; margin: 0 auto;
  animation: stage-in 0.35s ease;
}
.inquiry-ask { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.inquiry-ask-by {
  font-family: var(--font-serif); font-size: 13px; font-weight: 700;
  color: #FBF7EE; background: var(--cinnabar);
  padding: 3px 14px; border-radius: 6px; letter-spacing: 1px;
}
.inquiry-ask-no { font-size: 12px; color: var(--ink-3); font-variant-numeric: tabular-nums; }
.inquiry-question { font-family: var(--font-serif); font-size: 26px; line-height: 1.5; color: var(--ink); margin: 0 0 6px; letter-spacing: 0.5px; }
.inquiry-stage-hint { font-size: 13px; color: var(--ink-3); margin: 0 0 22px; }
.inquiry-stage .slider-wrap { margin-bottom: 22px; }
.inquiry-stage .supp-input { margin: 6px 0 24px; }
.inquiry-stage-actions { display: flex; align-items: center; justify-content: space-between; margin-top: auto; padding-top: 8px; }
.inquiry-stage-right { display: flex; align-items: center; gap: 14px; }

/* 大号选项卡（问诊舞台用） */
.opt-group.big { gap: 12px; margin-bottom: 22px; }
.opt-group.big :deep(.el-radio-button__inner),
.opt-group.big :deep(.el-checkbox-button__inner) { padding: 13px 24px; font-size: 16px; border-radius: 14px !important; }

/* ---- 斟酌下一问 ---- */
.ponder-stage {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px;
  animation: stage-in 0.3s ease;
}
.ponder-seal {
  width: 52px; height: 52px; border-radius: 12px;
  background: linear-gradient(135deg, var(--gold) 0%, var(--gold-soft) 100%);
  color: #1F1B16; display: flex; align-items: center; justify-content: center;
  font-family: var(--font-serif); font-weight: 700; font-size: 26px;
  animation: icon-pulse 1.6s ease-in-out infinite;
}
.ponder-text { font-size: 14px; color: var(--ink-2); }
.ponder-stage .typing-dots span { background: var(--gold); }

/* ---- 决断辨证过场（藏青面） ---- */
.diagnose-transition {
  height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: var(--on-navy-2); text-align: center; padding: 48px;
  animation: stage-in 0.4s ease;
}
.diagnose-transition h3 { font-family: var(--font-serif); font-size: 22px; color: var(--gold); margin: 8px 0; letter-spacing: 2px; }
.diagnose-transition p { font-size: 14px; line-height: 1.6; }

/* ---- 通用：图标脉冲 / 思考点 / 多模态按钮（复用） ---- */
.placeholder-icon { color: var(--gold); opacity: 0.7; margin-bottom: 12px; }
.placeholder-icon.pulsing { animation: icon-pulse 1.5s ease-in-out infinite; }
@keyframes icon-pulse { 0%, 100% { opacity: 0.4; transform: scale(0.94); } 50% { opacity: 0.9; transform: scale(1.06); } }

.typing-dots { display: flex; gap: 5px; }
.typing-dots span { width: 9px; height: 9px; border-radius: 50%; background: var(--ink-3); animation: typing-bounce 1.4s infinite ease-in-out; }
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing-bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }

.io-btn {
  width: 38px; height: 38px; border-radius: 50%;
  border: 1px solid var(--border-paper); background: var(--paper); color: var(--ink-2);
  display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s ease;
}
.io-btn:hover:not(:disabled) { border-color: var(--gold); color: var(--cinnabar); }
.io-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ===== 结构化问诊选项（问诊舞台复用） ===== */
.opt-group { display: flex; flex-wrap: wrap; gap: 8px; }

/* 单选 / 多选按钮：去掉 Element 拼接边框，做成独立药丸 */
.opt-group :deep(.el-radio-button__inner),
.opt-group :deep(.el-checkbox-button__inner) {
  border: 1px solid var(--border-paper);
  border-radius: 18px !important;
  background: var(--paper-card);
  color: var(--ink);
  box-shadow: none !important;
  padding: 8px 16px;
  font-size: 14px;
  transition: all 0.2s ease;
}
.opt-group :deep(.el-radio-button),
.opt-group :deep(.el-checkbox-button) { margin: 0; }
.opt-group :deep(.el-radio-button.is-active .el-radio-button__inner),
.opt-group :deep(.el-checkbox-button.is-checked .el-checkbox-button__inner) {
  background: var(--cinnabar);
  border-color: var(--cinnabar);
  color: #FBF7EE;
}

/* 滑块 */
.slider-wrap { display: flex; align-items: center; gap: 12px; padding: 0 4px; }
.slider-ctl { flex: 1; }
.slider-end { font-size: 12px; color: var(--ink-3); white-space: nowrap; }
.slider-val {
  min-width: 40px;
  text-align: center;
  font-weight: 700;
  color: var(--cinnabar);
  font-variant-numeric: tabular-nums;
}
.slider-wrap :deep(.el-slider__bar) { background: var(--cinnabar); }
.slider-wrap :deep(.el-slider__button) { border-color: var(--cinnabar); }

.supp-input :deep(.el-textarea__inner) {
  border-radius: 10px;
  border: 1px solid var(--border-paper);
  background: var(--paper-card);
  font-size: 13px;
}
.supp-input :deep(.el-textarea__inner:focus) {
  border-color: var(--gold);
  box-shadow: 0 0 0 2px rgba(200, 164, 92, 0.18);
}

.inquiry-actions { display: flex; align-items: center; justify-content: space-between; }
.link-btn {
  background: none;
  border: none;
  color: var(--ink-3);
  font-size: 13px;
  cursor: pointer;
  padding: 4px;
}
.link-btn:hover:not(:disabled) { color: var(--dai-qing); }
.link-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.inquiry-actions-right { display: flex; align-items: center; gap: 12px; }
.multi-count { font-size: 12px; color: var(--gold); font-variant-numeric: tabular-nums; }
.inquiry-submit { padding: 8px 28px; font-size: 15px; }
.inquiry-submit:disabled { opacity: 0.55; cursor: not-allowed; }

/* 选中态：多选打勾视觉强化 */
.opt-group :deep(.el-checkbox-button.is-checked .el-checkbox-button__inner)::before {
  content: '✓';
  margin-right: 4px;
  font-weight: 700;
}

/* ================================================================== */
/*  辨证结果（藏青数据面，承载于 .stage-panel.is-dark）               */
/* ================================================================== */
.diagnosis-steps { display: flex; flex-direction: column; gap: 16px; padding-bottom: 8px; }

/* 结果摘要条：辨证完成后置顶常驻 */
.result-summary-bar {
  position: sticky;
  top: -18px; /* 抵消 panel 的 18px 内边距，贴合顶部 */
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin: -4px 0 2px;
  padding: 14px 18px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, rgba(251, 247, 238, 0.97) 0%, rgba(251, 246, 234, 0.97) 100%);
  border: 1px solid rgba(200, 164, 92, 0.4);
  box-shadow: 0 6px 18px rgba(11, 22, 38, 0.28);
  backdrop-filter: blur(6px);
}
.rsb-main { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; min-width: 0; }
.rsb-label { font-size: 12px; font-weight: 700; color: var(--gold); flex-shrink: 0; }
.rsb-syndrome {
  font-family: var(--font-serif);
  font-size: 18px;
  font-weight: 700;
  color: var(--cinnabar);
  letter-spacing: 1px;
}
.rsb-conf {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.rsb-conf.high { color: #2f7d5b; background: rgba(95, 179, 161, 0.16); }
.rsb-conf.mid { color: #9a6a1f; background: rgba(200, 164, 92, 0.18); }
.rsb-conf.low { color: var(--ink-3); background: var(--paper-sunken); }

.rsb-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.rsb-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border-radius: 18px;
  border: 1px solid var(--cinnabar);
  background: var(--cinnabar);
  color: #FBF7EE;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}
.rsb-btn:hover:not(:disabled) { background: var(--cinnabar-soft); border-color: var(--cinnabar-soft); }
.rsb-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.rsb-btn.ghost { background: transparent; color: var(--navy); border-color: var(--border-paper); }
.rsb-btn.ghost:hover { border-color: var(--gold); color: var(--cinnabar); background: rgba(200, 164, 92, 0.08); }

.rsb-perspective {
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 10px;
  color: var(--navy);
  background: rgba(36, 69, 104, 0.1);
  border: 1px solid rgba(36, 69, 104, 0.2);
  white-space: nowrap;
}

/* ---- 视角切换器（聊天头部） ---- */
.role-switch { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.role-switch-hint {
  font-size: 12px;
  color: rgba(234, 240, 246, 0.7);
  cursor: help;
  white-space: nowrap;
  user-select: none;
}
.role-switch-hint:hover { color: var(--gold); }
.role-segmented { --el-border-radius-base: 14px; }

.role-tip { max-width: 260px; line-height: 1.5; }
.role-tip-title { font-weight: 700; color: var(--navy); margin-bottom: 6px; font-size: 13px; }
.role-tip-row { display: flex; gap: 6px; padding: 3px 0; font-size: 12px; color: var(--ink-2); }
.role-tip-row b { color: var(--ink-1); flex-shrink: 0; }
.role-tip-row.active b { color: var(--cinnabar); }
.role-tip-row.active { background: rgba(200, 164, 92, 0.1); border-radius: 4px; padding-left: 4px; }
.role-tip-note { margin-top: 6px; font-size: 11px; color: var(--ink-3); border-top: 1px dashed var(--border-paper); padding-top: 6px; }

/* ---- 视角漂移提示条 ---- */
.role-drift-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  margin: 6px 0 10px;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, rgba(200, 164, 92, 0.16) 0%, rgba(200, 164, 92, 0.08) 100%);
  border: 1px solid rgba(200, 164, 92, 0.45);
}
.rdb-text { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--ink-1); min-width: 0; }
.rdb-text b { color: var(--cinnabar); }
.rdb-icon { color: var(--gold); flex-shrink: 0; }
.rdb-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.rdb-btn {
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}
.rdb-btn.primary { background: var(--cinnabar); color: #FBF7EE; border-color: var(--cinnabar); }
.rdb-btn.primary:hover:not(:disabled) { background: var(--cinnabar-soft); border-color: var(--cinnabar-soft); }
.rdb-btn.ghost { background: transparent; color: var(--navy); border-color: var(--border-paper); }
.rdb-btn.ghost:hover:not(:disabled) { border-color: var(--gold); color: var(--cinnabar); }
.rdb-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.step-card {
  background: var(--paper-card);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 22px 24px 22px 72px;
  position: relative;
  transition: transform 0.2s, box-shadow 0.2s;
}
.step-card:hover { transform: translateY(-1px); box-shadow: 0 10px 28px rgba(11, 22, 38, 0.25); }

.step-badge {
  position: absolute;
  left: 20px;
  top: 22px;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--cinnabar);
  color: #FBF7EE;
  font-family: var(--font-serif);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 17px;
  box-shadow: 0 2px 8px rgba(154, 45, 45, 0.35), inset 0 0 0 1px rgba(251, 247, 238, 0.3);
}

.step-title {
  font-family: var(--font-serif);
  font-size: 17px;
  font-weight: 700;
  color: var(--navy);
  margin-bottom: 14px;
  letter-spacing: 1px;
}

.step-slide-enter-active { transition: all 0.5s cubic-bezier(0.22, 1, 0.36, 1); }
.step-slide-enter-from { opacity: 0; transform: translateY(30px); }

/* Step1 summary */
.summary-text { font-size: 14px; line-height: 1.8; color: var(--ink); }
.summary-text.muted { color: var(--ink-3); }

/* Step2 病位病性 */
.nature-block { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.nature-label {
  font-size: 12px;
  font-weight: 700;
  color: #FBF7EE;
  background: var(--dai-qing);
  padding: 3px 10px;
  border-radius: 6px;
  flex-shrink: 0;
}
.nature-text { font-size: 14px; color: var(--ink); }

.symptom-tag {
  border-color: var(--gold) !important;
  color: var(--ink) !important;
  background: rgba(200, 164, 92, 0.1) !important;
  font-size: 13px;
}

/* Step3 syndrome */
.syndrome-section { display: flex; flex-direction: column; gap: 16px; }
.syndrome-primary {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 20px;
  border-radius: var(--radius-sm);
  background: linear-gradient(135deg, rgba(200, 164, 92, 0.12) 0%, rgba(200, 164, 92, 0.02) 100%);
  border: 1px solid rgba(200, 164, 92, 0.3);
}
.syndrome-label { font-size: 13px; color: var(--gold); font-weight: 700; white-space: nowrap; }
.syndrome-value { font-family: var(--font-serif); font-size: 19px; font-weight: 700; color: var(--cinnabar); letter-spacing: 1px; }
.syndrome-conf { margin-left: auto; font-size: 12px; color: var(--ink-2); font-variant-numeric: tabular-nums; }
.concurrent-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }

.radar-chart { width: 100%; height: 300px; }

.syndrome-list { display: flex; flex-direction: column; gap: 10px; }
.syndrome-bar-row { display: flex; align-items: center; gap: 12px; }
.syndrome-name { width: 120px; font-size: 13px; color: var(--ink); text-align: right; flex-shrink: 0; }
.syndrome-bar-track { flex: 1; height: 8px; background: var(--paper-sunken); border-radius: 4px; overflow: hidden; }
.syndrome-bar-fill { height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--gold) 0%, var(--gold-soft) 100%); transition: width 1s cubic-bezier(0.22, 1, 0.36, 1); }
.syndrome-score { width: 42px; font-size: 13px; font-weight: 600; color: var(--gold); text-align: right; font-variant-numeric: tabular-nums; }

/* Step4 sources */
.sources-list { display: flex; flex-direction: column; gap: 8px; }
.source-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  background: var(--paper-sunken);
  border: 1px solid var(--border-paper);
  cursor: pointer;
  transition: all 0.2s;
}
.source-item:hover { background: rgba(200, 164, 92, 0.1); border-color: rgba(200, 164, 92, 0.35); transform: translateX(4px); }
.source-icon { color: var(--cinnabar); flex-shrink: 0; display: flex; }
.source-info { flex: 1; display: flex; flex-direction: column; gap: 3px; }
.source-book { font-size: 14px; font-weight: 600; color: var(--navy); }
.source-quote-inline { font-size: 12px; color: var(--ink-2); line-height: 1.5; }
.source-arrow { color: var(--ink-3); flex-shrink: 0; }

/* Step5 treatment */
.treatment-text {
  padding: 16px 24px;
  background: linear-gradient(135deg, rgba(31, 58, 95, 0.06) 0%, rgba(200, 164, 92, 0.08) 100%);
  border-radius: var(--radius-sm);
  border-left: 4px solid var(--gold);
}
.treatment-principle { font-family: var(--font-serif); font-size: 18px; font-weight: 600; color: var(--navy); letter-spacing: 2px; }

/* Step6 formula */
.formula-header { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px dashed rgba(200, 164, 92, 0.35); }
.formula-name { font-family: var(--font-serif); font-size: 20px; font-weight: 700; color: var(--cinnabar); }

.formula-layout { display: flex; flex-direction: column; gap: 18px; }
.herb-section { display: flex; flex-direction: column; gap: 10px; }
.herb-section-label { font-family: var(--font-serif); font-size: 14px; font-weight: 700; letter-spacing: 2px; padding-left: 4px; }
.herb-cards { display: flex; flex-wrap: wrap; gap: 10px; }
.herb-card { padding: 12px 16px; border-radius: var(--radius-sm); border: 1px solid; transition: transform 0.2s, box-shadow 0.2s; }
.herb-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(31, 27, 22, 0.1); }

.herb-card.jun { border-color: var(--gold); background: rgba(200, 164, 92, 0.08); padding: 16px 24px; min-width: 200px; box-shadow: 0 2px 8px rgba(200, 164, 92, 0.2); }
.herb-card.jun .herb-name { font-size: 18px; color: var(--gold); }
.herb-card.jun .herb-dosage { font-size: 15px; }
.herb-card.chen { border-color: rgba(52, 80, 92, 0.3); background: rgba(52, 80, 92, 0.05); min-width: 160px; }
.herb-card.chen .herb-name { color: var(--dai-qing); }
.herb-card.zuo { border-color: rgba(95, 179, 161, 0.3); background: rgba(95, 179, 161, 0.06); min-width: 150px; }
.herb-card.zuo .herb-name { color: #3e8d7c; }
.herb-card.shi { border-color: var(--border-paper); background: var(--paper-sunken); min-width: 140px; }
.herb-card.shi .herb-name { color: var(--ink-2); }

.herb-name { font-size: 15px; font-weight: 700; margin-bottom: 4px; }
.herb-dosage { font-size: 13px; color: var(--ink-2); font-weight: 600; margin-bottom: 4px; font-variant-numeric: tabular-nums; }
.herb-effect { font-size: 12px; color: var(--ink-2); line-height: 1.5; }

.patient-herbs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.modification-text { margin-top: 16px; font-size: 13px; color: var(--ink-2); line-height: 1.7; display: flex; gap: 8px; align-items: baseline; }

/* Step7 care */
.care-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.care-block { padding: 14px 16px; background: var(--paper-sunken); border-radius: var(--radius-sm); }
.care-block h4 { display: flex; align-items: center; gap: 8px; font-size: 15px; color: var(--ink); margin-bottom: 8px; }
.care-block p { font-size: 14px; line-height: 1.7; color: var(--ink-2); }
.mini-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: var(--cinnabar);
  color: #FBF7EE;
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

/* Step8 disclaimer */
.disclaimer-card { background: #FBF6EA; border: 1px solid rgba(200, 164, 92, 0.3); }
.disclaimer-badge { background: var(--gold) !important; color: #1F1B16 !important; }
.disclaimer-text {
  font-size: 13px;
  color: var(--ink-2);
  line-height: 1.8;
  padding: 12px 16px;
  background: rgba(200, 164, 92, 0.1);
  border-radius: var(--radius-sm);
  border: 1px dashed rgba(200, 164, 92, 0.35);
  margin-bottom: 16px;
}
.report-btn { display: inline-flex; align-items: center; gap: 8px; }
.report-btn:disabled { opacity: 0.7; cursor: not-allowed; }

/* Source dialog */
.source-dialog-body { display: flex; flex-direction: column; gap: 16px; min-height: 60px; }
.source-meta { display: flex; align-items: center; gap: 12px; }
.source-quote {
  margin: 0;
  padding: 20px 24px;
  background: linear-gradient(135deg, rgba(200, 164, 92, 0.08) 0%, rgba(31, 58, 95, 0.04) 100%);
  border-left: 4px solid var(--gold);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-family: var(--font-serif);
  font-size: 15px;
  color: var(--ink);
  line-height: 2;
  letter-spacing: 0.5px;
}
.source-plain { font-size: 14px; color: var(--ink-2); line-height: 1.8; }

/* Responsive */
@media (max-width: 1024px) {
  .diagnose-layout { flex-direction: column; flex: none; min-height: 0; }
  .case-panel { width: 100%; max-width: none; min-height: 220px; max-height: 320px; }
  .stage-panel { width: 100%; min-height: 460px; }
  .intake-stage, .inquiry-stage { padding: 28px 24px; }
  .inquiry-question { font-size: 22px; }
  .care-grid { grid-template-columns: 1fr; }
}
</style>
