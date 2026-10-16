<script setup lang="ts">
import { computed } from "vue";
import { useTts } from "@/composables/useTts";

/**
 * 朗读按钮（gf-* easycom 自动注册）。
 * 点击切换朗读 props.text；正在读本段时图标切 sound-off 并轻微脉动。
 * 仅微信小程序支持 WechatSI textToSpeech，supported=false 时整体不渲染。
 *
 * tone: paper（宣纸面，默认）/ navy（藏青深色面），决定描边/底色取哪一套 token。
 */
const props = withDefaults(
  defineProps<{
    text: string;
    /** 图标尺寸（rpx） */
    size?: number;
    /** 表面：宣纸面 / 藏青面 */
    tone?: "paper" | "navy";
    /** 可选文字标签，如「朗读报告」 */
    label?: string;
  }>(),
  { size: 36, tone: "paper", label: "" }
);

const { supported, playing, currentText, toggle } = useTts();

// 是否正在朗读「本段」（区别于全局其它 gf-speaker 在播）
const active = computed(
  () => playing.value && currentText.value === (props.text || "").trim()
);

const isNavy = computed(() => props.tone === "navy");

// 朗读中用强调色（宣纸面朱砂 / 藏青面玉色），静止用次文字色
const iconColor = computed(() => {
  if (active.value) return isNavy.value ? "#5FB3A1" : "#9A2D2D";
  return isNavy.value ? "#EAF0F6" : "#5C5345";
});

const iconName = computed(() => (active.value ? "sound-off" : "sound"));

function onTap() {
  toggle(props.text);
}
</script>

<template>
  <view
    v-if="supported"
    class="gf-speaker"
    :class="[`is-${tone}`, { 'is-active': active }]"
    hover-class="gf-speaker--hover"
    :hover-stay-time="60"
    @tap="onTap"
  >
    <view class="gf-speaker__ico" :class="{ pulse: active }">
      <gf-icon :name="iconName" :size="size" :color="iconColor" />
    </view>
    <text v-if="label" class="gf-speaker__label">{{ label }}</text>
  </view>
</template>

<style lang="scss" scoped>
.gf-speaker {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10rpx;
  // 触控区 ≥ 88rpx
  min-width: 88rpx;
  min-height: 88rpx;
  padding: 0 18rpx;
  box-sizing: border-box;
  border-radius: 999rpx;
  border: 1rpx solid transparent;

  // —— 宣纸面 ——
  &.is-paper {
    background: $paper-card;
    border-color: $border-paper;
    .gf-speaker__label {
      color: $ink-2;
    }
    &.is-active {
      border-color: $cinnabar;
      .gf-speaker__label {
        color: $cinnabar;
      }
    }
  }

  // —— 藏青面 ——
  &.is-navy {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.18);
    .gf-speaker__label {
      color: $on-navy-2;
    }
    &.is-active {
      border-color: $jade;
      .gf-speaker__label {
        color: $jade;
      }
    }
  }

  &--hover {
    opacity: 0.8;
  }

  &__ico {
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  &__label {
    font-size: 28rpx;
    line-height: 1;
  }
}

// 朗读中轻微脉动
.pulse {
  animation: gf-speaker-pulse 1.1s ease-in-out infinite;
}

@keyframes gf-speaker-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.12);
    opacity: 0.72;
  }
}

// 尊重「减少动态效果」：脉动降级为静态
@media (prefers-reduced-motion: reduce) {
  .pulse {
    animation: none;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .gf-speaker {
    min-width: 128rpx;
    min-height: 112rpx;
    padding: 0 28rpx;
    gap: 16rpx;
  }
  .gf-speaker__ico {
    min-width: 80rpx;
    min-height: 80rpx;
  }
  .gf-speaker__label {
    font-size: var(--gf-fs-sm);
  }
}
</style>
