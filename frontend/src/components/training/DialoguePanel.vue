<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, shallowRef, useTemplateRef, watch } from 'vue'

import ExpressionPreview from '@/components/training/ExpressionPreview.vue'
import MarkdownText from '@/components/training/MarkdownText.vue'
import VoiceComposer from '@/components/training/VoiceComposer.vue'
import { api } from '@/lib/api'
import { findExpressionWarnings } from '@/lib/expressionWarnings'
import type { ApiEnvelope, MessageRewrite, TrainingMessage } from '@/lib/types'

const props = defineProps<{
  sessionId: string
  messages: readonly TrainingMessage[]
  currentRound: number
  maxRounds: number
  stage: string
  sending: boolean
  finished: boolean
  flags: readonly string[]
  minimumRounds?: number
  mode: 'text' | 'voice'
  finishAfterNext: boolean
  startedAt?: string
}>()
const emit = defineEmits<{ send: [content: string]; finish: []; report: [] }>()
const input = shallowRef('')
// T-01：整场计时与本题作答计时
const elapsedSeconds = shallowRef(0)
const answerSeconds = shallowRef(0)
let clock: ReturnType<typeof setInterval> | null = null
let answerTick: ReturnType<typeof setInterval> | null = null
const rewrites = shallowRef<Record<number, MessageRewrite>>({})
const rewriting = shallowRef<number | null>(null)
interface Hint { question: string; dimension: string | null; structure: string[]; keywords: string[]; tips: string[] }
const hint = shallowRef<Hint | null>(null)
const hintOpen = shallowRef(false)
const hintLoading = shallowRef(false)

async function toggleHint(): Promise<void> {
  if (hintOpen.value) { hintOpen.value = false; return }
  if (hint.value) { hintOpen.value = true; return }
  hintLoading.value = true
  try {
    const response = await api.post<ApiEnvelope<Hint>>(`/training-sessions/${props.sessionId}/hint`)
    hint.value = response.data.data
    hintOpen.value = true
  } catch {
    // 提示卡失败不打断对话
  } finally {
    hintLoading.value = false
  }
}

async function loadRewrite(roundNo: number): Promise<void> {
  if (rewriting.value !== null) return
  rewriting.value = roundNo
  try {
    const response = await api.post<ApiEnvelope<MessageRewrite>>(
      `/training-sessions/${props.sessionId}/messages/${roundNo}/rewrite`,
    )
    rewrites.value = { ...rewrites.value, [roundNo]: response.data.data }
  } catch {
    // 改写是辅助信息，失败不影响对话
  } finally {
    rewriting.value = null
  }
}
const draftWarnings = computed(() => findExpressionWarnings(input.value))
const timeline = useTemplateRef<HTMLDivElement>('timeline')
const composerInput = useTemplateRef<HTMLTextAreaElement>('composerInput')
const latestReply = computed(() => [...props.messages].reverse().find((message) => message.speaker === 'AI') ?? null)

watch(
  () => props.messages.map((message) => message.content.length).join(','),
  async () => { await nextTick(); timeline.value?.scrollTo({ top: timeline.value.scrollHeight, behavior: 'smooth' }) },
)
watch(input, async () => {
  await nextTick()
  if (!composerInput.value) return
  composerInput.value.style.height = 'auto'
  composerInput.value.style.height = `${Math.min(composerInput.value.scrollHeight, 240)}px`
})

const draftKey = computed(() => `yanjie:draft:${props.sessionId}:${props.currentRound}`)
const remainingRounds = computed(() => Math.max(0, props.maxRounds - props.currentRound))
const elapsedLabel = computed(() => formatClock(elapsedSeconds.value))
const answerLabel = computed(() => formatClock(answerSeconds.value))

