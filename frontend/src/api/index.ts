import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://192.168.50.145:8000/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,
})

// 后端站点根（用于 /reports 等非 /api 资源）
export const apiOrigin = API_BASE.replace(/\/api\/?$/, '')

// 问诊对话单轮：user=患者主诉/回答，assistant=系统已问出的问题
export interface InquiryTurn {
  role: 'user' | 'assistant'
  content: string
}

// 辨证：问诊充分性检查（返回 ready / questions）
// history 传完整问答记录，让模型据上下文连贯追问（首问紧扣主诉、后续承接上一答）
export const inquiry = (
  symptoms: string,
  sessionId?: string | null,
  history: InquiryTurn[] = [],
) =>
  api.post('/chat/inquiry', { symptoms, session_id: sessionId, history })

// 辨证：8 步思维链（skip_inquiry 跳过后端再次问诊）
export const diagnose = (
  symptoms: string,
  role: string,
  sessionId?: string | null,
  skipInquiry = true,
) =>
  api.post('/chat/diagnose', {
    symptoms,
    role,
    session_id: sessionId,
    skip_inquiry: skipInquiry,
  })

// 知识库
export const searchKnowledge = (
  query: string,
  category?: string,
  page = 1,
  pageSize = 10,
) =>
  api.get('/knowledge/search', {
    params: { q: query, category, page, page_size: pageSize },
  })

export const getKnowledgeGraph = (disease?: string, maxEntries = 80) =>
  api.get('/knowledge/graph', { params: { disease, max_entries: maxEntries } })

export const getKnowledgeEntry = (id: string) =>
  api.get(`/knowledge/entry/${id}`)

export const getKnowledgeStats = () =>
  api.get('/knowledge/stats')

export const listKnowledgeEntries = (params: {
  page?: number
  page_size?: number
  category?: string
  disease?: string
  q?: string
}) => api.get('/knowledge/list', { params })

export const getKnowledgeEvaluation = () =>
  api.get('/knowledge/evaluation')

// 养生
export const getSeasonalRegimen = (season: string) =>
  api.get('/regimen/seasonal', { params: { season } })

export const getOrganRegimen = (organ: string) =>
  api.get('/regimen/organ', { params: { organ } })

// 慢病
export const getChronicDiseases = () => api.get('/chronic/diseases')

export const quickDiagnose = (disease: string, symptoms: string[]) =>
  api.post('/chronic/quick-diagnose', { disease, symptoms })

// 报告
export const generateReport = (sessionId: string) =>
  api.post('/report/generate', { session_id: sessionId })

export default api
