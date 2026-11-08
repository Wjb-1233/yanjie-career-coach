<script setup lang="ts">
import { computed, onMounted, reactive, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import { useAuth } from '@/composables/useAuth'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

const auth = useAuth()
const router = useRouter()

const form = reactive({ displayName: auth.user.value?.displayName ?? '', bio: auth.user.value?.bio ?? '' })
const saving = shallowRef(false)
const notice = shallowRef('')
const error = shallowRef('')

const avatarBusy = shallowRef(false)
const avatarNotice = shallowRef('')
const avatarError = shallowRef('')
const stats = shallowRef<{ finishedSessions: number; averageScore: number | null; lastEvaluatedAt: string | null } | null>(null)

const password = reactive({ current: '', next: '', confirm: '' })
const passwordBusy = shallowRef(false)
const passwordNotice = shallowRef('')
const passwordError = shallowRef('')

const isAdmin = computed(() => auth.user.value?.role === 'ADMIN')
const roleLabel = computed(() => isAdmin.value ? '管理员' : '训练学员')
const initial = computed(() => auth.user.value?.displayName?.slice(0, 1) ?? '?')
const avatar = computed(() => auth.user.value?.avatar ?? '')
const lastEvaluated = computed(() => {
  const value = stats.value?.lastEvaluatedAt
  return value ? new Date(value).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) : '—'
})
const bioLength = computed(() => form.bio.trim().length)
const dirty = computed(() => form.displayName.trim() !== (auth.user.value?.displayName ?? '') || form.bio.trim() !== (auth.user.value?.bio ?? ''))

onMounted(async () => {
  if (isAdmin.value) return
  try {
    const response = await api.get<ApiEnvelope<typeof stats.value>>('/auth/me/stats')
    stats.value = response.data.data
  } catch {
    // 统计是补充信息，失败不影响资料编辑
  }
})

async function save() {
  saving.value = true
  notice.value = ''
  error.value = ''
  try {
    await auth.updateProfile(form.displayName.trim(), form.bio.trim() || null)
    notice.value = '已保存'
  } catch (reason) { error.value = errorMessage(reason) }
  finally { saving.value = false }
}

function resizeToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('读取图片失败'))
    reader.onload = () => {
      const image = new Image()
      image.onerror = () => reject(new Error('图片格式不支持'))
      image.onload = () => {
        const size = 256
        const canvas = document.createElement('canvas')
        canvas.width = size
        canvas.height = size
        const context = canvas.getContext('2d')
        if (!context) { reject(new Error('无法处理图片')); return }
        const side = Math.min(image.width, image.height)
        context.drawImage(image, (image.width - side) / 2, (image.height - side) / 2, side, side, 0, 0, size, size)
        resolve(canvas.toDataURL('image/jpeg', 0.86))
      }
      image.src = String(reader.result)
    }
    reader.readAsDataURL(file)
  })
}

async function uploadAvatar(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  avatarBusy.value = true
  avatarError.value = ''
  avatarNotice.value = ''
  try {
    const dataUrl = await resizeToDataUrl(file)
    const response = await api.put<ApiEnvelope<{ avatar: string | null }>>('/auth/me/avatar', { dataUrl })
    auth.applyAvatar(response.data.data.avatar)
    avatarNotice.value = '头像已更新'
  } catch (reason) { avatarError.value = errorMessage(reason) }
  finally { avatarBusy.value = false }
}

async function removeAvatar() {
  avatarBusy.value = true
  avatarError.value = ''
  try {
    await api.put('/auth/me/avatar', { dataUrl: '' })
    auth.applyAvatar(null)
    avatarNotice.value = '已恢复默认头像'
  } catch (reason) { avatarError.value = errorMessage(reason) }
  finally { avatarBusy.value = false }
}

const exportBusy = shallowRef(false)
const exportNotice = shallowRef('')

