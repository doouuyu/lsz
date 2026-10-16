<script setup lang="ts">
import { ref, computed, watch } from "vue";
import type { AnswerSnapshot, InquiryQuestion } from "../types";
import { emptySnapshot } from "../types";

/**
 * 单个问诊问题 · 整屏步进卡（宣纸面）。对齐后端题型 single/multi/slider/text。
 * 交互重点：
 *  - single：点选只高亮、可改选，显式「下一问」确认（防误触）。
 *  - multi：多选，显式「下一问」。
 *  - slider：wd-slider，始终有值，带 min/max 文案。
 *  - text：textarea 即答案，自动避让键盘。
 *  - supplement（补充确认型 text）：没填字时主按钮为「没有要补充的」一键作答，
 *    打了字自动变「提交补充」；不再显示「跳过」（语义重复）。
 *  - single/multi/slider 可展开「补充说明（选填）」。
 *  - 底部统一 [上一问] [跳过] [下一问]，跨题型一致可预期。
 */
const props = withDefaults(
  defineProps<{
    question: InquiryQuestion;
    modelValue?: AnswerSnapshot;
    reviewing?: boolean;
    canPrev?: boolean;
    seal?: number;
    busy?: boolean;
  }>(),
  { reviewing: false, canPrev: false, seal: 1, busy: false }
);

const emit = defineEmits<{
  (e: "submit", snap: AnswerSnapshot): void;
  (e: "prev"): void;
  (e: "skip"): void;
}>();

const single = ref("");
const multi = ref<string[]>([]);
const slider = ref(0);
const supp = ref("");
const suppOpen = ref(false);
const locked = ref(false);

// 翻卡即按 modelValue 重置本地（回看时回填旧答案）
watch(
  () => props.question.key + "@" + props.seal,
  () => {
    const s = props.modelValue || emptySnapshot(props.question.min ?? 0);
    single.value = s.single;
    multi.value = [...s.multi];
    slider.value = typeof s.slider === "number" ? s.slider : props.question.min ?? 0;
    supp.value = s.supp;
    suppOpen.value = !!s.supp;
    locked.value = false;
  },
  { immediate: true }
);

const answered = computed(() => {
  switch (props.question.type) {
    case "single":
      return !!single.value;
    case "multi":
      return multi.value.length > 0;
    case "slider":
      return true;
    case "text":
      return !!supp.value.trim();
  }
  return false;
});

function snapshot(): AnswerSnapshot {
  return {
    single: single.value,
    multi: [...multi.value],
    slider: slider.value,
    supp: supp.value.trim(),
    skipped: false,
  };
}

function doSubmit() {
  if (locked.value) return;
  locked.value = true;
  emit("submit", snapshot());
}

function pickSingle(value: string) {
  single.value = value;
  uni.vibrateShort?.({ type: "light" } as any);
}

/* —— 补充确认型（supplement）：一键「没有要补充的」 —— */
const isSupplement = computed(() => props.question.type === "text" && !!props.question.supplement);
const NO_SUPP_TEXT = "没有其他要补充的了";

function onNoSupplement() {
  supp.value = NO_SUPP_TEXT;
  uni.vibrateShort?.({ type: "light" } as any);
  doSubmit();
}

function toggleMulti(value: string) {
  const i = multi.value.indexOf(value);
  if (i >= 0) multi.value.splice(i, 1);
  else multi.value.push(value);
}

function onSlider(e: any) {
  slider.value = typeof e === "number" ? e : e?.value ?? slider.value;
}

function toggleSupp() {
  suppOpen.value = !suppOpen.value;
}

function onNext() {
  if (!answered.value) {
    uni.showToast({ title: "请先作答，或点跳过", icon: "none" });
    return;
  }
  doSubmit();
}
</script>

