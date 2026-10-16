<script setup lang="ts">
import { ref, computed } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { getChronicDiseases, quickDiagnose } from "@/api";
import { useElder } from "@/composables/useElder";
import { useTts } from "@/composables/useTts";
import { useRoleStore } from "@/stores/role";

/**
 * 慢病助手（适老核心 · 大字超大按钮）。
 * 接 GET /chronic/diseases、POST /chronic/quick-diagnose。
 */
const { rootClass, autoTts } = useElder();
const { speak } = useTts();
// 接入全局角色（不再硬编码 patient）：随 quick-diagnose 上送 role，与仿真辨证共用同一持久角色。
const roleStore = useRoleStore();
interface DiseaseInfo {
  tcm_name: string;
  common_symptoms: string[];
}
interface SourceEntry {
  id: string;
  title: string;
  original_text: string;
  plain_explanation: string;
  source?: { book?: string; volume?: string; section?: string };
}
interface QuickResult {
  disease: string;
  syndrome: string;
  treatment: string;
  plan: Record<string, string>;
  sources: SourceEntry[];
  disclaimer?: string;
}

const PLAN_SEALS: { key: string; seal: string }[] = [
  { key: "食疗", seal: "食" },
  { key: "起居", seal: "居" },
  { key: "功法", seal: "功" },
  { key: "用药提示", seal: "药" },
  { key: "随访提醒", seal: "访" },
];

const diseases = ref<Record<string, DiseaseInfo>>({});
const diseaseNames = computed(() => Object.keys(diseases.value));
const selected = ref("");
const checked = ref<string[]>([]);
const stage = ref<"pick" | "result">("pick");
const loadingList = ref(false);
const submitting = ref(false);
const result = ref<QuickResult | null>(null);

const symptoms = computed(() => diseases.value[selected.value]?.common_symptoms || []);
const planItems = computed(() => {
  const p = result.value?.plan || {};
  return PLAN_SEALS.filter((x) => p[x.key]).map((x) => ({ ...x, text: p[x.key] }));
});

function selectDisease(name: string) {
  if (selected.value === name) return;
  selected.value = name;
  checked.value = [];
}
function toggleSymptom(s: string) {
  const i = checked.value.indexOf(s);
  if (i >= 0) checked.value.splice(i, 1);
  else checked.value.push(s);
}

async function loadDiseases() {
  loadingList.value = true;
  try {
    const res: any = await getChronicDiseases();
    diseases.value = res || {};
    const first = Object.keys(diseases.value)[0];
    if (first) selected.value = first;
  } catch {
    uni.showToast({ title: "病种加载失败，请重试", icon: "none" });
  } finally {
    loadingList.value = false;
  }
}

async function runDiagnose() {
  if (submitting.value) return;
  if (!checked.value.length) {
    uni.showToast({ title: "请至少勾选一个症状", icon: "none" });
    return;
  }
  submitting.value = true;
  try {
    const res: any = await quickDiagnose(selected.value, checked.value, roleStore.role);
    result.value = res as QuickResult;
    stage.value = "result";
    uni.pageScrollTo?.({ scrollTop: 0, duration: 0 });
    // 老年模式：结果就绪自动朗读（证型 + 治法 + 食疗/起居要点）
    if (autoTts.value && result.value) {
      const r = result.value;
      const plan = r.plan || {};
      const text = [
        `辨证结果，${r.disease}，证型${r.syndrome}。`,
        `治法，${r.treatment}。`,
        plan["食疗"] ? `食疗，${plan["食疗"]}。` : "",
        plan["起居"] ? `起居，${plan["起居"]}。` : "",
      ]
        .filter(Boolean)
        .join("");
      speak(text);
    }
  } catch {
    uni.showToast({ title: "辨证失败，请重试", icon: "none" });
  } finally {
    submitting.value = false;
  }
}

/* 溯源 sheet */
const srcShow = ref(false);
const activeSrc = ref<SourceEntry | null>(null);
function openSource(s: SourceEntry) {
  activeSrc.value = s;
  srcShow.value = true;
}
function srcLabel(s?: SourceEntry) {
  if (!s) return "";
  return [s.source?.book, s.source?.volume, s.source?.section].filter(Boolean).join(" · ");
}

