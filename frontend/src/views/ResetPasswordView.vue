<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, errorMessage } from '@/lib/api'

const route = useRoute()
const router = useRouter()
const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const password = ref('')
const confirm = ref('')
const busy = shallowRef(false)
const error = shallowRef('')
const done = shallowRef(false)

const ready = computed(() => token.value.length >= 10)
const canSubmit = computed(() => ready.value && password.value.length >= 8 && password.value === confirm.value)

async function submit(): Promise<void> {
  if (!canSubmit.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await api.post('/auth/password-reset/confirm', { token: token.value, password: password.value })
    done.value = true
    setTimeout(() => void router.replace({ name: 'login' }), 1800)
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="reset-page">
    <section class="reset-card">
      <p class="eyebrow">重置密码</p>
      <h1>设置一个新密码</h1>

      <template v-if="!ready">
        <p class="hint">链接缺少有效令牌，请回到登录页重新申请。</p>
        <RouterLink class="button" to="/login">回登录页</RouterLink>
      </template>

      <template v-else-if="done">
        <p class="hint success">密码已更新，正在跳转到登录页…</p>
        <RouterLink class="button" to="/login">立即登录</RouterLink>
      </template>

      <form v-else @submit.prevent="submit">
        <label>
          <span>新密码</span>
          <input v-model="password" class="field" type="password" autocomplete="new-password" minlength="8" maxlength="72" required />
          <small>至少 8 位，同时包含字母和数字</small>
        </label>
        <label>
          <span>确认新密码</span>
          <input v-model="confirm" class="field" type="password" autocomplete="new-password" minlength="8" maxlength="72" required />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="button" type="submit" :disabled="!canSubmit || busy">
          {{ busy ? '提交中…' : '更新密码' }}
        </button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.reset-page { min-height: 100vh; display: grid; place-items: center; padding: 40px 20px; background: var(--bg); }
.reset-card { width: min(420px, 100%); padding: 30px; border: 1px solid var(--border); border-radius: 14px; background: var(--card); display: grid; gap: 14px; }
.eyebrow { margin: 0; color: var(--accent-strong); font-size: 11px; letter-spacing: .14em; }
h1 { margin: 0; font-size: 24px; }
label { display: grid; gap: 6px; color: var(--text-2); font-size: 12px; }
small { color: var(--text-3); font-size: 11px; }
.hint { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.8; }
.hint.success { color: var(--success); }
.error { margin: 0; color: var(--danger); font-size: 12px; }
.button { width: fit-content; }
</style>
