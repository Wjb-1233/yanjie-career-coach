<script setup lang="ts">
import { reactive, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import { useAuth } from '@/composables/useAuth'
import { errorMessage } from '@/lib/api'

const auth = useAuth()
const router = useRouter()
const form = reactive({ displayName: auth.user.value?.displayName ?? '', bio: auth.user.value?.bio ?? '' })
const saving = shallowRef(false)
const notice = shallowRef('')
const error = shallowRef('')

async function save() {
  saving.value = true
  notice.value = ''
  error.value = ''
  try {
    await auth.updateProfile(form.displayName.trim(), form.bio.trim() || null)
    notice.value = '个人资料已保存。'
  } catch (reason) { error.value = errorMessage(reason) }
  finally { saving.value = false }
}
</script>

<template>
  <div class="page profile-page"><header class="page-heading"><div><p class="eyebrow">个人资料</p><h1 class="page-title">个人资料</h1><p class="page-lead">维护展示名称和个人介绍，这些信息用于训练记录与管理端学员报告。</p></div></header>
    <form class="panel profile-form" @submit.prevent="save"><label class="field-label">邮箱<input class="field" :value="auth.user.value?.email" disabled></label><label class="field-label">账号角色<input class="field" :value="auth.user.value?.role === 'ADMIN' ? '管理员' : '学员'" disabled></label><label class="field-label">展示名称<input v-model.trim="form.displayName" class="field" maxlength="60" required></label><label class="field-label">个人介绍<textarea v-model.trim="form.bio" class="field" maxlength="500" rows="5" placeholder="例如：应届毕业生，正在准备产品经理岗位面试。" /></label><p v-if="notice" class="success">{{ notice }}</p><p v-if="error" class="error-banner">{{ error }}</p><div class="actions"><button class="button" :disabled="saving">{{ saving ? '保存中…' : '保存资料' }}</button><button class="button secondary" type="button" @click="router.back()">返回</button></div></form>
  </div>
</template>

<style scoped>
.profile-page{max-width:820px}.profile-form{padding:26px;display:grid;gap:16px}.field-label{display:grid;gap:8px;color:var(--ink-soft);font-size:13px;font-weight:700}.field-label textarea{resize:vertical}.actions{display:flex;gap:10px}.success{color:var(--mint-dark)}
</style>
