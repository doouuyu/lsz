<script setup lang="ts">
/**
 * 录音 / 转写浮层（纯展示组件）。
 * 从 dx-intake.vue 原样抽出：rec-mask + rec-card 两态（录音中 / 转写中）
 * + 波纹 / 计时 / 上滑取消提示 / 转写点。交互无关，状态全由父层 props 驱动。
 *
 * 根元素 v-if 由父层控制（父层用 v-if="recording || processing" 渲染本组件）；
 * 组件内部再按 recording / processing 切换两态。
 */
defineProps<{
  recording: boolean;
  processing: boolean;
  cancelArmed: boolean;
  seconds: number;
  liveText: string;
}>();
</script>

<template>
  <!-- 长按录音 / 转写浮层（catchtouchmove 防滚动穿透） -->
  <view class="rec-mask" @touchmove.stop.prevent>
    <!-- 录音识别中 -->
    <view v-if="recording" class="rec-card" :class="{ 'is-cancel': cancelArmed }">
      <view class="rec-wave">
        <view v-for="i in 5" :key="i" class="rec-bar" :style="{ animationDelay: i * 0.1 + 's' }" />
      </view>
      <view v-if="liveText" class="rec-live">{{ liveText }}</view>
      <view class="rec-time gf-tnum">{{ seconds }}s</view>
      <view class="rec-tip">{{ cancelArmed ? "松开手指 · 取消" : "上滑取消　·　松开发送" }}</view>
    </view>
    <!-- 出结果中（非冻结反馈） -->
    <view v-else class="rec-card rec-card--proc">
      <view class="rec-proc-dots">
        <view v-for="i in 3" :key="i" class="rec-proc-dot" :style="{ animationDelay: i * 0.16 + 's' }" />
      </view>
      <view class="rec-tip">识别中…</view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
/* 录音浮层 */
.rec-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: rgba(31, 27, 22, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
}
.rec-card {
  width: 360rpx;
  padding: 48rpx 32rpx 32rpx;
  box-sizing: border-box;
  border-radius: $radius;
  background: $navy;
  color: $on-navy;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20rpx;
  box-shadow: $shadow-navy;
  &.is-cancel {
    background: $cinnabar;
  }
}
.rec-wave {
  display: flex;
  align-items: flex-end;
  gap: 8rpx;
  height: 72rpx;
}
.rec-bar {
  width: 10rpx;
  height: 24rpx;
  border-radius: 6rpx;
  background: $jade;
  animation: recPulse 0.8s ease-in-out infinite;
}
.rec-card.is-cancel .rec-bar {
  background: $paper-card;
}
.rec-live {
  max-width: 100%;
  font-size: 30rpx;
  line-height: 1.5;
  color: $on-navy;
  text-align: center;
  max-height: 180rpx;
  overflow: hidden;
}
.rec-time {
  font-size: 40rpx;
  font-weight: 700;
}
.rec-tip {
  font-size: 26rpx;
  opacity: 0.9;
}
@keyframes recPulse {
  0%,
  100% {
    height: 20rpx;
  }
  50% {
    height: 68rpx;
  }
}

/* 转写中 */
.rec-card--proc {
  padding: 56rpx 40rpx;
}
.rec-proc-dots {
  display: flex;
  gap: 14rpx;
  height: 40rpx;
  align-items: center;
}
.rec-proc-dot {
  width: 16rpx;
  height: 16rpx;
  border-radius: 50%;
  background: $jade;
  animation: recProc 1s ease-in-out infinite;
}
@keyframes recProc {
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
  .rec-bar {
    animation: none;
    height: 44rpx;
  }
  .rec-proc-dot {
    animation: none;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .rec-card {
    width: 480rpx;
    padding: 64rpx 44rpx 44rpx;
    gap: 28rpx;
  }
  .rec-live {
    font-size: var(--gf-fs-base);
    line-height: var(--gf-lh);
    max-height: 260rpx;
  }
  .rec-time {
    font-size: var(--gf-fs-lg);
  }
  .rec-tip {
    font-size: var(--gf-fs-sm);
  }
  .rec-card--proc {
    padding: 72rpx 52rpx;
  }
}
</style>
