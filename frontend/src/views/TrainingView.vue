<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DialoguePanel from '@/components/training/DialoguePanel.vue'
import { useTrainingSession } from '@/composables/useTrainingSession'
import { api, errorMessage } from '@/lib/api'

const route = useRoute()
const router = useRouter()
const sessionId = String(route.params.id)
const training = useTrainingSession(sessionId)
const jdInput = shallowRef('')
const jdBusy = shallowRef(false)

async function applyJd(): Promise<void> {
  const text = jdInput.value.trim()
  if (text.length < 20 || jdBusy.value) return
  jdBusy.value = true
  pageError.value = ''
  try {
    await api.post(`/training-sessions/${sessionId}/jd`, { jd_text: text })
    jdInput.value = ''
    await training.load()
  } catch (reason) {
    pageError.value = errorMessage(reason)
  } finally {
    jdBusy.value = false
  }
}

async function clearJd(): Promise<void> {
  jdBusy.value = true
  try {
    await api.delete(`/training-sessions/${sessionId}/jd`)
    await training.load()
  } catch (reason) {
    pageError.value = errorMessage(reason)
  } finally {
    jdBusy.value = false
  }
}
const loading = shallowRef(true)
const finishing = shallowRef(false)
const clearingResume = shallowRef(false)
const pageError = shallowRef('')
const finishAfterNext = shallowRef(false)
const mode = shallowRef<'text' | 'voice'>(route.query.mode === 'voice' ? 'voice' : 'text')
const planId = computed(() => String(route.query.planId ?? ''))
const taskKey = computed(() => String(route.query.taskKey ?? ''))
const isPlanTask = computed(() => Boolean(planId.value && taskKey.value))
// 计划任务要求至少 6 轮，提前结束会被后端拒绝
const planMinRounds = 6
const roundsLeft = computed(() => Math.max(0, planMinRounds - (training.session.value?.currentRound ?? 0)))
const stageLabel = computed(() => ({ OPENING: '情景开场', DISCOVERY: '深入追问', CHALLENGE: '情景应对', CLOSING: '沟通收尾' }[training.session.value?.stage ?? 'OPENING'] ?? '训练进行中'))