<template>
  <view class="qc">
    <!-- 题干 -->
    <view class="qc__head">
      <view class="qc__seal gf-seal gf-serif">{{ seal }}</view>
      <view class="qc__q gf-serif">{{ question.question }}</view>
      <gf-speaker class="qc__speak" :text="question.question" tone="paper" :size="34" />
    </view>

    <!-- 选项区 -->
    <scroll-view class="qc__body" scroll-y>
      <!-- single -->
      <view v-if="question.type === 'single'" class="qc__opts">
        <view
          v-for="opt in question.options"
          :key="opt.value"
          class="qc__opt"
          :class="{ active: single === opt.value }"
          hover-class="qc__opt--hover"
          :hover-stay-time="60"
          @tap="pickSingle(opt.value)"
        >
          <text class="qc__opt-text">{{ opt.label }}</text>
          <gf-icon v-if="single === opt.value" name="check" :size="34" color="#9A2D2D" />
        </view>
      </view>

      <!-- multi -->
      <view v-else-if="question.type === 'multi'" class="qc__opts">
        <view
          v-for="opt in question.options"
          :key="opt.value"
          class="qc__opt"
          :class="{ active: multi.includes(opt.value) }"
          hover-class="qc__opt--hover"
          :hover-stay-time="60"
          @tap="toggleMulti(opt.value)"
        >
          <text class="qc__opt-text">{{ opt.label }}</text>
          <gf-icon v-if="multi.includes(opt.value)" name="check" :size="34" color="#9A2D2D" />
        </view>
        <view class="qc__hint gf-ink-3">可多选</view>
      </view>

      <!-- slider -->
      <view v-else-if="question.type === 'slider'" class="qc__slider">
        <view class="qc__slider-val gf-tnum gf-serif">
          {{ slider }}<text class="qc__slider-unit">{{ question.unit }}</text>
        </view>
        <wd-slider
          :model-value="slider"
          :min="question.min"
          :max="question.max"
          @update:model-value="onSlider"
        />
        <view class="qc__slider-scale gf-ink-3">
          <text>{{ question.minLabel || question.min }}</text>
          <text>{{ question.maxLabel || question.max }}</text>
        </view>
      </view>

      <!-- text -->
      <view v-else class="qc__text">
        <gf-voice-field
          v-model="supp"
          :placeholder="isSupplement ? '想到什么补充，写在这里…' : '请输入…（可不填，直接跳过）'"
          :min-height="200"
        />
        <view v-if="isSupplement" class="qc__supp-hint gf-ink-3">
          没有想补充的，直接点下方按钮即可
        </view>
      </view>

      <!-- 补充（single/multi/slider） -->
      <view v-if="question.type !== 'text'" class="qc__supp">
        <view class="qc__supp-toggle" @tap="toggleSupp">
          <gf-icon :name="suppOpen ? 'close' : 'send'" :size="26" color="#8A7E6A" />
          <text>{{ suppOpen ? "收起补充" : "补充说明（选填）" }}</text>
        </view>
        <gf-voice-field
          v-if="suppOpen"
          v-model="supp"
          class="qc__voice--supp"
          placeholder="补充更多细节，辨证更准…"
          :min-height="140"
        />
      </view>
    </scroll-view>

    <!-- 底部操作 -->
    <view class="qc__actions">
      <view
        v-if="canPrev"
        class="qc__act qc__act--ghost"
        hover-class="qc__act--hover"
        @tap="emit('prev')"
      >
        <gf-icon name="back" :size="32" color="#9A2D2D" />
        <text>上一问</text>
      </view>
      <!-- 补充确认型：没填字一键「没有要补充的」，填了字变「提交补充」 -->
      <template v-if="isSupplement">
        <view
          v-if="!supp.trim()"
          class="qc__act qc__act--primary"
          :class="{ 'is-disabled': busy }"
          hover-class="qc__act--hover"
          @tap="onNoSupplement"
        >
          <gf-icon name="check" :size="32" color="#FBF7EE" />
          没有要补充的
        </view>
        <view
          v-else
          class="qc__act qc__act--primary"
          :class="{ 'is-disabled': busy }"
          hover-class="qc__act--hover"
          @tap="onNext"
        >
          提交补充
          <gf-icon name="arrow" :size="32" color="#FBF7EE" />
        </view>
      </template>
      <template v-else>
        <view class="qc__act qc__act--text" hover-class="qc__act--hover" @tap="emit('skip')">
          跳过
        </view>
        <view
          class="qc__act qc__act--primary"
          :class="{ 'is-disabled': !answered || busy }"
          hover-class="qc__act--hover"
          @tap="onNext"
        >
          下一问
          <gf-icon name="arrow" :size="32" color="#FBF7EE" />
        </view>
      </template>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.qc {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24rpx 32rpx;
  box-sizing: border-box;

  &__head {
    display: flex;
    align-items: flex-start;
    gap: 20rpx;
    margin-top: 12rpx;
  }
  &__seal {
    width: 64rpx;
    height: 64rpx;
    font-size: 34rpx;
    margin-top: 4rpx;
  }
  &__q {
    flex: 1;
    font-size: 42rpx;
    font-weight: 700;
    line-height: 1.4;
    color: $ink;
  }
  &__speak {
    flex-shrink: 0;
    margin-top: 4rpx;
  }
  &__body {
    flex: 1;
    min-height: 0;
    margin-top: 32rpx;
  }

  &__opts {
    display: flex;
    flex-direction: column;
    gap: 20rpx;
  }
  &__opt {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 96rpx;
    padding: 0 32rpx;
    background: $paper-card;
    border: 1px solid $border-paper;
    border-radius: $radius-sm;
    transition: border-color 0.15s ease, background 0.15s ease;
    &.active {
      border-color: $cinnabar;
      background: rgba(154, 45, 45, 0.06);
    }
    &--hover {
      background: $paper-sunken;
    }
  }
  &__opt-text {
    font-size: 34rpx;
    color: $ink;
  }
  &__hint {
    font-size: 24rpx;
    margin-top: 6rpx;
    padding-left: 8rpx;
  }

  &__slider {
    padding: 24rpx 12rpx;
  }
  &__slider-val {
    text-align: center;
    font-size: 80rpx;
    font-weight: 700;
    color: $cinnabar;
    margin-bottom: 24rpx;
  }
  &__slider-unit {
    font-size: 32rpx;
    margin-left: 6rpx;
    color: $ink-3;
  }
  &__slider-scale {
    display: flex;
    justify-content: space-between;
    font-size: 24rpx;
    margin-top: 12rpx;
  }

  &__text {
    padding-top: 8rpx;
  }
  &__supp-hint {
    font-size: 24rpx;
    margin-top: 14rpx;
    padding-left: 8rpx;
  }
  &__voice--supp {
    display: block;
    margin-top: 14rpx;
  }

  &__supp {
    margin-top: 28rpx;
  }
  &__supp-toggle {
    display: inline-flex;
    align-items: center;
    gap: 10rpx;
    font-size: 26rpx;
    color: $ink-3;
  }

  &__actions {
    display: flex;
    align-items: stretch;
    gap: 16rpx;
    padding: 16rpx 0 env(safe-area-inset-bottom);
  }
  &__act {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8rpx;
    min-height: 88rpx;
    border-radius: $radius-sm;
    font-size: 32rpx;
    &--hover {
      opacity: 0.85;
    }
    &--ghost {
      width: 168rpx;
      flex-shrink: 0;
      color: $cinnabar;
      border: 1px solid $cinnabar;
    }
    &--text {
      width: 130rpx;
      flex-shrink: 0;
      color: $ink-3;
    }
    &--primary {
      flex: 1;
      background: $cinnabar;
      color: $paper-card;
      font-weight: 600;
      &.is-disabled {
        opacity: 0.45;
      }
    }
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  /* 题干放大 */
  .qc__q { font-size: var(--gf-fs-title); line-height: var(--gf-lh); }
  /* 序号印章同比放大（覆盖局部 64rpx 定义）*/
  .qc__seal { width: 80rpx; height: 80rpx; font-size: var(--gf-fs-base); }

  /* 选项列表：纵向单列、加大间距 */
  .qc__opts { gap: 28rpx; }

  /* 单选/多选项 —— 可点重点，放大易点 */
  .qc__opt { min-height: 132rpx; padding: 28rpx 36rpx; }
  .qc__opt-text { font-size: var(--gf-fs-lg); line-height: var(--gf-lh); }
  .qc__hint { font-size: var(--gf-fs-sm); margin-top: 12rpx; padding-left: 12rpx; }

  /* 滑块 */
  .qc__slider-val { font-size: 108rpx; }
  .qc__slider-unit { font-size: var(--gf-fs-base); }
  .qc__slider-scale { font-size: var(--gf-fs-sm); margin-top: 20rpx; }

  /* 文本/补充提示 */
  .qc__supp-hint { font-size: var(--gf-fs-sm); margin-top: 20rpx; padding-left: 12rpx; }

  /* 补充展开开关 —— 可点元素，放大触区 */
  .qc__supp { margin-top: 36rpx; }
  .qc__supp-toggle { font-size: var(--gf-fs-base); gap: 16rpx; padding: 16rpx 0; }

  /* 底部按钮 —— 可点重点 */
  .qc__actions { gap: 24rpx; }
  .qc__act { min-height: 120rpx; font-size: var(--gf-fs-base); gap: 12rpx; }
  .qc__act--ghost { width: 220rpx; }
  .qc__act--text { width: 180rpx; }
}
</style>
