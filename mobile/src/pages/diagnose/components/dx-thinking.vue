<script setup lang="ts">
/**
 * 斟酌过场（宣纸面）。问诊卡之间等待 inquiry 响应时呈现：
 * 答 → 斟酌（脉动印章 + 水墨三点）→ 下一卡翻入。让网络等待变成有节奏的"被倾听"。
 */
</script>

<template>
  <view class="tk">
    <view class="tk__seal gf-seal gf-serif">思</view>
    <view class="tk__dots">
      <view v-for="i in 3" :key="i" class="tk__dot" :style="{ animationDelay: i * 0.16 + 's' }" />
    </view>
    <view class="tk__text gf-ink-3">李时珍正在斟酌下一问…</view>
  </view>
</template>

<style lang="scss" scoped>
.tk {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 28rpx;

  &__seal {
    width: 104rpx;
    height: 104rpx;
    font-size: 52rpx;
    animation: sealPulse 1.4s ease-in-out infinite;
  }
  &__dots {
    display: flex;
    gap: 14rpx;
  }
  &__dot {
    width: 14rpx;
    height: 14rpx;
    border-radius: 50%;
    background: $gold;
    animation: dotWave 1s ease-in-out infinite;
  }
  &__text {
    font-size: 28rpx;
    letter-spacing: 2rpx;
  }
}

@keyframes sealPulse {
  0%,
  100% {
    transform: scale(1);
    box-shadow: inset 0 0 0 1px rgba(251, 247, 238, 0.35), 0 0 0 0 rgba(154, 45, 45, 0.25);
  }
  50% {
    transform: scale(1.06);
    box-shadow: inset 0 0 0 1px rgba(251, 247, 238, 0.35), 0 0 0 16rpx rgba(154, 45, 45, 0);
  }
}
@keyframes dotWave {
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
  .tk__seal,
  .tk__dot {
    animation: none;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .tk { gap: 36rpx; }
  .tk__seal { width: 136rpx; height: 136rpx; font-size: 68rpx; }
  .tk__dots { gap: 18rpx; }
  .tk__dot { width: 18rpx; height: 18rpx; }
  .tk__text { font-size: var(--gf-fs-sm); letter-spacing: 3rpx; }
}
</style>
