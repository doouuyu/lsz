<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

/**
 * 老年版 · 分阶段假进度（dxe-progress）。
 * 契约与正常版 dx-progress 完全一致（running / done / stages / tone），供
 * dxe-decision 决断过场与 index.vue 报告导出覆盖层共用。
 *
 * 重排（相对 dx-progress 非放大）：进度条独占整行、超粗轨（28rpx），百分比与
 * 阶段文案均为老年大字；loading 环放大并与文案纵向居中堆叠、留白加大。
 * 进度推进算法（渐近停 92、done 缓动补满、文案轮播停末条）与正常版一致。
 */
const props = withDefaults(
  defineProps<{
    running: boolean;
    done?: boolean;
    stages?: string[];
    tone?: "paper" | "navy";
  }>(),
  {
    done: false,
    stages: () => ["正在望闻问切…", "推演病位病性…", "检索经典印证…", "斟酌遣方用药…"],
    tone: "navy",
  }
);

const TARGET = 92;
const progress = ref(0);
const stageIndex = ref(0);

let tickTimer: ReturnType<typeof setInterval> | null = null;
let stageTimer: ReturnType<typeof setInterval> | null = null;
let finishTimer: ReturnType<typeof setInterval> | null = null;

function clearTick() {
  if (tickTimer) {
    clearInterval(tickTimer);
    tickTimer = null;
  }
}
function clearStage() {
  if (stageTimer) {
    clearInterval(stageTimer);
    stageTimer = null;
  }
}
function clearFinish() {
  if (finishTimer) {
    clearInterval(finishTimer);
    finishTimer = null;
  }
}
function clearAll() {
  clearTick();
  clearStage();
  clearFinish();
}

function startTick() {
  if (tickTimer) return;
  tickTimer = setInterval(() => {
    progress.value += (TARGET - progress.value) * 0.06;
    if (progress.value > TARGET) progress.value = TARGET;
  }, 80);
}

function startStageRotate() {
  if (stageTimer) return;
  stageTimer = setInterval(() => {
    if (stageIndex.value < props.stages.length - 1) {
      stageIndex.value += 1;
    } else {
      clearStage();
    }
  }, 1600);
}

function startFinish() {
  clearTick();
  clearFinish();
  finishTimer = setInterval(() => {
    progress.value += (100 - progress.value) * 0.25;
    if (progress.value >= 99.6) {
      progress.value = 100;
      clearFinish();
    }
  }, 24);
  clearStage();
  stageIndex.value = props.stages.length - 1;
}

watch(
  () => props.running,
  (run) => {
    if (props.done) return;
    if (run) {
      startTick();
      startStageRotate();
    } else {
      clearTick();
      clearStage();
    }
  },
  { immediate: true }
);

watch(
  () => props.done,
  (d) => {
    if (d) startFinish();
  },
  { immediate: true }
);

onUnmounted(clearAll);

const pct = computed(() => Math.round(progress.value));
const label = computed(() => props.stages[stageIndex.value] ?? "");
const fillStyle = computed(() => ({ width: `${progress.value}%` }));
const fillColor = computed(() => (props.tone === "paper" ? "#9A2D2D" : "#5FB3A1"));
</script>

<template>
  <view class="dxe dxe-dp" :class="[`dxe-dp--${tone}`, { 'dxe-dp--done': done }]">
    <view class="dxe-dp__seal">
      <view v-if="!done" class="dxe-dp__ring" aria-hidden="true">
        <view class="dxe-dp__ring-arc" />
      </view>
      <view v-else class="dxe-dp__check">
        <gf-icon name="check" :size="56" :color="fillColor" />
      </view>
    </view>

    <view class="dxe-dp__label gf-serif">{{ label }}</view>

    <view class="dxe-dp__track">
      <view class="dxe-dp__fill" :style="fillStyle">
        <view class="dxe-dp__shimmer" />
      </view>
    </view>

    <view class="dxe-dp__pct gf-tnum">{{ pct }}<text class="dxe-dp__pct-sign">%</text></view>
  </view>
</template>

<style lang="scss" scoped>
.dxe-dp {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding: 16rpx 0;

  &__seal {
    width: 104rpx;
    height: 104rpx;
    margin-bottom: 40rpx;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  &__ring {
    position: relative;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    border: 4rpx solid rgba(159, 178, 200, 0.22);
  }
  &__ring-arc {
    position: absolute;
    inset: -4rpx;
    border-radius: 50%;
    border: 4rpx solid transparent;
    border-top-color: $jade;
    border-right-color: $jade;
    animation: dxeDpSpin 0.9s linear infinite;
  }
  &__check {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    border: 4rpx solid rgba(95, 179, 161, 0.4);
    animation: dxeDpPop 0.42s cubic-bezier(0.34, 1.56, 0.64, 1);
  }

  &__label {
    font-size: var(--gf-fs-base);
    letter-spacing: 5rpx;
    color: $on-navy;
    margin-bottom: 40rpx;
    min-height: 64rpx;
    transition: opacity 0.3s ease;
  }

  &__track {
    position: relative;
    width: 100%;
    max-width: 560rpx;
    height: 28rpx;
    border-radius: 999rpx;
    background: rgba(234, 240, 246, 0.16);
    overflow: hidden;
  }
  &__fill {
    position: relative;
    height: 100%;
    border-radius: 999rpx;
    background: linear-gradient(90deg, $jade, $gold);
    transition: width 0.18s linear;
    overflow: hidden;
  }
  &__shimmer {
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(251, 247, 238, 0.45), transparent);
    transform: translateX(-100%);
    animation: dxeDpShimmer 1.4s ease-in-out infinite;
  }

  &__pct {
    margin-top: 32rpx;
    font-family: $font-serif;
    font-size: 64rpx;
    font-weight: 700;
    letter-spacing: 3rpx;
    color: $on-navy;
  }
  &__pct-sign {
    font-size: var(--gf-fs-sm);
    margin-left: 6rpx;
    color: $on-navy-2;
  }

  /* 宣纸面配色覆盖 */
  &--paper {
    .dxe-dp__ring {
      border-color: rgba(31, 27, 22, 0.12);
    }
    .dxe-dp__ring-arc {
      border-top-color: $cinnabar;
      border-right-color: $cinnabar;
    }
    .dxe-dp__check {
      border-color: rgba(154, 45, 45, 0.32);
    }
    .dxe-dp__label {
      color: $ink;
    }
    .dxe-dp__track {
      background: rgba(31, 27, 22, 0.1);
    }
    .dxe-dp__fill {
      background: linear-gradient(90deg, $cinnabar, $gold);
    }
    .dxe-dp__pct {
      color: $cinnabar;
    }
    .dxe-dp__pct-sign {
      color: $ink-2;
    }
  }
}

@keyframes dxeDpSpin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes dxeDpShimmer {
  to {
    transform: translateX(100%);
  }
}
@keyframes dxeDpPop {
  0% {
    transform: scale(0.6);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dxe-dp__ring-arc {
    animation: none;
    border-top-color: $jade;
    border-right-color: $jade;
    border-bottom-color: $jade;
    border-left-color: rgba(95, 179, 161, 0.3);
  }
  .dxe-dp--paper .dxe-dp__ring-arc {
    border-top-color: $cinnabar;
    border-right-color: $cinnabar;
    border-bottom-color: $cinnabar;
    border-left-color: rgba(154, 45, 45, 0.3);
  }
  .dxe-dp__shimmer {
    display: none;
  }
  .dxe-dp__check {
    animation: none;
  }
  .dxe-dp__fill {
    transition: none;
  }
}
</style>
