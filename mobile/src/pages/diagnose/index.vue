<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useElder } from "@/composables/useElder";
import { useDiagnose } from "./useDiagnose";
import { generateReport } from "@/api";
import { API_ORIGIN } from "@/api/request";
import dxIntake from "./components/dx-intake.vue";
import dxQuestionCard from "./components/dx-question-card.vue";
import dxFootprints from "./components/dx-footprints.vue";
import dxThinking from "./components/dx-thinking.vue";
import dxCaseSheet from "./components/dx-case-sheet.vue";
import dxDecision from "./components/dx-decision.vue";
import dxResult from "./components/dx-result.vue";
import dxProgress from "./components/dx-progress.vue";
// 老年版组件树（dxe-*）：独立 template + 独立 scoped 样式，与正常版 dx-* 一一对应、契约一致。
// index.vue 按 elderMode 切换渲染两套组件树，共用同一个 useDiagnose() 实例与 props/emit。
import dxeIntake from "./components/elder/dxe-intake.vue";
import dxeQuestionCard from "./components/elder/dxe-question-card.vue";
import dxeFootprints from "./components/elder/dxe-footprints.vue";
import dxeThinking from "./components/elder/dxe-thinking.vue";
import dxeCaseSheet from "./components/elder/dxe-case-sheet.vue";
import dxeDecision from "./components/elder/dxe-decision.vue";
import dxeResult from "./components/elder/dxe-result.vue";
import dxeProgress from "./components/elder/dxe-progress.vue";

/**
 * 仿真辨证 · 编排（接入后端 inquiry/diagnose，详见 useDiagnose.ts）。
 * stage：intake → inquiry（步进卡，卡间用 dx-thinking 斟酌过场）→ diagnosing（决断）→ result。
 */
const { rootClass, elderMode } = useElder();
const dx = useDiagnose();
const {
  stage,
  thinking,
  chief,
  questions,
  qIndex,
  slideDir,
  vm,
  sources,
  sessionId,
  usedLab,
  labFindings,
  labUnreadable,
  roleSwitching,
  currentQuestion,
  currentAnswer,
  reviewing,
  footprintCount,
  caseEntries,
  tongueStatus,
  tongueImg,
  tongueResult,
  tongueHint,
  labFiles,
} = dx;

const caseSheet = ref(false);

// 问诊阶段的舌象后台状态丸：识别中常驻，刚识别完轻提示 ~2.2s 后隐去（不打断作答）。
const tonguePill = ref<"" | "analyzing" | "done">("");
let pillTimer: ReturnType<typeof setTimeout> | null = null;
watch(tongueStatus, (s, prev) => {
  if (pillTimer) {
    clearTimeout(pillTimer);
    pillTimer = null;
  }
  if (s === "analyzing") {
    tonguePill.value = "analyzing";
  } else if (s === "done" && prev === "analyzing") {
    tonguePill.value = "done";
    pillTimer = setTimeout(() => {
      if (tonguePill.value === "done") tonguePill.value = "";
    }, 2200);
  } else {
    // degraded / retake / idle：丸隐去（retake 交给软提示条）
    tonguePill.value = "";
  }
});

const showCard = computed(
  () => stage.value === "inquiry" && !thinking.value && !!currentQuestion.value
);
const cardTransition = computed(() => (slideDir.value === "back" ? "slide-back" : "slide-fwd"));
const navTitle = computed(() => (stage.value === "result" ? "辨证结果" : "仿真辨证"));
const navSurface = computed<"paper" | "navy">(() => (stage.value === "result" ? "navy" : "paper"));

function onRestart() {
  uni.showModal({
    title: "重新辨证",
    content: "将清空当前脉案，重新开始？",
    confirmColor: "#9A2D2D",
    success: ({ confirm }) => confirm && dx.restart(),
  });
}

// 报告导出等待体验：全屏宣纸覆盖层 + dx-progress（渐近假进度，永不卡死在 100%）。
// exporting 控制覆盖层显隐；exportDone 触发进度补满到 100% 的收束动效；done 后稍候收掉覆盖层。
const exporting = ref(false);
const exportDone = ref(false);
let exportHideTimer: ReturnType<typeof setTimeout> | null = null;

function finishExport(done: boolean) {
  if (exportHideTimer) clearTimeout(exportHideTimer);
  if (done) {
    // 成功：进度补满 → 略停后收覆盖层，让用户看到「生成报告」完成的收束
    exportDone.value = true;
    exportHideTimer = setTimeout(() => {
      exporting.value = false;
      exportDone.value = false;
    }, 700);
  } else {
    // 失败：立即收掉覆盖层（toast 另行提示）
    exporting.value = false;
    exportDone.value = false;
  }
}

