<script setup lang="ts">
import type { CaseEntry } from "../../types";

/**
 * 老年版 · 脉案 bottom sheet（dxe-case-sheet）。
 * 契约同 dx-case-sheet（props modelValue/chief/entries/current；emit update:modelValue/reopen）。
 *
 * 重排（相对 dx-case-sheet 非放大）：条目改单列超大行——序号印章 + 「问/答」双行
 * 纵向堆叠（答案为老年大字主体、问题为辅助字），每条 ≥ 触控高度、回退入口（整条可点 +
 * 行尾回退箭头）明确；标题区与关闭键放大；整屏可滚。class 全用独立 dxe-cs 命名空间。
 */
defineProps<{
  modelValue: boolean;
  chief: string;
  entries: CaseEntry[];
  current: number;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "reopen", index: number): void;
}>();

function close() {
  emit("update:modelValue", false);
}
function reopen(i: number) {
  emit("reopen", i);
  close();
}
</script>

<template>
  <wd-popup
    :model-value="modelValue"
    position="bottom"
    :safe-area-inset-bottom="true"
    custom-style="border-radius:28rpx 28rpx 0 0;background:#F3ECDD;"
    @update:model-value="emit('update:modelValue', $event)"
    @close="close"
  >
    <view class="dxe dxe-cs" @touchmove.stop>
      <view class="dxe-cs__bar">
        <view class="dxe-cs__title gf-serif">脉案</view>
        <view class="dxe-cs__close" @tap="close">
          <gf-icon name="close" :size="44" color="#5C5345" />
        </view>
      </view>

      <scroll-view scroll-y class="dxe-cs__scroll">
        <!-- 主诉 -->
        <view class="dxe-cs__chief">
          <view class="dxe-cs__seal gf-seal gf-serif">诉</view>
          <view class="dxe-cs__chief-body">
            <view class="dxe-cs__chief-label gf-ink-3">主诉</view>
            <view class="dxe-cs__chief-text">{{ chief || "（未填写主诉）" }}</view>
          </view>
        </view>

        <view v-if="entries.length" class="dxe-cs__divider" />

        <!-- 已答问诊：单列大行，问/答双行 -->
        <view
          v-for="(en, i) in entries"
          :key="en.key"
          class="dxe-cs__entry"
          :class="{ active: i === current }"
          hover-class="dxe-cs__entry--hover"
          @tap="reopen(i)"
        >
          <view class="dxe-cs__entry-top">
            <view class="dxe-cs__entry-no gf-tnum">{{ i + 1 }}</view>
            <view class="dxe-cs__entry-q">{{ en.label }}</view>
          </view>
          <view class="dxe-cs__entry-a" :class="{ skipped: en.skipped }">
            {{ en.skipped ? "已跳过" : en.answerText }}
          </view>
          <view class="dxe-cs__entry-reopen">
            <gf-icon name="back" :size="32" color="#9A2D2D" />
            <text>回到这一问重答</text>
          </view>
        </view>

        <view class="dxe-cs__tip gf-ink-3">点任意一问可回到该问重答，后续作答将随之更新。</view>
      </scroll-view>
    </view>
  </wd-popup>
</template>

<style lang="scss" scoped>
.dxe-cs {
  max-height: 82vh;
  width: 100%;
  box-sizing: border-box;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;

  &__bar {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 36rpx 40rpx 22rpx;
  }
  &__title {
    font-size: var(--gf-fs-title);
    font-weight: 700;
    color: $ink;
  }
  &__close {
    width: 88rpx;
    height: 88rpx;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &__scroll {
    flex: 1;
    min-height: 0;
    box-sizing: border-box;
    padding: 0 40rpx 24rpx;
  }

  &__chief {
    display: flex;
    align-items: flex-start;
    gap: 24rpx;
    padding: 16rpx 0;
  }
  &__seal {
    width: 80rpx;
    height: 80rpx;
    font-size: var(--gf-fs-base);
  }
  &__chief-body {
    flex: 1;
    min-width: 0;
  }
  &__chief-label {
    font-size: var(--gf-fs-sm);
    margin-bottom: 8rpx;
  }
  &__chief-text {
    font-size: var(--gf-fs-lg);
    line-height: var(--gf-lh);
    color: $ink;
  }

  &__divider {
    height: 2rpx;
    background: linear-gradient(90deg, transparent, $gold 18%, $gold 82%, transparent);
    opacity: 0.7;
    margin: 32rpx 0;
  }

  &__entry {
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 14rpx;
    padding: 28rpx 26rpx;
    margin-bottom: 20rpx;
    border-radius: var(--dxe-radius-sm);
    border: 1px solid $border-paper;
    background: $paper-card;
    &.active {
      border-color: $gold;
    }
    &--hover {
      background: $paper-sunken;
    }
  }
  &__entry-top {
    display: flex;
    align-items: center;
    gap: 20rpx;
  }
  &__entry-no {
    width: 64rpx;
    height: 64rpx;
    border-radius: 50%;
    background: $paper-sunken;
    color: $ink-2;
    font-size: var(--gf-fs-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  &__entry-q {
    flex: 1;
    min-width: 0;
    font-size: var(--gf-fs-sm);
    color: $ink-2;
  }
  &__entry-a {
    font-size: var(--gf-fs-base);
    line-height: var(--gf-lh);
    color: $ink;
    &.skipped {
      color: $ink-3;
      font-style: italic;
    }
  }
  &__entry-reopen {
    display: inline-flex;
    align-items: center;
    align-self: flex-start;
    gap: 10rpx;
    min-height: var(--dxe-tap-h);
    padding: 0 28rpx;
    border-radius: 999rpx;
    background: rgba(154, 45, 45, 0.06);
    border: 1px solid rgba(154, 45, 45, 0.4);
    font-size: var(--gf-fs-sm);
    color: $cinnabar;
  }
  &__tip {
    font-size: var(--gf-fs-sm);
    line-height: var(--gf-lh);
    padding: 32rpx 8rpx 12rpx;
  }
}
</style>
