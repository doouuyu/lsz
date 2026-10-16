/**
 * 仿真辨证 · 类型定义（对齐后端 app/models/schemas.py）。
 */

/* ===== 问诊（后端 InquiryQuestion） ===== */
export type QuestionType = "single" | "multi" | "slider" | "text";

export interface InquiryOption {
  label: string;
  value: string;
}

export interface InquiryQuestion {
  key: string; // 四诊维度，如 寒热/睡眠/二便
  question: string;
  type: QuestionType;
  options: InquiryOption[];
  min: number;
  max: number;
  minLabel: string;
  maxLabel: string;
  unit: string;
  supplement: boolean; // 补充确认型：卡片展示「没有要补充的」一键按钮
}

/** 单题作答快照（用于回看/改答比对） */
export interface AnswerSnapshot {
  single: string; // 单选 value
  multi: string[]; // 多选 values
  slider: number;
  supp: string; // 补充（text 题型即为答案本身）
  skipped: boolean;
}

export function emptySnapshot(min = 0): AnswerSnapshot {
  return { single: "", multi: [], slider: min, supp: "", skipped: false };
}

/** 脉案条目（展示用） */
export interface CaseEntry {
  key: string;
  label: string; // 问题标题（主诉为「主诉」）
  answerText: string;
  skipped?: boolean;
}

/* ===== 辨证结果视图模型（后端 8 步 JSON → VM，对齐 PC adapt()） ===== */
export interface Candidate {
  name: string;
  score: number; // 0-100
}
export interface Evidence {
  text: string;
  source: string;
  entry_id?: string;
}
export interface Herb {
  herb: string;
  dosage: string;
  role: string; // 君/臣/佐/使
  reason: string;
}
/** 文献引证（研究者版 step9_research.citations 单条） */
export interface Citation {
  ref: string; // 出处，如《伤寒论·辨太阳病脉证并治》
  point: string; // 对本案的支持说明
}
/** 理论溯源（研究者专属，后端 step9_research；其余角色为 null） */
export interface Research {
  theoryOrigin: string;
  citations: Citation[];
  schools: string;
}
export interface ViewModel {
  summary: string;
  location: { 病位: string[]; 病性: string[]; 气血津液: string };
  primary: string;
  concurrent: string[];
  confidence: number; // 0-100
  candidates: Candidate[];
  evidence: Evidence[];
  treatment: string;
  formula: { name: string; modification: string; herbs: Herb[] };
  care: { contraindication: string; diet: string; lifestyle: string; exercise: string };
  disclaimer: string;
  research: Research | null; // 研究者版理论溯源；其余角色 null（视图据此决定是否渲染该节）
}

/** 溯源条目（后端 KnowledgeEntry 子集） */
export interface SourceEntry {
  id: string;
  title: string;
  original_text: string;
  plain_explanation: string;
  source?: { book?: string; volume?: string; section?: string };
}

export type Role = "patient" | "doctor" | "researcher";