async function onExport() {
  if (!sessionId.value) {
    uni.showToast({ title: "请先完成一次辨证，再导出报告", icon: "none" });
    return;
  }
  exporting.value = true;
  exportDone.value = false;
  try {
    const data = await generateReport(sessionId.value);
    const url = data.download_url || "";
    const full = url.startsWith("http") ? url : API_ORIGIN + url;
    uni.downloadFile({
      url: full,
      success: (res) => {
        if (res.statusCode === 200) {
          finishExport(true);
          uni.openDocument({
            filePath: res.tempFilePath,
            showMenu: true,
            fail: () => uni.showToast({ title: "报告已生成，但手机上暂不能直接打开", icon: "none" }),
          });
        } else {
          finishExport(false);
          uni.showToast({ title: "报告生成失败", icon: "none" });
        }
      },
      fail: () => {
        finishExport(false);
        uni.showToast({ title: "下载失败，请检查网络后重试", icon: "none" });
      },
    });
  } catch {
    finishExport(false);
    uni.showToast({ title: "报告生成失败", icon: "none" });
  }
}

function handleBack() {
  if (stage.value === "intake" || stage.value === "result") {
    uni.navigateBack({ fail: () => uni.reLaunch({ url: "/pages/index/index" }) });
    return;
  }
  uni.showModal({
    title: "退出辨证",
    content: "当前脉案尚未完成，确定退出？",
    confirmColor: "#9A2D2D",
    success: ({ confirm }) => {
      if (confirm) uni.navigateBack({ fail: () => uni.reLaunch({ url: "/pages/index/index" }) });
    },
  });
}
</script>