// 一句话没说就离开的会话直接丢弃，避免留下"进行中 0 轮"的空记录
onBeforeUnmount(() => {
  const current = training.session.value
  if (!current) return
  if (current.status === 'FINISHED' || current.currentRound > 0) return
  void api.delete(`/training-sessions/${current.id}`).catch(() => {})
})

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
      <div><p class="eyebrow">角色演练 · {{ stageLabel }}<span v-if="training.session.value?.mode === 'DRILL'" class="drill-tag">深挖模式</span></p><h1>{{ training.session.value?.sceneTitle || '情景训练' }}</h1><p class="training-subtitle">面对模拟角色，按自己的节奏回答。系统会记录对话并在结束后提供复盘建议。</p></div>
      <div class="heading-actions">
        <button v-if="training.session.value?.status === 'FINISHED'" class="button secondary" type="button" @click="restart">同场景重新开始</button>
        <RouterLink class="back" to="/scenes">退出训练</RouterLink>
      </div>
    </header>
    <div v-if="isPlanTask" class="plan-hint">
      <template v-if="roundsLeft > 0">这是训练计划里的任务：至少完成 {{ planMinRounds }} 轮才能结束，还差 {{ roundsLeft }} 轮。</template>
      <template v-else>已满足计划的 {{ planMinRounds }} 轮要求，可以结束并自动勾掉这项任务。</template>
    </div>
    <div class="mode-bar">
      <div><strong>训练方式</strong><span>{{ mode === 'voice' ? '说出回答，听面试官回应' : '键入回答，按自己的节奏思考' }}</span></div>
    </div>
    <div v-if="training.session.value" class="jd-bar">
      <template v-if="training.session.value.jdText">
        <div><strong>已按目标岗位出题</strong><span>{{ training.session.value.questionTotal }} 个考察点 · 来自岗位描述</span></div>
        <button type="button" :disabled="jdBusy" @click="clearJd">{{ jdBusy ? '处理中…' : '移除 JD' }}</button>
      </template>
      <details v-else>
        <summary>粘贴目标岗位 JD（选填）· 面试官会按岗位考察点出题</summary>
        <textarea v-model="jdInput" class="field" rows="4" maxlength="4000" placeholder="把招聘网站上的岗位职责与要求粘贴进来，至少 20 字" />
        <div class="jd-actions">
          <span>{{ jdInput.trim().length }} / 4000</span>
          <button class="button" type="button" :disabled="jdBusy || jdInput.trim().length < 20" @click="applyJd">{{ jdBusy ? '生成中…' : '生成考察计划' }}</button>
        </div>
      </details>
    </div>
    <div v-if="training.session.value?.jobMatch" class="match-card">
      <header>
        <div class="score"><strong>{{ training.session.value.jobMatch.score }}</strong><span>/100 匹配度</span></div>
        <p v-if="training.session.value.jobMatch.degraded" class="degraded">规则估算（模型暂不可用）</p>
        <p v-else class="degraded">按 JD 与简历对比得出</p>
      </header>
      <div v-if="training.session.value.jobMatch.strengths.length" class="match-block">
        <strong>优势</strong>
        <ul><li v-for="item in training.session.value.jobMatch.strengths" :key="item">{{ item }}</li></ul>
      </div>
      <div v-if="training.session.value.jobMatch.gaps.length" class="match-block">
        <strong>缺口</strong>
        <ul class="gaps">
          <li v-for="gap in training.session.value.jobMatch.gaps" :key="gap.requirement">
            <b>{{ gap.requirement }}</b>
            <span>{{ gap.why }}</span>
            <em>{{ gap.drill }}</em>
          </li>
        </ul>
      </div>
      <div v-if="training.session.value.jobMatch.followUps.length" class="match-block">
        <strong>可能被追问</strong>
        <ul><li v-for="item in training.session.value.jobMatch.followUps" :key="item">{{ item }}</li></ul>
      </div>
    </div>

    <div v-if="training.session.value && training.session.value.questionPlan?.length" class="plan-card">
      <details>
        <summary>本场必问题 · {{ training.session.value.questionPlan.length }} 个</summary>
        <ol class="plan-list">
          <li v-for="(item, index) in training.session.value.questionPlan" :key="index" :class="{ done: index < training.session.value.questionCovered }">
            <span class="num">{{ String(index + 1).padStart(2, '0') }}</span>
            <span class="plan-text">{{ item.text }}</span>
            <span v-if="item.dimension" class="plan-tag">{{ item.dimension }}</span>
          </li>
        </ol>
      </details>
    </div>
    <div v-if="training.session.value && training.session.value.questionTotal" class="coverage-bar">
      <div>
        <strong>必问进度</strong>
        <span>{{ training.session.value.questionCovered }} / {{ training.session.value.questionTotal }} 个必问题已问到</span>
      </div>
      <i class="coverage-track"><b :style="{ width: `${Math.round((training.session.value.questionCovered / training.session.value.questionTotal) * 100)}%` }" /></i>
    </div>
    <div v-if="training.session.value?.resumeFilename" class="resume-bar">
      <div><strong>简历定制面试已开启</strong><span>{{ training.session.value.resumeFilename }} · 面试官会参考其中的真实项目和技术经历</span></div>
      <button type="button" :disabled="clearingResume" @click="clearResume">{{ clearingResume ? '清除中…' : '清除简历内容' }}</button>
    </div>
    <div v-if="training.session.value?.resumeOpeningDegraded" class="model-notice">首题由本地模板生成；请检查大模型配置。后续对话会继续尝试使用大模型结合简历追问。</div>
    <div v-if="pageError || training.error.value" class="error-banner">{{ pageError || training.error.value }}</div>
    <div v-if="training.degraded.value" class="model-notice">本轮由本地教练模板接续。请确认模型服务状态；这轮内容仍可继续训练。</div>
    <div v-if="finishing" class="model-notice">正在生成四维评分，请稍候；报告通常比单轮对话需要更长时间。</div>
    <div v-if="loading" class="panel skeleton dialogue-loading" />
    <DialoguePanel
      v-else-if="training.session.value"
      :session-id="training.session.value.id"
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
.drill-tag { margin-left: 8px; padding: 2px 9px; border-radius: 999px; background: rgba(107,79,160,.12); color: #6b4fa0; font-size: 11px; }
.training-heading { margin-bottom: 20px; padding: 27px 30px; display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; border: 1px solid var(--line); border-radius:var(--radius); background:var(--card); }
.training-heading h1 { margin: 0; font: 700 clamp(26px, 3vw, 34px)/1.2 var(--font-ui); }
.training-subtitle { max-width: 550px; margin: 10px 0 0; color: var(--ink-soft); font-size: 13px; line-height: 1.7; }
.mode-bar { margin-bottom: 17px; padding: 12px 14px 12px 19px; display: flex; align-items: center; justify-content: space-between; gap: 14px; border: 1px solid var(--line); border-radius:var(--radius); background:var(--card); }
.plan-card { padding: 12px 20px; margin-bottom: 14px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--card); }
.plan-card summary { color: var(--text-2); font-size: 12.5px; cursor: pointer; }
.plan-card summary:hover { color: var(--text); }
.plan-list { margin: 12px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.plan-list li { display: grid; grid-template-columns: 26px minmax(0,1fr) auto; align-items: baseline; gap: 12px; color: var(--text-2); font-size: 12.5px; line-height: 1.7; }
.plan-list li.done .plan-text { color: var(--text-3); text-decoration: line-through; text-decoration-thickness: 1px; }
.plan-list .num { color: var(--text-3); font-size: 11px; }
.plan-tag { padding: 2px 7px; border: 1px solid var(--border); border-radius: 4px; color: var(--text-3); font-size: 10.5px; }
.jd-bar { padding: 14px 20px; margin-bottom: 14px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--card); }
.jd-bar strong { color: var(--text); font-size: 13px; font-weight: 500; }
.jd-bar span { margin-left: 10px; color: var(--text-3); font-size: 11.5px; }
.jd-bar > div:first-child { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; }
.jd-bar summary { color: var(--text-2); font-size: 12.5px; cursor: pointer; }
.jd-bar summary:hover { color: var(--text); }
.jd-bar textarea { margin-top: 12px; resize: vertical; }
.jd-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; }
.jd-actions span { color: var(--text-3); font-size: 11px; }
.coverage-bar { display: flex; align-items: center; gap: 20px; padding: 14px 20px; margin-bottom: 14px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--card); }
.coverage-bar strong { display: block; color: var(--text); font-size: 13px; font-weight: 500; }
.coverage-bar span { display: block; margin-top: 4px; color: var(--text-3); font-size: 11.5px; }
.coverage-bar > div { flex: none; }
.coverage-track { flex: 1; height: 2px; background: var(--track); }
.coverage-track b { display: block; height: 100%; background: var(--accent); transition: width .3s var(--ease); }
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

.match-card { margin: 14px 0; padding: 16px 18px; border: 1px solid var(--border); border-radius: 12px; background: var(--card); display: grid; gap: 12px; }
.match-card header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.match-card .score strong { font-size: 30px; font-weight: 750; }
.match-card .score span { margin-left: 6px; color: var(--text-3); font-size: 12px; }
.match-card .degraded { margin: 0; color: var(--text-3); font-size: 11.5px; }
.match-block strong { display: block; margin-bottom: 6px; color: var(--text-3); font-size: 11.5px; letter-spacing: .06em; }
.match-block ul { margin: 0; padding-left: 18px; color: var(--text-2); font-size: 12.5px; line-height: 1.8; }
.match-block .gaps li { margin-bottom: 6px; }
.match-block .gaps b { color: var(--text); font-weight: 600; }
.match-block .gaps span { margin-left: 6px; color: var(--text-2); }
.match-block .gaps em { display: block; color: var(--accent-strong); font-style: normal; font-size: 12px; }

.plan-hint {
  margin: 0 0 14px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-left: 2px solid var(--accent);
  border-radius: 0 8px 8px 0;
  background: var(--bg-2);
  color: var(--text-2);
  font-size: 12.5px;
  line-height: 1.7;
}
</style>