async function exportData() {
  if (exportBusy.value) return
  exportBusy.value = true
  exportNotice.value = ''
  try {
    const response = await api.get('/auth/me/export')
    const blob = new Blob([JSON.stringify(response.data.data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `yanjie-export-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(url)
    exportNotice.value = '已导出'
  } catch (reason) {
    exportNotice.value = errorMessage(reason)
  } finally {
    exportBusy.value = false
  }
}

const deletePassword = shallowRef('')
const deleteConfirm = shallowRef('')
const deleteBusy = shallowRef(false)
const deleteError = shallowRef('')

async function deleteAccount() {
  if (deleteBusy.value) return
  if (deleteConfirm.value.trim() !== '注销') {
    deleteError.value = '请输入「注销」两个字确认'
    return
  }
  deleteError.value = ''
  deleteBusy.value = true
  try {
    await api.delete('/auth/me/delete', { data: { password: deletePassword.value, confirm: deleteConfirm.value.trim() } })
    auth.logout?.()
    await router.replace({ name: 'login' })
  } catch (reason) {
    deleteError.value = errorMessage(reason)
  } finally {
    deleteBusy.value = false
  }
}

async function changePassword() {
  passwordError.value = ''
  passwordNotice.value = ''
  if (password.next !== password.confirm) { passwordError.value = '两次输入的新密码不一致'; return }
  passwordBusy.value = true
  try {
    await api.patch('/auth/me/password', { currentPassword: password.current, newPassword: password.next })
    passwordNotice.value = '密码已更新'
    password.current = ''
    password.next = ''
    password.confirm = ''
  } catch (reason) { passwordError.value = errorMessage(reason) }
  finally { passwordBusy.value = false }
}
</script>

<template>
  <div class="page profile-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">个人资料</p>
        <h1 class="page-title">{{ isAdmin ? '管理员账号' : '账号与偏好' }}</h1>
        <p class="page-lead">{{ isAdmin ? '这里是你的管理员账号信息与登录密码。展示名称会出现在管理后台的操作记录里。' : '名字和介绍会出现在训练记录、评分报告与管理端学员列表。' }}</p>
      </div>
    </header>

    <section class="hero-card">
      <div class="hero-glow" aria-hidden="true" />
      <div class="hero-top">
        <div class="avatar-block">
          <div class="avatar-ring">
            <img v-if="avatar" class="avatar-img" :src="avatar" alt="当前头像">
            <span v-else class="avatar-fallback">{{ initial }}</span>
          </div>
          <div class="avatar-actions">
            <label class="avatar-upload">
              {{ avatarBusy ? '处理中…' : avatar ? '更换' : '上传' }}
              <input type="file" accept="image/png,image/jpeg,image/webp" hidden :disabled="avatarBusy" @change="uploadAvatar">
            </label>
            <button v-if="avatar" class="avatar-remove" type="button" :disabled="avatarBusy" @click="removeAvatar">移除</button>
          </div>
        </div>

        <div class="hero-identity">
          <h2>{{ auth.user.value?.displayName }}</h2>
          <p class="hero-meta">{{ roleLabel }} · {{ auth.user.value?.email }}</p>
          <p v-if="avatarNotice" class="hero-hint ok">✓ {{ avatarNotice }}</p>
          <p v-if="avatarError" class="hero-hint bad">{{ avatarError }}</p>
        </div>
      </div>

      <dl v-if="!isAdmin" class="metrics">
        <div>
          <dt>已完成训练</dt>
          <dd><span class="metric-num">{{ stats?.finishedSessions ?? '—' }}</span><small>场</small></dd>
        </div>
        <div>
          <dt>平均综合分</dt>
          <dd><span class="metric-num">{{ stats?.averageScore ?? '—' }}</span><small>分</small></dd>
        </div>
        <div>
          <dt>最近评分</dt>
          <dd><span class="metric-num">{{ lastEvaluated }}</span></dd>
        </div>
      </dl>
    </section>

    <div class="card-grid">
      <form class="card" @submit.prevent="save">
        <header class="card-head">
          <div>
            <h3>{{ isAdmin ? '管理员资料' : '展示资料' }}</h3>
            <p>{{ isAdmin ? '只影响管理后台显示的名字' : '这两项由你自己维护' }}</p>
          </div>
          <span class="card-state">
            <template v-if="notice">✓ {{ notice }}</template>
            <template v-else-if="dirty">未保存</template>
          </span>
        </header>

        <label class="field-row">
          <span>展示名称</span>
          <input v-model.trim="form.displayName" class="input" maxlength="60" required>
          <small>{{ isAdmin ? '最多 60 字，会显示在管理后台' : '最多 60 字，会出现在训练记录和报告里' }}</small>
        </label>

        <label v-if="!isAdmin" class="field-row">
          <span>个人介绍</span>
          <textarea v-model.trim="form.bio" class="input" maxlength="500" rows="4" placeholder="例如：应届毕业生，正在准备产品经理岗位面试。" />
          <small>{{ bioLength }} / 500 · 可留空，用于让教练更了解你的背景</small>
        </label>

        <p v-if="error" class="form-error">{{ error }}</p>

        <footer class="card-foot">
          <button class="button secondary" type="button" @click="router.back()">返回</button>
          <button class="button" :disabled="saving || !dirty">{{ saving ? '保存中…' : '保存资料' }}</button>
        </footer>
      </form>

      <form class="card" @submit.prevent="changePassword">
        <header class="card-head">
          <div>
            <h3>修改密码</h3>
            <p>下次登录使用新密码</p>
          </div>
          <span class="card-state">
            <template v-if="passwordNotice">✓ {{ passwordNotice }}</template>
          </span>
        </header>

        <label class="field-row">
          <span>当前密码</span>
          <input v-model="password.current" class="input" type="password" autocomplete="current-password" required>
        </label>

        <label class="field-row">
          <span>新密码</span>
          <input v-model="password.next" class="input" type="password" autocomplete="new-password" required minlength="8">
          <small>至少 8 位，需同时包含字母和数字</small>
        </label>

        <label class="field-row">
          <span>确认新密码</span>
          <input v-model="password.confirm" class="input" type="password" autocomplete="new-password" required minlength="8">
        </label>

        <p v-if="passwordError" class="form-error">{{ passwordError }}</p>

        <footer class="card-foot">
          <button class="button" :disabled="passwordBusy || !password.current || !password.next">
            {{ passwordBusy ? '提交中…' : '更新密码' }}
          </button>
        </footer>
      </form>

      <section class="card">
        <header class="card-head">
          <div>
            <h3>我的数据</h3>
            <p>导出账号资料、训练记录、评分、计划与话术，JSON 格式。</p>
          </div>
          <span class="card-state"><template v-if="exportNotice">✓ {{ exportNotice }}</template></span>
        </header>
        <footer class="card-foot">
          <button class="button secondary" type="button" :disabled="exportBusy" @click="exportData">
            {{ exportBusy ? '导出中…' : '导出我的数据' }}
          </button>
        </footer>
      </section>

      <section v-if="!isAdmin" class="card danger-card">
        <header class="card-head">
          <div>
            <h3>注销账号</h3>
            <p>删除账号、训练记录、评分与录像，操作不可恢复。建议先导出数据。</p>
          </div>
        </header>
        <label class="field-row">
          <span>当前密码</span>
          <input v-model="deletePassword" class="input" type="password" autocomplete="current-password" />
        </label>
        <label class="field-row">
          <span>输入「注销」确认</span>
          <input v-model="deleteConfirm" class="input" maxlength="10" />
        </label>
        <p v-if="deleteError" class="form-error">{{ deleteError }}</p>
        <footer class="card-foot">
          <button class="button danger" type="button" :disabled="deleteBusy || !deletePassword || deleteConfirm.trim() !== '注销'" @click="deleteAccount">
            {{ deleteBusy ? '正在注销…' : '确认注销账号' }}
          </button>
        </footer>
      </section>
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  max-width: 1000px;
  display: grid;
  gap: 22px;
}

.hero-card {
  position: relative;
  overflow: hidden;
  padding: 28px 30px 24px;
  border: 1px solid rgba(255, 255, 255, .12);
  border-radius: 16px;
  background:
    radial-gradient(120% 150% at 0% 0%, rgba(150, 104, 255, .22) 0%, rgba(15, 12, 28, 0) 58%),
    radial-gradient(90% 120% at 100% 0%, rgba(201, 138, 86, .12) 0%, rgba(15, 12, 28, 0) 55%),
    linear-gradient(160deg, rgba(255, 255, 255, .07) 0%, rgba(255, 255, 255, .022) 100%),
    rgba(16, 13, 28, .78);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .14), 0 34px 70px -40px rgba(0, 0, 0, .95);
}
.hero-glow {
  position: absolute;
  top: -70px;
  left: -40px;
  width: 320px;
  height: 320px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(160, 116, 255, .3) 0%, rgba(160, 116, 255, 0) 68%);
  filter: blur(10px);
  pointer-events: none;
}
.hero-top { position: relative; display: flex; align-items: center; gap: 20px; }
.hero-card:only-child, .hero-card { padding-bottom: 28px; }

.avatar-block { display: grid; justify-items: center; gap: 8px; }
.avatar-ring {
  display: grid;
  place-items: center;
  width: 76px;
  height: 76px;
  border-radius: 50%;
  padding: 2px;
  background: linear-gradient(150deg, rgba(190, 160, 255, .7), rgba(255, 255, 255, .08));
}
.avatar-img, .avatar-fallback {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  border: 1px solid rgba(10, 8, 18, .9);
  object-fit: cover;
}
.avatar-fallback {
  display: grid;
  place-items: center;
  background: linear-gradient(160deg, #241d3a, #16121f);
  color: var(--text);
  font-size: 26px;
  font-weight: 400;
}
.avatar-actions { display: flex; align-items: center; gap: 8px; }
.avatar-upload, .avatar-remove {
  border: 0;
  padding: 0;
  background: none;
  color: var(--text-3);
  font-size: 11.5px;
  cursor: pointer;
}
.avatar-upload:hover, .avatar-remove:hover { color: var(--text-2); }

.hero-identity { display: grid; gap: 6px; }
.hero-identity h2 { margin: 0; color: var(--text); font-size: 24px; font-weight: 500; letter-spacing: -.01em; }
.hero-meta { margin: 0; color: var(--text-3); font-size: 12.5px; }
.hero-hint { margin: 2px 0 0; font-size: 11.5px; }
.hero-hint.ok { color: #8fbf9a; }
.hero-hint.bad { color: #cf9a92; }

.metrics {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 24px 0 0;
}
.metrics div {
  padding: 16px 18px;
  border: 1px solid rgba(255, 255, 255, .08);
  border-radius: 12px;
  background: rgba(255, 255, 255, .035);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .06);
}
.metrics dt { color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.metrics dd { margin: 10px 0 0; display: flex; align-items: baseline; gap: 5px; }
.metric-num { color: var(--text); font-family: var(--font-num); font-size: 26px; font-weight: 300; line-height: 1; }
.metrics small { color: var(--text-3); font-size: 11px; }

.card-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 20px; align-items: start; }
.card {
  display: grid;
  gap: 18px;
  padding: 24px 26px 26px;
  border: 1px solid rgba(255, 255, 255, .1);
  border-radius: 16px;
  background: linear-gradient(165deg, rgba(255, 255, 255, .055) 0%, rgba(255, 255, 255, .018) 100%), rgba(14, 11, 24, .72);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .1), 0 26px 54px -36px rgba(0, 0, 0, .9);
}
.card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding-bottom: 16px; border-bottom: 1px solid rgba(255, 255, 255, .07); }
.card-head h3 { margin: 0; color: var(--text); font-size: 15px; font-weight: 500; }
.card-head p { margin: 6px 0 0; color: var(--text-3); font-size: 11.5px; }
.card-state { color: var(--text-3); font-size: 11.5px; white-space: nowrap; }

.field-row { display: grid; gap: 8px; }
.field-row > span { color: var(--text-2); font-size: 12.5px; }
.field-row small { color: var(--text-3); font-size: 11px; }

.input {
  width: 100%;
  padding: 11px 13px;
  border: 1px solid rgba(255, 255, 255, .1);
  border-radius: 10px;
  background: rgba(255, 255, 255, .035);
  color: var(--text);
  font-size: 13px;
  transition: border-color .16s var(--ease), box-shadow .16s var(--ease), background .16s var(--ease);
}
.input::placeholder { color: var(--text-3); }
.input:hover { border-color: rgba(255, 255, 255, .18); }
.input:focus {
  outline: none;
  border-color: rgba(186, 150, 255, .65);
  background: rgba(255, 255, 255, .05);
  box-shadow: 0 0 0 3px rgba(150, 108, 240, .18);
}
textarea.input { resize: vertical; line-height: 1.8; }

.form-error { margin: 0; color: #cf9a92; font-size: 12px; }
.card-foot { display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding-top: 4px; }

@media (max-width: 860px) {
  .card-grid { grid-template-columns: 1fr; }
  .hero-card { padding: 22px; }
  .hero-identity h2 { font-size: 21px; }
  .metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
  .metrics div { padding: 12px 12px; }
  .metric-num { font-size: 20px; }
  .metrics dt { font-size: 10px; }
  .profile-page { padding-bottom: 84px; }
}

@media (max-width: 480px) {
  .hero-top { gap: 14px; }
  .avatar-ring { width: 62px; height: 62px; }
  .avatar-img, .avatar-fallback { width: 58px; height: 58px; font-size: 22px; }
  .hero-identity h2 { font-size: 19px; }
  .metrics dt { letter-spacing: 0; }
  .card { padding: 20px 18px 22px; }
}
.danger-card { border-color: color-mix(in srgb, #b4553f 35%, var(--border)); }
.button.danger { background: #b4553f; border-color: #b4553f; color: #fff; }
.button.danger:hover { background: #9c4635; border-color: #9c4635; }
</style>
<style scoped>
.profile-page { max-width: 900px; }
.page-title { font-size: clamp(28px, 3vw, 36px); letter-spacing: -.02em; }
.page-lead { margin-top: 10px; font-size: 14px; }
.hero-card { padding: 24px 26px; border-radius: 16px; }
.hero-top { gap: 18px; }
.avatar-ring { width: 64px; height: 64px; }
.avatar-fallback { font-size: 22px; }
.hero-identity h2 { font-size: 22px; }
.hero-meta { font-size: 13px; }
.metrics { margin-top: 18px; gap: 10px; }
.metrics dt { font-size: 12px; color: var(--text-3); }
.metrics .metric-num { font-size: 24px; }
.card-grid { gap: 16px; margin-top: 20px; }
.card { padding: 22px; border-radius: 14px; }
.card-head h2 { font-size: 16px; }
.field-row { font-size: 12.5px; color: var(--text-3); }
.card p, .card small { font-size: 12.5px; }
</style>