function handleBack() {
  if (stage.value === "result") {
    stage.value = "pick";
    return;
  }
  uni.navigateBack({ fail: () => uni.reLaunch({ url: "/pages/index/index" }) });
}

onLoad(() => loadDiseases());
</script>

<template>
  <view class="cd" :class="rootClass">
    <gf-navbar title="慢病助手" :show-back="true" custom-back @back="handleBack" />

    <!-- 选择阶段 -->
    <scroll-view v-if="stage === 'pick'" scroll-y class="cd__scroll">
      <view class="cd__lead gf-serif">选择病种，勾选您的症状</view>

      <view v-if="loadingList" class="cd__loading gf-ink-3">载入中…</view>
      <template v-else>
        <!-- 病种 -->
        <view class="cd__diseases">
          <view
            v-for="name in diseaseNames"
            :key="name"
            class="cd__disease"
            :class="{ active: selected === name }"
            hover-class="cd__disease--hover"
            @tap="selectDisease(name)"
          >
            <text class="cd__disease-name gf-serif">{{ name }}</text>
            <text class="cd__disease-tcm">{{ diseases[name].tcm_name }}</text>
          </view>
        </view>

        <!-- 症状 -->
        <view class="cd__sym-label gf-serif">常见症状（可多选）</view>
        <view class="cd__symptoms">
          <view
            v-for="s in symptoms"
            :key="s"
            class="cd__symptom"
            :class="{ active: checked.includes(s) }"
            hover-class="cd__symptom--hover"
            @tap="toggleSymptom(s)"
          >
            <view class="cd__check" :class="{ on: checked.includes(s) }">
              <gf-icon v-if="checked.includes(s)" name="check" :size="34" color="#FBF7EE" />
            </view>
            <text class="cd__symptom-text">{{ s }}</text>
          </view>
        </view>
        <view class="cd__bottom-pad" />
      </template>
    </scroll-view>

    <!-- 选择阶段底部 CTA -->
    <view v-if="stage === 'pick'" class="cd__cta-bar gf-safe-bottom">
      <view class="cd__count gf-ink-3">已选 {{ checked.length }} 项</view>
      <view
        class="cd__cta"
        :class="{ 'is-disabled': !checked.length || submitting }"
        hover-class="cd__cta--hover"
        @tap="runDiagnose"
      >
        {{ submitting ? "辨证中…" : "一键辨证" }}
      </view>
    </view>

    <!-- 结果阶段 -->
    <scroll-view v-else scroll-y class="cd__scroll">
      <view v-if="result" class="cd__result">
        <!-- 证型 + 治法 -->
        <view class="cd__verdict gf-card">
          <view class="cd__verdict-head">
            <view class="cd__verdict-seal gf-seal gf-serif">证</view>
            <view class="cd__verdict-body">
              <view class="cd__verdict-disease gf-ink-3">{{ result.disease }}</view>
              <view class="cd__verdict-syndrome gf-serif">{{ result.syndrome }}</view>
            </view>
          </view>
          <view v-if="result.treatment" class="cd__treatment">
            <text class="cd__treatment-label gf-ink-3">治法</text>
            <text class="cd__treatment-text">{{ result.treatment }}</text>
          </view>
        </view>

        <!-- 调护方案 -->
        <view
          v-for="(p, i) in planItems"
          :key="p.key"
          class="cd__plan gf-card"
          :style="{ animationDelay: i * 0.06 + 's' }"
        >
          <view class="cd__plan-head">
            <view class="cd__plan-seal gf-seal gf-serif">{{ p.seal }}</view>
            <text class="cd__plan-label gf-serif">{{ p.key }}</text>
          </view>
          <view class="cd__plan-text">{{ p.text }}</view>
        </view>

        <!-- 经典依据 -->
        <view v-if="result.sources && result.sources.length" class="cd__sources">
          <view class="cd__sources-label gf-serif">经典依据</view>
          <view
            v-for="s in result.sources"
            :key="s.id"
            class="cd__source gf-card"
            hover-class="cd__source--hover"
            @tap="openSource(s)"
          >
            <gf-icon name="book" :size="30" color="#C8A45C" />
            <view class="cd__source-body">
              <view class="cd__source-title gf-serif">{{ s.title }}</view>
              <view class="cd__source-hint gf-ink-3">点击查看原文 · 白话</view>
            </view>
            <gf-icon name="arrow" :size="30" color="#8A7E6A" />
          </view>
        </view>

        <view v-if="result.disclaimer" class="cd__disclaimer gf-ink-3">{{ result.disclaimer }}</view>
        <view class="cd__redo gf-btn gf-btn-ghost" @tap="stage = 'pick'">重新选择</view>
        <view class="cd__bottom-pad" />
      </view>
    </scroll-view>

    <!-- 溯源 sheet -->
    <wd-popup
      v-model="srcShow"
      position="bottom"
      :safe-area-inset-bottom="true"
      custom-style="border-radius:24rpx 24rpx 0 0;background:#F3ECDD;"
    >
      <!-- @touchmove.stop：面板手势不穿透到下层页面（内部 scroll-view 原生滚动不受影响） -->
      <view class="src" @touchmove.stop>
        <view class="src__bar">
          <view class="src__title gf-serif">{{ activeSrc?.title }}</view>
          <view class="src__close" @tap="srcShow = false"><gf-icon name="close" :size="36" color="#5C5345" /></view>
        </view>
        <scroll-view scroll-y class="src__scroll">
          <view v-if="srcLabel(activeSrc || undefined)" class="src__meta gf-ink-3">{{ srcLabel(activeSrc || undefined) }}</view>
          <view class="src__orig-label gf-ink-3">原文</view>
          <view class="src__orig gf-serif">{{ activeSrc?.original_text || "—" }}</view>
          <template v-if="activeSrc?.plain_explanation">
            <view class="gf-divider" />
            <view class="src__plain-label gf-ink-3">白话</view>
            <view class="src__plain">{{ activeSrc?.plain_explanation }}</view>
          </template>
        </scroll-view>
      </view>
    </wd-popup>
  </view>
