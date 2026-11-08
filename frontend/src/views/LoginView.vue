<script setup lang="ts">
import { onMounted, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AuthForm, { type AuthSubmitPayload } from '@/components/auth/AuthForm.vue'
import DemoLoginPanel from '@/components/auth/DemoLoginPanel.vue'
import { useAuth } from '@/composables/useAuth'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

const router = useRouter()
const route = useRoute()
const auth = useAuth()
const error = shallowRef('')
type DemoState = 'loading' | 'enabled' | 'disabled' | 'unreachable'
const demoState = shallowRef<DemoState>('loading')
const forgotOpen = shallowRef(false)
const forgotEmail = shallowRef('')
const forgotBusy = shallowRef(false)
const forgotNotice = shallowRef('')

onMounted(async () => {
  try {
    const response = await api.get<ApiEnvelope<{ enabled: boolean }>>('/auth/demo-status')
    demoState.value = response.data.data.enabled ? 'enabled' : 'disabled'
  } catch {
    // 后端未启动时接口会失败：区分「未连接」与「已关闭」，避免入口静默消失
    demoState.value = 'unreachable'
  }
})

async function submit(payload: AuthSubmitPayload) {
  error.value = ''
  try {
    if (payload.mode === 'register') {
      await auth.register(payload.email, payload.password, payload.displayName ?? '')
    } else {
      await auth.login(payload.email, payload.password)
    }
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

async function submitPasswordRequest() {
  const email = forgotEmail.value.trim()
  if (!/^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(email)) {
    forgotNotice.value = '请输入正确的邮箱地址'
    return
  }
  forgotBusy.value = true
  forgotNotice.value = ''
  try {
    await api.post('/auth/password-reset/request', { email })
    forgotNotice.value = '如果这个邮箱已注册，重置链接会发送到邮箱；未开通邮件服务时会转交管理员处理。'
  } catch (reason) {
    forgotNotice.value = errorMessage(reason)
  } finally {
    forgotBusy.value = false
  }
}
async function demoLogin(role: 'STUDENT' | 'ADMIN') {
  error.value = ''
  try {
    await auth.demoLogin(role)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(role === 'ADMIN' ? '/admin' : redirect)
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-card">
      <header class="brand">
        <strong>言阶</strong>
        <span>面试沟通训练</span>
      </header>

      <h1>面试，是练出来的。</h1>
      <p class="lead">一场十分钟的模拟面试，换一份能落地的复盘。</p>

      <AuthForm
        :loading="auth.loading.value"
        :error="error"
        @submit="submit"
        @clear-error="error = ''"
      />

      <div class="forgot">
        <button class="forgot-link" type="button" @click="forgotOpen = !forgotOpen">{{ forgotOpen ? '收起' : '忘记密码？' }}</button>
        <div v-if="forgotOpen" class="forgot-form">
          <p>输入注册邮箱提交申请，管理员重置后会给你一个临时密码。</p>
          <input v-model.trim="forgotEmail" class="field" type="email" maxlength="254" placeholder="你的注册邮箱">
          <button class="button" type="button" :disabled="forgotBusy" @click="submitPasswordRequest">{{ forgotBusy ? '提交中…' : '提交申请' }}</button>
          <p v-if="forgotNotice" class="forgot-note">{{ forgotNotice }}</p>
        </div>
      </div>

      <DemoLoginPanel v-if="demoState === 'enabled'" :loading="auth.loading.value" @select="demoLogin" />
      <p v-else-if="demoState === 'unreachable'" class="demo-hint">一键登录需要本机后端服务运行；当前未连接。</p>
      <p v-else-if="demoState === 'disabled'" class="demo-hint">当前环境未开启演示登录。</p>
    </section>
  </main>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; place-items: center; padding: 40px 20px; background: var(--bg); }
.login-card { width: min(440px, 100%); display: grid; gap: 18px; padding: 36px 34px; border: 1px solid var(--border); border-radius: 18px; background: var(--card); }
.brand { display: flex; align-items: baseline; gap: 10px; }
.brand strong { font-family: var(--font-display); font-size: 20px; font-weight: 600; letter-spacing: .16em; }
.brand span { color: var(--text-3); font-size: 12px; }
.login-card h1 { margin: 6px 0 0; font-size: 30px; font-weight: 650; letter-spacing: -.02em; line-height: 1.25; }
.login-card .lead { margin: -6px 0 4px; color: var(--text-3); font-size: 14px; line-height: 1.7; }
.login-card :deep(.form-heading) { display: none; }
.login-card :deep(.privacy-note) { display: none; }
.login-card :deep(.mode-switch) { background: var(--bg-2); }
.login-card :deep(.submit-button) { min-height: 46px; font-size: 14px; }
.forgot { display: grid; gap: 10px; justify-items: center; }
.forgot-link { border: 0; background: transparent; color: var(--text-3); font-size: 13px; cursor: pointer; }
.forgot-link:hover { color: var(--text); }
.forgot-form { width: 100%; display: grid; gap: 10px; padding: 14px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-2); }
.forgot-form p { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.7; }
.forgot-note { color: var(--text-3) !important; }
.demo-hint { margin: 0; color: var(--text-3); font-size: 12.5px; line-height: 1.7; }
</style>
