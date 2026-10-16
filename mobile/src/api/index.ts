/**
 * 业务 API。本轮接入「仿真辨证」相关端点，与 PC 端 frontend/src/api/index.ts 对齐。
 * http.post/get 直接返回响应体（非 axios 的 { data }）。
 */
import { http, upload, uploadAuthorized } from "./request";

// V2 语音通过自有 WebSocket 代理转发 Fun-ASR；百炼 Key 不进入小程序。

// 问诊对话单轮：user=患者主诉/回答，assistant=系统已问出的问题
export interface InquiryTurn {
  role: "user" | "assistant";
  content: string;
}

// 后端 InquiryQuestion（原始字段名，含下划线）
export interface ApiInquiryOption {
  label: string;
  value: string;
}
export interface ApiInquiryQuestion {
  key: string;
  question: string;
  type: string; // single | multi | slider | text
  options: ApiInquiryOption[];
  min: number;
  max: number;
  min_label: string;
  max_label: string;
  unit: string;
  supplement?: boolean; // 补充确认型问题：前端展示「没有要补充的」一键按钮
}
export interface InquiryResponse {
  ready: boolean;
  questions: ApiInquiryQuestion[];
  session_id?: string | null;
}

export interface DiagnoseResponse {
  session_id: string;
  need_more: boolean;
  questions?: any[];
  result?: Record<string, any> | null;
  sources?: any[];
  role: string;
  disclaimer?: string;
  lab_findings?: string; // 本次实际读取到的化验单/检查报告要点（空=未带或未识别）
}

export interface ReportResponse {
  report_id: string;
  download_url: string;
  disclaimer?: string;
}

// 辨证：问诊充分性检查（返回 ready / questions）
export const inquiry = (
  symptoms: string,
  sessionId?: string | null,
  history: InquiryTurn[] = []
) =>
  http.post<InquiryResponse>("/chat/inquiry", {
    symptoms,
    session_id: sessionId,
    history,
  });

// 辨证：8 步思维链（skip_inquiry 跳过后端再次问诊）
// labImageIds：化验单原图直达辨证（方案乙，不做 OCR/摘要）。有值才带 lab_image_ids。
export const diagnose = (
  symptoms: string,
  role: string,
  sessionId?: string | null,
  skipInquiry = true,
  labImageIds?: string[]
) =>
  http.post<DiagnoseResponse>("/chat/diagnose", {
    symptoms,
    role,
    session_id: sessionId,
    skip_inquiry: skipInquiry,
    lab_image_ids: labImageIds && labImageIds.length ? labImageIds : undefined,
  });

// 报告
export const generateReport = (sessionId: string) =>
  http.post<ReportResponse>("/report/generate", { session_id: sessionId });

/* ===== 养生 ===== */
export const getSeasonalRegimen = (season: string) =>
  http.get("/regimen/seasonal", { season });
export const getOrganRegimen = (organ: string) =>
  http.get("/regimen/organ", { organ });

/* ===== 慢病 ===== */
export const getChronicDiseases = () => http.get("/chronic/diseases");
export const quickDiagnose = (disease: string, symptoms: string[], role = "patient") =>
  http.post("/chronic/quick-diagnose", { disease, symptoms, role });

/* ===== 知识库 ===== */
export const searchKnowledge = (
  q: string,
  category?: string,
  page = 1,
  pageSize = 10
) => http.get("/knowledge/search", { q, category, page, page_size: pageSize });
export const getKnowledgeStats = () => http.get("/knowledge/stats");
export const getKnowledgeEntry = (id: string) => http.get(`/knowledge/entry/${id}`);

// ===================== 拍照舌诊 =====================
export interface TongueFeatures {
  tongue_color: string;
  tongue_shape: string[];
  coating_color: string;
  coating_texture: string[];
  moisture: string;
}

export interface TongueAnalyzeResponse {
  ok: boolean;
  session_id?: string | null;
  reject_reason: string;
  retake_hint: string;
  features?: TongueFeatures | null;
  tcm_text: string;
  summary: string;
  confidence: number;
  disclaimer: string;
}

export interface TongueSubmitResponse {
  task_id: string;
}

export interface TongueResultResponse {
  status: "pending" | "done";
  result?: TongueAnalyzeResponse | null;
}

