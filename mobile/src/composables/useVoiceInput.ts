import { onUnmounted, ref, type Ref } from "vue";
import { API_BASE } from "@/api/request";
import { useRoleStore } from "@/stores/role";
import { ensureConsultationSession } from "./consultationSession";

export interface UseVoiceInputOptions {
  onResult: (text: string) => void;
}

export interface UseVoiceInputReturn {
  supported: Ref<boolean>;
  recording: Ref<boolean>;
  processing: Ref<boolean>;
  cancelArmed: Ref<boolean>;
  seconds: Ref<number>;
  liveText: Ref<string>;
  onPressStart: (e: TouchEvent) => void;
  onPressMove: (e: TouchEvent) => void;
  onPressEnd: () => void;
}

const WS_BASE = API_BASE.replace(/^http/, "ws");
const endsWithPunctuation = (text: string) => /[。！？；，,.!?;]$/.test(text);
const joinNaturally = (parts: string[]) =>
  parts.reduce((all, part) => {
    const text = part.trim();
    if (!text) return all;
    if (!all) return text;
    return all + (endsWithPunctuation(all) ? "" : "，") + text;
  }, "");

export function useVoiceInput(opts: UseVoiceInputOptions): UseVoiceInputReturn {
  const roleStore = useRoleStore();
  const supported = ref(typeof uni.getRecorderManager === "function");
  const recording = ref(false);
  const processing = ref(false);
  const cancelArmed = ref(false);
  const seconds = ref(0);
  const liveText = ref("");

  let startY = 0;
  let startedAt = 0;
  let pressingFinger = false;
  let timer: ReturnType<typeof setInterval> | null = null;
  let watchdog: ReturnType<typeof setTimeout> | null = null;
  let socket: UniApp.SocketTask | null = null;
  let finalParts: string[] = [];
  let pending: "fill" | "discard" = "discard";
  const recorder = supported.value ? uni.getRecorderManager() : null;

  function clearTimer() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  function clearWatchdog() {
    if (watchdog) clearTimeout(watchdog);
    watchdog = null;
  }

  function closeSocket() {
    socket?.close({ code: 1000, reason: "client_done" });
    socket = null;
  }

  function recover(message?: string) {
    clearTimer();
    clearWatchdog();
    recording.value = false;
    processing.value = false;
    closeSocket();
    if (message) uni.showToast({ title: message, icon: "none" });
  }

  function askOpenSetting() {
    uni.showModal({
      title: "需要麦克风权限",
      content: "语音说话要用到麦克风。点「去设置」，把「麦克风」打开后再试。",
      confirmText: "去设置",
      cancelText: "暂不",
      confirmColor: "#9A2D2D",
      success: ({ confirm }) => {
        if (confirm) uni.openSetting({});
      },
    });
  }

  function ensureRecordAuth(): Promise<boolean> {
    return new Promise((resolve) => {
      uni.getSetting({
        success: (res: any) => {
          const auth = res?.authSetting?.["scope.record"];
          if (auth === true) {
            resolve(true);
          } else if (auth === false) {
            askOpenSetting();
            resolve(false);
          } else {
            uni.authorize({
              scope: "scope.record",
              success: () => resolve(true),
              fail: () => {
                uni.showToast({ title: "未开麦克风也没关系，可以打字输入", icon: "none" });
                resolve(false);
              },
            });
          }
        },
        fail: () => resolve(true),
      });
    });
  }

  recorder?.onFrameRecorded(({ frameBuffer }: any) => {
    if (recording.value && socket) socket.send({ data: frameBuffer });
  });
  recorder?.onError(() => recover("语音启动失败，请手动输入"));
  recorder?.onStop(() => {
    if (pending === "fill" && socket) {
      processing.value = true;
      socket.send({ data: JSON.stringify({ type: "finish" }) });
      clearWatchdog();
      watchdog = setTimeout(
        () => recover("识别超时，请重试或手动输入"),
        12000
      );
    } else {
      closeSocket();
    }
  });

  function beginRecording() {
    if (!pressingFinger || !recorder) {
      recover();
      return;
    }
    recording.value = true;
    startedAt = Date.now();
    seconds.value = 0;
    liveText.value = "";
    finalParts = [];
    timer = setInterval(() => (seconds.value += 1), 1000);
    recorder.start({
      duration: 60000,
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 48000,
      format: "mp3",
      frameSize: 4,
    });
    uni.vibrateShort?.({ type: "light" } as any);
  }

  function connect(credentials: { id: string; token: string }) {
    socket = uni.connectSocket({
      url: `${WS_BASE}/v2/asr/realtime`,
      header: {
        "X-Consultation-Id": credentials.id,
        "X-Consultation-Token": credentials.token,
      },
      complete: () => {},
    });
    socket.onOpen(beginRecording);
    socket.onMessage(({ data }) => {
      if (typeof data !== "string") return;
      const event = JSON.parse(data);
      if (event.type === "partial") {
        liveText.value = joinNaturally([...finalParts, event.text || ""]);
      } else if (event.type === "final") {
        finalParts.push(event.text || "");
        liveText.value = joinNaturally(finalParts);
      } else if (event.type === "finished") {
        const text = joinNaturally(finalParts);
        recover();
        if (pending === "fill" && text) {
          opts.onResult(text);
          uni.showToast({ title: "已识别填入", icon: "none" });
        } else if (pending === "fill") {
          uni.showToast({ title: "没听清，请再说一次或打字输入", icon: "none" });
        }
      } else if (event.type === "error") {
        recover(event.message || "语音服务暂不可用，请手动输入");
      }
    });
    socket.onError(() => recover("网络不畅，请手动输入或稍后重试"));
    socket.onClose(() => {
      if (recording.value || processing.value) recover();
    });
  }

  async function onPressStart(e: TouchEvent) {
    if (!supported.value || recording.value || processing.value) return;
    pressingFinger = true;
    cancelArmed.value = false;
    startY = e.touches?.[0]?.clientY ?? 0;
    const authorized = await ensureRecordAuth();
    if (!authorized || !pressingFinger) return;
    const credentials = await ensureConsultationSession(roleStore.role);
    if (!pressingFinger) return;
    connect(credentials);
  }

  function onPressMove(e: TouchEvent) {
    if (!recording.value) return;
    const y = e.touches?.[0]?.clientY ?? 0;
    cancelArmed.value = startY - y > 80;
  }

  function onPressEnd() {
    pressingFinger = false;
    if (!recording.value) {
      closeSocket();
      return;
    }
    const tooShort = Date.now() - startedAt < 1000;
    pending = cancelArmed.value || tooShort ? "discard" : "fill";
    recording.value = false;
    clearTimer();
    recorder?.stop();
    if (cancelArmed.value) uni.showToast({ title: "已取消", icon: "none" });
    else if (tooShort) uni.showToast({ title: "说话时间太短", icon: "none" });
  }

  onUnmounted(() => {
    if (recording.value) recorder?.stop();
    recover();
  });

  return {
    supported,
    recording,
    processing,
    cancelArmed,
    seconds,
    liveText,
    onPressStart,
    onPressMove,
    onPressEnd,
  };
}
