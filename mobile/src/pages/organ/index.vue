<script setup lang="ts">
import { ref, computed } from "vue";
import { useElder } from "@/composables/useElder";
import { onLoad } from "@dcloudio/uni-app";
import { getOrganRegimen } from "@/api";

/**
 * 五脏调养（宣纸面 · 适老平铺）。接 GET /regimen/organ。
 */
interface NamedItem {
  name: string;
  desc: string;
  source?: string;
}
interface OrganData {
  title: string;
  color?: string;
  element?: string;
  function?: string;
  quote?: string;
  quote_source?: string;
  diet?: NamedItem[];
  herbal?: NamedItem[];
  herbs?: string[];
  solar_term?: { content: string; source: string };
}

// 五行正色
const { rootClass } = useElder();
const ORGANS = [
  { key: "心", color: "#C0504D" },
  { key: "肝", color: "#5B8C5A" },
  { key: "脾", color: "#C8A45C" },
  { key: "肺", color: "#34505C" },
  { key: "肾", color: "#1F3A5F" },
];

const active = ref("心");
const loading = ref(false);
const errorMsg = ref("");
const data = ref<OrganData | null>(null);
const disclaimer = ref("");

const activeColor = computed(() => ORGANS.find((o) => o.key === active.value)?.color || "#C0504D");

async function load(organ: string) {
  active.value = organ;
  loading.value = true;
  errorMsg.value = "";
  try {
    const res: any = await getOrganRegimen(organ);
    data.value = res?.data || null;
    disclaimer.value = res?.disclaimer || "";
  } catch {
    errorMsg.value = "加载失败，请重试";
    data.value = null;
  } finally {
    loading.value = false;
  }
}

onLoad(() => load("心"));
</script>

<template>
  <view class="organ" :class="rootClass">
    <gf-navbar title="五脏调养" :show-back="true" />

    <scroll-view scroll-y class="organ__scroll">
      <!-- 五脏选择 -->
      <view class="organ__tabs">
        <view
          v-for="o in ORGANS"
          :key="o.key"
          class="organ__tab"
          :class="{ active: active === o.key }"
          :style="active === o.key ? { background: o.color, borderColor: o.color } : {}"
          @tap="load(o.key)"
        >{{ o.key }}</view>
      </view>

      <view v-if="loading" class="organ__loading gf-ink-3">载入中…</view>
      <view v-else-if="errorMsg" class="organ__error">
        <text class="gf-ink-2">{{ errorMsg }}</text>
        <view class="organ__retry gf-btn gf-btn-ghost" @tap="load(active)">重试</view>
      </view>

      <template v-else-if="data">
        <!-- Hero -->
        <view class="organ__hero gf-card" :style="{ borderLeft: '8rpx solid ' + activeColor }">
          <view class="organ__hero-head">
            <text class="organ__name gf-serif" :style="{ color: activeColor }">{{ active }}</text>
            <text v-if="data.element" class="organ__chip">五行 · {{ data.element }}</text>
          </view>
          <view v-if="data.function" class="organ__function">{{ data.function }}</view>
          <view v-if="data.quote" class="organ__quote">
            <view class="organ__quote-text gf-serif">{{ data.quote }}</view>
            <view v-if="data.quote_source" class="organ__quote-src gf-ink-3">—— {{ data.quote_source }}</view>
          </view>
        </view>

        <view class="gf-divider" />

        <!-- 食疗 -->
        <view v-if="data.diet && data.diet.length" class="organ__section">
          <view class="organ__sec-head">
            <view class="organ__sec-seal gf-seal gf-serif">食</view>
            <text class="organ__sec-title gf-serif">食疗食养</text>
          </view>
          <view v-for="(d, i) in data.diet" :key="i" class="organ__item gf-card">
            <view class="organ__item-name gf-serif">{{ d.name }}</view>
            <view class="organ__item-desc">{{ d.desc }}</view>
            <view v-if="d.source" class="organ__item-src gf-ink-3">
              <gf-icon name="book" :size="24" color="#8A7E6A" /><text>{{ d.source }}</text>
            </view>
          </view>
        </view>

        <!-- 药膳 -->
        <view v-if="data.herbal && data.herbal.length" class="organ__section">
          <view class="organ__sec-head">
            <view class="organ__sec-seal gf-seal gf-serif">膳</view>
            <text class="organ__sec-title gf-serif">药膳方</text>
          </view>
          <view v-for="(d, i) in data.herbal" :key="i" class="organ__item gf-card">
            <view class="organ__item-name gf-serif">{{ d.name }}</view>
            <view class="organ__item-desc">{{ d.desc }}</view>
            <view v-if="d.source" class="organ__item-src gf-ink-3">
              <gf-icon name="book" :size="24" color="#8A7E6A" /><text>{{ d.source }}</text>
            </view>
          </view>
        </view>

        <!-- 常用药材 -->
        <view v-if="data.herbs && data.herbs.length" class="organ__section">
          <view class="organ__sec-head">
            <view class="organ__sec-seal gf-seal gf-serif">药</view>
            <text class="organ__sec-title gf-serif">常用药材</text>
          </view>
          <view class="organ__herbs">
            <text v-for="(h, i) in data.herbs" :key="i" class="organ__herb">{{ h }}</text>
          </view>
        </view>

        <!-- 节气养生 -->
        <view v-if="data.solar_term && data.solar_term.content" class="organ__section">
          <view class="organ__sec-head">
            <view class="organ__sec-seal gf-seal gf-serif">节</view>
            <text class="organ__sec-title gf-serif">节气养生</text>
          </view>
          <view class="organ__item gf-card">
            <view class="organ__item-desc">{{ data.solar_term.content }}</view>
            <view v-if="data.solar_term.source" class="organ__item-src gf-ink-3">
              <gf-icon name="book" :size="24" color="#8A7E6A" /><text>{{ data.solar_term.source }}</text>
            </view>
          </view>
        </view>

        <view v-if="disclaimer" class="organ__disclaimer gf-ink-3">{{ disclaimer }}</view>
      </template>
    </scroll-view>
  </view>
