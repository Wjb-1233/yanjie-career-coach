import { createRouter, createWebHistory } from 'vue-router'

import { useAuth } from '@/composables/useAuth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true } },
    { path: '/', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
    { path: '/scenes', name: 'scenes', component: () => import('@/views/ScenesView.vue') },
    { path: '/scripts', name: 'scripts', component: () => import('@/views/ScriptStudioView.vue') },
    { path: '/favorites', name: 'favorites', component: () => import('@/views/FavoritesView.vue') },
    { path: '/history', name: 'training-history', component: () => import('@/views/TrainingHistoryView.vue') },
    { path: '/profile', name: 'profile', component: () => import('@/views/ProfileView.vue') },
    { path: '/training/:id', name: 'training', component: () => import('@/views/TrainingView.vue') },
    { path: '/report/:id', name: 'report', component: () => import('@/views/ReportView.vue') },
    { path: '/courses', name: 'courses', component: () => import('@/views/CoursesView.vue') },
    { path: '/legacy-lesson', name: 'legacy-lesson', component: () => import('@/views/LegacyLessonView.vue') },
    { path: '/plans', name: 'training-plans', component: () => import('@/views/TrainingPlansView.vue') },
    { path: '/plans/:id', name: 'training-plan', component: () => import('@/views/TrainingPlanView.vue') },
    { path: '/admin', name: 'admin', component: () => import('@/views/AdminView.vue'), meta: { admin: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuth()
  if (!auth.initialized.value) await auth.restore()
  if (to.meta.public) return auth.user.value ? { name: auth.user.value.role === 'ADMIN' ? 'admin' : 'dashboard' } : true
  if (!auth.user.value) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.meta.admin && auth.user.value.role !== 'ADMIN') return { name: 'dashboard' }
  if (auth.user.value.role === 'ADMIN' && to.name !== 'admin' && to.name !== 'profile') return { name: 'admin' }
  return true
})

export default router

