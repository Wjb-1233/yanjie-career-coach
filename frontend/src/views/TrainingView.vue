<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DialoguePanel from '@/components/training/DialoguePanel.vue'
import { useTrainingSession } from '@/composables/useTrainingSession'
import { api, errorMessage } from '@/lib/api'

const route = useRoute()
const router = useRouter()
const sessionId = String(route.params.id)
const training = useTrainingSession(sessionId)
const loading = shallowRef(true)
const finishing = shallowRef(false)
const clearingResume = shallowRef(false)
const pageError = shallowRef('')
const finishAfterNext = shallowRef(false)
const mode = shallowRef<'text' | 'voice'>(route.query.mode === 'voice' ? 'voice' : 'text')
const planId = computed(() => String(route.query.planId ?? ''))
const taskKey = computed(() => String(route.query.taskKey ?? ''))
const isPlanTask = computed(() => Boolean(planId.value && taskKey.value))
const stageLabel = computed(() => ({ OPENING: '情景开场', DISCOVERY: '深入追问', CHALLENGE: '情景应对', CLOSING: '沟通收尾' }[training.session.value?.stage ?? 'OPENING'] ?? '训练进行中'))

onMounted(async () => {
  try { await training.load() } catch (reason) { pageError.value = errorMessage(reason) }
  finally { loading.value = false }
})

async function finish() {
  if (finishing.value) return
  finishing.value = true
  pageError.value = ''
  try {
    await training.finish(!isPlanTask.value)
    if (isPlanTask.value) {
      await api.post(`/training-plans/${planId.value}/tasks/${taskKey.value}/complete`, { evidence: sessionId })
      await router.push(`/plans/${planId.value}`)
      return
    }
    await router.push(`/report/${sessionId}`)
  } catch (reason) { pageError.value = errorMessage(reason) }
  finally { finishing.value = false }
}

async function send(content: string) {
  const closing = finishAfterNext.value
  await training.send(content, closing)
  if (training.session.value?.status === 'FINISHED') {
    finishAfterNext.value = false
    await finish()
  }
}

async function restart() {
  try {
    const id = await training.restart()
    await router.push({ name: 'training', params: { id }, query: route.query })
  } catch (reason) { pageError.value = errorMessage(reason) }
}

async function selectMode(next: 'text' | 'voice') {
  mode.value = next
  await router.replace({ query: { ...route.query, mode: next === 'voice' ? 'voice' : undefined } })
}

async function clearResume(): Promise<void> {
  if (!training.session.value?.resumeFilename || clearingResume.value) return
  if (!window.confirm('清除本次面试的简历文字？之后的提问将不再参考简历。已生成的对话仍保留，如需一并删除请到训练记录中彻底删除会话。')) return
  clearingResume.value = true
  pageError.value = ''
  try {
    await api.delete(`/training-sessions/${sessionId}/resume`)
    await training.load()
  } catch (reason) { pageError.value = errorMessage(reason) }
  finally { clearingResume.value = false }
}
</script>

<template>
  <div class="page training-page" :class="{ 'voice-page': mode === 'voice' }">
    <header class="training-heading">
      <div><p class="eyebrow">角色演练 · {{ stageLabel }}</p><h1>{{ training.session.value?.sceneTitle || '情景训练' }}</h1><p class="training-subtitle">面对模拟角色，按自己的节奏回答。系统会记录对话并在结束后提供复盘建议。</p></div>
      <div class="heading-actions">
        <button v-if="training.session.value?.status === 'FINISHED'" class="button secondary" type="button" @click="restart">同场景重新开始</button>
        <RouterLink class="back" to="/scenes">退出训练</RouterLink>
      </div>
    </header>
    <div class="mode-bar">
      <div><strong>训练方式</strong><span>{{ mode === 'voice' ? '说出回答，听面试官回应' : '键入回答，按自己的节奏思考' }}</span></div>
      <div class="mode-switch" role="group" aria-label="训练方式">
        <button type="button" :class="{ active: mode === 'text' }" :aria-pressed="mode === 'text'" @click="selectMode('text')">文字模式</button>
        <button type="button" :class="{ active: mode === 'voice' }" :aria-pressed="mode === 'voice'" @click="selectMode('voice')">语音模式</button>
      </div>
    </div>
    <div v-if="training.session.value?.resumeFilename" class="resume-bar">
      <div><strong>简历定制面试已开启</strong><span>{{ training.session.value.resumeFilename }} · 面试官会参考其中的真实项目和技术经历</span></div>
      <button type="button" :disabled="clearingResume" @click="clearResume">{{ clearingResume ? '清除中…' : '清除简历内容' }}</button>
    </div>
    <div v-if="training.session.value?.resumeOpeningDegraded" class="model-notice">首题由本地模板生成；请检查大模型配置。后续对话会继续尝试使用大模型结合简历追问。</div>
    <div v-if="pageError || training.error.value" class="error-banner">{{ pageError || training.error.value }}</div>
    <div v-if="training.degraded.value" class="model-notice">本轮由本地教练模板接续。请确认模型服务状态；这轮内容仍可继续训练。</div>
    <div v-if="finishing" class="model-notice">正在生成五维评分，请稍候；报告通常比单轮对话需要更长时间。</div>
    <div v-if="loading" class="panel skeleton dialogue-loading" />
    <DialoguePanel
      v-else-if="training.session.value"
      :messages="training.session.value.messages"
      :current-round="training.session.value.currentRound"
      :max-rounds="training.session.value.maxRounds"
      :stage="stageLabel"
      :sending="training.sending.value || finishing"
      :finished="training.session.value.status === 'FINISHED'"
      :flags="training.liveFlags.value"
      :minimum-rounds="isPlanTask ? 6 : 2"
      :mode="mode"
      :finish-after-next="finishAfterNext"
      @send="send"
      @finish="finishAfterNext = !finishAfterNext"
      @report="finish"
    />
  </div>
