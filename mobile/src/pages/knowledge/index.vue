<script setup lang="ts">
import { ref, computed } from "vue";
import { useElder } from "@/composables/useElder";
import { useVoiceInput } from "@/composables/useVoiceInput";
import { onLoad } from "@dcloudio/uni-app";
import { searchKnowledge, getKnowledgeStats } from "@/api";

/**
 * 知识检索（宣纸面）。接 GET /knowledge/search（分页）、/knowledge/stats。
 * 图谱在小屏成本高，移动端以「检索 + 分类浏览 + 详情」替代。
 */
interface KEntry {
  id: string;
  category: string;
  title: string;
  source?: { book?: string; volume?: string; section?: string };
  original_text: string;
  plain_explanation: string;
  related_diseases?: string[];
  related_syndromes?: string[];
  treatment_method?: string;
  tags?: string[];
  verified?: boolean;
}

const { rootClass } = useElder();
const CATS = ["全部", "理", "法", "方", "药", "养生"];

const query = ref("");
const category = ref("全部");
const items = ref<KEntry[]>([]);
const page = ref(1);
const pages = ref(0);
const total = ref(0);
const loading = ref(false);
const loadingMore = ref(false);
const stats = ref<{ total: number; verified: number; by_category: Record<string, number> } | null>(
  null
);

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

const hasMore = computed(() => page.value < pages.value);
const catCount = (c: string) =>
  c === "全部" ? stats.value?.total ?? "" : stats.value?.by_category?.[c] ?? "";

async function fetchPage(reset: boolean) {
  if (reset) {
    loading.value = true;
    page.value = 1;
  } else {
    if (!hasMore.value || loadingMore.value) return;
    loadingMore.value = true;
    page.value += 1;
  }
  try {
    const cat = category.value === "全部" ? undefined : category.value;
    const res: any = await searchKnowledge(query.value.trim(), cat, page.value, 10);
    total.value = res?.total ?? 0;
    pages.value = res?.pages ?? 0;
    const list = (res?.items || []) as KEntry[];
    items.value = reset ? list : items.value.concat(list);
  } catch {
    uni.showToast({ title: "检索失败，请重试", icon: "none" });
    if (!reset) page.value -= 1; // 回退页码
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function onInput() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => fetchPage(true), 300);
}

// 语音检索：单行搜索框形态不适合 gf-voice-field（textarea），改为在搜索框内挂一枚话筒，
// 识别结果直接作为检索词（搜索词通常短，替换语义比追加更合适）并立即检索。
function onVoiceResult(text: string) {
  const t = (text || "").trim();
  if (!t) return;
  query.value = t;
  if (debounceTimer) clearTimeout(debounceTimer);
  fetchPage(true);
}
const {
  supported: voiceSupported,
  recording: voiceRecording,
  processing: voiceProcessing,
  cancelArmed: voiceCancelArmed,
  seconds: voiceSeconds,
  liveText: voiceLiveText,
  onPressStart: onVoicePressStart,
  onPressMove: onVoicePressMove,
  onPressEnd: onVoicePressEnd,
} = useVoiceInput({ onResult: onVoiceResult });
function pickCategory(c: string) {
  if (category.value === c) return;
  category.value = c;
  fetchPage(true);
}
function onReachBottom() {
  fetchPage(false);
}

const snippet = (e: KEntry) => (e.plain_explanation || e.original_text || "").slice(0, 60);
function srcLabel(s?: KEntry["source"]) {
  if (!s) return "";
  return [s.book, s.volume, s.section].filter(Boolean).join(" · ");
}

/* 详情 sheet */
const detailShow = ref(false);
const active = ref<KEntry | null>(null);
function openDetail(e: KEntry) {
  active.value = e;
  detailShow.value = true;
}

onLoad(async () => {
  try {
    stats.value = (await getKnowledgeStats()) as any;
  } catch {
    /* 统计失败不阻断检索 */
  }
  fetchPage(true);
});
</script>