<template>
  <view class="dx" :class="rootClass">
    <gf-navbar
      :title="navTitle"
      :show-back="true"
      :surface="navSurface"
      custom-back
      @back="handleBack"
    />

    <!-- 进度带：足迹点（可滚动）+ 脉案入口钉在行尾（同为「回看」族功能） -->
    <view v-if="stage === 'inquiry' && footprintCount > 0" class="dx__progress">
      <dx-footprints
        v-if="!elderMode"
        class="dx__fp"
        :count="footprintCount"
        :current="qIndex"
        @jump="dx.goto"
      />
      <dxe-footprints
        v-else
        class="dx__fp"
        :count="footprintCount"
        :current="qIndex"
        @jump="dx.goto"
      />
      <view
        class="dx__case-btn"
        hover-class="dx__case-btn--hover"
        :hover-stay-time="60"
        @tap="caseSheet = true"
      >
        <gf-icon name="book" :size="26" color="#9A2D2D" />
        <text>脉案</text>
      </view>
    </view>

    <!-- 舌象后台识别状态丸：识别中 / 刚识别完（轻提示，不打断作答） -->
    <view
      v-if="stage === 'inquiry' && tonguePill"
      class="dx__tongue-pill"
      :class="`is-${tonguePill}`"
    >
      <template v-if="tonguePill === 'analyzing'">
        <view class="dx__tongue-dots">
          <view
            v-for="i in 3"
            :key="i"
            class="dx__tongue-dot"
            :style="{ animationDelay: i * 0.16 + 's' }"
          />
        </view>
        <text>舌象识别中</text>
      </template>
      <template v-else>
        <gf-icon name="check" :size="24" color="#5FB3A1" />
        <text>舌象已识别</text>
      </template>
    </view>

    <!-- 需重拍软提示：不打断作答，可重拍或忽略 -->
    <view v-if="stage === 'inquiry' && tongueStatus === 'retake'" class="dx__tongue-banner">
      <text class="dx__tongue-banner-txt">舌象建议重拍 · {{ tongueHint }}</text>
      <view class="dx__tongue-banner-ops">
        <text class="dx__tongue-banner-op" @tap="dx.recaptureTongue">重拍</text>
        <text
          class="dx__tongue-banner-op dx__tongue-banner-op--ghost"
          @tap="dx.keepTongueAnyway"
        >忽略</text>
      </view>
    </view>

    <!-- 主舞台 -->
    <view class="dx__stage">
      <transition :name="cardTransition">
        <!-- 正常版录入 / 问诊卡 -->
        <dx-intake
          v-if="!elderMode && stage === 'intake'"
          key="intake"
          class="dx__pane"
          :tongue-status="tongueStatus"
          :tongue-img="tongueImg"
          :tongue-desc="tongueResult?.tcm_text || ''"
          :tongue-hint="tongueHint"
          :lab-files="labFiles"
          @submit="dx.start"
          @tongue-confirm="dx.analyzeTongueBg"
          @tongue-remove="dx.clearTongue"
          @lab-add="dx.addLabFiles"
          @lab-remove="dx.removeLab"
          @lab-retry="dx.retryLab"
        />
        <dx-question-card
          v-else-if="!elderMode && showCard"
          :key="'q-' + qIndex"
          class="dx__pane"
          :question="currentQuestion!"
          :model-value="currentAnswer"
          :reviewing="reviewing"
          :can-prev="qIndex > 0"
          :seal="qIndex + 1"
          :busy="thinking"
          @submit="dx.submit"
          @prev="dx.prev"
          @skip="dx.skip"
        />
        <!-- 老年版录入 / 问诊卡（dxe-*，独立 template + scoped 样式） -->
        <dxe-intake
          v-else-if="elderMode && stage === 'intake'"
          key="dxe-intake"
          class="dx__pane"
          :tongue-status="tongueStatus"
          :tongue-img="tongueImg"
          :tongue-desc="tongueResult?.tcm_text || ''"
          :tongue-hint="tongueHint"
          :lab-files="labFiles"
          @submit="dx.start"
          @tongue-confirm="dx.analyzeTongueBg"
          @tongue-remove="dx.clearTongue"
          @lab-add="dx.addLabFiles"
          @lab-remove="dx.removeLab"
          @lab-retry="dx.retryLab"
        />
        <dxe-question-card
          v-else-if="elderMode && showCard"
          :key="'dxe-q-' + qIndex"
          class="dx__pane"
          :question="currentQuestion!"
          :model-value="currentAnswer"
          :reviewing="reviewing"
          :can-prev="qIndex > 0"
          :seal="qIndex + 1"
          :busy="thinking"
          @submit="dx.submit"
          @prev="dx.prev"
          @skip="dx.skip"
        />
      </transition>

      <!-- 斟酌过场（卡间） -->
      <transition name="fade">
        <dx-thinking v-if="!elderMode && stage === 'inquiry' && thinking" class="dx__pane" />
        <dxe-thinking v-else-if="elderMode && stage === 'inquiry' && thinking" class="dx__pane" />
      </transition>

      <!-- 结果长卷 -->
      <dx-result
        v-if="!elderMode && stage === 'result' && vm"
        class="dx__pane"
        :vm="vm"
        :chief="chief"
        :sources="sources"
        :has-lab="usedLab"
        :lab-findings="labFindings"
        :lab-unreadable="labUnreadable"
        :role-switching="roleSwitching"
        @restart="onRestart"
        @export="onExport"
        @role-change="dx.switchRole"
      />
      <dxe-result
        v-else-if="elderMode && stage === 'result' && vm"
        class="dx__pane"
        :vm="vm"
        :chief="chief"
        :sources="sources"
        :has-lab="usedLab"
        :lab-findings="labFindings"
        :lab-unreadable="labUnreadable"
        :role-switching="roleSwitching"
        @restart="onRestart"
        @export="onExport"
        @role-change="dx.switchRole"
      />
    </view>

    <!-- 决断过场（全屏覆盖） -->
    <dx-decision v-if="!elderMode && stage === 'diagnosing'" />
    <dxe-decision v-else-if="elderMode && stage === 'diagnosing'" />

    <!-- 报告导出等待覆盖层（全屏宣纸 scrim + 居中卡片 + 假进度） -->
    <view v-if="exporting" class="dx__export" @touchmove.stop.prevent>
      <view class="dx__export-card">
        <dx-progress
          v-if="!elderMode"
          :running="exporting && !exportDone"
          :done="exportDone"
          tone="paper"
          :stages="['汇总脉案…', '排版医嘱…', '生成报告…']"
        />
        <dxe-progress
          v-else
          :running="exporting && !exportDone"
          :done="exportDone"
          tone="paper"
          :stages="['汇总脉案…', '排版医嘱…', '生成报告…']"
        />
      </view>
    </view>

    <!-- 脉案 sheet -->
    <dx-case-sheet
      v-if="!elderMode"
      v-model="caseSheet"
      :chief="chief"
      :entries="caseEntries"
      :current="qIndex"
      @reopen="dx.goto"
    />
    <dxe-case-sheet
      v-else
      v-model="caseSheet"
      :chief="chief"
      :entries="caseEntries"
      :current="qIndex"
      @reopen="dx.goto"
    />
  </view>
</template>

