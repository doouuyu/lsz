<script setup lang="ts">
import { computed } from "vue";

/**
 * 古籍风自定义导航栏。
 * 页面使用 navigationStyle:custom，由本组件接管状态栏占位 + 标题 + 返回。
 * surface: paper（宣纸面，默认）/ navy（藏青面，用于深色页头）。
 */
const props = withDefaults(
  defineProps<{
    title?: string;
    showBack?: boolean;
    surface?: "paper" | "navy";
    /** 拦截返回：开启后点返回只 emit('back')，由页面自行处理（如二次确认/分阶段退出） */
    customBack?: boolean;
  }>(),
  { title: "", showBack: false, surface: "paper", customBack: false }
);

const emit = defineEmits<{ (e: "back"): void }>();

// 布局对齐系统胶囊（微信规范），同时让返回键做成左侧「镜像胶囊」与之呼应：
//  - barHeight = (胶囊上边距 - 状态栏) * 2 + 胶囊高度，整栏与胶囊垂直居中对齐
//  - capSize/sideGap = 胶囊高度/其距屏幕右缘的间隙，镜像到左侧作为返回键的尺寸与边距
//  - rightInset = 胶囊占位宽（windowWidth - 胶囊左缘），标题两侧各让出该值保证真居中
// 非小程序端无胶囊，回退 44px 标准栏。
const layout = computed(() => {
  let statusBar = 20;
  let barHeight = 44;
  let capSize = 32;
  let sideGap = 10;
  let rightInset = 50;
  try {
    const win = uni.getWindowInfo();
    statusBar = win.statusBarHeight || 20;
    const getMenu = (uni as any).getMenuButtonBoundingClientRect;
    if (typeof getMenu === "function") {
      const menu = getMenu();
      if (menu && menu.height && menu.top >= statusBar) {
        barHeight = (menu.top - statusBar) * 2 + menu.height;
        capSize = menu.height;
        sideGap = Math.max(win.windowWidth - menu.right, 6);
        rightInset = win.windowWidth - menu.left + 8;
      }
    }
  } catch {
    /* 取窗口信息失败时用默认值 */
  }
  return { statusBar, barHeight, capSize, sideGap, rightInset };
});

const isNavy = computed(() => props.surface === "navy");
const iconColor = computed(() => (isNavy.value ? "#EAF0F6" : "#1F1B16"));

function onBack() {
  if (props.customBack) {
    emit("back");
    return;
  }
  const pages = getCurrentPages();
  if (pages.length > 1) uni.navigateBack();
  else uni.switchTab?.({ url: "/pages/index/index" });
}
</script>

<template>
  <view class="gf-navbar" :class="{ 'is-navy': isNavy }">
    <view :style="{ height: layout.statusBar + 'px' }" />
    <view class="gf-navbar__bar" :style="{ height: layout.barHeight + 'px' }">
      <view
        v-if="showBack"
        class="gf-navbar__back"
        :style="{
          width: layout.capSize + 'px',
          height: layout.capSize + 'px',
          left: layout.sideGap + 'px',
        }"
        hover-class="gf-navbar__back--hover"
        :hover-stay-time="60"
        @tap="onBack"
      >
        <gf-icon name="back" :size="36" :color="iconColor" />
      </view>
      <view
        class="gf-navbar__title gf-serif"
        :style="{ maxWidth: `calc(100% - ${layout.rightInset * 2}px)` }"
      >{{ title }}</view>
      <view class="gf-navbar__right" :style="{ right: layout.rightInset + 'px' }">
        <slot name="right" />
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.gf-navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: $paper;

  &.is-navy {
    background: $navy-2;
    .gf-navbar__title {
      color: $on-navy;
    }
    .gf-navbar__back {
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.18);
    }
  }

  &__bar {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
  }

  // 镜像系统胶囊的圆形返回键：同高、同边距、同样的描边+半透底
  &__back {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.55);
    border: 1rpx solid $border-paper;
    box-sizing: border-box;

    &--hover {
      background: $paper-sunken;
    }
  }

  &__title {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--gf-fs-nav);
    font-weight: 700;
    color: $ink;
    letter-spacing: 1rpx;
  }

  &__right {
    position: absolute;
    right: 16rpx;
    display: flex;
    align-items: center;
    min-height: 64rpx;
  }
}
</style>
