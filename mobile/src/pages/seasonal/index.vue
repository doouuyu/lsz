<script setup lang="ts">
import { ref, computed } from "vue";
import { useElder } from "@/composables/useElder";
import { onLoad } from "@dcloudio/uni-app";
import { getSeasonalRegimen } from "@/api";

/**
 * 四时养生（宣纸面 · 适老平铺）。接 GET /regimen/seasonal。
 * 交互：顶部四季选择，按当前月份自动定位当令季；切换时内容 stagger 淡入。
 */
interface SeasonData {
  title: string;
  color?: string;
  element?: string;
  organ?: string;
  principle?: string;
  principle_source?: string;
  quote?: string;
  advices?: Record<string, { content: string; source: string }>;
  source?: { book?: string; volume?: string; section?: string };
}

const { rootClass } = useElder();
const SEASONS = [
  { key: "春", en: "spring", color: "#5B8C5A" },
  { key: "夏", en: "summer", color: "#C0504D" },
  { key: "秋", en: "autumn", color: "#C8A45C" },
  { key: "冬", en: "winter", color: "#34505C" },
];
const ADVICE_SEALS: Record<string, string> = { 起居: "起", 膳食: "膳", 情志: "情", 功法: "功" };

const active = ref("春");
const loading = ref(false);
const errorMsg = ref("");
const data = ref<SeasonData | null>(null);
const disclaimer = ref("");

const activeColor = computed(
  () => SEASONS.find((s) => s.key === active.value)?.color || "#C8A45C"
);
const adviceList = computed(() => {
  const a = data.value?.advices || {};
  return ["起居", "膳食", "情志", "功法"]
    .filter((k) => a[k])
    .map((k) => ({ seal: ADVICE_SEALS[k], label: k, ...a[k] }));
});

function sourceText(src?: { book?: string; volume?: string; section?: string }) {
  if (!src) return "";
  return [src.book, src.volume, src.section].filter(Boolean).join(" · ");
}

async function load(season: string) {
  active.value = season;
  loading.value = true;
  errorMsg.value = "";
  try {
    const res: any = await getSeasonalRegimen(season);
    data.value = res?.data || null;
    disclaimer.value = res?.disclaimer || "";
  } catch {
    errorMsg.value = "加载失败，请重试";
    data.value = null;
  } finally {
    loading.value = false;
  }
}

onLoad(() => {
  // 按当前月份定位当令季：3-5春 6-8夏 9-11秋 12-2冬
  const m = new Date().getMonth() + 1;
  const cur = m >= 3 && m <= 5 ? "春" : m >= 6 && m <= 8 ? "夏" : m >= 9 && m <= 11 ? "秋" : "冬";
  load(cur);
});
</script>

<template>
  <view class="seasonal" :class="rootClass">
    <gf-navbar title="四时养生" :show-back="true" />

    <scroll-view scroll-y class="seasonal__scroll">
      <!-- 季节选择 -->
      <view class="seasonal__tabs">
        <view
          v-for="s in SEASONS"
          :key="s.key"
          class="seasonal__tab"
          :class="{ active: active === s.key }"
          :style="active === s.key ? { background: s.color, borderColor: s.color } : {}"
          @tap="load(s.key)"
        >{{ s.key }}</view>
      </view>

      <!-- loading -->
      <view v-if="loading" class="seasonal__loading gf-ink-3">载入中…</view>

      <!-- error -->
      <view v-else-if="errorMsg" class="seasonal__error">
        <text class="gf-ink-2">{{ errorMsg }}</text>
        <view class="seasonal__retry gf-btn gf-btn-ghost" @tap="load(active)">重试</view>
      </view>

      <!-- content -->
      <template v-else-if="data">
        <!-- Hero -->
        <view class="seasonal__hero gf-card" :style="{ borderLeft: '8rpx solid ' + activeColor }">
          <view class="seasonal__hero-head">
            <text class="seasonal__season gf-serif" :style="{ color: activeColor }">{{ active }}</text>
            <view class="seasonal__chips">
              <text v-if="data.element" class="seasonal__chip">五行 · {{ data.element }}</text>
              <text v-if="data.organ" class="seasonal__chip">应脏 · {{ data.organ }}</text>
            </view>
          </view>
          <view v-if="data.principle" class="seasonal__principle">
            <view class="seasonal__principle-text gf-serif">{{ data.principle }}</view>
            <view v-if="data.principle_source" class="seasonal__principle-src gf-ink-3">
              —— {{ data.principle_source }}
            </view>
          </view>
          <view v-if="data.quote" class="seasonal__quote">
            <view class="seasonal__quote-seal gf-seal gf-serif">珍</view>
            <text class="seasonal__quote-text gf-serif">{{ data.quote }}</text>
          </view>
        </view>

        <view class="gf-divider" />

        <!-- 四调 -->
        <view
          v-for="(a, i) in adviceList"
          :key="a.label"
          class="seasonal__advice gf-card"
          :style="{ animationDelay: i * 0.06 + 's' }"
        >
          <view class="seasonal__advice-head">
            <view class="seasonal__advice-seal gf-seal gf-serif">{{ a.seal }}</view>
            <text class="seasonal__advice-label gf-serif">{{ a.label }}</text>
          </view>
          <view class="seasonal__advice-content">{{ a.content }}</view>
          <view v-if="a.source" class="seasonal__advice-src gf-ink-3">
            <gf-icon name="book" :size="24" color="#8A7E6A" />
            <text>{{ a.source }}</text>
          </view>
        </view>

        <view v-if="disclaimer" class="seasonal__disclaimer gf-ink-3">{{ disclaimer }}</view>
      </template>
    </scroll-view>
  </view>