<template>
  <view class="kn" :class="rootClass">
    <gf-navbar title="知识检索" :show-back="true" />

    <!-- 检索框 -->
    <view class="kn__search">
      <view class="kn__search-box">
        <gf-icon name="search" :size="34" color="#8A7E6A" />
        <input
          v-model="query"
          class="kn__input"
          type="text"
          confirm-type="search"
          placeholder="搜索本草知识，如 失眠、黄连…"
          placeholder-class="kn__ph"
          @input="onInput"
          @confirm="fetchPage(true)"
        />
        <view v-if="query" class="kn__clear" @tap="query = ''; fetchPage(true)">
          <gf-icon name="close" :size="30" color="#8A7E6A" />
        </view>
        <!-- 语音检索话筒（长按说话）；supported=false（非微信端/无插件）时不渲染，纯打字降级 -->
        <view
          v-if="voiceSupported"
          class="kn__mic"
          :class="{ 'is-recording': voiceRecording }"
          @touchstart.stop.prevent="onVoicePressStart"
          @touchmove.stop.prevent="onVoicePressMove"
          @touchend.stop.prevent="onVoicePressEnd"
          @touchcancel.stop.prevent="onVoicePressEnd"
        >
          <gf-icon name="mic" :size="34" :color="voiceRecording ? '#FBF7EE' : '#8A7E6A'" />
        </view>
      </view>
    </view>

    <!-- 语音录音 / 转写浮层 -->
    <gf-rec-overlay
      v-if="voiceRecording || voiceProcessing"
      :recording="voiceRecording"
      :processing="voiceProcessing"
      :cancel-armed="voiceCancelArmed"
      :seconds="voiceSeconds"
      :live-text="voiceLiveText"
    />

    <!-- 分类 -->
    <scroll-view scroll-x class="kn__cats" :show-scrollbar="false">
      <view class="kn__cats-row">
        <view
          v-for="c in CATS"
          :key="c"
          class="kn__cat"
          :class="{ active: category === c }"
          @tap="pickCategory(c)"
        >{{ c }}<text v-if="catCount(c) !== ''" class="kn__cat-n">{{ catCount(c) }}</text></view>
      </view>
    </scroll-view>

    <view class="kn__stat gf-ink-3">
      共 <text class="gf-tnum">{{ total }}</text> 条<text v-if="stats"> · 已核验 <text class="gf-tnum">{{ stats.verified }}</text></text>
    </view>

    <!-- 列表 -->
    <scroll-view scroll-y class="kn__list" @scrolltolower="onReachBottom">
      <view v-if="loading" class="kn__loading gf-ink-3">检索中…</view>
      <view v-else-if="!items.length" class="kn__empty gf-ink-3">未找到相关条目，换个关键词试试</view>
      <template v-else>
        <view
          v-for="(e, i) in items"
          :key="e.id"
          class="kn__card gf-card"
          :style="{ animationDelay: Math.min(i, 8) * 0.04 + 's' }"
          hover-class="kn__card--hover"
          @tap="openDetail(e)"
        >
          <view class="kn__card-head">
            <text class="kn__card-title gf-serif">{{ e.title }}</text>
            <text class="kn__card-cat">{{ e.category }}</text>
          </view>
          <view class="kn__card-snippet">{{ snippet(e) }}…</view>
          <view class="kn__card-foot">
            <text v-if="e.verified" class="kn__verified"><gf-icon name="check" :size="22" color="#5FB3A1" />已核验</text>
            <text class="kn__card-src gf-ink-3">{{ srcLabel(e.source) }}</text>
          </view>
        </view>
        <view v-if="loadingMore" class="kn__more gf-ink-3">加载中…</view>
        <view v-else-if="!hasMore" class="kn__more gf-ink-3">已全部加载</view>
        <view class="kn__bottom-pad" />
      </template>
    </scroll-view>

    <!-- 详情 sheet -->
    <wd-popup
      v-model="detailShow"
      position="bottom"
      :safe-area-inset-bottom="true"
      custom-style="border-radius:24rpx 24rpx 0 0;background:#F3ECDD;"
    >
      <!-- @touchmove.stop：面板手势不穿透到下层页面（内部 scroll-view 原生滚动不受影响） -->
      <view class="kd" v-if="active" @touchmove.stop>
        <view class="kd__bar">
          <view class="kd__title gf-serif">{{ active.title }}</view>
          <view class="kd__close" @tap="detailShow = false"><gf-icon name="close" :size="36" color="#5C5345" /></view>
        </view>
        <scroll-view scroll-y class="kd__scroll">
          <view class="kd__meta">
            <text class="kd__tag kd__tag--cat">{{ active.category }}</text>
            <text v-if="active.verified" class="kd__tag kd__tag--ok">已核验</text>
            <text v-if="srcLabel(active.source)" class="kd__src gf-ink-3">{{ srcLabel(active.source) }}</text>
          </view>
          <view class="kd__label gf-ink-3">原文</view>
          <view class="kd__orig gf-serif">{{ active.original_text || "—" }}</view>
          <template v-if="active.plain_explanation">
            <view class="gf-divider" />
            <view class="kd__label gf-ink-3">白话</view>
            <view class="kd__plain">{{ active.plain_explanation }}</view>
          </template>
          <view v-if="active.treatment_method" class="kd__kv"><text class="kd__k gf-ink-3">治法</text><text>{{ active.treatment_method }}</text></view>
          <view v-if="active.related_diseases && active.related_diseases.length" class="kd__rel">
            <text class="kd__k gf-ink-3">关联病证</text>
            <view class="kd__tags"><text v-for="(t, i) in active.related_diseases" :key="i" class="kd__rtag">{{ t }}</text></view>
          </view>
          <view v-if="active.related_syndromes && active.related_syndromes.length" class="kd__rel">
            <text class="kd__k gf-ink-3">关联证型</text>
            <view class="kd__tags"><text v-for="(t, i) in active.related_syndromes" :key="i" class="kd__rtag kd__rtag--jade">{{ t }}</text></view>
          </view>
          <view class="kd__pad" />
        </scroll-view>
      </view>
    </wd-popup>
  </view>
