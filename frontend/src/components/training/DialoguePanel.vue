<script setup lang="ts">
import { computed, nextTick, shallowRef, useTemplateRef, watch } from 'vue'

import ExpressionPreview from '@/components/training/ExpressionPreview.vue'
import MarkdownText from '@/components/training/MarkdownText.vue'
import VoiceComposer from '@/components/training/VoiceComposer.vue'
import { findExpressionWarnings } from '@/lib/expressionWarnings'
import type { TrainingMessage } from '@/lib/types'

const props = defineProps<{
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
}>()
const emit = defineEmits<{ send: [content: string]; finish: []; report: [] }>()
const input = shallowRef('')
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

function submit() {
  const content = input.value.trim()
  if (!content || props.sending || props.finished) return
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
      <div class="round-rail" aria-label="训练轮次进度">
        <i v-for="round in maxRounds" :key="round" :class="{ active: round <= currentRound }" />
      </div>
    </header>

    <div ref="timeline" class="timeline" aria-live="polite">
      <article v-for="(message, index) in messages" :key="message.id" class="message" :class="[message.speaker.toLowerCase(), { flagged: message.flagged, streaming: sending && index === messages.length - 1 && message.speaker === 'AI' }]">
        <span class="speaker">{{ message.speaker === 'AI' ? '情景角色' : '我的回答' }}</span>
        <div class="message-bubble"><MarkdownText v-if="message.content" :text="message.content" /><span v-else>正在组织回应…</span><span v-if="sending && index === messages.length - 1 && message.speaker === 'AI'" class="typing-cursor" aria-hidden="true" /></div>
        <div v-if="message.flags.length" class="message-flags">
          <span v-for="flag in message.flags" :key="flag">{{ flag }}</span>
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
    <form v-if="!finished && mode === 'text'" class="composer" @submit.prevent="submit">
      <textarea ref="composerInput" v-model="input" class="field" :class="{ 'at-risk': draftWarnings.length }" rows="3" maxlength="2000" aria-label="输入面试回答" placeholder="像真实面试一样回答。清楚说出经历、行动和结果…" @keydown.ctrl.enter.prevent="submit" />
      <ExpressionPreview v-if="draftWarnings.length" :text="input" :warnings="draftWarnings" />
      <div class="composer-actions">
        <span>{{ input.length }} / 2000 <span class="keyboard-hint">· Ctrl + Enter 发送</span></span>
        <div>
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
      <span>现在可以查看五维评分与逐轮改写建议。</span>
      <button class="button signal" type="button" :disabled="sending" @click="emit('report')">{{ sending ? '报告生成中…' : '生成训练报告' }}</button>
    </div>
  </section>
</template>

<style scoped>
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
</style>

