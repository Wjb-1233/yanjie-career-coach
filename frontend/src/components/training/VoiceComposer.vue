<script setup lang="ts">
import { computed, watch } from 'vue'

import ExpressionPreview from '@/components/training/ExpressionPreview.vue'
import { useBrowserSpeech } from '@/composables/useBrowserSpeech'
import { findExpressionWarnings } from '@/lib/expressionWarnings'
import type { TrainingMessage } from '@/lib/types'

const props = defineProps<{
  latestReply: TrainingMessage | null
  sending: boolean
  finished: boolean
}>()
const emit = defineEmits<{ send: [content: string] }>()
const speech = useBrowserSpeech()
const warnings = computed(() => findExpressionWarnings(speech.transcript.value))
const status = computed(() => {
  if (props.sending) return '面试官正在思考并组织回应…'
  if (speech.listening.value) return '正在听你说话，讲完后点“结束录音”。'
  if (speech.speaking.value) return '面试官正在说话。'
  if (speech.transcript.value.trim()) return '已转成文字。可以修改，再发送给面试官。'
  return props.finished ? '本场面试已结束，可以重播最后一段回复。' : '点击麦克风开始回答本轮问题。'
})

watch(
  () => props.latestReply?.id,
  () => {
    if (props.latestReply?.content && speech.autoRead.value && !props.latestReply.id.startsWith('local-')) {
      speech.speak(props.latestReply.content)
    }
  },
)

function toggleRecording(): void {
  if (speech.listening.value) speech.stop()
  else if (!props.sending && !props.finished) speech.start()
}

function submit(): void {
  const text = speech.transcript.value.trim()
  if (!text || props.sending || props.finished || speech.listening.value) return
  speech.transcript.value = ''
  emit('send', text)
}
</script>

<template>
  <section class="voice-composer" aria-label="语音面试控制台">
    <div class="voice-header">
      <div><p class="eyebrow">语音练习</p><h3>轮流说，更接近真实面试</h3></div>
      <label class="auto-read"><input v-model="speech.autoRead.value" type="checkbox" /> 自动朗读回复</label>
    </div>
    <div v-if="latestReply?.content" class="current-question">
      <strong>面试官</strong>
      <p>{{ latestReply.content }}</p>
    </div>
    <p class="voice-intro">每轮点击麦克风回答，核对识别文字后发送。平台只保存文字对话、不保存录音；手机的语音识别服务可能处理音频。</p>
    <div class="voice-controls">
      <button class="record-button" :class="{ recording: speech.listening.value }" type="button" :aria-pressed="speech.listening.value" :disabled="!speech.available.value || sending || finished" @click="toggleRecording">
        <span class="microphone" aria-hidden="true">{{ speech.listening.value ? '■' : '●' }}</span>
        {{ speech.listening.value ? '结束录音' : '点击说话' }}
      </button>
      <button class="replay-button" type="button" :disabled="!latestReply?.content || speech.listening.value" @click="speech.speaking.value ? speech.stopSpeaking() : speech.speak(latestReply?.content || '')">
        {{ speech.speaking.value ? '停止播报' : '重播提问' }}
      </button>
    </div>
    <p class="voice-status" role="status">{{ status }}</p>
    <p v-if="!speech.available.value" class="voice-error">当前浏览器不支持网页语音识别。请用最新版安卓 Chrome，或切换上方“文字模式”。</p>
    <p v-else-if="!speech.secureContext.value" class="voice-hint">局域网 HTTP 地址可能无法获取麦克风权限；如录音失败，请用提供的 HTTPS 测试地址。</p>
    <p v-if="speech.error.value" class="voice-error" role="alert">{{ speech.error.value }}</p>
    <label class="transcript-label" for="voice-transcript">识别文字 · 发送前可以修改</label>
    <textarea id="voice-transcript" v-model="speech.transcript.value" class="field transcript" rows="3" maxlength="2000" :disabled="sending || finished" placeholder="说完后，识别结果会出现在这里；也可以直接输入文字。" />
    <p v-if="speech.interim.value" class="interim">识别中：{{ speech.interim.value }}</p>
    <ExpressionPreview v-if="warnings.length" :text="speech.transcript.value" :warnings="warnings" />
    <div class="voice-footer"><span>{{ speech.transcript.value.length }} / 2000</span><button class="button" type="button" :disabled="sending || finished || speech.listening.value || !speech.transcript.value.trim()" @click="submit">{{ sending ? '等待面试官…' : '发送本轮回答' }}</button></div>
  </section>