/** 提交舌象 → 后台异步分析，秒回 task_id。坏图/超限当场 400（reject 给调用方判重拍）。
 *  分析耗时改由 getTongueResult 轮询，避免单请求超时。上传超时放宽到 180s（弱网大图兜底）。 */
export const submitTongue = (filePath: string, sessionId?: string | null) =>
  upload<TongueSubmitResponse>(
    "/tongue/submit",
    filePath,
    { session_id: sessionId ?? undefined },
    180000
  );

/** 轮询舌象识别结果。status=pending 继续轮询，done 取 result。静默：失败不弹 toast。 */
export const getTongueResult = (taskId: string) =>
  http.getSilent<TongueResultResponse>(`/tongue/result/${taskId}`);

/** 拍照舌诊（同步等结果版，兼容保留；移动端主流程已改 submit+poll）。 */
export const analyzeTongue = (filePath: string, sessionId?: string | null) =>
  upload<TongueAnalyzeResponse>("/tongue/analyze", filePath, {
    session_id: sessionId ?? undefined,
  });

// ===================== 化验单上传（方案乙：原图直达辨证） =====================
export interface LabUploadResponse {
  lab_id: string;
}

/** 上传一份化验单原件（图片/PDF）→ 秒回 lab_id，后续随 diagnose 的 lab_image_ids 直送辨证。
 *  不做 OCR/摘要。坏图/超限后端 400 → reject（含 res，供调用方标记「失败·可重传」）。 */
export const uploadLab = (filePath: string) =>
  upload<LabUploadResponse>("/lab/upload", filePath, undefined, 180000);

// ===================== V2 多模态会话 =====================
export type V2TaskStatus = "queued" | "processing" | "succeeded" | "failed" | "expired";
export interface V2Session {
  consultation_id: string;
  consultation_token: string;
  status: string;
  expires_in: number;
}
export interface V2Task {
  task_id: string;
  type: "prepare" | "answer" | "finalize";
  status: V2TaskStatus;
  result?: Record<string, any> | null;
  error?: { code: string; message: string } | null;
}
export interface V2Attachment {
  attachment_id: string;
  filename: string;
  mime_type: string;
  size: number;
  pages: number;
  status: "ready";
}

const tokenHeader = (token: string) => ({ "X-Consultation-Token": token });
const taskHeaders = (token: string, idempotencyKey: string) => ({
  ...tokenHeader(token),
  "Idempotency-Key": idempotencyKey,
});

export const createConsultation = (role: string) =>
  http.post<V2Session>("/v2/consultations", { role });
export const uploadConsultationAttachment = (
  consultationId: string,
  token: string,
  filePath: string
) =>
  uploadAuthorized<V2Attachment>(
    `/v2/consultations/${consultationId}/attachments`,
    filePath,
    tokenHeader(token)
  );
export const deleteConsultationAttachment = (
  consultationId: string,
  token: string,
  attachmentId: string
) =>
  http.deleteWithHeaders(
    `/v2/consultations/${consultationId}/attachments/${attachmentId}`,
    tokenHeader(token)
  );
export const prepareConsultation = (
  consultationId: string,
  token: string,
  chiefComplaint: string,
  idempotencyKey: string
) =>
  http.postWithHeaders<{ task_id: string; status: V2TaskStatus }>(
    `/v2/consultations/${consultationId}/prepare`,
    { chief_complaint: chiefComplaint },
    taskHeaders(token, idempotencyKey)
  );
export const answerConsultation = (
  consultationId: string,
  token: string,
  answer: Record<string, any>,
  idempotencyKey: string
) =>
  http.postWithHeaders<{ task_id: string; status: V2TaskStatus }>(
    `/v2/consultations/${consultationId}/answers`,
    answer,
    taskHeaders(token, idempotencyKey)
  );
export const finalizeConsultation = (
  consultationId: string,
  token: string,
  idempotencyKey: string
) =>
  http.postWithHeaders<{ task_id: string; status: V2TaskStatus }>(
    `/v2/consultations/${consultationId}/finalize`,
    {},
    taskHeaders(token, idempotencyKey),
    600000
  );
export const getV2Task = (taskId: string, token: string) =>
  http.getWithHeaders<V2Task>(`/v2/tasks/${taskId}`, tokenHeader(token), true);
