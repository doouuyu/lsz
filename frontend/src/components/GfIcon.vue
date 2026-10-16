<script setup lang="ts">
import { computed } from 'vue'

/**
 * 国风细线条 SVG 图标集
 * 统一 viewBox 24、stroke=currentColor、stroke-width 1.5、圆角端点。
 * 严禁使用 emoji —— 所有图标均从此处取用。
 */
const props = withDefaults(defineProps<{
  name: string
  size?: number | string
}>(), { size: 24 })

const icons: Record<string, string> = {
  // —— 五大模块 ——
  // 仿真辨证：诊脉脉象波形
  diagnose: '<path d="M2 13h4l2-6 3 11 2.5-7H22"/>',
  // 四时养生：四时轮盘
  seasonal: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/><circle cx="12" cy="12" r="2"/>',
  // 五脏调养：心
  organ: '<path d="M12 20s-7-4.4-9.4-8.8C1.1 8 2.6 4.6 6 4.6c2 0 3.2 1.2 4 2.4.8-1.2 2-2.4 4-2.4 3.4 0 4.9 3.4 3.4 6.6C19 15.6 12 20 12 20z"/>',
  // 慢病助手：医录夹 + 脉线
  chronic: '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4.5V3h6v1.5"/><path d="M8 13h2l1.5-3 1.5 5 1-2h2"/>',
  // 知识图谱：关系节点
  knowledge: '<circle cx="12" cy="12" r="2.5"/><circle cx="6" cy="7" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="17.5" cy="18" r="2"/><circle cx="6.5" cy="17.5" r="2"/><path d="M7.6 8.4l2.6 2.6M16.2 7.4l-2.6 2.6M15.9 16.4l-2.5-2.5M8 16.2l2.2-2.2"/>',

  // —— 首页架构层 ——
  // 经典文献：典籍
  book: '<path d="M4 5c0-1 .9-1.6 2-1.6h5V20H6c-1.1 0-2 .6-2 1.5zM20 5c0-1-.9-1.6-2-1.6h-5V20h5c1.1 0 2 .6 2 1.5z"/><path d="M11 3.4V20M13 3.4V20"/>',
  // 向量化：嵌入矩阵
  vector: '<rect x="3.5" y="3.5" width="17" height="17" rx="2"/><circle cx="8" cy="8" r="1.1"/><circle cx="12" cy="8" r="1.1"/><circle cx="16" cy="8" r="1.1"/><circle cx="8" cy="12" r="1.1"/><circle cx="12" cy="12" r="1.1"/><circle cx="16" cy="12" r="1.1"/><circle cx="8" cy="16" r="1.1"/><circle cx="12" cy="16" r="1.1"/><circle cx="16" cy="16" r="1.1"/>',
  // RAG引擎：检索增强
  engine: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4-4"/><path d="M11 8.4v5.2M8.4 11h5.2"/>',
  // 辨证输出：结构化文档
  output: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M9 12h6M9 15h6M9 18h3.5"/>',

  // —— 导航与通用 ——
  home: '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M2.2 11h19.6"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="M20.5 20.5L16 16"/>',
  report: '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/><path d="M12 11v6M9.5 14.5L12 17l2.5-2.5"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"/>',
  camera: '<rect x="3" y="7" width="18" height="13" rx="2"/><circle cx="12" cy="13.5" r="3.5"/><path d="M8 7l1.5-2.5h5L16 7"/>',
  send: '<path d="M4 12L20 4l-6 16-2.5-6.5z"/><path d="M11.5 13.5L20 4"/>',
  back: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  close: '<path d="M6 6l12 12M18 6L6 18"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 6.5"/>',
}

const inner = computed(() => icons[props.name] ?? icons.knowledge)
const dim = computed(() => typeof props.size === 'number' ? `${props.size}px` : props.size)
</script>

<template>
  <svg
    :width="dim"
    :height="dim"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    class="gf-icon"
    v-html="inner"
  />
</template>

<style scoped>
.gf-icon {
  display: inline-block;
  vertical-align: middle;
  flex-shrink: 0;
}
</style>
