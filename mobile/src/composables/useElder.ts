/**
 * 老年模式接入 helper。
 * 页面把 rootClass 绑到根节点 -> 注入 .gf-elder -> CSS 变量向下继承，全树字号放大。
 *   <view class="xxx" :class="rootClass"> … </view>
 */
import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useSettingsStore } from "@/stores/settings";

export function useElder() {
  const store = useSettingsStore();
  const { elderMode, autoTts } = storeToRefs(store);
  const rootClass = computed(() => (elderMode.value ? "gf-elder" : ""));
  return {
    elderMode,
    autoTts,
    rootClass,
    toggleElderMode: store.toggleElderMode,
    setElderMode: store.setElderMode,
  };
}
