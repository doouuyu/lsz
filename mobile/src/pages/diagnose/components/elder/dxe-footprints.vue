<script setup lang="ts">
import { computed } from "vue";

/**
 * 老年版 · 问诊进度（dxe-footprints）。契约同 dx-footprints（props count/current，emit jump）。
 *
 * 重排（相对 dx-footprints 非放大）：彻底放弃横滚小圆点（老人难辨/易误触），
 * 改为「第 N 问」文字进度大字 + 「← 上一问」明确文字回退按钮（点击 jump 到上一问）。
 * 严守红线：只显示当前序号（current+1），绝不预告总步数、绝不出现 X-Y。
 * count 仅用于判断「是否已有上一问可回退」，不展示为总数。
 */
const props = defineProps<{
  count: number; // 已走过步数（含当前）—— 仅用于判断可否回退，不展示
  current: number; // 当前步 index（0-based）
}>();

const emit = defineEmits<{ (e: "jump", index: number): void }>();

const canBack = computed(() => props.current > 0);
function back() {
  if (canBack.value) emit("jump", props.current - 1);
}
</script>

<template>
  <view class="dxe dxe-fp">
    <view class="dxe-fp__now gf-serif">
      第 <text class="dxe-fp__no gf-tnum">{{ current + 1 }}</text> 问
    </view>
    <view
      v-if="canBack"
      class="dxe-fp__back"
      hover-class="dxe-fp__back--hover"
      :hover-stay-time="60"
      @tap="back"
    >
      <gf-icon name="back" :size="34" color="#9A2D2D" />
      <text>上一问</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.dxe-fp {
  display: flex;
  align-items: center;
  gap: var(--dxe-gap);
  padding: 20rpx 32rpx;
  box-sizing: border-box;

  &__now {
    flex: 1;
    min-width: 0;
    font-size: var(--gf-fs-lg);
    font-weight: 700;
    color: $ink;
  }
  &__no {
    font-size: var(--gf-fs-title);
    color: $cinnabar;
    margin: 0 4rpx;
  }
  &__back {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 10rpx;
    min-height: var(--dxe-tap-h);
    padding: 0 32rpx;
    border-radius: 999rpx;
    border: 1px solid rgba(154, 45, 45, 0.45);
    background: rgba(154, 45, 45, 0.06);
    font-size: var(--gf-fs-sm);
    color: $cinnabar;

    &--hover {
      background: rgba(154, 45, 45, 0.12);
    }
  }
}
</style>