<style lang="scss" scoped>
.dx {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;

  &__progress {
    display: flex;
    align-items: center;
    padding-right: 24rpx;
  }
  &__fp {
    flex: 1;
    min-width: 0;
  }
  &__case-btn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: 8rpx;
    padding: 10rpx 24rpx;
    border-radius: 999rpx;
    border: 1px solid rgba(154, 45, 45, 0.45);
    background: rgba(154, 45, 45, 0.06);
    font-size: 26rpx;
    color: $cinnabar;

    &--hover {
      background: rgba(154, 45, 45, 0.12);
    }
  }

  /* 舌象后台状态丸 */
  &__tongue-pill {
    display: flex;
    align-items: center;
    gap: 10rpx;
    align-self: flex-start;
    margin: 0 0 8rpx 24rpx;
    padding: 8rpx 20rpx;
    border-radius: 999rpx;
    font-size: 24rpx;
    background: $paper-card;
    border: 1px solid $border-paper;
    color: $ink-2;
    animation: pillIn 0.28s ease;
    &.is-done {
      border-color: rgba(95, 179, 161, 0.5);
      color: $ink;
    }
  }
  &__tongue-dots {
    display: flex;
    gap: 6rpx;
    align-items: center;
  }
  &__tongue-dot {
    width: 8rpx;
    height: 8rpx;
    border-radius: 50%;
    background: $cinnabar;
    animation: pillDot 1s ease-in-out infinite;
  }

  /* 需重拍软提示条 */
  &__tongue-banner {
    display: flex;
    align-items: center;
    gap: 16rpx;
    margin: 0 24rpx 10rpx;
    padding: 14rpx 20rpx;
    border-radius: $radius-sm;
    background: rgba(200, 164, 92, 0.12);
    border: 1px solid rgba(200, 164, 92, 0.45);
    animation: pillIn 0.28s ease;
  }
  &__tongue-banner-txt {
    flex: 1;
    min-width: 0;
    font-size: 24rpx;
    line-height: 1.4;
    color: $ink-2;
  }
  &__tongue-banner-ops {
    display: flex;
    gap: 8rpx;
    flex-shrink: 0;
  }
  &__tongue-banner-op {
    padding: 8rpx 22rpx;
    border-radius: 999rpx;
    font-size: 26rpx;
    color: $paper-card;
    background: $cinnabar;
    &--ghost {
      color: $ink-3;
      background: transparent;
      border: 1px solid $border-paper;
    }
  }

  &__stage {
    position: relative;
    flex: 1;
    min-height: 0;
  }
  &__pane {
    position: absolute;
    inset: 0;
  }

  /* 报告导出覆盖层 */
  &__export {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(31, 27, 22, 0.42);
    animation: dxExportIn 0.24s ease;
  }
  &__export-card {
    width: 540rpx;
    max-width: 80vw;
    padding: 56rpx 48rpx 48rpx;
    box-sizing: border-box;
    border-radius: $radius;
    background: $paper-card;
    border: 1px solid $border-paper;
    box-shadow: 0 12rpx 48rpx rgba(31, 27, 22, 0.22);
  }
}

@keyframes dxExportIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* 翻卡过渡：前进自右入、后退自左入（仅 transform/opacity） */
.slide-fwd-enter-active,
.slide-fwd-leave-active,
.slide-back-enter-active,
.slide-back-leave-active {
  transition: transform 0.32s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.3s ease;
}
.slide-fwd-enter-from {
  transform: translateX(48rpx);
  opacity: 0;
}
.slide-fwd-leave-to {
  transform: translateX(-48rpx);
  opacity: 0;
}
.slide-back-enter-from {
  transform: translateX(-48rpx);
  opacity: 0;
}
.slide-back-leave-to {
  transform: translateX(48rpx);
  opacity: 0;
}

/* 斟酌淡入淡出 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.28s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* 舌象状态丸 */
@keyframes pillIn {
  from {
    opacity: 0;
    transform: translateY(-6rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@keyframes pillDot {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  50% {
    transform: translateY(-6rpx);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .dx__tongue-pill,
  .dx__tongue-banner,
  .dx__export {
    animation: none;
  }
  .dx__tongue-dot {
    animation: none;
  }
  .slide-fwd-enter-active,
  .slide-fwd-leave-active,
  .slide-back-enter-active,
  .slide-back-leave-active {
    transition: opacity 0.2s ease;
  }
  .slide-fwd-enter-from,
  .slide-back-enter-from,
  .slide-fwd-leave-to,
  .slide-back-leave-to {
    transform: none;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .dx__progress { padding-right: 32rpx; }
  .dx__case-btn { min-height: 112rpx; gap: 12rpx; padding: 16rpx 32rpx; font-size: var(--gf-fs-sm); }
  .dx__tongue-pill { margin: 0 0 12rpx 24rpx; gap: 14rpx; padding: 14rpx 28rpx; font-size: var(--gf-fs-sm); }
  .dx__tongue-dots { gap: 9rpx; }
  .dx__tongue-dot { width: 12rpx; height: 12rpx; }
  .dx__tongue-banner { gap: 22rpx; margin: 0 24rpx 14rpx; padding: 22rpx 28rpx; }
  .dx__tongue-banner-txt { font-size: var(--gf-fs-sm); }
  .dx__tongue-banner-ops { gap: 14rpx; }
  .dx__tongue-banner-op { min-height: 96rpx; display: flex; align-items: center; padding: 14rpx 32rpx; font-size: var(--gf-fs-sm); }
}
</style>