</template>

<style scoped>
.voice-composer { padding: 23px 26px 26px; border-top: 1px solid var(--line); background:var(--card); }
.voice-header { display: flex; align-items: start; justify-content: space-between; gap: 12px; }
.voice-header h3 { margin: 0; font: 700 22px/1.3 var(--font-ui); }
.current-question { margin-top: 16px; padding: 13px 16px; border-left: 3px solid var(--mint-dark); border-radius: 0 12px 12px 0; background: #eef7f3; }
.current-question strong { color: var(--mint-dark); font-size: 11px; letter-spacing: .08em; }
.current-question p { margin: 6px 0 0; max-height: 120px; overflow: auto; color: var(--ink); font-size: 15px; line-height: 1.65; white-space: pre-wrap; }
.auto-read { display: flex; align-items: center; gap: 7px; color: var(--ink-soft); font-size: 12px; white-space: nowrap; cursor: pointer; }
.auto-read input { accent-color: var(--mint-dark); }
.voice-intro { margin: 13px 0 19px; color: var(--ink-soft); font-size: 13px; line-height: 1.65; }
.voice-controls { display: flex; align-items: stretch; gap: 10px; }
.record-button { min-height: 62px; min-width: 185px; padding: 0 18px; display: inline-flex; align-items: center; justify-content: center; gap: 12px; border: 0; border-radius:var(--radius); background: var(--ink); color: white; font-weight: 800; cursor: pointer; }
.record-button.recording { background: #bc4632; }
.record-button:disabled { opacity: .5; cursor: not-allowed; }
.microphone { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 50%; background: var(--overlay-3); color: var(--mint); font-size: 16px; }
.recording .microphone { color: white; animation: pulse 1s ease-in-out infinite; }
.replay-button { min-height: 62px; padding: 0 16px; border: 1px solid var(--line); border-radius:var(--radius); background: var(--bg-2); color: var(--ink); cursor: pointer; font-size: 13px; font-weight: 700; }
.replay-button:disabled { opacity: .5; cursor: not-allowed; }
.voice-status { margin: 12px 0 18px; color: var(--mint-dark); font-size: 13px; font-weight: 700; }
.voice-error, .voice-hint { margin: 10px 0; padding: 10px 12px; border-radius:var(--radius-sm); font-size: 12px; line-height: 1.6; }
.voice-error { background: rgba(192,127,117,.1); color: var(--warn); }
.voice-hint { background: var(--sky); color: var(--mint-dark); }
.transcript-label { display: block; margin-bottom: 8px; color: var(--ink-soft); font-size: 12px; font-weight: 700; }
.transcript { min-height: 93px; resize: vertical; background: var(--bg-2); line-height: 1.7; }
.interim { margin: 7px 0; color: var(--ink-soft); font-size: 12px; }
.voice-footer { margin-top: 11px; display: flex; align-items: center; justify-content: space-between; gap: 10px; color: var(--ink-soft); font-size: 12px; }
.voice-composer { border-color:var(--border);background:var(--card); }
.current-question { border-color:var(--border);background:var(--bg-2); }
.current-question strong { color:var(--text); }
.record-button { background:var(--accent);box-shadow:none;transition:background var(--ease),transform var(--ease); }
.record-button:hover:not(:disabled) { transform:translateY(-1px);background:var(--accent-strong);box-shadow:0 0 12px rgba(91,141,239,.15); }
.record-button.recording { background:#a75d67;box-shadow:none; }
.microphone { color:var(--text); }
.replay-button { border-color:var(--border);background:var(--glass);color:var(--text); }
.voice-status { color:var(--text-2); }
.voice-error { background:rgba(248,113,113,.1);color:#cf9a92; }
.voice-hint { background:var(--bg-2);color:var(--text-2); }
.transcript { background:var(--bg-2); }
@keyframes pulse { 50% { opacity:.65; } }
@media (max-width: 650px) { .voice-composer { padding: 18px; } .voice-header { flex-direction: column; } .voice-controls { display: grid; grid-template-columns: 1fr 1fr; } .record-button { min-width: 0; padding: 0 11px; } .replay-button { padding: 0 8px; } }
@media (prefers-reduced-motion: reduce) { .recording .microphone { animation: none; } }
</style>
