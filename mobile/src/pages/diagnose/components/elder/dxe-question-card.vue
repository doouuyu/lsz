<script setup lang="ts">
import { ref, computed, watch } from "vue";
import type { AnswerSnapshot, InquiryQuestion } from "../../types";
import { emptySnapshot } from "../../types";

/**
 * 老年版 · 问诊步进卡（dxe-question-card）。
 * 契约同 dx-question-card（props question/modelValue/reviewing/canPrev/seal/busy；
 * emit submit/prev/skip），仅替换视图，业务全在 useDiagnose。
 *
 * 重排（相对 dx-question-card 非放大，非缩放）：
 *  - 题干区改大字 title + 显著「朗读题干」按钮（带文字标签，gf-speaker 主控件化）。
 *  - single/multi：单列超大整行、勾选整行高亮 + 大对勾。
 *  - slider 题型彻底替换（核心，CSS 改不动）：wd-slider → 大号「− 值 +」加减步进器，
 *    数值超大字居中，min/max 标注大字；老人单击加减即可，免精细拖拽。
 *  - 补充说明：取消折叠小开关，改为「直接可见」的大输入区（gf-voice-field）。
 *  - 底部重排：主操作「下一问 / 提交补充 / 没有要补充的」独占整行大 CTA（每屏一个主 CTA）；
 *    「上一问 / 跳过」降为次级文字/描边按钮，单独一行、不与主 CTA 等权挤一行。
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
const locked = ref(false);

watch(
  () => props.question.key + "@" + props.seal,
  () => {
    const s = props.modelValue || emptySnapshot(props.question.min ?? 0);
    single.value = s.single;
    multi.value = [...s.multi];
    slider.value = typeof s.slider === "number" ? s.slider : props.question.min ?? 0;
    supp.value = s.supp;
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

/* —— slider 替换：大号加减步进器 —— */
const stepMin = computed(() => props.question.min ?? 0);
const stepMax = computed(() => props.question.max ?? 10);
const canDec = computed(() => slider.value > stepMin.value);
const canInc = computed(() => slider.value < stepMax.value);
function decStep() {
  if (!canDec.value) return;
  slider.value = Math.max(stepMin.value, slider.value - 1);
  uni.vibrateShort?.({ type: "light" } as any);
}
function incStep() {
  if (!canInc.value) return;
  slider.value = Math.min(stepMax.value, slider.value + 1);
  uni.vibrateShort?.({ type: "light" } as any);
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
  <view class="dxe dxe-qc">
    <!-- 题干 + 显著朗读 -->
    <view class="dxe-qc__head">
      <view class="dxe-qc__seal gf-seal gf-serif">{{ seal }}</view>
      <view class="dxe-qc__q gf-serif">{{ question.question }}</view>
    </view>
    <view class="dxe-qc__speak-row">
      <gf-speaker
        class="dxe-qc__speak"
        :text="question.question"
        tone="paper"
        :size="44"
        label="朗读题干"
      />
    </view>

    <!-- 选项区 -->
    <scroll-view class="dxe-qc__body" scroll-y>
      <!-- single -->
      <view v-if="question.type === 'single'" class="dxe-qc__opts">
        <view
          v-for="opt in question.options"
          :key="opt.value"
          class="dxe-qc__opt"
          :class="{ active: single === opt.value }"
          hover-class="dxe-qc__opt--hover"
          :hover-stay-time="60"
          @tap="pickSingle(opt.value)"
        >
          <text class="dxe-qc__opt-text">{{ opt.label }}</text>
          <gf-icon v-if="single === opt.value" name="check" :size="48" color="#9A2D2D" />
        </view>
      </view>

      <!-- multi -->
      <view v-else-if="question.type === 'multi'" class="dxe-qc__opts">
        <view
          v-for="opt in question.options"
          :key="opt.value"
          class="dxe-qc__opt"
          :class="{ active: multi.includes(opt.value) }"
          hover-class="dxe-qc__opt--hover"
          :hover-stay-time="60"
          @tap="toggleMulti(opt.value)"
        >
          <text class="dxe-qc__opt-text">{{ opt.label }}</text>
          <gf-icon v-if="multi.includes(opt.value)" name="check" :size="48" color="#9A2D2D" />
        </view>
        <view class="dxe-qc__hint gf-ink-3">可多选</view>
      </view>

      <!-- slider 替换为大号加减步进器 -->
      <view v-else-if="question.type === 'slider'" class="dxe-qc__step">
        <view class="dxe-qc__step-val gf-tnum gf-serif">
          {{ slider }}<text class="dxe-qc__step-unit">{{ question.unit }}</text>
        </view>
        <view class="dxe-qc__step-ctrl">
          <view
            class="dxe-qc__step-btn"
            :class="{ 'is-off': !canDec }"
            hover-class="dxe-qc__step-btn--hover"
            @tap="decStep"
          >
            <text class="dxe-qc__step-sign">−</text>
          </view>
          <view class="dxe-qc__step-scale gf-ink-3">
            <text>{{ question.minLabel || stepMin }}</text>
            <text>{{ question.maxLabel || stepMax }}</text>
          </view>
          <view
            class="dxe-qc__step-btn"
            :class="{ 'is-off': !canInc }"
            hover-class="dxe-qc__step-btn--hover"
            @tap="incStep"
          >
            <text class="dxe-qc__step-sign">＋</text>
          </view>
        </view>
        <view class="dxe-qc__step-tip gf-ink-3">点「＋」「−」调整，无需拖动</view>
      </view>

      <!-- text -->
      <view v-else class="dxe-qc__text">
        <gf-voice-field
          v-model="supp"
          :placeholder="isSupplement ? '想到什么补充，写在这里…' : '请输入…（可不填，直接跳过）'"
          :min-height="260"
        />
        <view v-if="isSupplement" class="dxe-qc__supp-hint gf-ink-3">
          没有想补充的，直接点下方按钮即可
        </view>
      </view>

      <!-- 补充说明（single/multi/slider）：直接可见的大输入区，不再折叠 -->
      <view v-if="question.type !== 'text'" class="dxe-qc__supp">
        <view class="dxe-qc__supp-label gf-ink-3">补充说明（选填）</view>
        <gf-voice-field
          v-model="supp"
          placeholder="补充更多细节，辨证更准…"
          :min-height="200"
        />
      </view>
    </scroll-view>

    <!-- 底部操作：主 CTA 独占整行；次级单独一行 -->
    <view class="dxe-qc__actions">
      <!-- 主 CTA -->
      <template v-if="isSupplement">
        <view
          v-if="!supp.trim()"
          class="dxe-qc__cta"
          :class="{ 'is-disabled': busy }"
          hover-class="dxe-qc__cta--hover"
          @tap="onNoSupplement"
        >
          <gf-icon name="check" :size="40" color="#FBF7EE" />
          <text>没有要补充的</text>
        </view>
        <view
          v-else
          class="dxe-qc__cta"
          :class="{ 'is-disabled': busy }"
          hover-class="dxe-qc__cta--hover"
          @tap="onNext"
        >
          <text>提交补充</text>
          <gf-icon name="arrow" :size="40" color="#FBF7EE" />
        </view>
      </template>
      <view
        v-else
        class="dxe-qc__cta"
        :class="{ 'is-disabled': !answered || busy }"
        hover-class="dxe-qc__cta--hover"
        @tap="onNext"
      >
        <text>下一问</text>
        <gf-icon name="arrow" :size="40" color="#FBF7EE" />
      </view>

      <!-- 次级：上一问 / 跳过，单独一行、不与主 CTA 等权 -->
      <view v-if="canPrev || !isSupplement" class="dxe-qc__sub">
        <view
          v-if="canPrev"
          class="dxe-qc__sub-btn dxe-qc__sub-btn--ghost"
          hover-class="dxe-qc__sub-btn--hover"
          @tap="emit('prev')"
        >
          <gf-icon name="back" :size="34" color="#9A2D2D" />
          <text>上一问</text>
        </view>
        <view
          v-if="!isSupplement"
          class="dxe-qc__sub-btn dxe-qc__sub-btn--text"
          hover-class="dxe-qc__sub-btn--hover"
          @tap="emit('skip')"
        >
          跳过这一问
        </view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.dxe-qc {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24rpx var(--dxe-pad);
  box-sizing: border-box;

  &__head {
    display: flex;
    align-items: flex-start;
    gap: 20rpx;
    margin-top: 12rpx;
  }
  &__seal {
    width: 88rpx;
    height: 88rpx;
    font-size: var(--gf-fs-base);
    margin-top: 4rpx;
  }
  &__q {
    flex: 1;
    font-size: var(--gf-fs-title);
    font-weight: 700;
    line-height: var(--gf-lh);
    color: $ink;
  }
  &__speak-row {
    display: flex;
    margin-top: 16rpx;
  }

  &__body {
    flex: 1;
    min-height: 0;
    margin-top: 28rpx;
  }

  /* 单选 / 多选：单列超大整行 */
  &__opts {
    display: flex;
    flex-direction: column;
    gap: var(--dxe-gap);
  }
  &__opt {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 132rpx;
    padding: 28rpx 36rpx;
    background: $paper-card;
    border: 2rpx solid $border-paper;
    border-radius: var(--dxe-radius-sm);
    transition: border-color 0.15s ease, background 0.15s ease;
    &.active {
      border-color: $cinnabar;
      background: rgba(154, 45, 45, 0.08);
    }
    &--hover {
      background: $paper-sunken;
    }
  }
  &__opt-text {
    flex: 1;
    font-size: var(--gf-fs-lg);
    line-height: var(--gf-lh);
    color: $ink;
  }
  &__hint {
    font-size: var(--gf-fs-sm);
    margin-top: 12rpx;
    padding-left: 12rpx;
  }

  /* slider 替换：加减步进器 */
  &__step {
    padding: 24rpx 12rpx;
  }
  &__step-val {
    text-align: center;
    font-size: 132rpx;
    font-weight: 700;
    color: $cinnabar;
    margin-bottom: 28rpx;
  }
  &__step-unit {
    font-size: var(--gf-fs-base);
    margin-left: 8rpx;
    color: $ink-3;
  }
  &__step-ctrl {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24rpx;
  }
  &__step-btn {
    width: 140rpx;
    height: 140rpx;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--dxe-radius);
    background: $paper-card;
    border: 2rpx solid $cinnabar;
    &.is-off {
      opacity: 0.35;
      border-color: $border-paper;
    }
    &--hover {
      background: $paper-sunken;
    }
  }
  &__step-sign {
    font-size: 88rpx;
    line-height: 1;
    color: $cinnabar;
    font-weight: 700;
  }
  &__step-scale {
    flex: 1;
    display: flex;
    justify-content: space-between;
    font-size: var(--gf-fs-sm);
    padding: 0 8rpx;
  }
  &__step-tip {
    text-align: center;
    font-size: var(--gf-fs-sm);
    margin-top: 24rpx;
  }

  &__text {
    padding-top: 8rpx;
  }
  &__supp-hint {
    font-size: var(--gf-fs-sm);
    margin-top: 20rpx;
    padding-left: 12rpx;
  }

  /* 补充说明：直接可见大输入区 */
  &__supp {
    margin-top: 36rpx;
  }
  &__supp-label {
    font-size: var(--gf-fs-sm);
    margin-bottom: 16rpx;
    padding-left: 4rpx;
  }

  /* 底部操作 */
  &__actions {
    display: flex;
    flex-direction: column;
    gap: 20rpx;
    padding: 20rpx 0 env(safe-area-inset-bottom);
  }
  &__cta {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14rpx;
    width: 100%;
    min-height: var(--dxe-cta-h);
    border-radius: var(--dxe-radius);
    background: $cinnabar;
    color: $paper-card;
    font-size: var(--gf-fs-lg);
    font-weight: 600;
    box-sizing: border-box;
    &.is-disabled {
      opacity: 0.45;
    }
    &--hover {
      background: $cinnabar-soft;
    }
  }
  &__sub {
    display: flex;
    gap: var(--dxe-gap);
  }
  &__sub-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10rpx;
    min-height: var(--dxe-tap-h);
    border-radius: var(--dxe-radius-sm);
    font-size: var(--gf-fs-base);
    &--ghost {
      flex: 1;
      color: $cinnabar;
      border: 2rpx solid $cinnabar;
    }
    &--text {
      flex: 1;
      color: $ink-3;
      border: 2rpx solid $border-paper;
    }
    &--hover {
      opacity: 0.85;
    }
  }
}
</style>