</template>

<style scoped>
.training-page { max-width: 1080px; }
.model-notice { margin-bottom: 14px; padding: 11px 14px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--sky); color: var(--mint-dark); font-size: 13px; }
.training-heading { margin-bottom: 20px; padding: 27px 30px; display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; border: 1px solid var(--line); border-radius:var(--radius); background:var(--card); }
.training-heading h1 { margin: 0; font: 700 clamp(26px, 3vw, 34px)/1.2 var(--font-ui); }
.training-subtitle { max-width: 550px; margin: 10px 0 0; color: var(--ink-soft); font-size: 13px; line-height: 1.7; }
.mode-bar { margin-bottom: 17px; padding: 12px 14px 12px 19px; display: flex; align-items: center; justify-content: space-between; gap: 14px; border: 1px solid var(--line); border-radius:var(--radius); background:var(--card); }
.resume-bar { margin-bottom: 17px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; gap: 14px; border: 1px solid var(--border); border-radius:var(--radius); background: var(--sky); }
.resume-bar div { display: grid; gap: 3px; min-width: 0; }
.resume-bar strong { color: var(--mint-dark); font-size: 13px; }
.resume-bar span { overflow-wrap: anywhere; font-size: 12px; }
.resume-bar button { flex: none; border: 0; background: transparent; color: #9c3f33; cursor: pointer; font-size: 12px; font-weight: 800; }
.mode-bar > div:first-child { display: grid; gap: 3px; }
.mode-bar strong { color: var(--ink); font-size: 13px; }
.mode-bar span { color: var(--ink-soft); font-size: 12px; }
.mode-switch { display: flex; padding: 3px; border-radius:var(--radius); background: #edf4f0; }
.mode-switch button { min-height: 35px; padding: 0 15px; border: 0; border-radius:var(--radius-sm); background: transparent; color: var(--ink-soft); cursor: pointer; font-size: 12px; font-weight: 700; white-space: nowrap; }
.mode-switch button.active { background: var(--ink); color: white; box-shadow: 0 3px 10px rgba(16,37,43,.13); }
.back { color: var(--ink-soft); font-size: 13px; }
.back:hover { color: var(--mint-dark); }
.heading-actions { display: flex; align-items: center; gap: 14px; }
.dialogue-loading { min-height: 680px; }
.training-heading,.mode-bar { border-color:var(--border);background:var(--card);box-shadow:var(--shadow);backdrop-filter:none; }
.model-notice,.resume-bar { border-color:var(--border);background:var(--card);color:var(--text-2); }
.resume-bar strong { color:var(--text); }
.resume-bar button { color:#cf9a92; }
.mode-switch { border:1px solid var(--border);background:var(--bg-2); }
.mode-switch button.active { background:var(--overlay-3);color:var(--text);box-shadow:none; }
@media (max-width: 700px) {
  .training-heading { padding: 23px; align-items: flex-start; flex-direction: column; }
  .heading-actions { width: 100%; justify-content: space-between; }
  .mode-bar { align-items: stretch; flex-direction: column; }
  .resume-bar { align-items: flex-start; flex-direction: column; }
  .mode-switch button { flex: 1; }
  .voice-page .training-heading { padding: 14px 18px; margin-bottom: 12px; flex-direction: row; align-items: center; }
  .voice-page .training-heading .eyebrow, .voice-page .training-subtitle { display: none; }
  .voice-page .training-heading h1 { font-size: 20px; }
  .voice-page .heading-actions { width: auto; }
  .voice-page .mode-bar { margin-bottom: 12px; padding: 8px 12px; }
  .voice-page .mode-bar > div:first-child { display: none; }
}
</style>

