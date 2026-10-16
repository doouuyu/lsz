/**
 * 仿真辨证 · V2 多模态会话流。
 * intake 主诉/附件 → prepare 首问 → answers 逐轮追问 → finalize 多模态报告。
 *
 * 关键不变量：
 *  - accumulated[0]=主诉，accumulated[i]=第 i-1 问的作答；fullSymptoms = accumulated.join('；')。
 *  - inquiryHistory 为「完整问答对」：主诉只记 user；每答一问补 assistant(问)+user(答)。
 *    回退到第 i 问（0-based）时截断到 1 + 2*i 条。
 *  - 充分性只认后端 ready；第 3～8 轮由后端统一控制。
 *  - 已提交回答不覆盖，避免前后端病例历史不一致。
 */
import { reactive, ref, computed } from "vue";
import { onHide, onShow } from "@dcloudio/uni-app";
import { storeToRefs } from "pinia";
import { useRoleStore } from "@/stores/role";
import {
  answerConsultation,
  deleteConsultationAttachment,
  finalizeConsultation,
  getV2Task,
  prepareConsultation,
  submitTongue,
  getTongueResult,
  uploadConsultationAttachment,
  type ApiInquiryQuestion,
  type InquiryTurn,
  type TongueAnalyzeResponse,
  type V2Task,
} from "@/api";
import {
  clearConsultationSession,
  ensureConsultationSession,
  getConsultationSession,
} from "@/composables/consultationSession";
import {
  emptySnapshot,
  type AnswerSnapshot,
  type CaseEntry,
  type InquiryQuestion,
  type Role,
  type SourceEntry,
  type ViewModel,
} from "./types";

export type Stage = "intake" | "inquiry" | "diagnosing" | "result";

const MAX_ROUNDS = 8;
const DECISION_MIN_MS = 1900; // 决断过场最短播放时长

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));
const normScore = (x: any) => {
  const n = Number(x) || 0;
  return n <= 1 ? Math.round(n * 100) : Math.round(n);
};
const sig = (s?: AnswerSnapshot) =>
  JSON.stringify(s ? { a: s.single, m: s.multi, s: s.slider, p: s.supp, k: s.skipped } : null);

function adaptQuestion(q: ApiInquiryQuestion): InquiryQuestion {
  const t = ["single", "multi", "slider", "text"].includes(q.type) ? q.type : "single";
  return {
    key: q.key || "",
    question: q.question || "",
    type: t as InquiryQuestion["type"],
    options: Array.isArray(q.options) ? q.options : [],
    min: q.min ?? 0,
    max: q.max ?? 10,
    minLabel: q.min_label || "",
    maxLabel: q.max_label || "",
    unit: q.unit || "",
    supplement: !!q.supplement,
  };
}

function adaptResult(result: any): ViewModel {
  const s2 = result.step2_location_nature || {};
  const s3 = result.step3_syndrome || {};
  const s6 = result.step6_formula || {};
  const s7 = result.step7_care || {};
  // step9_research 仅研究者版返回（后端按 role 切提示词时才生成）；缺失则置 null，视图不渲染该节。
  const s9 = result.step9_research;
  const research =
    s9 && typeof s9 === "object"
      ? {
          theoryOrigin: s9.theory_origin || "",
          citations: (Array.isArray(s9.citations) ? s9.citations : []).map((c: any) => ({
            ref: c?.ref || "",
            point: c?.point || "",
          })),
          schools: s9.schools || "",
        }
      : null;
  return {
    summary: result.step1_symptom_summary || "",
    location: { 病位: s2.病位 || [], 病性: s2.病性 || [], 气血津液: s2.气血津液 || "" },
    primary: s3.主证 || "待辨证",
    concurrent: s3.兼证 || [],
    confidence: normScore(s3.confidence),
    candidates: (s3.syndrome_candidates || []).map((c: any) => ({
      name: c.name,
      score: normScore(c.score),
    })),
    evidence: result.step4_classic_evidence || [],
    treatment: result.step5_treatment || "",
    formula: {
      name: s6.name || "",
      modification: s6.modification || "",
      herbs: (s6.composition || []).map((h: any) => ({
        herb: h.herb || "",
        dosage: h.dosage || "",
        role: h.role || "",
        reason: h.reason || "",
      })),
    },
    care: {
      contraindication: s7.contraindication || "",
      diet: s7.diet || "",
      lifestyle: s7.lifestyle || "",
      exercise: s7.exercise || "",
    },
    disclaimer:
      result.step8_disclaimer || "本结果为学术研究与辅助参考，不替代执业医师面诊。",
    research,
  };
}

