<script setup lang="ts">
import { onMounted, onUnmounted } from "vue";
import DxProgress from "./dx-progress.vue";

/**
 * 决断过场（宣纸明 → 藏青暗）。问诊被判定 ready 后的高光时刻。
 * 朱砂印章「四诊已明 · 胸有定见」盖印 + 轻震动。
 * 时机由编排层（useDiagnose.runDiagnose）控制：过场最短播放 + diagnose 返回，二者取其长后进结果。
 * 本组件只负责盖印动画 + 在盖印瞬间震一下。
 */
let t1: ReturnType<typeof setTimeout> | null = null;

onMounted(() => {
  // 盖印瞬间震一下（与 stampIn 动画的 0.45s 延迟对齐）
  t1 = setTimeout(() => uni.vibrateShort?.({ type: "medium" } as any), 520);
});
onUnmounted(() => {
  if (t1) clearTimeout(t1);
});
</script>

<template>
  <view class="dec">
    <!-- 藏青暗面自下而上覆盖（明→暗） -->
    <view class="dec__navy" />
    <!-- 印章 -->
    <view class="dec__stamp">四诊已明</view>
    <view class="dec__line" />
    <view class="dec__sub">胸有定见 · 正在辨证</view>
    <!-- 较长的辨证等待：渐近进度 + 文案轮播安抚情绪。组件卸载自清定时器，故 running 恒 true。 -->
    <view class="dec__progress">
      <dx-progress :running="true" tone="navy" />
    </view>
  </view>
</template>

<style lang="scss" scoped>
.dec {
  position: fixed;
  inset: 0;
  z-index: 900;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: $paper; // 起始为宣纸明面
}

/* 藏青暗面：自下而上揭幕 */
.dec__navy {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 50% 35%, rgba(95, 179, 161, 0.12), transparent 55%),
    linear-gradient(160deg, $navy 0%, $navy-2 100%);
  transform: translateY(100%);
  animation: navyRise 0.55s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

/* 朱砂印章盖印 */
.dec__stamp {
  position: relative;
  z-index: 2;
  font-family: $font-serif;
  font-size: 72rpx;
  font-weight: 700;
  letter-spacing: 8rpx;
  color: $paper-card;
  padding: 28rpx 44rpx;
  border-radius: 20rpx;
  background: $cinnabar;
  box-shadow: inset 0 0 0 3rpx rgba(251, 247, 238, 0.4), $shadow-navy;
  opacity: 0;
  transform: scale(1.6) rotate(-6deg);
  animation: stampIn 0.42s cubic-bezier(0.34, 1.56, 0.64, 1) 0.45s forwards;
}
.dec__line {
  position: relative;
  z-index: 2;
  width: 120rpx;
  height: 2rpx;
  margin: 32rpx 0 20rpx;
  background: linear-gradient(90deg, transparent, $gold, transparent);
  opacity: 0;
  animation: fadeIn 0.4s ease 0.75s forwards;
}
.dec__sub {
  position: relative;
  z-index: 2;
  font-size: 30rpx;
  letter-spacing: 4rpx;
  color: $on-navy-2;
  opacity: 0;
  animation: fadeIn 0.5s ease 0.85s forwards;
}
/* 进度条作为下方补充信息层：印章定格后淡入，留白与主体拉开 */
.dec__progress {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 560rpx;
  margin-top: 64rpx;
  padding: 0 48rpx;
  box-sizing: border-box;
  opacity: 0;
  animation: fadeIn 0.5s ease 1s forwards;
}

@keyframes navyRise {
  to {
    transform: translateY(0);
  }
}
@keyframes stampIn {
  to {
    opacity: 1;
    transform: scale(1) rotate(-3deg);
  }
}
@keyframes fadeIn {
  to {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dec__navy {
    animation: none;
    transform: translateY(0);
  }
  .dec__stamp,
  .dec__line,
  .dec__sub,
  .dec__progress {
    animation: none;
    opacity: 1;
    transform: none;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .dec__stamp { font-size: 96rpx; letter-spacing: 10rpx; padding: 36rpx 56rpx; }
  .dec__line { width: 160rpx; margin: 40rpx 0 26rpx; }
  .dec__sub { font-size: var(--gf-fs-base); letter-spacing: 5rpx; }
  .dec__progress { max-width: 640rpx; margin-top: 80rpx; }
}
</style>
