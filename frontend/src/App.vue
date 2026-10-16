<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import GfIcon from './components/GfIcon.vue'

const router = useRouter()
const route = useRoute()

const navItems = [
  { path: '/', label: '首页', icon: 'home' },
  { path: '/diagnose', label: '仿真辨证', icon: 'diagnose' },
  { path: '/regimen/seasonal', label: '四时养生', icon: 'seasonal' },
  { path: '/regimen/organ', label: '五脏调养', icon: 'organ' },
  { path: '/chronic', label: '慢病助手', icon: 'chronic' },
  { path: '/knowledge', label: '知识图谱', icon: 'knowledge' },
  { path: '/knowledge/overview', label: '知识库评估', icon: 'report' },
]
</script>

<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-left" @click="router.push('/')">
        <span class="logo-seal">時</span>
        <span class="logo-text">李时珍智能医师</span>
      </div>

      <el-menu
        :default-active="route.path"
        mode="horizontal"
        :ellipsis="false"
        class="nav-menu"
        router
      >
        <el-menu-item
          v-for="item in navItems"
          :key="item.path"
          :index="item.path"
        >
          <GfIcon :name="item.icon" :size="18" class="nav-icon" />
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>

    </el-header>

    <el-main class="app-main">
      <div class="app-main-inner">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </el-main>

    <el-footer class="app-footer">
      <span>李时珍智能医师 · 湖北时珍实验室 · 基于检索增强生成技术 ｜ 本系统为学术研究与辅助参考，不替代执业医师诊断</span>
    </el-footer>
  </el-container>
</template>

<style scoped>
.app-container {
  /* 撑满固定高度的 #app，自身为纵向 flex（含 header/main/footer 时由 el-container 自动设定） */
  height: 100%;
  overflow: hidden;
}

.app-header {
  display: flex;
  align-items: center;
  background: linear-gradient(180deg, #244568 0%, var(--navy) 100%);
  color: var(--on-navy);
  padding: 0 24px;
  height: var(--header-h);
  flex-shrink: 0;
  z-index: 100;
  box-shadow: 0 2px 12px rgba(11, 22, 38, 0.35);
  border-bottom: 1px solid rgba(200, 164, 92, 0.35);
}

.header-left {
  cursor: pointer;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 6px;
  background: var(--cinnabar);
  color: #FBF7EE;
  font-family: var(--font-serif);
  font-weight: 700;
  font-size: 18px;
  box-shadow: inset 0 0 0 1px rgba(251, 247, 238, 0.4);
}

.logo-text {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 700;
  color: var(--gold);
  letter-spacing: 3px;
}

.nav-menu {
  flex: 1;
  background: transparent;
  border-bottom: none;
  margin-left: 32px;
}

.nav-menu .el-menu-item {
  color: rgba(234, 240, 246, 0.78);
  border-bottom: none;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.nav-icon { color: inherit; }

.nav-menu .el-menu-item:hover,
.nav-menu .el-menu-item.is-active {
  color: var(--gold);
  background: rgba(200, 164, 92, 0.12);
  border-bottom: 2px solid var(--gold);
}

.header-right {
  flex-shrink: 0;
  margin-left: 16px;
}

/* 唯一的纵向滚动容器：内容溢出时仅此处滚动 */
.app-main {
  flex: 1;
  min-height: 0;
  width: 100%;
  padding: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
}

/* 内层为纵向 flex 列，高度被约束为可视区域：
   - 全高页面（如辨证页）可用 flex:1 取得确定高度，使左右面板各自在内容区滚动，互不牵连
   - 普通文档页内容超高时，溢出冒泡到 .app-main 由其滚动 */
.app-main-inner {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
  padding: 28px 24px;
}

.app-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--ink-2);
  font-size: 12px;
  border-top: 1px solid var(--border-paper);
  background: var(--paper-card);
  min-height: var(--footer-h);
  height: auto;
  flex-shrink: 0;
  padding: 6px 24px;
  line-height: 1.5;
}

@media (max-width: 768px) {
  .app-header { padding: 0 12px; height: 56px; }
  .logo-text { font-size: 16px; letter-spacing: 1px; }
  .nav-menu { margin-left: 8px; }
  .nav-menu .el-menu-item span { display: none; }
}
</style>
