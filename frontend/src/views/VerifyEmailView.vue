<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { useRoute } from 'vue-router'

import { api, errorMessage } from '@/lib/api'

const route = useRoute()
const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const state = shallowRef<'checking' | 'ok' | 'error'>('checking')
const message = shallowRef('')

onMounted(async () => {
  if (!token.value) {
    state.value = 'error'
    message.value = '链接缺少验证令牌，请回到看板重新发送验证邮件。'
    return
  }
  try {
    await api.post('/auth/verify-email/confirm', { token: token.value })
    state.value = 'ok'
  } catch (reason) {
    state.value = 'error'
    message.value = errorMessage(reason)
  }
})
</script>

<template>
  <main class="verify-page">
    <section class="verify-card">
      <p class="eyebrow">邮箱验证</p>
      <h1>{{ state === 'ok' ? '邮箱已验证' : state === 'error' ? '验证没成功' : '正在验证…' }}</h1>
      <p class="hint">
        {{ state === 'ok' ? '现在可以开始训练了。' : state === 'error' ? message : '稍等一下，正在确认链接。' }}
      </p>
      <RouterLink v-if="state !== 'checking'" class="button" to="/">{{ state === 'ok' ? '去看板' : '回看板重发' }}</RouterLink>
    </section>
  </main>
</template>

<style scoped>
.verify-page { min-height: 100vh; display: grid; place-items: center; padding: 40px 20px; background: var(--bg); }
.verify-card { width: min(420px, 100%); padding: 30px; border: 1px solid var(--border); border-radius: 14px; background: var(--card); display: grid; gap: 12px; }
.eyebrow { margin: 0; color: var(--accent-strong); font-size: 11px; letter-spacing: .14em; }
h1 { margin: 0; font-size: 24px; }
.hint { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.8; }
.button { width: fit-content; }
</style>