</template>

<style lang="scss" scoped>
.kn {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;

  &__search {
    padding: 12rpx 32rpx 8rpx;
  }
  &__search-box {
    display: flex;
    align-items: center;
    gap: 16rpx;
    height: 84rpx;
    padding: 0 24rpx;
    background: $paper-card;
    border: 1px solid $border-paper;
    border-radius: 999rpx;
  }
  &__input {
    flex: 1;
    font-size: 30rpx;
    color: $ink;
  }
  &__ph {
    color: $ink-3;
  }
  &__clear {
    width: 48rpx;
    height: 48rpx;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  /* 语音检索话筒：触控区充足，录音时朱砂高亮 */
  &__mic {
    flex-shrink: 0;
    width: 64rpx;
    height: 64rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 999rpx;
    &.is-recording {
      background: $cinnabar;
    }
  }

  &__cats {
    white-space: nowrap;
    padding: 12rpx 32rpx;
    box-sizing: border-box;
  }
  &__cats-row {
    display: inline-flex;
    gap: 14rpx;
  }
  &__cat {
    flex-shrink: 0;
    padding: 12rpx 28rpx;
    font-size: 28rpx;
    color: $ink-2;
    background: $paper-card;
    border: 1px solid $border-paper;
    border-radius: 999rpx;
    &.active {
      background: $cinnabar;
      color: $paper-card;
      border-color: $cinnabar;
    }
  }
  &__cat-n {
    font-size: 22rpx;
    margin-left: 8rpx;
    opacity: 0.8;
  }

  &__stat {
    font-size: 24rpx;
    padding: 4rpx 32rpx 12rpx;
  }

  &__list {
    flex: 1;
    min-height: 0;
    padding: 0 32rpx env(safe-area-inset-bottom);
    box-sizing: border-box;
  }
  &__loading,
  &__empty,
  &__more {
    text-align: center;
    padding: 48rpx 0;
    font-size: 26rpx;
  }

  &__card {
    padding: 28rpx;
    margin-bottom: 16rpx;
    opacity: 0;
    transform: translateY(12rpx);
    animation: knIn 0.35s ease forwards;
    &--hover {
      background: $paper-sunken;
    }
  }
  &__card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16rpx;
    margin-bottom: 10rpx;
  }
  &__card-title {
    flex: 1;
    font-size: 32rpx;
    font-weight: 700;
    color: $ink;
    line-height: 1.4;
  }
  &__card-cat {
    flex-shrink: 0;
    padding: 4rpx 18rpx;
    font-size: 24rpx;
    color: $cinnabar;
    background: rgba(154, 45, 45, 0.08);
    border-radius: 999rpx;
  }
  &__card-snippet {
    font-size: 28rpx;
    line-height: 1.6;
    color: $ink-2;
  }
  &__card-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16rpx;
    margin-top: 14rpx;
  }
  &__verified {
    display: inline-flex;
    align-items: center;
    gap: 6rpx;
    font-size: 24rpx;
    color: $jade;
  }
  &__card-src {
    font-size: 23rpx;
    text-align: right;
    flex: 1;
  }
  &__bottom-pad {
    height: 32rpx;
  }
}

