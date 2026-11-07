<script setup lang="ts">
import { onBeforeUnmount, onMounted, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AuthForm, { type AuthSubmitPayload } from '@/components/auth/AuthForm.vue'
import DemoLoginPanel from '@/components/auth/DemoLoginPanel.vue'
import { useAuth } from '@/composables/useAuth'
import { useTheme } from '@/composables/useTheme'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

const router = useRouter()
const route = useRoute()
const auth = useAuth()
const { applyTemporary } = useTheme()
let previousTheme: 'dark' | 'light' = 'dark'
const error = shallowRef('')
type DemoState = 'loading' | 'enabled' | 'disabled' | 'unreachable'
const demoState = shallowRef<DemoState>('loading')
const forgotOpen = shallowRef(false)
const forgotEmail = shallowRef('')
const forgotBusy = shallowRef(false)
const forgotNotice = shallowRef('')

// 登录页固定使用夜间视觉，不影响用户保存的主题偏好
onMounted(() => {
  previousTheme = (document.documentElement.dataset.theme as 'dark' | 'light') || 'dark'
  applyTemporary('dark')
})
onBeforeUnmount(() => {
  applyTemporary(previousTheme)
})

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

    <section class="manifesto">
      <div class="brand"><strong>言阶</strong><span>面试沟通训练</span></div>

      <div class="manifesto-copy">
        <p class="eyebrow">YANJIE · 面试情景模拟</p>
        <h1 class="manifesto-title">把每一次<em>被问住</em>的问题，<br />练成能答上来的话。</h1>
        <div class="facts">
          <span>25 场真实面试场景</span><i aria-hidden="true" />
          <span>逐轮证据批注</span><i aria-hidden="true" />
          <span>四维分档评分</span>
        </div>
      </div>

      <p class="login-foot">言阶 · 面试沟通训练系统</p>
    </section>

    <section class="login-panel">
      <div class="auth-stack">
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
        <p v-else-if="demoState === 'unreachable'" class="demo-hint">
          一键登录需要本机后端服务在 <code>127.0.0.1:8081</code> 运行；当前未连接，因此暂时隐藏演示入口。
        </p>
        <p v-else-if="demoState === 'disabled'" class="demo-hint">
          当前环境未开启演示登录（仅开发环境且通过 localhost:5173 访问时可用）。
        </p>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(400px, .9fr);
  background: var(--bg);
  color: var(--text);
}

.manifesto {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 100vh;
  padding: 44px 5vw 40px;
  border-right: 1px solid var(--border);
}

.brand { display: flex; align-items: baseline; gap: 12px; }
.brand strong { font-family: var(--font-display); font-size: 20px; font-weight: 600; letter-spacing: .18em; }
.brand span { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }

.manifesto-copy { max-width: 560px; margin: auto 0; }
.eyebrow { margin: 0 0 22px; color: var(--text-3); font-size: 11px; letter-spacing: .3em; }

.manifesto-title {
  margin: 0;
  color: var(--text);
  font-family: var(--font-display);
  font-size: clamp(32px, 3.6vw, 48px);
  font-weight: 600;
  line-height: 1.32;
  letter-spacing: .01em;
}
.manifesto-title em { font-style: normal; color: var(--accent); }

.facts {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 30px;
  color: var(--text-2);
  font-size: 13px;
  letter-spacing: .06em;
}
.facts i { width: 1px; height: 11px; background: var(--border-bright); }

.login-foot { color: var(--text-3); font-size: 11.5px; letter-spacing: .04em; }

/* 右侧：实心登录卡 */
.login-panel {
  display: grid;
  place-items: center;
  padding: 40px;
  background: var(--bg);
}

.auth-stack {
  width: min(400px, 100%);
  padding: 28px 26px 24px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--card);
  box-shadow: none;
}

.demo-hint {
  margin: 18px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--divider);
  color: var(--text-3);
  font-size: 11px;
  line-height: 1.9;
}
.demo-hint code { padding: 1px 5px; border-radius: 4px; background: var(--card-2); color: var(--text-2); font-size: 11px; }

.forgot { margin-top: 14px; }
.forgot-link { padding: 0; border: 0; background: none; color: var(--text-3); font-size: 12px; cursor: pointer; }
.forgot-link:hover { color: var(--text-2); }
.forgot-form { margin-top: 12px; display: grid; gap: 10px; }
.forgot-form p { margin: 0; color: var(--text-3); font-size: 12px; line-height: 1.8; }
.forgot-note { color: var(--accent-strong) !important; }

@media (max-width: 900px) {
  .login-page { grid-template-columns: 1fr; }
  .manifesto { min-height: auto; padding: 34px 24px 24px; gap: 28px; border-right: 0; border-bottom: 1px solid var(--border); }
  .manifesto-title { font-size: clamp(28px, 7.4vw, 38px); }
  .login-foot { display: none; }
  .login-panel { padding: 28px 20px 48px; }
  .auth-stack { width: 100%; padding: 22px 20px 20px; }
}
</style>
