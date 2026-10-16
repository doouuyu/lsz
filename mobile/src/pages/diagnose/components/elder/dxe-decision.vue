<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import DxeProgress from "./dxe-progress.vue";

/**
 * 老年版 · 决断过场（dxe-decision）。无 props/emit，与 dx-decision 契约一致。
 *
 * 重排（相对 dx-decision 非放大）：盖印「四诊已明」放大并加大字距/留白，副文案
 * 与进度区改老年大字尺度，进度复用 dxe-progress（超粗轨大数字）。盖印瞬间轻震，
 * 全部动效尊重 reduced-motion。class 全用独立 dxe-dec 命名空间。
 */
let t1: ReturnType<typeof setTimeout> | null = null;

onMounted(() => {
  t1 = setTimeout(() => uni.vibrateShort?.({ type: "medium" } as any), 520);
});
onUnmounted(() => {
  if (t1) clearTimeout(t1);
});
</script>

<template>
  <view class="dxe dxe-dec">
    <view class="dxe-dec__navy" />
    <view class="dxe-dec__stamp">四诊已明</view>
    <view class="dxe-dec__line" />
    <view class="dxe-dec__sub">胸有定见 · 正在辨证</view>
    <view class="dxe-dec__progress">
      <dxe-progress :running="true" tone="navy" />
    </view>
  </view>
</template>

<style lang="scss" scoped>
.dxe-dec {
  position: fixed;
  inset: 0;
  z-index: 900;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: $paper;

  &__navy {
    position: absolute;
    inset: 0;
    background:
      radial-gradient(circle at 50% 35%, rgba(95, 179, 161, 0.12), transparent 55%),
      linear-gradient(160deg, $navy 0%, $navy-2 100%);
    transform: translateY(100%);
    animation: dxeDecRise 0.55s cubic-bezier(0.22, 1, 0.36, 1) forwards;
  }

  &__stamp {
    position: relative;
    z-index: 2;
    font-family: $font-serif;
    font-size: 96rpx;
    font-weight: 700;
    letter-spacing: 12rpx;
    color: $paper-card;
    padding: 36rpx 56rpx;
    border-radius: 24rpx;
    background: $cinnabar;
    box-shadow: inset 0 0 0 3rpx rgba(251, 247, 238, 0.4), $shadow-navy;
    opacity: 0;
    transform: scale(1.6) rotate(-6deg);
    animation: dxeDecStampIn 0.42s cubic-bezier(0.34, 1.56, 0.64, 1) 0.45s forwards;
  }
  &__line {
    position: relative;
    z-index: 2;
    width: 160rpx;
    height: 2rpx;
    margin: 40rpx 0 26rpx;
    background: linear-gradient(90deg, transparent, $gold, transparent);
    opacity: 0;
    animation: dxeDecFade 0.4s ease 0.75s forwards;
  }
  &__sub {
    position: relative;
    z-index: 2;
    font-size: var(--gf-fs-base);
    letter-spacing: 6rpx;
    color: $on-navy-2;
    opacity: 0;
    animation: dxeDecFade 0.5s ease 0.85s forwards;
  }
  &__progress {
    position: relative;
    z-index: 2;
    width: 100%;
    max-width: 640rpx;
    margin-top: 80rpx;
    padding: 0 48rpx;
    box-sizing: border-box;
    opacity: 0;
    animation: dxeDecFade 0.5s ease 1s forwards;
  }
}

@keyframes dxeDecRise {
  to {
    transform: translateY(0);
  }
}
@keyframes dxeDecStampIn {
  to {
    opacity: 1;
    transform: scale(1) rotate(-3deg);
  }
}
@keyframes dxeDecFade {
  to {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dxe-dec__navy {
    animation: none;
    transform: translateY(0);
  }
  .dxe-dec__stamp,
  .dxe-dec__line,
  .dxe-dec__sub,
  .dxe-dec__progress {
    animation: none;
    opacity: 1;
    transform: none;
  }
}
</style>