@keyframes knIn {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@media (prefers-reduced-motion: reduce) {
  .kn__card {
    animation: none;
    opacity: 1;
    transform: none;
  }
}

/* 详情 sheet */
.kd {
  max-height: 78vh;
  display: flex;
  flex-direction: column;
  &__bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 28rpx 32rpx 16rpx;
  }
  &__title {
    flex: 1;
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
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 12rpx;
    margin-bottom: 20rpx;
  }
  &__tag {
    padding: 4rpx 18rpx;
    font-size: 24rpx;
    border-radius: 999rpx;
    &--cat {
      color: $cinnabar;
      background: rgba(154, 45, 45, 0.08);
    }
    &--ok {
      color: $jade;
      background: rgba(95, 179, 161, 0.14);
    }
  }
  &__src {
    font-size: 24rpx;
  }
  &__label {
    font-size: 24rpx;
    margin-bottom: 10rpx;
  }
  &__orig {
    font-size: 34rpx;
    line-height: 1.9;
    color: $cinnabar;
  }
  &__plain {
    font-size: 30rpx;
    line-height: 1.7;
    color: $ink;
  }
  &__kv,
  &__rel {
    display: flex;
    gap: 16rpx;
    margin-top: 20rpx;
    font-size: 28rpx;
    color: $ink;
  }
  &__k {
    font-size: 26rpx;
    width: 120rpx;
    flex-shrink: 0;
  }
  &__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 10rpx;
    flex: 1;
  }
  &__rtag {
    padding: 4rpx 18rpx;
    font-size: 24rpx;
    color: $ink-2;
    background: $paper-sunken;
    border-radius: 999rpx;
    &--jade {
      color: $jade;
      background: rgba(95, 179, 161, 0.14);
    }
  }
  &__pad {
    height: 40rpx;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  /* 检索框 */
  .kn__search { padding: 20rpx 32rpx 12rpx; }
  .kn__search-box { gap: 20rpx; height: 120rpx; padding: 0 32rpx; border-radius: 999rpx; }
  .kn__input { font-size: var(--gf-fs-lg); }
  .kn__clear { width: 72rpx; height: 72rpx; }
  .kn__mic { width: 96rpx; height: 96rpx; }

  /* 分类标签：换行更宽松 */
  .kn__cats { white-space: normal; padding: 16rpx 32rpx; }
  .kn__cats-row { display: flex; flex-wrap: wrap; gap: 20rpx; }
  .kn__cat { padding: 22rpx 40rpx; min-height: 112rpx; box-sizing: border-box; display: inline-flex; align-items: center; font-size: var(--gf-fs-base); border-radius: 999rpx; }
  .kn__cat-n { font-size: var(--gf-fs-sm); margin-left: 12rpx; }

  /* 统计 */
  .kn__stat { font-size: var(--gf-fs-sm); padding: 8rpx 32rpx 16rpx; }

  /* 列表占位/提示 */
  .kn__loading { font-size: var(--gf-fs-base); padding: 64rpx 0; }
  .kn__empty { font-size: var(--gf-fs-base); padding: 64rpx 0; }
  .kn__more { font-size: var(--gf-fs-base); padding: 64rpx 0; }

  /* 结果项：纵向加大 */
  .kn__card { padding: 40rpx; margin-bottom: 24rpx; }
  .kn__card-head { gap: 20rpx; margin-bottom: 16rpx; }
  .kn__card-title { font-size: var(--gf-fs-title); line-height: 1.5; }
  .kn__card-cat { padding: 10rpx 26rpx; font-size: var(--gf-fs-sm); border-radius: 999rpx; }
  .kn__card-snippet { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }
  .kn__card-foot { gap: 20rpx; margin-top: 22rpx; }
  .kn__verified { gap: 10rpx; font-size: var(--gf-fs-sm); }
  .kn__card-src { font-size: var(--gf-fs-sm); }
  .kn__bottom-pad { height: 48rpx; }

  /* 详情 sheet */
  .kd__bar { padding: 36rpx 32rpx 20rpx; }
  .kd__title { font-size: var(--gf-fs-title); }
  .kd__close { width: 80rpx; height: 80rpx; }
  .kd__meta { gap: 16rpx; margin-bottom: 28rpx; }
  .kd__tag { padding: 10rpx 26rpx; font-size: var(--gf-fs-sm); border-radius: 999rpx; }
  .kd__src { font-size: var(--gf-fs-sm); }
  .kd__label { font-size: var(--gf-fs-sm); margin-bottom: 14rpx; }
  .kd__orig { font-size: var(--gf-fs-lg); line-height: var(--gf-lh); }
  .kd__plain { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }
  .kd__kv { gap: 20rpx; margin-top: 28rpx; font-size: var(--gf-fs-base); }
  .kd__rel { gap: 20rpx; margin-top: 28rpx; font-size: var(--gf-fs-base); }
  .kd__k { font-size: var(--gf-fs-base); width: 160rpx; }
  .kd__tags { gap: 16rpx; }
  .kd__rtag { padding: 12rpx 28rpx; font-size: var(--gf-fs-sm); border-radius: 999rpx; }
  .kd__pad { height: 56rpx; }
}
</style>
