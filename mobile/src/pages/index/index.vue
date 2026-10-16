<script setup lang="ts">
/**
 * 首页 · 模块入口（脚手架）。
 * 本轮仅「仿真辨证」可进入，其余四大模块占位（disabled）。
 */
import { useElder } from "@/composables/useElder";

const { elderMode, rootClass, toggleElderMode } = useElder();

interface ModuleItem {
  key: string;
  icon: string;
  title: string;
  desc: string;
  url?: string;
  enabled: boolean;
}

const modules: ModuleItem[] = [
  {
    key: "diagnose",
    icon: "diagnose",
    title: "仿真辨证",
    desc: "望闻问切 · 一问一答",
    url: "/pages/diagnose/index",
    enabled: true,
  },
  {
    key: "seasonal",
    icon: "seasonal",
    title: "四时养生",
    desc: "随节气调摄",
    url: "/pages/seasonal/index",
    enabled: true,
  },
  {
    key: "organ",
    icon: "organ",
    title: "五脏调养",
    desc: "脏腑辨调",
    url: "/pages/organ/index",
    enabled: true,
  },
  {
    key: "chronic",
    icon: "chronic",
    title: "慢病助手",
    desc: "适老 · 大字",
    url: "/pages/chronic/index",
    enabled: true,
  },
  {
    key: "knowledge",
    icon: "knowledge",
    title: "知识检索",
    desc: "病证治方药",
    url: "/pages/knowledge/index",
    enabled: true,
  },
];

function openModule(m: ModuleItem) {
  if (!m.enabled || !m.url) {
    uni.showToast({ title: "该模块后续上线", icon: "none" });
    return;
  }
  uni.navigateTo({ url: m.url });
}
</script>

<template>
  <view class="home" :class="rootClass">
    <gf-navbar title="李时珍智能医师" />

    <!-- 头部：印章 + 主副标题 -->
    <view class="home__hero">
      <view class="home__seal gf-seal gf-serif">李</view>
      <view class="home__hero-text">
        <view class="gf-page-title">李时珍智能医师</view>
        <view class="gf-page-subtitle">本草纲目 · 智能辨证助手</view>
      </view>
    </view>

    <!-- 老年模式（大字）总开关：首页一处大开关，全局生效 -->
    <view
      class="home__elder"
      :class="{ 'is-on': elderMode }"
      hover-class="home__elder--hover"
      :hover-stay-time="80"
      @tap="toggleElderMode"
    >
      <view class="home__elder-main">
        <view class="home__elder-title gf-serif">大字模式</view>
        <view class="home__elder-desc">放大字体，看得更清楚{{ elderMode ? "（已开启 · 自动朗读结果）" : "" }}</view>
      </view>
      <view class="home__elder-switch" :class="{ 'is-on': elderMode }">
        <view class="home__elder-knob" />
      </view>
    </view>

    <view class="gf-divider" />

    <!-- 模块网格 -->
    <view class="home__grid">
      <view
        v-for="m in modules"
        :key="m.key"
        class="home__cell gf-card"
        :class="{ 'is-disabled': !m.enabled }"
        hover-class="home__cell--hover"
        :hover-stay-time="80"
        @tap="openModule(m)"
      >
        <view class="home__cell-icon">
          <gf-icon :name="m.icon" :size="56" :color="m.enabled ? '#9A2D2D' : '#8A7E6A'" />
        </view>
        <view class="home__cell-title gf-serif">{{ m.title }}</view>
        <view class="home__cell-desc gf-ink-3">{{ m.desc }}</view>
        <view v-if="!m.enabled" class="home__cell-badge">敬请期待</view>
      </view>
    </view>

    <!-- 免责声明（医疗合规红线） -->
    <view class="home__disclaimer gf-ink-3">
      本应用内容由人工智能生成，仅供参考，不构成诊疗依据，请遵医嘱。
    </view>
  </view>
</template>

