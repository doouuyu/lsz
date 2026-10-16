---
name: elder-mode-css
description: 老年模式（大字模式）的 CSS 架构与 WXSS 嵌套 var 的坑
metadata:
  type: project
---

移动端「老年模式」= 两套独立 CSS，不是变量缩放。

- 状态：`stores/settings.ts`（Pinia，elderMode 持久化）+ `composables/useElder.ts` 暴露 `rootClass`；每个**页面根 view** 绑 `:class="rootClass"`，开启时注入 `.gf-elder`。开关只在首页一处大卡片（`home__elder`）。
- 字号 token 在 `styles/global.scss`：常规值挂 `page`，老年值挂 `.gf-elder` 直接给**具体数**（--gf-fs-sm/base/lg/title/nav、--gf-lh）。`.gf-elder` 还重设自身 font-size/line-height，让未显式设字号的文本也放大。
- 各页/组件的老年差异写成 scoped `<style>` 末尾的扁平块 `.gf-elder { .组件类 { ... } }`（完整类名、不用 `&`）。Vue scoped 下后代选择器对本组件元素有效；子组件也能命中，因为 `.gf-elder` 在祖先页面根。正常模式规则一律不动。
- 弹窗能继承：项目所有 `wd-popup` 都未启用 `root-portal`，内联在页面根内，故 `.gf-elder` 的 token 继承得到。

**关键坑（踩过两次）**：绝不要写 `--gf-fs-base: calc(32rpx * var(--gf-scale))` 这种「自定义属性里再嵌 var()」的两层引用——部分小程序 WXSS 不会对其逐元素重求值，老年模式整体失效。token 一律用单层具体值。

**已知无关红点**：`dx-intake.vue` 用 uni 条件编译 `#ifdef MP-WEIXIN` 在两分支各 `const itemList`，`vue-tsc` 不识别 #ifdef 会误报 TS2451；实际各平台只保留一支，`build:h5` 正常。验证 SCSS 是否编译用 `npm run build:h5`（vite 走 #ifdef），不要只看 vue-tsc。
