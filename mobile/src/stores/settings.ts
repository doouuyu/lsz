/**
 * 全局设置 store（Pinia）。
 * 目前承载「老年模式」单一开关：放大字号 + 联动自动朗读结果。
 * 持久化到本地存储（uni.getStorageSync/setStorageSync），首启自动回灌。
 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";

const STORAGE_KEY = "lsz.settings.v1";

interface PersistShape {
  elderMode: boolean;
}

function loadPersisted(): PersistShape {
  try {
    const raw = uni.getStorageSync(STORAGE_KEY);
    if (raw && typeof raw === "object") return raw as PersistShape;
  } catch {
    /* 读取失败回退默认 */
  }
  return { elderMode: false };
}

export const useSettingsStore = defineStore("settings", () => {
  const persisted = loadPersisted();

  /** 老年模式：true 时全局放大字号 */
  const elderMode = ref<boolean>(persisted.elderMode);

  /**
   * 是否自动朗读结果。当前产品决策：完全跟随老年模式
   *（开老年模式即自动朗读，无独立开关）。TTS 实现见 composables/useTts。
   */
  const autoTts = computed(() => elderMode.value);

  function persist() {
    try {
      uni.setStorageSync(STORAGE_KEY, { elderMode: elderMode.value });
    } catch {
      /* 持久化失败忽略，不阻塞交互 */
    }
  }

  function setElderMode(on: boolean) {
    elderMode.value = on;
    persist();
  }
  function toggleElderMode() {
    setElderMode(!elderMode.value);
  }

  return { elderMode, autoTts, setElderMode, toggleElderMode };
});