function formatClock(total: number): string {
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function restoreDraft(): void {
  try {
    const saved = localStorage.getItem(draftKey.value)
    if (saved) input.value = saved
  } catch {
    // 隐私模式下 localStorage 不可用，忽略即可
  }
}

function clearDraft(): void {
  try { localStorage.removeItem(draftKey.value) } catch { /* 忽略 */ }
}

function startClock(): void {
  const started = props.startedAt ? new Date(props.startedAt).getTime() : Date.now()
  const tick = () => {
    const base = Number.isFinite(started) ? started : Date.now()
    elapsedSeconds.value = Math.max(0, Math.round((Date.now() - base) / 1000))
  }
  tick()
  clock = setInterval(tick, 1000)
}

function startAnswerClock(): void {
  answerSeconds.value = 0
  if (answerTick) clearInterval(answerTick)
  answerTick = setInterval(() => { answerSeconds.value += 1 }, 1000)
}

function stopAnswerClock(): void {
  if (answerTick) { clearInterval(answerTick); answerTick = null }
}

onMounted(() => {
  restoreDraft()
  startClock()
})
onBeforeUnmount(() => {
  if (clock) clearInterval(clock)
  stopAnswerClock()
})

watch(draftKey, () => restoreDraft())
watch(input, (value) => {
  try {
    if (value.trim()) localStorage.setItem(draftKey.value, value)
    else localStorage.removeItem(draftKey.value)
  } catch {
    // 忽略存储失败
  }
})
// 对方问完 → 开始计时；发送后停表
watch(() => props.sending, (sendingNow, wasSending) => {
  if (wasSending && !sendingNow && !props.finished) startAnswerClock()
})

function submit() {
  const content = input.value.trim()
  if (!content || props.sending || props.finished) return
  stopAnswerClock()
  clearDraft()
  input.value = ''
  emit('send', content)
}
</script>

<template>
  <section class="dialogue panel" :class="{ 'voice-mode': mode === 'voice' }">
    <header class="dialogue-header">
      <div>
        <p class="eyebrow">实时演练 · {{ stage }}</p>
        <h2>已完成 {{ currentRound }} <span>/ {{ maxRounds }} 轮</span></h2>
      </div>
      <div class="header-side">
        <div class="timer-row" aria-label="训练计时">
          <span class="timer"><b>{{ elapsedLabel }}</b> 整场</span>
          <span class="timer" :class="{ overtime: answerSeconds >= 180 }"><b>{{ answerLabel }}</b> 本题</span>
          <span class="remaining">剩余 {{ remainingRounds }} 轮</span>
        </div>
      </div>
    </header>

    <div ref="timeline" class="timeline" aria-live="polite">
      <article v-for="(message, index) in messages" :key="message.id" class="message" :class="[message.speaker.toLowerCase(), { flagged: message.flagged, streaming: sending && index === messages.length - 1 && message.speaker === 'AI' }]">
        <span class="speaker">{{ message.speaker === 'AI' ? '情景角色' : '我的回答' }}</span>
        <div class="message-bubble"><MarkdownText v-if="message.content" :text="message.content" /><span v-else>正在组织回应…</span><span v-if="sending && index === messages.length - 1 && message.speaker === 'AI'" class="typing-cursor" aria-hidden="true" /></div>
        <div v-if="message.flags.length" class="message-flags">
          <span v-for="flag in message.flags" :key="flag">{{ flag }}</span>
          <button
            v-if="message.speaker === 'USER' && !rewrites[message.roundNo]"
            class="rewrite-trigger"
            type="button"
            :disabled="rewriting === message.roundNo"
            @click="loadRewrite(message.roundNo)"
          >{{ rewriting === message.roundNo ? '正在改写…' : '这句怎么改？→' }}</button>
        </div>
        <div v-if="message.speaker === 'USER' && rewrites[message.roundNo]" class="rewrite-box">
          <span class="rewrite-label">建议改写</span>
          <p class="rewrite-text">{{ rewrites[message.roundNo].rewrite }}</p>
          <p class="rewrite-reason">{{ rewrites[message.roundNo].reason }}</p>
        </div>
      </article>
    </div>

    <div v-if="flags.length" class="live-warning">
      检测到 {{ flags.join('、') }}，下一轮可尝试“事实—影响—请求”的表达结构。
    </div>

    <VoiceComposer v-if="mode === 'voice'" :latest-reply="latestReply" :sending="sending" :finished="finished" @send="emit('send', $event)" />
    <div v-if="mode === 'voice' && !finished" class="voice-finish">
      <span>{{ finishAfterNext ? '回答当前问题后将结束并生成报告' : `至少回答 ${minimumRounds ?? 2} 轮后，可选择回答下一题即结束` }}</span>
      <button class="button secondary" type="button" :disabled="sending || currentRound < (minimumRounds ?? 0)" @click="emit('finish')">{{ finishAfterNext ? '取消提前结束' : currentRound < (minimumRounds ?? 0) ? `还需 ${(minimumRounds ?? 0) - currentRound} 轮` : '答完下一题结束' }}</button>
    </div>
    <section v-if="mode === 'text' && hintOpen && hint" class="hint-card" aria-live="polite">
      <div class="hint-head">
        <strong>提示卡</strong>
        <span>{{ hint.dimension || '回答结构' }}</span>
        <button type="button" class="hint-close" aria-label="收起提示卡" @click="hintOpen = false">收起</button>
      </div>
      <p class="hint-question">当前问题：{{ hint.question }}</p>
      <ol class="hint-steps"><li v-for="step in hint.structure" :key="step">{{ step }}</li></ol>
      <p class="hint-keywords"><span v-for="word in hint.keywords" :key="word">{{ word }}</span></p>
      <ul class="hint-tips"><li v-for="tip in hint.tips" :key="tip">{{ tip }}</li></ul>
    </section>

    <form v-if="!finished && mode === 'text'" class="composer" @submit.prevent="submit">
      <textarea ref="composerInput" v-model="input" class="field" :class="{ 'at-risk': draftWarnings.length }" rows="3" maxlength="2000" aria-label="输入面试回答" placeholder="像真实面试一样回答。清楚说出经历、行动和结果…" @keydown.ctrl.enter.prevent="submit" />
      <ExpressionPreview v-if="draftWarnings.length" :text="input" :warnings="draftWarnings" />
      <div class="composer-actions">
        <span>{{ input.length }} / 2000 <span class="keyboard-hint">· Ctrl + Enter 发送</span></span>
        <div>
          <button class="button secondary hint-button" type="button" :disabled="sending" @click="toggleHint">
            {{ hintLoading ? '生成提示…' : hintOpen ? '收起提示' : '提示卡' }}
          </button>
          <button
            class="button secondary"
            type="button"
            :disabled="sending || currentRound < (minimumRounds ?? 0)"
            :title="currentRound < (minimumRounds ?? 0) ? `计划任务至少需要 ${minimumRounds} 轮` : ''"
            @click="emit('finish')"
          >{{ finishAfterNext ? '取消提前结束' : currentRound < (minimumRounds ?? 0) ? `还需 ${(minimumRounds ?? 0) - currentRound} 轮` : '答完本题后结束' }}</button>
          <button class="button" type="submit" :disabled="sending || !input.trim()">{{ sending ? '对方回应中…' : finishAfterNext ? '发送回答并结束' : '发送回答' }}</button>
        </div>
      </div>
    </form>
    <div v-if="finished" class="finished-block">
      <strong>本场训练已完成</strong>
      <span>现在可以查看四维评分与逐轮改写建议。</span>
      <button class="button signal" type="button" :disabled="sending" @click="emit('report')">{{ sending ? '报告生成中…' : '生成训练报告' }}</button>
    </div>
  </section>
</template>

<style scoped>
.hint-card { margin: 12px 0; padding: 12px 14px; border: 1px solid var(--accent); border-radius: 12px; background: var(--accent-soft); display: grid; gap: 8px; }
.hint-head { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--accent-strong); }
.hint-head span { color: var(--text-2); }
.hint-close { margin-left: auto; border: 0; background: transparent; color: var(--text-3); font-size: 11.5px; cursor: pointer; }
.hint-question { margin: 0; font-size: 12.5px; color: var(--text); }
.hint-steps { margin: 0; padding-left: 18px; font-size: 12.5px; color: var(--text-2); display: grid; gap: 3px; }
.hint-keywords { display: flex; flex-wrap: wrap; gap: 6px; margin: 0; }
.hint-keywords span { padding: 2px 8px; border: 1px solid var(--border); border-radius: 999px; font-size: 11.5px; color: var(--text-2); background: var(--surface); }
.hint-tips { margin: 0; padding-left: 16px; color: var(--text-3); font-size: 11.5px; display: grid; gap: 2px; }
.dialogue { overflow: hidden; box-shadow: 0 13px 40px rgba(16,37,43,.07); }
.dialogue.voice-mode { display: flex; flex-direction: column; }
.voice-mode .dialogue-header { order: 0; }
.voice-mode .voice-composer { order: 1; border-top: 0; }
.voice-mode .voice-finish, .voice-mode .finished-block { order: 2; }
.voice-mode .live-warning { order: 3; }
.voice-mode .timeline { order: 4; height: 220px; min-height: 0; border-top: 1px solid var(--line); }
.dialogue-header { min-height: 92px; padding: 20px 28px; display: flex; align-items: center; justify-content: space-between; gap: 24px; border-bottom: 1px solid var(--line); background: var(--bg-2); }
.dialogue-header h2 { margin: 0; font: 700 27px/1 var(--font-ui); }
.dialogue-header h2 span { color: #8ca29d; font-size: 16px; }
.round-rail { display: flex; align-items: flex-end; gap: 5px; }
.round-rail i { display: block; width: 5px; height: 18px; border-radius: 99px; background: #dce7e3; }
.round-rail i:nth-child(3n) { height: 29px; }
.round-rail i.active { background: var(--mint-dark); }
.timeline { height: min(56vh, 570px); min-height: 390px; padding: 30px; overflow-y: auto; display: flex; flex-direction: column; gap: 21px; background: linear-gradient(150deg, #f1f7f4 0%, #f7f9f7 55%, #eef5f2 100%); }
.message { width: min(76%, 620px); }
.message.user { align-self: flex-end; }
.speaker { display: block; margin: 0 8px 7px; color: var(--mint-dark); font-size: 11px; font-weight: 800; letter-spacing: .06em; }
.message.user .speaker { text-align: right; }
.message p { margin: 0; padding: 17px 19px; border: 1px solid var(--line); border-radius: 5px 17px 17px 17px; background:var(--card); box-shadow: 0 6px 18px rgba(16,37,43,.045); line-height: 1.8; white-space: pre-wrap; }
.message.user p { border-color: var(--ink); border-radius: 17px 5px 17px 17px; background: var(--ink); color: white; }
.message.user.flagged p { border:2px solid var(--danger); box-shadow:0 0 0 3px var(--danger)1c; }
.dialogue-header { background:var(--card); }
.dialogue-header h2 { font: 750 23px/1.25 var(--font-ui); }
.round-rail i { background: var(--track); }
.round-rail i.active { background: var(--primary); }
.timeline { background: var(--bg-2); }
.message { position: relative; width: min(78%, 620px); padding-left: 40px; }
.message.user { padding-left: 0; padding-right: 40px; }
.message::before { content: 'AI'; position: absolute; top: 20px; left: 0; display: grid; width: 30px; height: 30px; place-items: center; border-radius:var(--radius-sm); background: var(--border); color: var(--primary-hover); font-size: 11px; font-weight: 800; }
.message.user::before { content: '我'; left: auto; right: 0; background: var(--primary); color: white; }
.speaker { color: var(--text-2); }
.message-bubble { padding: 15px 17px; border: 1px solid var(--border); border-radius:var(--radius); background:var(--card); box-shadow: var(--shadow); line-height: 1.75; }
.message.user .message-bubble { border-color: var(--border); background: var(--primary-soft); color: var(--text); }
.message.user.flagged .message-bubble { border-color: rgba(192,127,117,.5); }
.typing-cursor { display: inline-block; width: 2px; height: 1em; margin-left: 3px; vertical-align: -.15em; background: var(--primary); animation: blink .7s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }
.composer { position: sticky; bottom: 0; z-index: 2; background:var(--card); }
.composer textarea { min-height: 76px; max-height: 240px; background:var(--card); resize: vertical; }
.message-flags { margin-top: 8px; display: flex; justify-content: flex-end; gap: 6px; }
.message-flags span, .live-warning { color: var(--warn); font-size: 12px; }
.live-warning { padding: 10px 24px; border-top: 1px solid var(--border); background: rgba(192,127,117,.1); }
.composer { padding: 20px 26px 23px; border-top: 1px solid var(--line); background:var(--card); }
.composer textarea { min-height: 115px; resize: vertical; background: var(--bg-2); line-height: 1.7; }
.composer textarea.at-risk { border-color:var(--danger); box-shadow:0 0 0 2px var(--danger)22; }
.composer-actions { margin-top: 10px; display: flex; align-items: center; justify-content: space-between; color: var(--ink-soft); font-size: 12px; }
.keyboard-hint { color: #839994; }
.composer-actions div { display: flex; gap: 8px; }
.voice-finish { padding: 13px 26px 21px; display: flex; align-items: center; justify-content: space-between; gap: 12px; background:var(--card); color: var(--ink-soft); font-size: 12px; }
.finished-block { padding: 22px; display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 14px; border-top: 1px solid var(--line); background: var(--sky); }
.finished-block span { color: var(--ink-soft); font-size: 13px; }
.dialogue { border-color:var(--border);box-shadow:var(--shadow); }
.dialogue-header { border-color:var(--divider);background:var(--card); }
.dialogue-header h2 span { color:var(--text-2); }
.round-rail i { background:var(--track); }
.round-rail i.active { background:var(--muted-progress);box-shadow:none; }
.timeline { background:var(--bg-2); }
.message { animation:message-in .4s cubic-bezier(.2,.7,.2,1) both; }
.message:nth-child(3n + 2) { animation-delay:.055s; }
.message:nth-child(3n + 3) { animation-delay:.1s; }
.message::before { content:'';top:19px;left:0;width:32px;height:32px;border-radius:50%;background:var(--raised);animation:none;box-shadow:none; }
.message::after { content:'AI';position:absolute;top:22px;left:3px;display:grid;width:26px;height:26px;place-items:center;border-radius:50%;background:var(--bg-2);color:var(--text-2);font-size:10px;font-weight:650; }
.message.user::before { left:auto;right:0;background:var(--raised);animation:none; }
.message.user::after { content:'我';left:auto;right:3px; }
.speaker { color:var(--text-3); }
.message-bubble { border:1px solid var(--border);border-radius:var(--radius);background:var(--card);box-shadow:none;color:var(--text); }
.message.user .message-bubble { border-color:var(--border-bright);background:var(--card-2);color:var(--text); }
.message.user.flagged .message-bubble { border-color:rgba(248,113,113,.65); }
.typing-cursor { background:var(--accent);box-shadow:none; }
.composer { border-color:var(--divider);background:var(--card);backdrop-filter:none; }
.composer textarea { background:var(--bg-2);border-color:var(--border); }
.composer textarea.at-risk { border-color:rgba(248,113,113,.55);box-shadow:0 0 0 2px rgba(248,113,113,.12); }
.keyboard-hint { color:var(--text-3); }
.live-warning { border-color:var(--border);background:var(--card-2);color:var(--warning); }
.voice-finish { background:var(--card); }
.finished-block { background:var(--bg-2); }
@keyframes message-in { from { opacity:0;transform:translateY(12px) scale(.985); } to { opacity:1;transform:translateY(0) scale(1); } }
@media (max-width: 650px) {
  .dialogue-header { padding: 20px; align-items: flex-start; flex-direction: column; gap: 13px; }
  .message { width: 100%; }
  .timeline { min-height: 330px; height: 48vh; padding: 18px; }
  .composer { padding: 18px; }
  .voice-finish { padding: 12px 18px 20px; align-items: stretch; flex-direction: column; }
  .finished-block { grid-template-columns: 1fr; }
  .composer-actions { align-items: flex-start; gap: 10px; }
  .composer-actions div { flex-direction: column; }
  .keyboard-hint { display: none; }
  .message::before { animation-duration:14s; }
}
@media (prefers-reduced-motion:reduce) { .message,.message::before { animation:none; } }

.message-flags { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px; }
.rewrite-trigger {
  padding: 2px 8px;
  border: 1px solid var(--border-bright);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-2);
  font-size: 11px;
  cursor: pointer;
  transition: border-color .16s var(--ease), color .16s var(--ease), background .16s var(--ease);
}
.rewrite-trigger:hover { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.rewrite-trigger:disabled { opacity: .5; cursor: default; }
.message .rewrite-box {
  margin-top: 10px;
  padding: 12px 14px;
  border-left: 2px solid var(--accent);
  border-radius: var(--radius-sm);
  background: var(--card-2);
}
.message .rewrite-box .rewrite-label { color: var(--accent-strong); font-size: 10px; letter-spacing: .18em; }
.message .rewrite-box .rewrite-text {
  margin: 6px 0 0;
  padding: 0 !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  color: var(--text) !important;
  font-size: 13px;
  line-height: 1.9;
  white-space: pre-wrap;
}
.message .rewrite-box .rewrite-reason {
  margin: 6px 0 0;
  padding: 0 !important;
  border: 0 !important;
  border-radius: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  color: var(--text-3) !important;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.header-side { display: grid; gap: 10px; justify-items: end; }
.timer-row { display: flex; align-items: center; gap: 14px; color: var(--text-3); font-size: 11.5px; letter-spacing: .02em; }
.timer-row b { color: var(--text); font-family: var(--font-num); font-size: 13px; font-variant-numeric: tabular-nums; }
.timer-row .overtime b { color: var(--accent-strong); }
.remaining { padding: 2px 8px; border: 1px solid var(--border); border-radius: 999px; }
@media (max-width: 720px) {
  .timer-row { gap: 8px; font-size: 10.5px; }
  .remaining { display: none; }
}
</style>
<style scoped>
.dialogue-header { padding: 20px 26px; }
.dialogue-header h2 { font-size: 20px; }
.dialogue-header .eyebrow { font-size: 12px; }
.timeline { height: min(46vh, 440px); min-height: 300px; padding: 24px 26px; }
.message-bubble { max-width: 78%; font-size: 15px; line-height: 1.8; }
.message.user .message-bubble { margin-left: auto; }
.message .speaker { font-size: 12px; }
.composer { padding: 16px 24px 20px; }
.composer textarea { min-height: 92px; }
.composer-actions { font-size: 12.5px; }
@media (max-width: 720px) { .timeline { height: 40vh; min-height: 240px; padding: 16px; } .message-bubble { max-width: 90%; } }
</style>