</template>

<style lang="scss" scoped>
.cd {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;

  &__scroll {
    flex: 1;
    min-height: 0;
    padding: 16rpx 32rpx 0;
    box-sizing: border-box;
  }
  &__lead,
  &__sym-label,
  &__sources-label {
    font-size: 34rpx;
    font-weight: 700;
    color: $ink;
    margin: 16rpx 0 20rpx;
  }
  &__loading {
    text-align: center;
    padding: 80rpx 0;
    font-size: 30rpx;
  }

  /* 病种 */
  &__diseases {
    display: flex;
    flex-wrap: wrap;
    gap: 20rpx;
  }
  &__disease {
    width: calc((100% - 40rpx) / 3);
    box-sizing: border-box;
    padding: 24rpx 12rpx;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6rpx;
    background: $paper-card;
    border: 2rpx solid $border-paper;
    border-radius: $radius-sm;
    &.active {
      border-color: $cinnabar;
      background: rgba(154, 45, 45, 0.06);
    }
    &--hover {
      background: $paper-sunken;
    }
  }
  &__disease-name {
    font-size: 34rpx;
    font-weight: 700;
    color: $ink;
  }
  &__disease-tcm {
    font-size: 24rpx;
    color: $ink-3;
  }

  /* 症状 */
  &__symptoms {
    display: flex;
    flex-direction: column;
    gap: 16rpx;
  }
  &__symptom {
    display: flex;
    align-items: center;
    gap: 24rpx;
    min-height: 100rpx;
    padding: 0 28rpx;
    background: $paper-card;
    border: 1px solid $border-paper;
    border-radius: $radius-sm;
    &.active {
      border-color: $cinnabar;
      background: rgba(154, 45, 45, 0.05);
    }
    &--hover {
      background: $paper-sunken;
    }
  }
  &__check {
    width: 52rpx;
    height: 52rpx;
    border-radius: 12rpx;
    border: 2rpx solid $ink-3;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    &.on {
      background: $cinnabar;
      border-color: $cinnabar;
    }
  }
  &__symptom-text {
    font-size: 34rpx;
    color: $ink;
  }
  &__bottom-pad {
    height: 48rpx;
  }

  /* CTA 条 */
  &__cta-bar {
    display: flex;
    align-items: center;
    gap: 24rpx;
    padding: 16rpx 32rpx;
    background: $paper-card;
    border-top: 1px solid $border-paper;
  }
  &__count {
    font-size: 28rpx;
    flex-shrink: 0;
  }
  &__cta {
    flex: 1;
    min-height: 104rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    background: $cinnabar;
    color: $paper-card;
    font-size: 38rpx;
    font-weight: 700;
    border-radius: $radius-sm;
    &.is-disabled {
      opacity: 0.45;
    }
    &--hover {
      background: $cinnabar-soft;
    }
  }

  /* 结果 */
  &__verdict {
    padding: 32rpx;
  }
  &__verdict-head {
    display: flex;
    align-items: center;
    gap: 20rpx;
  }
  &__verdict-seal {
    width: 72rpx;
    height: 72rpx;
    font-size: 38rpx;
  }
  &__verdict-disease {
    font-size: 26rpx;
  }
  &__verdict-syndrome {
    font-size: 44rpx;
    font-weight: 700;
    color: $cinnabar;
  }
  &__treatment {
    margin-top: 20rpx;
    padding-top: 20rpx;
    border-top: 1px dashed $border-paper;
  }
  &__treatment-label {
    font-size: 26rpx;
    margin-right: 12rpx;
  }
  &__treatment-text {
    font-size: 32rpx;
    color: $ink;
  }

  &__plan {
    padding: 28rpx;
    margin-top: 20rpx;
    opacity: 0;
    transform: translateY(14rpx);
    animation: cdIn 0.4s ease forwards;
  }
  &__plan-head {
    display: flex;
    align-items: center;
    gap: 16rpx;
    margin-bottom: 14rpx;
  }
  &__plan-seal {
    width: 56rpx;
    height: 56rpx;
    font-size: 30rpx;
    background: $gold;
    color: $ink;
  }
  &__plan-label {
    font-size: 34rpx;
    font-weight: 700;
    color: $ink;
  }
  &__plan-text {
    font-size: 32rpx;
    line-height: 1.75;
    color: $ink;
  }

  &__sources {
    margin-top: 28rpx;
  }
  &__source {
    display: flex;
    align-items: center;
    gap: 20rpx;
    padding: 24rpx 28rpx;
    margin-bottom: 16rpx;
    &--hover {
      background: $paper-sunken;
    }
  }
  &__source-body {
    flex: 1;
    min-width: 0;
  }
  &__source-title {
    font-size: 30rpx;
    color: $ink;
  }
  &__source-hint {
    font-size: 24rpx;
    margin-top: 4rpx;
  }

  &__disclaimer {
    font-size: 24rpx;
    line-height: 1.6;
    text-align: center;
    padding: 28rpx 24rpx;
  }
  &__redo {
    min-height: 96rpx;
    margin: 0 0 16rpx;
  }
}