</template>

<style lang="scss" scoped>
.organ {
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
    gap: 12rpx;
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

  &__hero {
    padding: 32rpx;
  }
  &__hero-head {
    display: flex;
    align-items: center;
    gap: 24rpx;
    margin-bottom: 16rpx;
  }
  &__name {
    font-size: 56rpx;
    font-weight: 700;
  }
  &__chip {
    padding: 6rpx 20rpx;
    font-size: 24rpx;
    color: $ink-2;
    background: $paper-sunken;
    border-radius: 999rpx;
  }
  &__function {
    font-size: 30rpx;
    line-height: 1.75;
    color: $ink;
  }
  &__quote {
    margin-top: 20rpx;
    padding: 20rpx 24rpx;
    background: $paper-sunken;
    border-radius: $radius-sm;
    border-left: 4rpx solid $cinnabar;
  }
  &__quote-text {
    font-size: 28rpx;
    line-height: 1.7;
    color: $cinnabar;
  }
  &__quote-src {
    font-size: 24rpx;
    margin-top: 10rpx;
    text-align: right;
  }

  &__section {
    margin-top: 28rpx;
  }
  &__sec-head {
    display: flex;
    align-items: center;
    gap: 16rpx;
    margin-bottom: 16rpx;
  }
  &__sec-seal {
    width: 56rpx;
    height: 56rpx;
    font-size: 30rpx;
  }
  &__sec-title {
    font-size: 34rpx;
    font-weight: 700;
    color: $ink;
  }
  &__item {
    padding: 24rpx 28rpx;
    margin-bottom: 16rpx;
  }
  &__item-name {
    font-size: 32rpx;
    font-weight: 700;
    color: $cinnabar;
    margin-bottom: 8rpx;
  }
  &__item-desc {
    font-size: 30rpx;
    line-height: 1.7;
    color: $ink;
  }
  &__item-src {
    display: flex;
    align-items: center;
    gap: 8rpx;
    font-size: 24rpx;
    margin-top: 14rpx;
    padding-top: 12rpx;
    border-top: 1px dashed $border-paper;
  }
  &__herbs {
    display: flex;
    flex-wrap: wrap;
    gap: 16rpx;
  }
  &__herb {
    padding: 14rpx 28rpx;
    background: $paper-card;
    border: 1px solid $gold-soft;
    border-radius: 999rpx;
    font-size: 30rpx;
    color: $ink;
  }

  &__disclaimer {
    font-size: 24rpx;
    line-height: 1.6;
    text-align: center;
    padding: 32rpx 24rpx;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  .organ__scroll { padding: 24rpx 36rpx env(safe-area-inset-bottom); }

  .organ__tabs { gap: 20rpx; margin: 16rpx 0 36rpx; }
  .organ__tab { line-height: 116rpx; font-size: var(--gf-fs-lg); border-radius: 16rpx; }

  .organ__loading { font-size: var(--gf-fs-base); padding: 100rpx 0; }
  .organ__error { font-size: var(--gf-fs-base); padding: 100rpx 0; gap: 32rpx; }
  .organ__retry { min-height: 116rpx; padding: 0 60rpx; }

  .organ__hero { padding: 44rpx; }
  .organ__hero-head { gap: 32rpx; margin-bottom: 24rpx; }
  .organ__name { font-size: 76rpx; }
  .organ__chip { padding: 12rpx 30rpx; font-size: var(--gf-fs-sm); }
  .organ__function { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }
  .organ__quote { margin-top: 28rpx; padding: 28rpx 32rpx; }
  .organ__quote-text { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }
  .organ__quote-src { font-size: var(--gf-fs-sm); margin-top: 16rpx; }

  .organ__section { margin-top: 40rpx; }
  .organ__sec-head { gap: 24rpx; margin-bottom: 24rpx; }
  .organ__sec-seal { width: 80rpx; height: 80rpx; font-size: var(--gf-fs-base); }
  .organ__sec-title { font-size: var(--gf-fs-title); }

  .organ__item { padding: 36rpx 40rpx; margin-bottom: 24rpx; }
  .organ__item-name { font-size: var(--gf-fs-lg); margin-bottom: 14rpx; }
  .organ__item-desc { font-size: var(--gf-fs-base); line-height: var(--gf-lh); }
  .organ__item-src { font-size: var(--gf-fs-sm); margin-top: 22rpx; padding-top: 18rpx; gap: 14rpx; }

  .organ__herbs { gap: 24rpx; }
  .organ__herb { padding: 22rpx 40rpx; font-size: var(--gf-fs-base); min-height: 112rpx; box-sizing: border-box; display: flex; align-items: center; }

  .organ__disclaimer { font-size: var(--gf-fs-sm); line-height: var(--gf-lh); padding: 44rpx 32rpx; }
}
</style>
