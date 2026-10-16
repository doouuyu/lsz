<script setup lang="ts">
/**
 * 老年版 · 斟酌过场（dxe-thinking）。无 props/emit，与 dx-thinking 契约一致。
 *
 * 重排（相对 dx-thinking 非放大）：印章「思」放大居中、与文案纵向堆叠，
 * 文案改为老年大字单行并加大字距留白；脉动/三点尊重 reduced-motion。
 * 结构本就简单，重做量小，但 class 全用独立 dxe-tk 命名空间。
 */
</script>

<template>
  <view class="dxe dxe-tk">
    <view class="dxe-tk__seal gf-seal gf-serif">思</view>
    <view class="dxe-tk__dots">
      <view
        v-for="i in 3"
        :key="i"
        class="dxe-tk__dot"
        :style="{ animationDelay: i * 0.16 + 's' }"
      />
    </view>
    <view class="dxe-tk__text gf-ink-3">李时珍正在斟酌下一问…</view>
  </view>
</template>

<style lang="scss" scoped>
.dxe-tk {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 40rpx;

  &__seal {
    width: 144rpx;
    height: 144rpx;
    font-size: 72rpx;
    animation: dxeTkPulse 1.4s ease-in-out infinite;
  }
  &__dots {
    display: flex;
    gap: 20rpx;
  }
  &__dot {
    width: 20rpx;
    height: 20rpx;
    border-radius: 50%;
    background: $gold;
    animation: dxeTkWave 1s ease-in-out infinite;
  }
  &__text {
    font-size: var(--gf-fs-base);
    letter-spacing: 4rpx;
  }
}

@keyframes dxeTkPulse {
  0%,
  100% {
    transform: scale(1);
    box-shadow: inset 0 0 0 1px rgba(251, 247, 238, 0.35), 0 0 0 0 rgba(154, 45, 45, 0.25);
  }
  50% {
    transform: scale(1.06);
    box-shadow: inset 0 0 0 1px rgba(251, 247, 238, 0.35), 0 0 0 20rpx rgba(154, 45, 45, 0);
  }
}
@keyframes dxeTkWave {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  50% {
    transform: translateY(-12rpx);
    opacity: 1;
  }
}
@media (prefers-reduced-motion: reduce) {
  .dxe-tk__seal,
  .dxe-tk__dot {
    animation: none;
  }
}
</style>