/** 作答 → 文本（对齐 PC submitCard） */
function buildText(q: InquiryQuestion, s: AnswerSnapshot): string {
  if (s.skipped) return "这一项不太清楚";
  const parts: string[] = [];
  if (q.type === "text") {
    if (s.supp.trim()) parts.push(s.supp.trim());
  } else {
    if (q.type === "single" && s.single) parts.push(s.single);
    if (q.type === "multi" && s.multi.length) parts.push(s.multi.join("、"));
    if (q.type === "slider") parts.push(`${q.key || "程度"}：${s.slider}${q.unit || ""}`);
    if (s.supp.trim()) parts.push(s.supp.trim());
  }
  return parts.join("；") || "（未作答）";
}

export function useDiagnose() {
  let pageHidden = false;
  let pollWake: (() => void) | null = null;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;
  onHide(() => {
    pageHidden = true;
  });
  onShow(() => {
    pageHidden = false;
    pollWake?.();
  });

  function waitPoll(ms: number) {
    return new Promise<void>((resolve) => {
      const done = () => {
        if (pollTimer) clearTimeout(pollTimer);
        pollTimer = null;
        pollWake = null;
        resolve();
      };
      pollWake = done;
      pollTimer = setTimeout(done, ms);
    });
  }

  const stage = ref<Stage>("intake");
  const thinking = ref(false); // 斟酌下一问（等 inquiry 响应）
  const chief = ref("");
  // 角色提升为全局持久状态（pinia）：切换即向后端按角色重新生成（切提示词），而非前端裁剪。
  const roleStore = useRoleStore();
  const { role } = storeToRefs(roleStore);

  const sessionId = ref<string | null>(null);
  const consultationToken = ref("");
  const accumulated = ref<string[]>([]);
  const inquiryHistory = ref<InquiryTurn[]>([]);

  const questions = ref<InquiryQuestion[]>([]); // 已追问到的问题（每张卡一个）
  const answers = reactive<Record<number, AnswerSnapshot>>({});
  const qIndex = ref(0);
  const slideDir = ref<"fwd" | "back">("fwd");

  const vm = ref<ViewModel | null>(null);
  const sources = ref<SourceEntry[]>([]);
  const errorMsg = ref("");
  // 本次辨证是否实际纳入了化验单（以后端真实识别到的要点为准，而非只看上传成功）→ 结果页据此显示「含化验单」标识
  const usedLab = ref(false);
  // 后端视觉模型实际读取到的化验单要点文本（供结果页展示，让用户直观看到「确实读了」）；空=未带或未识别
  const labFindings = ref("");
  // 本次带了化验单原图但后端未能识别（要点为空）→ 结果页给「未能识别·建议重拍」提示
  const labUnreadable = ref(false);

  // ===== 角色自适应：按 role 重新请求 + 缓存 =====
  // 决断时把"最终提交给后端的入参"定格，供出结果后切角色时按同样上下文重发（仅换 role）。
  const lastSymptoms = ref<string>(""); // 含舌象/化验单注入后的完整主诉
  const lastLabIds = ref<string[]>([]);
  // 按 role 缓存结果，避免重复请求：{ doctor: {vm,sources}, ... }
  const roleCache = reactive<Record<string, { vm: ViewModel; sources: SourceEntry[] }>>({});
  const roleSwitching = ref(false); // 切角色重新请求中（视图据此显示 loading）

  function cacheRole(r: Role, v: ViewModel, s: SourceEntry[]) {
    roleCache[r] = { vm: v, sources: s };
  }

  // ===== 舌象后台识别：贯穿 intake→inquiry，决断前汇入 =====
  // 旧实现把识别做成 intake 内的全屏阻塞 loading（用户只能盯着舌头照片干等）；
  // 改为后台任务——拍完即可继续填问卷，识别结果在 runDiagnose 前 await 汇入辨证。
  const tongueStatus = ref<"idle" | "analyzing" | "done" | "degraded" | "retake">("idle");
  const tongueImg = ref(""); // 已采集的舌象图（临时路径）
  const tongueResult = ref<TongueAnalyzeResponse | null>(null); // ok=true 的分析结果
  const tongueHint = ref(""); // 需重拍 / 降级时的说明文案
  let tonguePromise: Promise<void> | null = null;
  let tongueReqId = 0; // 防竞态：删除/重拍后，旧请求回来不得复活已弃结果

  /** 舌象注入辨证的文本：优先中医术语，其次「已拍照片」占位，未拍则空 */
  const tongueNote = () =>
    tongueResult.value?.tcm_text
      ? `；舌象（拍照分析）：${tongueResult.value.tcm_text}`
      : tongueImg.value
        ? "；（已拍摄舌象照片供参考）"
        : "";

  const TONGUE_POLL_INTERVAL = 800; // 轮询间隔（快模型约 1~2s 出结果，间隔太大会把结果拖慢一拍）
  const TONGUE_POLL_MAX = 225; // 最多轮询次数（225×0.8s≈180s 上限，与后端识别超时一致）
  const TONGUE_POLL_FAIL_MAX = 6; // 连续轮询失败容忍上限（防瞬断误判超时）

  /** 把识别结果落到状态（ok/降级/需重拍） */
  function applyTongueResult(res: TongueAnalyzeResponse) {
    if (res.ok) {
      tongueResult.value = res;
      tongueStatus.value = "done";
      uni.vibrateShort?.({ type: "light" } as any);
    } else if (res.reject_reason === "vl_unavailable") {
      // 服务降级：保留照片走旧文本标记，不拦用户
      tongueStatus.value = "degraded";
      tongueHint.value = res.retake_hint || "舌象分析暂不可用，已保留照片";
    } else {
      // 门控未通过：软提示建议重拍，绝不打断用户作答
      tongueStatus.value = "retake";
      tongueHint.value = res.retake_hint || "照片不太清晰，建议重拍";
    }
  }

  /** 轮询任务结果，直到 done / 超时 / 被取消。被取消返回 null。 */
  async function pollTongue(taskId: string, myId: number): Promise<TongueAnalyzeResponse | null> {
    let fails = 0;
    for (let i = 0; i < TONGUE_POLL_MAX; i++) {
      await delay(TONGUE_POLL_INTERVAL);
      if (myId !== tongueReqId) return null; // 已被删除/替换
      try {
        const data = await getTongueResult(taskId);
        if (myId !== tongueReqId) return null;
        if (data.status === "done" && data.result) return data.result;
        fails = 0; // pending 也算一次成功通信
      } catch (e) {
        // 单次轮询失败容忍：瞬时网络抖动不应判超时；连续失败才放弃
        if (++fails >= TONGUE_POLL_FAIL_MAX) throw e;
      }
    }
    throw new Error("tongue_timeout");
  }

  /** 后台识别一张舌象：提交→轮询，全程不阻塞用户；结果到了改 tongueStatus，决断前由 runDiagnose await。 */
  function analyzeTongueBg(filePath: string) {
    const myId = ++tongueReqId;
    tongueImg.value = filePath;
    tongueResult.value = null;
    tongueHint.value = "";
    tongueStatus.value = "analyzing";
    tonguePromise = (async () => {
      try {
        const { task_id } = await submitTongue(filePath); // 上传，秒回任务号
        if (myId !== tongueReqId) return; // 已被删除/替换 → 丢弃
        const res = await pollTongue(task_id, myId);
        if (res === null || myId !== tongueReqId) return; // 被取消
        applyTongueResult(res);
      } catch (err: any) {
        if (myId !== tongueReqId) return;
        if (err && typeof err.statusCode === "number" && err.statusCode === 400) {
          // 提交阶段后端拒收（非有效图片/超过8MB）：建议重拍
          let detail = "照片不可用，建议重拍";
          try {
            detail = JSON.parse(err.data)?.detail || detail;
          } catch {
            /* 保持默认文案 */
          }
          tongueStatus.value = "retake";
          tongueHint.value = detail;
        } else {
          // 轮询超时 / 网络异常：降级保留照片，不阻断主流程
          tongueStatus.value = "degraded";
          tongueHint.value = "识别超时，舌象照片已保留";
        }
      }
    })();
  }

  /** 重新拍摄（intake 卡 / inquiry 软提示通用：直接调起相机，省去取景层） */
  function recaptureTongue() {
    uni.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["camera", "album"],
      sizeType: ["compressed"],
      camera: "back",
      success: (res: any) => {
        const f = res?.tempFiles?.[0];
        if (f?.tempFilePath) analyzeTongueBg(f.tempFilePath);
      },
      fail: () => {
        /* 取消：保留原状态 */
      },
    });
  }

  /** 仍用此张：消解「需重拍」软提示，照片退回文本标记 */
  function keepTongueAnyway() {
    if (tongueStatus.value === "retake") tongueStatus.value = "degraded";
  }

  /** 删除舌象：让在途请求作废 */
  function clearTongue() {
    tongueReqId++;
    tonguePromise = null;
    tongueImg.value = "";
    tongueResult.value = null;
    tongueHint.value = "";
    tongueStatus.value = "idle";
  }

  // ===== 化验单上传（方案乙：原图直达辨证，不做 OCR/识别，无需轮询）=====
  // 拍/选完即并发上传换 lab_id；决断 runDiagnose 时把 done 项的 lab_id 一并直送辨证。
  // 问诊阶段 fetchNext 不带化验单，互不影响舌象。后端 /lab/* 可能未上线 → 失败优雅降级（标 failed 可重传）。
  type LabFile = {
    localPath: string;
    isPdf: boolean;
    status: "uploading" | "done" | "failed";
    labId?: string;
  };
  const labFiles = ref<LabFile[]>([]);
  const uploadTasks = new Map<LabFile, Promise<void>>();
  let labFailToasted = false; // 一批里失败只 toast 一次，避免连珠弹

  /** 上传单项：成功写 labId+done，失败置 failed（首次失败 toast 一次）。 */
  async function uploadOne(file: LabFile) {
    try {
      const credentials = await ensureConsultationSession(role.value);
      sessionId.value = credentials.id;
      consultationToken.value = credentials.token;
      const result = await uploadConsultationAttachment(
        credentials.id,
        credentials.token,
        file.localPath
      );
      file.labId = result.attachment_id;
      file.status = "done";
    } catch {
      file.status = "failed";
      if (!labFailToasted) {
        labFailToasted = true;
        uni.showToast({ title: "附件上传失败，可重传", icon: "none" });
      }
    }
  }

  function startUpload(file: LabFile) {
    const task = uploadOne(file);
    uploadTasks.set(file, task);
    task.finally(() => uploadTasks.delete(file));
    return task;
  }

  /** 加入若干化验单（图片/PDF），逐项 push（uploading）后并发上传。 */
  function addLabFiles(items: { path: string; isPdf: boolean }[]) {
    if (!items?.length) return;
    labFailToasted = false;
    const remaining = Math.max(0, 5 - labFiles.value.length);
    const added: LabFile[] = items.slice(0, remaining).map((it) => ({
      localPath: it.path,
      isPdf: it.isPdf,
      status: "uploading" as const,
    }));
    labFiles.value.push(...added);
    added.forEach(startUpload);
  }

  /** 重传：对 failed 项重新上传。 */
  function retryLab(index: number) {
    const f = labFiles.value[index];
    if (!f || f.status !== "failed") return;
    labFailToasted = false;
    f.status = "uploading";
    startUpload(f);
  }

  /** 移除某项化验单。 */
  async function removeLab(index: number) {
    if (index < 0 || index >= labFiles.value.length) return;
    const file = labFiles.value[index];
    const credentials = getConsultationSession();
    if (file.labId && credentials) {
      await deleteConsultationAttachment(
        credentials.id,
        credentials.token,
        file.labId
      );
    }
    labFiles.value.splice(index, 1);
  }

  /** 清空化验单（reset/restart 调用）。 */
  function clearLab() {
    labFiles.value = [];
    uploadTasks.clear();
    labFailToasted = false;
  }

  const currentQuestion = computed<InquiryQuestion | undefined>(() => questions.value[qIndex.value]);
  const currentAnswer = computed<AnswerSnapshot>(
    () => answers[qIndex.value] || emptySnapshot(currentQuestion.value?.min ?? 0)
  );
  const reviewing = computed(() => false);
  const footprintCount = computed(() => questions.value.length);
  const answeredCount = computed(() => Math.max(0, accumulated.value.length - 1));

  const caseEntries = computed<CaseEntry[]>(() => {
    const list: CaseEntry[] = [];
    questions.value.forEach((q, i) => {
      const a = answers[i];
      if (!a) return;
      list.push({ key: q.key, label: q.question, skipped: a.skipped, answerText: buildText(q, a) });
    });
    return list;
  });

  function reset() {
    chief.value = "";
    accumulated.value = [];
    inquiryHistory.value = [];
    questions.value = [];
    for (const k of Object.keys(answers)) delete answers[Number(k)];
    qIndex.value = 0;
    vm.value = null;
    sources.value = [];
    errorMsg.value = "";
    thinking.value = false;
    usedLab.value = false;
    labFindings.value = "";
    labUnreadable.value = false;
    lastSymptoms.value = "";
    lastLabIds.value = [];
    for (const k of Object.keys(roleCache)) delete roleCache[k];
    roleSwitching.value = false;
    // 注意：不在此清化验单/舌象——它们是用户在录入屏刚上传的「本次输入」，
    // start() 提交主诉时会调 reset()，若在此 clearLab 会把刚传的化验单一起抹掉
    // （这正是「化验单上传成功却进不了辨证」的根因）。统一改由 restart() 清理。
  }

  function idempotencyKey(type: string) {
    return `${type}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }

  async function ensureV2Session() {
    const credentials = await ensureConsultationSession(role.value);
    sessionId.value = credentials.id;
    consultationToken.value = credentials.token;
    return credentials;
  }

  async function pollTask(taskId: string, timeoutMs = 20 * 60 * 1000): Promise<V2Task> {
    const startedAt = Date.now();
    let interval = 2000;
    let failures = 0;
    while (Date.now() - startedAt < timeoutMs) {
      await waitPoll(pageHidden ? Math.max(5000, interval) : interval);
      let pollError: any = null;
      const task = await getV2Task(taskId, consultationToken.value).then(
        (value) => value,
        (error) => {
          pollError = error;
          return null;
        }
      );
      if (!task) {
        if (pollError?.statusCode === 404 || pollError?.statusCode === 410) {
          throw new Error("CONSULTATION_EXPIRED");
        }
        failures += 1;
        if (failures >= 3) {
          uni.showToast({ title: "网络异常，正在继续重试", icon: "none" });
        }
        continue;
      }
      failures = 0;
      if (task.status === "succeeded") return task;
      if (task.status === "failed" || task.status === "expired") {
        throw new Error(task.error?.code || task.status);
      }
      if (Date.now() - startedAt > 30000) interval = Math.min(5000, interval + 500);
    }
    throw new Error("task_timeout");
  }

  /** 出报告前若舌象仍在识别：弹框让用户选「等结果（更准）/ 直接出结果」。返回 true=等待。 */
  function confirmWaitTongue(): Promise<boolean> {
    return new Promise((resolve) => {
      uni.showModal({
        title: "舌象还在识别",
        content: "舌象识别还没出结果。要等一下、让辨证把舌象也算进去吗？\n（直接出结果也行，本次辨证将不纳入舌象）",
        confirmText: "等一下",
        cancelText: "直接出结果",
        confirmColor: "#9A2D2D",
        success: (r) => resolve(!!r.confirm),
        fail: () => resolve(true), // 弹窗异常默认等待，宁可慢一点也别丢望诊
      });
    });
  }

  /** 主诉与已上传附件一起提交 V2 首次多模态任务。 */
  async function start(text: string) {
    reset();
    chief.value = text;
    accumulated.value = [text];
    inquiryHistory.value = [{ role: "user", content: text }];
    stage.value = "inquiry";
    thinking.value = true;
    errorMsg.value = "";
    try {
      const previous = getConsultationSession();
      if (previous && previous.role !== role.value) {
        clearConsultationSession();
        labFiles.value.forEach((file) => {
          file.labId = undefined;
          file.status = "uploading";
          startUpload(file);
        });
      }
      const credentials = await ensureV2Session();
      if (uploadTasks.size) await Promise.all(Array.from(uploadTasks.values()));
      const accepted = await prepareConsultation(
        credentials.id,
        credentials.token,
        text,
        idempotencyKey("prepare")
      );
      const task = await pollTask(accepted.task_id);
      const question = task.result?.next_question;
      if (!question) throw new Error("prepare_question_missing");
      if (task.result?.attachment_warning) {
        uni.showToast({ title: "部分附件未能识别，将继续问诊", icon: "none" });
      }
      questions.value.push(adaptQuestion(question as ApiInquiryQuestion));
      qIndex.value = 0;
      thinking.value = false;
    } catch (e: any) {
      thinking.value = false;
      stage.value = "intake";
      errorMsg.value = "问诊启动失败，请检查网络或配置后重试";
      uni.showToast({ title: errorMsg.value, icon: "none" });
    }
  }

  /** 最终 V2 任务内部完成检索词标准化、RAG 和多模态八步报告。 */
  async function runDiagnose() {
    stage.value = "diagnosing";
    const minAnim = delay(DECISION_MIN_MS);
    try {
      if (!sessionId.value || !consultationToken.value) throw new Error("session_missing");
      const accepted = await finalizeConsultation(
        sessionId.value,
        consultationToken.value,
        idempotencyKey("finalize")
      );
      const task = await pollTask(accepted.task_id);
      vm.value = adaptResult(task.result?.report || {});
      sources.value = (task.result?.sources || []) as SourceEntry[];
      usedLab.value = labFiles.value.some((file) => file.status === "done");
      labFindings.value = "";
      labUnreadable.value = false;
      cacheRole(role.value, vm.value, sources.value); // 当前角色结果入缓存
      await minAnim;
      stage.value = "result";
    } catch (e: any) {
      stage.value = "inquiry";
      errorMsg.value = "辨证没能完成，请重试";
      uni.showModal({
        title: "报告生成失败",
        content: "附件将在 30 分钟内保留，是否现在重试？",
        confirmText: "重试",
        cancelText: "稍后",
        success: ({ confirm }) => {
          if (confirm) runDiagnose();
        },
      });
    }
  }

  /**
   * 出结果后切换角色（全局 role 已变）：按角色重新请求后端（切提示词），命中缓存则秒切。
   * 仅在 result 阶段、已有定格入参时生效；缺会话/入参时静默忽略（理论不会发生）。
   */
  async function switchRole(target: Role) {
    if (target === role.value) return;
    uni.showToast({ title: "报告视角已在问诊开始时锁定", icon: "none" });
  }

  /** 截断第 i 问之后的所有状态（改答时调用） */
  function truncateAfter(i: number) {
    questions.value.splice(i + 1);
    accumulated.value.splice(i + 1); // 保留 [主诉, q0..q_{i-1} 的答]
    inquiryHistory.value.splice(2 * i + 1); // 保留主诉(1) + 前 i 问的问答对(2i)
    for (const k of Object.keys(answers)) {
      if (Number(k) > i) delete answers[Number(k)];
    }
  }

  /** 提交当前卡作答 */
  async function submit(snap: AnswerSnapshot) {
    const i = qIndex.value;
    const q = questions.value[i];
    if (!q) return;
    const changed = sig(answers[i]) !== sig(snap);
    answers[i] = snap;
    const atFrontier = i === questions.value.length - 1;

    if (!changed && !atFrontier) {
      // 回看后未改 → 直接前进到已存在的下一问，不发请求
      slideDir.value = "fwd";
      qIndex.value = i + 1;
      return;
    }

    truncateAfter(i);
    const text = buildText(q, snap);
    accumulated.value.push(text);
    inquiryHistory.value.push({ role: "assistant", content: q.question });
    inquiryHistory.value.push({ role: "user", content: text });
    thinking.value = true;
    errorMsg.value = "";
    try {
      if (!sessionId.value || !consultationToken.value) throw new Error("session_missing");
      const accepted = await answerConsultation(
        sessionId.value,
        consultationToken.value,
        {
          answer: text,
          skipped: snap.skipped,
          question_key: q.key,
          structured_answer: snap,
        },
        idempotencyKey(`answer-${i}`)
      );
      const task = await pollTask(accepted.task_id);
      if (task.result?.ready || answeredCount.value >= MAX_ROUNDS) {
        thinking.value = false;
        await runDiagnose();
        return;
      }
      const nextQuestion = task.result?.next_question;
      if (!nextQuestion) throw new Error("question_missing");
      questions.value.push(adaptQuestion(nextQuestion as ApiInquiryQuestion));
      await delay(220);
      slideDir.value = "fwd";
      qIndex.value = questions.value.length - 1;
      thinking.value = false;
    } catch (e: any) {
      thinking.value = false;
      accumulated.value.pop();
      inquiryHistory.value.splice(-2);
      errorMsg.value =
        e?.message === "CONSULTATION_EXPIRED"
          ? "问诊已过期，请重新开始"
          : "问诊没能继续，答案已保留，请重试";
      uni.showToast({ title: errorMsg.value, icon: "none" });
    }
  }

  function skip() {
    const q = currentQuestion.value;
    const snap = emptySnapshot(q?.min ?? 0);
    snap.skipped = true;
    return submit(snap);
  }

  function prev() {
    uni.showToast({ title: "已提交回答不能修改，可在后续补充说明", icon: "none" });
  }

  function goto(i: number) {
    if (i !== qIndex.value) {
      uni.showToast({ title: "已提交回答不能修改，可在后续补充说明", icon: "none" });
    }
  }

  function restart() {
    reset();
    clearTongue(); // 重新辨证才真正清掉上次的舌象
    clearLab(); // 与舌象一致：仅在重新辨证时清化验单，避免 start() 误抹本次上传
    clearConsultationSession();
    sessionId.value = null;
    consultationToken.value = "";
    stage.value = "intake";
  }

  return {
    // state
    stage,
    thinking,
    chief,
    role,
    sessionId,
    questions,
    answers,
    qIndex,
    slideDir,
    vm,
    sources,
    errorMsg,
    usedLab,
    labFindings,
    labUnreadable,
    // 角色自适应
    roleSwitching,
    switchRole,
    // 舌象后台识别
    tongueStatus,
    tongueImg,
    tongueResult,
    tongueHint,
    analyzeTongueBg,
    recaptureTongue,
    keepTongueAnyway,
    clearTongue,
    // 化验单上传
    labFiles,
    addLabFiles,
    retryLab,
    removeLab,
    // computed
    currentQuestion,
    currentAnswer,
    reviewing,
    footprintCount,
    caseEntries,
    // actions
    start,
    submit,
    skip,
    prev,
    goto,
    restart,
  };
}