</template>

<style lang="scss" scoped>
.seasonal {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;

  &__scroll {
    flex: 1;
    min-height: 0;
    padding: 16rpx 32rpx env(safe-area-inset-bottom);
    box-sizing: border-box;
  }

  &__tabs {
    display: flex;
    gap: 16rpx;
    margin: 8rpx 0 24rpx;
  }
  &__tab {
    flex: 1;
    text-align: center;
    line-height: 84rpx;
    font-family: $font-serif;
    font-size: 34rpx;
    color: $ink-2;
    background: $paper-card;
    border: 1px solid $border-paper;
    border-radius: $radius-sm;
    &.active {
      color: $paper-card;
      font-weight: 700;
    }
  }

  &__loading,
  &__error {
    text-align: center;
    padding: 80rpx 0;
    font-size: 28rpx;
  }
  &__error {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 24rpx;
  }
  &__retry {
    min-height: 80rpx;
    padding: 0 48rpx;
  }

  /* hero */
  &__hero {
    padding: 32rpx;
  }
  &__hero-head {
    display: flex;
    align-items: center;
    gap: 24rpx;
    margin-bottom: 20rpx;
  }
  &__season {
    font-size: 56rpx;
    font-weight: 700;
  }
  &__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 12rpx;
  }
  &__chip {
    padding: 6rpx 20rpx;
    font-size: 24rpx;
    color: $ink-2;
    background: $paper-sunken;
    border-radius: 999rpx;
  }
  &__principle {
    padding: 20rpx 24rpx;
    background: $paper-sunken;
    border-radius: $radius-sm;
    border-left: 4rpx solid $cinnabar;
  }
  &__principle-text {
    font-size: 30rpx;
    line-height: 1.8;
    color: $ink;
  }
  &__principle-src {
    font-size: 24rpx;
    margin-top: 10rpx;
    text-align: right;
  }
  &__quote {
    display: flex;
    align-items: flex-start;
    gap: 16rpx;
    margin-top: 20rpx;
  }
  &__quote-seal {
    width: 52rpx;
    height: 52rpx;
    font-size: 28rpx;
  }
  &__quote-text {
    flex: 1;
    font-size: 28rpx;
    line-height: 1.7;
    color: $cinnabar;
  }

  /* advice */
  &__advice {
    padding: 28rpx;
    margin-bottom: 20rpx;
    opacity: 0;
    transform: translateY(14rpx);
    animation: seaIn 0.4s ease forwards;
  }
  &__advice-head {
    display: flex;
    align-items: center;
    gap: 16rpx;
    margin-bottom: 14rpx;
  }
  &__advice-seal {
    width: 56rpx;
    height: 56rpx;
    font-size: 30rpx;
    background: $gold;
    color: $ink;
  }
  &__advice-label {
    font-size: 34rpx;
    font-weight: 700;
    color: $ink;
  }
  &__advice-content {
    font-size: 30rpx;
    line-height: 1.75;
    color: $ink;
  }
  &__advice-src {
    display: flex;
    align-items: center;
    gap: 8rpx;
    font-size: 24rpx;
    margin-top: 16rpx;
    padding-top: 14rpx;
    border-top: 1px dashed $border-paper;
  }

  &__disclaimer {
    font-size: 24rpx;
    line-height: 1.6;
    text-align: center;
    padding: 24rpx 24rpx 32rpx;
  }
}

@keyframes seaIn {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
@media (prefers-reduced-motion: reduce) {
  .seasonal__advice {
    animation: none;
    opacity: 1;
    transform: none;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .seasonal__scroll { padding: 24rpx 40rpx env(safe-area-inset-bottom); }

  .seasonal__tabs { gap: 24rpx; margin: 16rpx 0 36rpx; }
  .seasonal__tab { line-height: 116rpx; font-size: var(--gf-fs-nav); border-radius: $radius; }

  .seasonal__loading,
  .seasonal__error { padding: 100rpx 0; font-size: var(--gf-fs-base); }
  .seasonal__error { gap: 36rpx; }
  .seasonal__retry { min-height: 116rpx; padding: 0 64rpx; }

  .seasonal__hero { padding: 44rpx; }
  .seasonal__hero-head { gap: 32rpx; margin-bottom: 32rpx; }
  .seasonal__season { font-size: 76rpx; }
  .seasonal__chips { gap: 20rpx; }
  .seasonal__chip { padding: 12rpx 32rpx; font-size: var(--gf-fs-sm); }
  .seasonal__principle { padding: 32rpx 36rpx; border-left-width: 6rpx; }
  .seasonal__principle-text { font-size: var(--gf-fs-lg); line-height: var(--gf-lh); }
  .seasonal__principle-src { font-size: var(--gf-fs-sm); margin-top: 16rpx; }
  .seasonal__quote { gap: 24rpx; margin-top: 32rpx; }
  .seasonal__quote-seal { width: 80rpx; height: 80rpx; font-size: var(--gf-fs-base); }
  .seasonal__quote-text { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }

  .seasonal__advice { padding: 40rpx; margin-bottom: 32rpx; }
  .seasonal__advice-head { gap: 24rpx; margin-bottom: 24rpx; }
  .seasonal__advice-seal { width: 84rpx; height: 84rpx; font-size: var(--gf-fs-lg); }
  .seasonal__advice-label { font-size: var(--gf-fs-lg); }
  .seasonal__advice-content { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }
  .seasonal__advice-src { font-size: var(--gf-fs-sm); margin-top: 24rpx; padding-top: 22rpx; }

  .seasonal__disclaimer { font-size: var(--gf-fs-sm); padding: 36rpx 36rpx 48rpx; }
}
</style>
