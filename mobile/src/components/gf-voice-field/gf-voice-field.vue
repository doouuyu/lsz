<script setup lang="ts">
import { computed } from "vue";
import { useVoiceInput } from "@/composables/useVoiceInput";

/**
 * 「textarea + 角落小话筒」输入框（宣纸面）。供所有需要语音的输入框复用
 * （主诉框、问诊补充框、备注框等）。长按话筒说话，与主诉框一致的交互。
 *
 * - 语音识别逻辑全部来自 useVoiceInput（自有 WSS → Fun-ASR）。
 * - 录音浮层由 <gf-rec-overlay> 渲染，状态由 useVoiceInput 驱动。
 * - supported=false（运行端无 RecorderManager）时不渲染话筒，优雅降级为纯 textarea。
 */
const props = withDefaults(
  defineProps<{
    modelValue: string;
    placeholder?: string;
    minHeight?: number; // rpx
    maxlength?: number;
  }>(),
  {
    placeholder: "",
    minHeight: 200,
    maxlength: -1,
  }
);

const emit = defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const value = computed<string>({
  get: () => props.modelValue,
  set: (v) => emit("update:modelValue", v),
});

const minHeightStyle = computed(() => `${props.minHeight}rpx`);

/** 把多段识别文本按自然标点衔接，不自动提交。 */
function appendResult(text: string) {
  const cur = (props.modelValue || "").trim();
  if (!cur) {
    emit("update:modelValue", text);
  } else if (cur.includes(text)) {
    return; // 已含则不重复
  } else {
    const separator = /[。！？；，,.!?;]$/.test(cur) ? "" : "，";
    emit("update:modelValue", cur + separator + text);
  }
}

const { supported, recording, processing, cancelArmed, seconds, liveText, onPressStart, onPressMove, onPressEnd } =
  useVoiceInput({ onResult: appendResult });
</script>

<template>
  <view class="vf">
    <textarea
      v-model="value"
      class="vf__textarea"
      :style="{ minHeight: minHeightStyle }"
      :maxlength="maxlength"
      :auto-height="true"
      :adjust-position="true"
      :cursor-spacing="32"
      :show-confirm-bar="false"
      :placeholder="placeholder"
      placeholder-class="vf__ph"
    />

    <!-- 角落小话筒（长按说话）；supported=false 时不渲染，纯 textarea 降级 -->
    <view
      v-if="supported"
      class="vf__mic"
      :class="{ 'is-recording': recording }"
      @touchstart.stop.prevent="onPressStart"
      @touchmove.stop.prevent="onPressMove"
      @touchend.stop.prevent="onPressEnd"
      @touchcancel.stop.prevent="onPressEnd"
    >
      <gf-icon name="mic" :size="40" :color="recording ? '#FBF7EE' : '#5C5345'" />
    </view>

    <!-- 录音 / 转写浮层 -->
    <gf-rec-overlay
      v-if="recording || processing"
      :recording="recording"
      :processing="processing"
      :cancel-armed="cancelArmed"
      :seconds="seconds"
      :live-text="liveText"
    />
  </view>
</template>

<style lang="scss" scoped>
.vf {
  position: relative;
  width: 100%;

  &__textarea {
    width: 100%;
    min-height: 200rpx;
    padding: 24rpx;
    padding-right: 104rpx; // 让出右下角话筒触控区
    background: $paper-card;
    border: 1px solid $border-paper;
    border-radius: $radius-sm;
    font-size: 34rpx;
    line-height: 1.6;
    color: $ink;
    box-sizing: border-box;
  }
  &__ph {
    color: $ink-3;
  }

  /* 角落小话筒：触控区 ≥88rpx，录音时朱砂高亮 */
  &__mic {
    position: absolute;
    right: 12rpx;
    bottom: 12rpx;
    width: 88rpx;
    height: 88rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: $radius-sm;
    background: $paper-sunken;
    border: 1px solid $border-paper;
    &.is-recording {
      background: $cinnabar;
      border-color: $cinnabar;
    }
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .vf__textarea {
    padding: 32rpx;
    padding-right: 140rpx;
    font-size: var(--gf-fs-lg);
    line-height: var(--gf-lh);
  }
  .vf__ph {
    font-size: var(--gf-fs-lg);
  }
  .vf__mic {
    right: 16rpx;
    bottom: 16rpx;
    width: 120rpx;
    height: 120rpx;
  }
}
</style>
