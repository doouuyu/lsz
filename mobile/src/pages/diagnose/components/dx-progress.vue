<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";

/**
 * 分阶段假进度 + loading 动画。
 * 用于「仿真辨证」决断阶段与「生成报告」阶段——这两处要把化验单原图喂多模态模型，
 * 等待偏长，需要一个一直在动、却永不卡死在 100% 的进度来安抚情绪。
 *
 * 进度采用「渐近曲线」：running 期间每 tick 朝 92% 逼近，既一直在动又不到顶；
 * done 置 true 时清掉渐近定时器，进度在约 0.4s 内缓动补到 100% 并定格（伴对勾微动效）。
 * 文案随阶段轮播，到末条后停在末条（不循环回第一条，避免显得卡）。
 *
 * 禁用 Date.now() / Math.random()——进度推进、文案切换均为确定性逻辑。
 */
const props = withDefaults(
  defineProps<{
    /** 为 true 时开始/继续推进进度与文案轮播；false 时停。 */
    running: boolean;
    /** 置 true：进度快速补到 100% 并定格，伴随完成微动效。 */
    done?: boolean;
    /** 文案数组，默认一组中医风辨证文案。 */
    stages?: string[];
    /** 配色：navy（藏青面，默认）/ paper（宣纸面）。 */
    tone?: "paper" | "navy";
  }>(),
  {
    done: false,
    stages: () => ["正在望闻问切…", "推演病位病性…", "检索经典印证…", "斟酌遣方用药…"],
    tone: "navy",
  }
);

// —— 进度（0~100，渐近停 92） ——
const TARGET = 92; // 渐近上限
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

/** 渐近推进：每 tick 朝 TARGET 逼近 6%（确定性，不依赖随机/时间戳）。 */
function startTick() {
  if (tickTimer) return;
  tickTimer = setInterval(() => {
    progress.value += (TARGET - progress.value) * 0.06;
    if (progress.value > TARGET) progress.value = TARGET;
  }, 80);
}

/** 文案轮播：约 1.6s 切下一条，到末条停住。 */
function startStageRotate() {
  if (stageTimer) return;
  stageTimer = setInterval(() => {
    if (stageIndex.value < props.stages.length - 1) {
      stageIndex.value += 1;
    } else {
      clearStage(); // 停在末条
    }
  }, 1600);
}

/** done：清渐近，约 0.4s 缓动补到 100%。 */
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
  // 完成时跳到末条文案，给个收束感
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

// —— 视图派生 ——
const pct = computed(() => Math.round(progress.value));
const label = computed(() => props.stages[stageIndex.value] ?? "");
const fillStyle = computed(() => ({ width: `${progress.value}%` }));
const fillColor = computed(() => (props.tone === "paper" ? "#9A2D2D" : "#5FB3A1"));
</script>

<template>
  <view class="dp" :class="[`dp--${tone}`, { 'dp--done': done }]">
    <!-- 印章感 loading 环 / 完成对勾 -->
    <view class="dp__seal">
      <view v-if="!done" class="dp__ring" aria-hidden="true">
        <view class="dp__ring-arc" />
      </view>
      <view v-else class="dp__check">
        <gf-icon name="check" :size="40" :color="fillColor" />
      </view>
    </view>

    <!-- 文案 -->
    <view class="dp__label gf-serif">{{ label }}</view>

    <!-- 进度轨 -->
    <view class="dp__track">
      <view class="dp__fill" :style="fillStyle">
        <view class="dp__shimmer" />
      </view>
    </view>

    <!-- 进度数字 -->
    <view class="dp__pct gf-tnum">{{ pct }}<text class="dp__pct-sign">%</text></view>
  </view>
</template>

<style lang="scss" scoped>
.dp {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  padding: 8rpx 0;
}

