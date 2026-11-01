import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import './assets/main.css'

createApp(App).use(router).mount('#app')

// 刷新令牌失效时统一回到登录页，避免每个页面各自弹「缺少刷新令牌」
window.addEventListener('auth:expired', () => {
  if (router.currentRoute.value.name === 'login') return
  void router.replace({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
})

if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch((error: unknown) => {
      console.error('Service Worker 注册失败', error)
    })
  })
}

