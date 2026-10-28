<script setup lang="ts">
import { computed, reactive, shallowRef } from 'vue'

export type AuthMode = 'login' | 'register'

export interface AuthSubmitPayload {
  mode: AuthMode
  email: string
  password: string
  displayName?: string
}

interface Props {
  loading: boolean
  error: string
}

interface Emits {
  submit: [payload: AuthSubmitPayload]
  clearError: []
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const mode = shallowRef<AuthMode>('login')
const validationError = shallowRef('')
const form = reactive({
  email: '',
  password: '',
  displayName: '',
  confirmPassword: '',
})

const copy = computed(() => mode.value === 'login'
  ? {
      eyebrow: '再次登录',
      title: '继续你的训练',
      hint: '使用你的邮箱和密码进入训练空间。',
      submit: '进入训练空间',
      pending: '正在进入…',
    }
  : {
      eyebrow: '开始训练',
      title: '创建训练档案',
      hint: '注册后即可保存训练记录、评分报告和个性化计划。',
      submit: '注册并开始训练',
      pending: '正在创建…',
    })

const visibleError = computed(() => validationError.value || props.error)

function selectMode(nextMode: AuthMode) {
  mode.value = nextMode
  validationError.value = ''
  form.password = ''
  form.confirmPassword = ''
  emit('clearError')
}

function clearError() {
  validationError.value = ''
  emit('clearError')
}

function submit() {
  validationError.value = ''
  const email = form.email.trim()
  const displayName = form.displayName.trim()

  if (mode.value === 'register' && form.password !== form.confirmPassword) {
    validationError.value = '两次输入的密码不一致。'
    return
  }
  if (mode.value === 'register' && !displayName) {
    validationError.value = '请输入你的称呼。'
    return
  }

  emit('submit', {
    mode: mode.value,
    email,
    password: form.password,
    ...(mode.value === 'register' ? { displayName } : {}),
  })
}
</script>

<template>
  <form class="auth-form" @submit.prevent="submit">
    <div class="mode-switch" aria-label="选择认证方式">
      <button
        class="mode-button"
        :class="{ active: mode === 'login' }"
        type="button"
        :aria-pressed="mode === 'login'"
        @click="selectMode('login')"
      >
        登录
      </button>
      <button
        class="mode-button"
        :class="{ active: mode === 'register' }"
        type="button"
        :aria-pressed="mode === 'register'"
        @click="selectMode('register')"
      >
        注册
      </button>
    </div>

    <header class="form-heading">
      <p class="eyebrow">{{ copy.eyebrow }}</p>
      <h2 class="form-title">{{ copy.title }}</h2>
      <p class="hint">{{ copy.hint }}</p>
    </header>

    <div v-if="visibleError" class="error-banner" role="alert">{{ visibleError }}</div>

    <label v-if="mode === 'register'" class="field-label">
      称呼
      <input
        v-model="form.displayName"
        class="field"
        name="displayName"
        type="text"
        autocomplete="name"
        minlength="1"
        maxlength="60"
        required
        :disabled="loading"
        @input="clearError"
      />
    </label>

    <label class="field-label">
      邮箱
      <input
        v-model="form.email"
        class="field"
        name="email"
        type="email"
        autocomplete="email"
        maxlength="254"
        required
        :disabled="loading"
        @input="clearError"
      />
    </label>

    <label class="field-label">
      密码
      <input
        v-model="form.password"
        class="field"
        name="password"
        type="password"
        :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
        minlength="8"
        maxlength="72"
        required
        :disabled="loading"
        @input="clearError"
      />
      <small v-if="mode === 'register'" class="field-help">至少 8 个字符，建议同时包含字母、数字和符号。</small>
    </label>

    <label v-if="mode === 'register'" class="field-label">
      确认密码
      <input
        v-model="form.confirmPassword"
        class="field"
        name="confirmPassword"
        type="password"
        autocomplete="new-password"
        minlength="8"
        maxlength="72"
        required
        :disabled="loading"
        @input="clearError"
      />
    </label>

    <button class="button submit-button" type="submit" :disabled="loading">
      {{ loading ? copy.pending : copy.submit }}
    </button>

    <p class="privacy-note">密码只用于身份验证，页面不会把登录凭据保存在浏览器本地存储中。</p>
  </form>
</template>

<style scoped>
.auth-form { width: min(400px, 100%); display: grid; gap: 18px; }

.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--overlay-1);
}
.mode-button {
  min-height: 34px;
  border: 0;
  border-radius: 3px;
  background: transparent;
  color: var(--text-3);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: .06em;
  transition: background var(--ease), color var(--ease);
}
.mode-button:hover { color: var(--text-2); }
.mode-button.active { background: var(--overlay-3); color: var(--text); }

.form-heading { margin: 10px 0 4px; }
.form-title { margin: 0; color: var(--text); font-size: 26px; font-weight: 600; letter-spacing: -.01em; line-height: 1.35; }
.hint { margin: 10px 0 0; color: var(--text-3); font-size: 13px; line-height: 1.8; }
.field-help { color: var(--text-3); font-size: 11px; font-weight: 400; line-height: 1.6; }
.submit-button { width: 100%; margin-top: 4px; }
.privacy-note { margin: 0; color: var(--text-3); font-size: 11px; line-height: 1.7; text-align: center; }

@media (max-width: 520px) {
  .auth-form { gap: 16px; }
  .form-title { font-size: 23px; }
}
</style>