/* —— 印章感 loading 环 —— */
.dp__seal {
  width: 72rpx;
  height: 72rpx;
  margin-bottom: 28rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dp__ring {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 3rpx solid rgba(159, 178, 200, 0.22);
}
.dp__ring-arc {
  position: absolute;
  inset: -3rpx;
  border-radius: 50%;
  border: 3rpx solid transparent;
  border-top-color: $jade;
  border-right-color: $jade;
  animation: dpSpin 0.9s linear infinite;
}

/* 完成对勾微动效 */
.dp__check {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 3rpx solid rgba(95, 179, 161, 0.4);
  animation: dpPop 0.42s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* —— 文案 —— */
.dp__label {
  font-size: 32rpx;
  letter-spacing: 4rpx;
  color: $on-navy;
  margin-bottom: 28rpx;
  min-height: 44rpx;
  transition: opacity 0.3s ease;
}

/* —— 进度轨 —— */
.dp__track {
  position: relative;
  width: 100%;
  max-width: 420rpx;
  height: 12rpx;
  border-radius: 999rpx;
  background: rgba(234, 240, 246, 0.16);
  overflow: hidden;
}
.dp__fill {
  position: relative;
  height: 100%;
  border-radius: 999rpx;
  background: linear-gradient(90deg, $jade, $gold);
  transition: width 0.18s linear;
  overflow: hidden;
}
.dp__shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(251, 247, 238, 0.45),
    transparent
  );
  transform: translateX(-100%);
  animation: dpShimmer 1.4s ease-in-out infinite;
}

/* —— 进度数字 —— */
.dp__pct {
  margin-top: 22rpx;
  font-family: $font-serif;
  font-size: 40rpx;
  font-weight: 700;
  letter-spacing: 2rpx;
  color: $on-navy;
}
.dp__pct-sign {
  font-size: 26rpx;
  margin-left: 4rpx;
  color: $on-navy-2;
}

/* —— 宣纸面配色覆盖 —— */
.dp--paper {
  .dp__ring {
    border-color: rgba(31, 27, 22, 0.12);
  }
  .dp__ring-arc {
    border-top-color: $cinnabar;
    border-right-color: $cinnabar;
  }
  .dp__check {
    border-color: rgba(154, 45, 45, 0.32);
  }
  .dp__label {
    color: $ink;
  }
  .dp__track {
    background: rgba(31, 27, 22, 0.1);
  }
  .dp__fill {
    background: linear-gradient(90deg, $cinnabar, $gold);
  }
  .dp__pct {
    color: $cinnabar;
  }
  .dp__pct-sign {
    color: $ink-2;
  }
}

@keyframes dpSpin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes dpShimmer {
  to {
    transform: translateX(100%);
  }
}
@keyframes dpPop {
  0% {
    transform: scale(0.6);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

/* —— 尊重 prefers-reduced-motion：无 shimmer、无旋转、进度直接到位 —— */
@media (prefers-reduced-motion: reduce) {
  .dp__ring-arc {
    animation: none;
    border-top-color: $jade;
    border-right-color: $jade;
    border-bottom-color: $jade;
    border-left-color: rgba(95, 179, 161, 0.3);
  }
  .dp--paper .dp__ring-arc {
    border-top-color: $cinnabar;
    border-right-color: $cinnabar;
    border-bottom-color: $cinnabar;
    border-left-color: rgba(154, 45, 45, 0.3);
  }
  .dp__shimmer {
    display: none;
  }
  .dp__check {
    animation: none;
  }
  .dp__fill {
    transition: none;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .dp { padding: 14rpx 0; }
  .dp__seal { width: 104rpx; height: 104rpx; margin-bottom: 36rpx; }
  .dp__label { font-size: var(--gf-fs-base); letter-spacing: 5rpx; margin-bottom: 36rpx; min-height: 60rpx; }
  .dp__track { max-width: 560rpx; height: 18rpx; }
  .dp__pct { font-size: 52rpx; margin-top: 30rpx; letter-spacing: 3rpx; }
  .dp__pct-sign { font-size: 34rpx; }
}
</style>