<style lang="scss" scoped>
.home {
  min-height: 100vh;
  padding-bottom: 48rpx;

  &__hero {
    display: flex;
    align-items: center;
    gap: 24rpx;
    padding: 24rpx 32rpx 8rpx;
  }
  &__seal {
    width: 88rpx;
    height: 88rpx;
    font-size: 48rpx;
  }

  /* 大字模式总开关 */
  &__elder {
    display: flex;
    align-items: center;
    gap: 24rpx;
    margin: 12rpx 32rpx 4rpx;
    padding: 24rpx 28rpx;
    background: $paper-card;
    border: 1px solid $border-paper;
    border-radius: $radius;
    box-shadow: $shadow;

    &.is-on {
      border-color: $gold-soft;
      background: linear-gradient(180deg, #FBF7EE, #F6EFDD);
    }
    &--hover {
      transform: translateY(-2rpx);
    }
  }
  &__elder-main {
    flex: 1;
    min-width: 0;
  }
  &__elder-title {
    font-size: var(--gf-fs-lg);
    font-weight: 700;
    color: $ink;
  }
  &__elder-desc {
    font-size: var(--gf-fs-sm);
    color: $ink-2;
    margin-top: 4rpx;
  }
  &__elder-switch {
    flex-shrink: 0;
    width: 96rpx;
    height: 56rpx;
    border-radius: 999rpx;
    background: $paper-sunken;
    border: 1px solid $border-paper;
    padding: 4rpx;
    box-sizing: border-box;
    transition: background 0.2s ease;

    &.is-on {
      background: $cinnabar;
      border-color: $cinnabar;
    }
  }
  &__elder-knob {
    width: 46rpx;
    height: 46rpx;
    border-radius: 50%;
    background: $paper-card;
    box-shadow: 0 2rpx 8rpx rgba(31, 27, 22, 0.25);
    transition: transform 0.2s ease;
    .home__elder-switch.is-on & {
      transform: translateX(40rpx);
    }
  }

  &__grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24rpx;
    padding: 8rpx 32rpx;
  }
  &__cell {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 10rpx;
    padding: 32rpx 28rpx;

    &--hover {
      transform: translateY(-2rpx);
    }
    &.is-disabled {
      opacity: 0.62;
    }
  }
  &__cell-icon {
    width: 84rpx;
    height: 84rpx;
    border-radius: 20rpx;
    background: $paper-sunken;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 6rpx;
  }
  &__cell-title {
    font-size: var(--gf-fs-lg);
    font-weight: 700;
    color: $ink;
  }
  &__cell-desc {
    font-size: var(--gf-fs-sm);
  }
  &__cell-badge {
    position: absolute;
    top: 20rpx;
    right: 20rpx;
    font-size: 22rpx;
    color: $gold;
    border: 1px solid $gold-soft;
    border-radius: 999rpx;
    padding: 2rpx 14rpx;
  }

  &__disclaimer {
    font-size: 24rpx;
    line-height: 1.6;
    text-align: center;
    padding: 32rpx 48rpx 48rpx;
  }
}

/* ===== 老年模式 ===== */
.gf-elder {
  /* 头部印章放大 */
  .home__seal {
    width: 116rpx;
    height: 116rpx;
    font-size: var(--gf-fs-title);
  }

  /* 大字开关卡片：放大内边距与点击区 */
  .home__elder {
    gap: 32rpx;
    padding: 36rpx 36rpx;
  }
  .home__elder-desc {
    margin-top: 10rpx;
  }
  /* 开关滑块同比放大，触控更友好 */
  .home__elder-switch {
    width: 132rpx;
    height: 76rpx;
    padding: 6rpx;
  }
  .home__elder-knob {
    width: 62rpx;
    height: 62rpx;
  }
  .home__elder-switch.is-on .home__elder-knob {
    transform: translateX(56rpx);
  }

  /* 模块网格改单列、更宽松 */
  .home__grid {
    grid-template-columns: 1fr;
    gap: 28rpx;
  }
  .home__cell {
    gap: 16rpx;
    padding: 40rpx 36rpx;
    min-height: 160rpx;
  }
  /* 图标容器放大 */
  .home__cell-icon {
    width: 120rpx;
    height: 120rpx;
    border-radius: 28rpx;
    margin-bottom: 10rpx;
  }
  /* 占位徽标字号放大（原 22rpx 硬编码） */
  .home__cell-badge {
    font-size: var(--gf-fs-sm);
    padding: 6rpx 22rpx;
    top: 28rpx;
    right: 28rpx;
  }

  /* 免责声明字号放大（原 24rpx 硬编码） */
  .home__disclaimer {
    font-size: var(--gf-fs-sm);
    padding: 40rpx 48rpx 56rpx;
  }
}
</style>
