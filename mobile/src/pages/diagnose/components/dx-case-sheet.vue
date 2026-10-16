<script setup lang="ts">
import type { CaseEntry } from "../types";

/**
 * 脉案 bottom sheet（宣纸面）。问诊期间可随时召唤，看清"已经说了什么"。
 * 交互重点：点任意已答条目 → 回退到那一问重答（父级负责截断后续）。
 */
defineProps<{
  modelValue: boolean;
  chief: string;
  entries: CaseEntry[]; // 已答问诊条目（不含主诉）
  current: number; // 当前问 index，用于高亮
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
    custom-style="border-radius:24rpx 24rpx 0 0;background:#F3ECDD;"
    @update:model-value="emit('update:modelValue', $event)"
    @close="close"
  >
    <!-- @touchmove.stop：面板手势不穿透到下层页面（内部 scroll-view 原生滚动不受影响） -->
    <view class="cs" @touchmove.stop>
      <view class="cs__bar">
        <view class="cs__title gf-serif">脉案</view>
        <view class="cs__close" @tap="close">
          <gf-icon name="close" :size="36" color="#5C5345" />
        </view>
      </view>

      <scroll-view scroll-y class="cs__scroll">
        <!-- 主诉 -->
        <view class="cs__chief">
          <view class="cs__seal gf-seal gf-serif">诉</view>
          <view class="cs__chief-text">{{ chief || "（未填写主诉）" }}</view>
        </view>

        <view v-if="entries.length" class="gf-divider" />

        <!-- 已答问诊 -->
        <view
          v-for="(en, i) in entries"
          :key="en.key"
          class="cs__entry"
          :class="{ active: i === current }"
          hover-class="cs__entry--hover"
          @tap="reopen(i)"
        >
          <view class="cs__entry-no gf-tnum">{{ i + 1 }}</view>
          <view class="cs__entry-body">
            <view class="cs__entry-q">{{ en.label }}</view>
            <view class="cs__entry-a" :class="{ skipped: en.skipped }">
              {{ en.skipped ? "已跳过" : en.answerText }}
            </view>
          </view>
          <gf-icon name="back" :size="30" color="#8A7E6A" />
        </view>

        <view class="cs__tip gf-ink-3">点任意一问可回到该问重答，后续作答将随之更新。</view>
      </scroll-view>
    </view>
  </wd-popup>
</template>

<style lang="scss" scoped>
.cs {
  max-height: 70vh;
  width: 100%;
  box-sizing: border-box;
  overflow-x: hidden; // 兜底：任何内层意外溢出都不产生横向滚动
  display: flex;
  flex-direction: column;

  &__bar {
    box-sizing: border-box; // 含横向 padding 时不撑出 100% 宽
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 28rpx 32rpx 16rpx;
  }
  &__title {
    font-size: 36rpx;
    font-weight: 700;
    color: $ink;
  }
  &__close {
    width: 56rpx;
    height: 56rpx;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &__scroll {
    flex: 1; // 关键：在 70vh 内约束高度，scroll-view 内部才能纵向滚动
    min-height: 0;
    box-sizing: border-box; // 含横向 padding 时不撑出 100% 宽 → 不再横向滚动
    padding: 0 32rpx 16rpx;
  }

  &__chief {
    display: flex;
    align-items: flex-start;
    gap: 18rpx;
    padding: 8rpx 0;
  }
  &__seal {
    width: 56rpx;
    height: 56rpx;
    font-size: 28rpx;
  }
  &__chief-text {
    flex: 1;
    font-size: 32rpx;
    line-height: 1.6;
    color: $ink;
  }

  &__entry {
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 18rpx;
    padding: 22rpx 20rpx;
    border-radius: $radius-sm;
    border: 1px solid transparent;
    &.active {
      border-color: $gold;
      background: $paper-card;
    }
    &--hover {
      background: $paper-sunken;
    }
  }
  &__entry-no {
    width: 44rpx;
    height: 44rpx;
    border-radius: 50%;
    background: $paper-sunken;
    color: $ink-2;
    font-size: 26rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  &__entry-body {
    flex: 1;
    min-width: 0;
  }
  &__entry-q {
    font-size: 28rpx;
    color: $ink-2;
  }
  &__entry-a {
    font-size: 32rpx;
    color: $ink;
    margin-top: 4rpx;
    &.skipped {
      color: $ink-3;
      font-style: italic;
    }
  }
  &__tip {
    font-size: 24rpx;
    line-height: 1.6;
    padding: 24rpx 8rpx 8rpx;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .cs { max-height: 80vh; }
  .cs__bar { padding: 36rpx 40rpx 22rpx; }
  .cs__title { font-size: var(--gf-fs-title); }
  .cs__close { width: 80rpx; height: 80rpx; }
  .cs__scroll { padding: 0 40rpx 24rpx; }
  .cs__chief { gap: 24rpx; padding: 14rpx 0; }
  .cs__seal { width: 80rpx; height: 80rpx; font-size: var(--gf-fs-sm); }
  .cs__chief-text { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }
  .cs__entry { gap: 24rpx; padding: 30rpx 26rpx; min-height: 116rpx; }
  .cs__entry-no { width: 64rpx; height: 64rpx; font-size: var(--gf-fs-sm); }
  .cs__entry-q { font-size: var(--gf-fs-sm); }
  .cs__entry-a { font-size: var(--gf-fs-base); margin-top: 8rpx; }
  .cs__tip { font-size: var(--gf-fs-sm); line-height: var(--gf-lh); padding: 32rpx 8rpx 12rpx; }
}
</style>