@keyframes cdIn {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@media (prefers-reduced-motion: reduce) {
  .cd__plan {
    animation: none;
    opacity: 1;
    transform: none;
  }
}

/* 溯源 sheet */
.src {
  max-height: 72vh;
  display: flex;
  flex-direction: column;
  &__bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 28rpx 32rpx 16rpx;
  }
  &__title {
    font-size: 34rpx;
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
    flex: 1; // 在 max-height 内约束高度，内容超长时 scroll-view 才能纵向滚动
    min-height: 0;
    padding: 0 32rpx 32rpx;
    box-sizing: border-box;
  }
  &__meta {
    font-size: 24rpx;
    margin-bottom: 16rpx;
  }
  &__orig-label,
  &__plain-label {
    font-size: 24rpx;
    margin-bottom: 10rpx;
  }
  &__orig {
    font-size: 34rpx;
    line-height: 1.9;
    color: $cinnabar;
  }
  &__plain {
    font-size: 32rpx;
    line-height: 1.7;
    color: $ink;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .cd__scroll { padding: 24rpx 36rpx 0; }
  .cd__lead { font-size: var(--gf-fs-lg); margin: 24rpx 0 28rpx; }
  .cd__sym-label { font-size: var(--gf-fs-lg); margin: 28rpx 0 24rpx; }
  .cd__sources-label { font-size: var(--gf-fs-lg); margin: 28rpx 0 24rpx; }
  .cd__loading { font-size: var(--gf-fs-base); padding: 100rpx 0; }

  /* 病种：三列改单列纵向，超大可点项 */
  .cd__diseases { gap: 24rpx; }
  .cd__disease {
    width: 100%;
    flex-direction: row;
    justify-content: center;
    align-items: baseline;
    gap: 20rpx;
    min-height: 132rpx;
    padding: 32rpx 36rpx;
  }
  .cd__disease-name { font-size: var(--gf-fs-lg); }
  .cd__disease-tcm { font-size: var(--gf-fs-sm); }

  /* 症状：勾选框与文字放大，触控更大 */
  .cd__symptoms { gap: 24rpx; }
  .cd__symptom { min-height: 140rpx; padding: 0 36rpx; gap: 32rpx; }
  .cd__check { width: 72rpx; height: 72rpx; border-radius: 16rpx; }
  .cd__symptom-text { font-size: var(--gf-fs-lg); }
  .cd__bottom-pad { height: 64rpx; }

  /* CTA 条 */
  .cd__cta-bar { gap: 28rpx; padding: 24rpx 36rpx; }
  .cd__count { font-size: var(--gf-fs-base); }
  .cd__cta { min-height: 132rpx; font-size: var(--gf-fs-title); }

  /* 结果：证型 */
  .cd__verdict { padding: 40rpx; }
  .cd__verdict-head { gap: 28rpx; }
  .cd__verdict-seal { width: 96rpx; height: 96rpx; font-size: var(--gf-fs-lg); }
  .cd__verdict-disease { font-size: var(--gf-fs-sm); }
  .cd__verdict-syndrome { font-size: var(--gf-fs-title); }
  .cd__treatment { margin-top: 28rpx; padding-top: 28rpx; }
  .cd__treatment-label { font-size: var(--gf-fs-sm); }
  .cd__treatment-text { font-size: var(--gf-fs-lg); }

  /* 调护方案 */
  .cd__plan { padding: 36rpx; margin-top: 28rpx; }
  .cd__plan-head { gap: 24rpx; margin-bottom: 20rpx; }
  .cd__plan-seal { width: 76rpx; height: 76rpx; font-size: var(--gf-fs-base); }
  .cd__plan-label { font-size: var(--gf-fs-lg); }
  .cd__plan-text { font-size: var(--gf-fs-lg); line-height: var(--gf-lh); }

  /* 经典依据 */
  .cd__sources { margin-top: 36rpx; }
  .cd__source { gap: 28rpx; padding: 32rpx 36rpx; margin-bottom: 24rpx; min-height: 132rpx; }
  .cd__source-title { font-size: var(--gf-fs-base); }
  .cd__source-hint { font-size: var(--gf-fs-sm); }

  .cd__disclaimer { font-size: var(--gf-fs-sm); line-height: var(--gf-lh); padding: 36rpx 32rpx; }
  .cd__redo { min-height: 116rpx; margin: 0 0 24rpx; }

  /* 溯源 sheet */
  .src__bar { padding: 36rpx 40rpx 24rpx; }
  .src__title { font-size: var(--gf-fs-lg); }
  .src__close { width: 76rpx; height: 76rpx; }
  .src__scroll { padding: 0 40rpx 40rpx; }
  .src__meta { font-size: var(--gf-fs-sm); margin-bottom: 24rpx; }
  .src__orig-label { font-size: var(--gf-fs-sm); margin-bottom: 16rpx; }
  .src__plain-label { font-size: var(--gf-fs-sm); margin-bottom: 16rpx; }
  .src__orig { font-size: var(--gf-fs-lg); line-height: var(--gf-lh); }
  .src__plain { font-size: var(--gf-fs-lg); line-height: var(--gf-lh); }
}
</style>
