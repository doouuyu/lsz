import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/Dashboard.vue'),
    },
    {
      path: '/diagnose',
      name: 'diagnose',
      component: () => import('../views/Diagnose.vue'),
    },
    {
      path: '/regimen/seasonal',
      name: 'seasonal',
      component: () => import('../views/SeasonalRegimen.vue'),
    },
    {
      path: '/regimen/organ',
      name: 'organ',
      component: () => import('../views/OrganRegimen.vue'),
    },
    {
      path: '/chronic',
      name: 'chronic',
      component: () => import('../views/ChronicDisease.vue'),
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('../views/KnowledgeGraph.vue'),
    },
    {
      path: '/knowledge/overview',
      name: 'knowledge-overview',
      component: () => import('../views/KnowledgeOverview.vue'),
    },
  ],
})

export default router
