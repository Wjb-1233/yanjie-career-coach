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
      <div class="brand"><strong>言阶</strong><span>职场沟通训练</span></div>
      <div class="manifesto-copy">
        <p class="eyebrow">职场沟通训练</p>
        <h1 class="manifesto-title">每一次表达，<br />都有清晰的<br /><em class="title-accent">下一阶。</em></h1>
        <p class="manifesto-lead">在安全、可重复的职场情景中练习。系统记录你的结构、分寸、说服力与成长轨迹。</p>
      </div>
      <div class="manifesto-foot"><span>五维评分</span><span>逐轮复盘</span><span>话术改写</span></div>
    </section>

    <section class="login-panel">
      <div class="auth-stack">
        <AuthForm
          :loading="auth.loading.value"
          :error="error"
          @submit="submit"
          @clear-error="error = ''"
        />
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
.login-page { min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1.12fr) minmax(420px, .88fr); background: var(--bg); }

.manifesto {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-height: 100vh;
  padding: 44px 6vw 40px;
  border-right: 1px solid var(--divider);
  background: var(--bg-2);
}
.brand { display: flex; align-items: baseline; gap: 12px; }
.brand strong { font-size: 17px; font-weight: 600; letter-spacing: .18em; }
.brand span { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }

.manifesto-copy { max-width: 640px; }
.manifesto .eyebrow { color: var(--text-3); margin-bottom: 26px; }
.manifesto-title {
  margin: 0;
  color: var(--text);
  font-size: clamp(44px, 5.4vw, 76px);
  font-weight: 600;
  line-height: 1.18;
  letter-spacing: -.02em;
}
.title-accent { color: var(--text-3); font-style: normal; }
.manifesto-lead { max-width: 460px; margin: 30px 0 0; color: var(--text-2); font-size: 14px; line-height: 2; letter-spacing: .01em; }
.manifesto-foot {
  display: flex;
  gap: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--divider);
  color: var(--text-3);
  font-size: 11px;
  letter-spacing: .14em;
}

.login-panel { display: grid; place-items: center; padding: 36px; background: var(--bg); }
.auth-stack { width: min(400px, 100%); }
.demo-hint {
  margin: 22px 0 0;
  padding-top: 16px;
  border-top: 1px solid var(--divider);
  color: var(--text-3);
  font-size: 11px;
  line-height: 1.9;
}
.demo-hint code { padding: 1px 5px; border-radius: 3px; background: var(--overlay-2); color: var(--text-2); font-size: 11px; }

@media (max-width: 900px) {
  .login-page { grid-template-columns: 1fr; }
  .manifesto { min-height: auto; padding: 32px 24px 38px; border-right: 0; border-bottom: 1px solid var(--divider); }
  .manifesto-title { font-size: clamp(38px, 10vw, 56px); }
  .manifesto-lead { display: none; }
  .manifesto-foot { display: none; }
  .login-panel { padding: 40px 24px 64px; }
}
</style>

