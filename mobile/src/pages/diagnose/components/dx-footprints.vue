<script setup lang="ts">
/**
 * 足迹点（问诊进度）。
 * ⚠️ 红线：只显示「已走过」的步，绝不预排未来点 / 绝不出现 X-Y 总数（遵守"不预告步数"）。
 * 当前步放大为朱砂印点，已走过为金/墨小点；点任意点回退到那一问。
 */
defineProps<{
  count: number; // 已走过的步数（含当前）
  current: number; // 当前步 index（0-based）
}>();

const emit = defineEmits<{ (e: "jump", index: number): void }>();
</script>

<template>
  <scroll-view scroll-x class="fp" :show-scrollbar="false">
    <view class="fp__row">
      <view
        v-for="i in count"
        :key="i"
        class="fp__dot"
        :class="{ active: i - 1 === current, done: i - 1 < current }"
        @tap="emit('jump', i - 1)"
      />
    </view>
  </scroll-view>
</template>

<style lang="scss" scoped>
.fp {
  white-space: nowrap;
  padding: 16rpx 32rpx;
  box-sizing: border-box;

  &__row {
    display: inline-flex;
    align-items: center;
    gap: 18rpx;
  }
  &__dot {
    width: 16rpx;
    height: 16rpx;
    border-radius: 4rpx; // 方圆角印点
    background: rgba(31, 27, 22, 0.18);
    transition: all 0.2s ease;
    flex-shrink: 0;

    &.done {
      background: $gold;
    }
    &.active {
      width: 40rpx;
      height: 20rpx;
      border-radius: 6rpx;
      background: $cinnabar;
    }
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .fp { padding: 22rpx 40rpx; }
  .fp__row { gap: 24rpx; }
  .fp__dot { width: 22rpx; height: 22rpx; border-radius: 6rpx; }
  .fp__dot.active { width: 54rpx; height: 28rpx; border-radius: 8rpx; }
}
</style>
