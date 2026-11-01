<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Mic, PhoneOff } from 'lucide-vue-next'

import { api } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'

type Status = 'idle' | 'connecting' | 'live' | 'error'
type Engine = 'doubao' | 'pipeline'

const route = useRoute()
const router = useRouter()
const scene = shallowRef<Scene | null>(null)
const sceneId = computed(() => (typeof route.query.sceneId === 'string' ? route.query.sceneId : ''))
const planId = computed(() => (typeof route.query.planId === 'string' ? route.query.planId : ''))
const taskKey = computed(() => (typeof route.query.taskKey === 'string' ? route.query.taskKey : ''))
const status = shallowRef<Status>('idle')
const engine = shallowRef<Engine>('doubao')
const error = shallowRef('')
const heard = shallowRef('')
const reply = shallowRef('')
const rounds = shallowRef(0)
const turns = shallowRef<Array<{ question: string; answer: string }>>([])
let lastAnswer = ''
let lastQuestion = ''
const saving = shallowRef(false)
let startedAt = 0
const micOn = shallowRef(false)

let socket: WebSocket | null = null
let audioContext: AudioContext | null = null
let playbackContext: AudioContext | null = null
let micStream: MediaStream | null = null
let processor: ScriptProcessorNode | null = null
let source: MediaStreamAudioSourceNode | null = null
let playbackAt = 0
let pending = new Float32Array(0)
let recorder: MediaRecorder | null = null
const recordedChunks: Blob[] = []

const canStart = computed(() => status.value === 'idle' || status.value === 'error')

function instructions(): string {
  const current = scene.value
  const base = '你是一名中文面试官，正在模拟真实面试。候选人说话后，你先简短回应，再追问一个具体问题，每次不超过 60 字。不要自问自答，不要长时间独白。'
  if (!current) return base
  return `${base}本场场景：${current.title}（${current.category}）。你的角色：${current.roleName}。场景背景：${current.background}。考察目标：${current.goal}。请始终围绕这个场景提问。`
}

function openingLine(): string {
  const current = scene.value
  if (!current) return '你好，我是今天的面试官，请先做个自我介绍。'
  return `你好，我是${current.roleName}，今天这场是${current.category}。${current.openingLine || '请先简单介绍一下自己。'}`
}

function wsUrl(): string {
  if (engine.value === 'pipeline') {
    const base = import.meta.env.VITE_API_BASE ?? '/api/v1'
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
    const query = sceneId.value ? `?sceneId=${sceneId.value}` : ''
    return `${scheme}://${location.host}${base}/voice/ws/pipeline${query}`
  }
  const base = import.meta.env.VITE_API_BASE ?? '/api/v1'
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${scheme}://${location.host}${base}/voice/ws`
}

function toBase64(buffer: ArrayBuffer): string {
  let binary = ''
  const bytes = new Uint8Array(buffer)
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i])
  return btoa(binary)
}

function fromBase64(text: string): Uint8Array {
  const binary = atob(text)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i)
  return bytes
}

function playPcm(base64: string): void {
  if (!playbackContext) playbackContext = new AudioContext({ sampleRate: 24000 })
  const bytes = fromBase64(base64)
  const samples = new Float32Array(bytes.length / 2)
  const view = new DataView(bytes.buffer)
  for (let i = 0; i < samples.length; i += 1) samples[i] = view.getInt16(i * 2, true) / 32768

  const buffer = playbackContext.createBuffer(1, samples.length, 24000)
  buffer.copyToChannel(samples, 0)
  const node = playbackContext.createBufferSource()
  node.buffer = buffer
  node.connect(playbackContext.destination)
  playbackAt = Math.max(playbackAt, playbackContext.currentTime + 0.05)
  node.start(playbackAt)
  playbackAt += buffer.duration
}

function handleEvent(raw: string): void {
  let event: Record<string, unknown>
  try {
    event = JSON.parse(raw)
  } catch {
    return
  }
  const type = String(event.type ?? '')
  if (engine.value === 'pipeline') {
    if (type === 'user' && event.text) {
      heard.value = String(event.text)
      lastAnswer = String(event.text)
    } else if (type === 'assistant_delta' && event.text) {
      reply.value = `${reply.value}${event.text}`
    } else if (type === 'assistant_end') {
      lastQuestion = reply.value
      if (lastAnswer.trim()) {
        turns.value = [...turns.value, { question: lastQuestion, answer: lastAnswer }]
        lastAnswer = ''
      }
      rounds.value += 1
    }
    return
  }
  if (type === 'session.created') {
    // 让面试官先说第一句，用户马上能听到声音
    socket?.send(JSON.stringify({ type: 'speech_text_buffer.commit', text: openingLine() }))
  }
  if (type.endsWith('transcription.delta')) {
    heard.value = `${heard.value}${event.delta ?? ''}`
  } else if (type.endsWith('transcription.completed')) {
    lastAnswer = String(event.transcript ?? heard.value)
    heard.value = lastAnswer
  } else if (type === 'response.output_text.done') {
    reply.value = String(event.text ?? '')
    lastQuestion = reply.value
    if (lastAnswer.trim()) {
      turns.value = [...turns.value, { question: lastQuestion, answer: lastAnswer }]
      lastAnswer = ''
    }
    rounds.value += 1
  } else if (type === 'response.output_audio.delta') {
    playPcm(String(event.delta ?? ''))
  } else if (type === 'error') {
    error.value = JSON.stringify(event.error ?? event).slice(0, 200)
  }
}

async function start(): Promise<void> {
  status.value = 'connecting'
  error.value = ''
  heard.value = ''
  reply.value = ''
  rounds.value = 0

  const info = await api.get<ApiEnvelope<{ enabled: boolean; voice: string }>>('/voice/status')
  if (!info.data.data.enabled) {
    status.value = 'error'
    error.value = '语音服务未配置'
    return
  }

  socket = new WebSocket(wsUrl())
  socket.onopen = async () => {
    if (engine.value === 'doubao') {
      reply.value = openingLine()  // 开场白是纯语音，先把字幕补上
      socket?.send(
      JSON.stringify({
        type: 'session.create',
        session: {
          model: '1.2.6.1',
          instructions: instructions(),
          audio: {
            input: { format: { type: 'pcm', rate: 16000 } },
            output: { format: { type: 'pcm_s16le', rate: 24000 }, voice: info.data.data.voice },
          },
        },
        extension: { asr: { extra: {} }, tts: {}, dialog: {} },
        }),
      )
    }
    status.value = 'live'
    startedAt = Date.now()
    await startMic()
  }
  socket.onmessage = (message) => handleEvent(String(message.data))
  socket.onerror = () => {
    status.value = 'error'
    error.value = '连接语音服务失败'
  }
  let wasLive = false
  socket.onclose = (event) => {
    status.value = status.value === 'error' ? 'error' : 'idle'
    micOn.value = false
    const reasons: Record<number, string> = {
      4001: '语音服务未配置，请联系管理员',
      4003: '语音服务已断开，请重新开始',
      4004: '语音服务暂时不可用，请稍后重试',
      4005: '语音管线启动失败，可切换到标准引擎',
      4029: '当前语音并发已满，请稍后再试',
    }
    if (reasons[event.code]) {
      status.value = 'error'
      error.value = reasons[event.code]
    } else if (wasLive) {
      status.value = 'error'
      error.value = '语音连接已断开，请重新开始'
    }
    wasLive = false
  }
}

async function startMic(): Promise<void> {
  micStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } })
  audioContext = new AudioContext()
  source = audioContext.createMediaStreamSource(micStream)
  if (typeof MediaRecorder !== 'undefined') {
    recordedChunks.length = 0
    recorder = new MediaRecorder(micStream)
    recorder.ondataavailable = (event) => { if (event.data.size) recordedChunks.push(event.data) }
    recorder.start(1000)
  }
  processor = audioContext.createScriptProcessor(1024, 1, 1)
  processor.onaudioprocess = (event) => {
    if (socket?.readyState !== WebSocket.OPEN || !audioContext) return
    const input = event.inputBuffer.getChannelData(0)
    const resampled = resample(input, audioContext.sampleRate, 16000)
    const merged = new Float32Array(pending.length + resampled.length)
    merged.set(pending)
    merged.set(resampled, pending.length)
    let offset = 0
    // 每包 320 个采样点 = 20ms @16k
    while (merged.length - offset >= 320) {
      const chunk = merged.subarray(offset, offset + 320)
      const pcm = new Int16Array(chunk.length)
      for (let i = 0; i < chunk.length; i += 1) {
        pcm[i] = Math.max(-1, Math.min(1, chunk[i])) * 0x7fff
      }
      socket.send(JSON.stringify({ type: 'input_audio_buffer.append', audio: toBase64(pcm.buffer) }))
      offset += 320
    }
    pending = merged.slice(offset)
  }
  source.connect(processor)
  processor.connect(audioContext.destination)
  micOn.value = true
}

function resample(input: Float32Array, from: number, to: number): Float32Array {
  if (Math.abs(from - to) < 1) return input
  const ratio = from / to
  const length = Math.floor(input.length / ratio)
  const output = new Float32Array(length)
  for (let i = 0; i < length; i += 1) {
    const position = i * ratio
    const index = Math.floor(position)
    const next = Math.min(index + 1, input.length - 1)
    const weight = position - index
    output[i] = input[index] * (1 - weight) + input[next] * weight
  }
  return output
}

async function stopAndReport(): Promise<void> {
  if (saving.value) return
  saving.value = true
  error.value = ''
  const pending = lastAnswer.trim() ? [...turns.value, { question: lastQuestion, answer: lastAnswer }] : turns.value
  try {
    if (!pending.length) {
      error.value = '这次通话还没有可评分的内容'
      saving.value = false
      return
    }
    const form = new FormData()
    form.append('sceneId', sceneId.value)
    form.append('turns', JSON.stringify(pending))
    form.append('engine', engine.value)
    form.append('durationSeconds', String(startedAt ? Math.round((Date.now() - startedAt) / 1000) : 0))
    if (recordedChunks.length) {
      form.append('audio', new Blob(recordedChunks, { type: 'audio/webm' }), 'voice.webm')
    }
    const saved = await api.post<ApiEnvelope<{ id: string }>>('/voice/sessions', form, { timeout: 120000 })
    const sessionId = saved.data.data.id
    await api.post(`/training-sessions/${sessionId}/finish`)
    if (planId.value && taskKey.value) {
      await api
        .post(`/training-plans/${planId.value}/tasks/${taskKey.value}/complete`, { evidence: sessionId })
        .catch(() => undefined)
    }
    stop()
    await router.push(`/report/${sessionId}`)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '生成报告失败'
  } finally {
    saving.value = false
  }
}

function stop(): void {
  try { recorder?.state !== 'inactive' && recorder?.stop() } catch { /* 忽略 */ }
  recorder = null
  processor?.disconnect()
  source?.disconnect()
  audioContext?.close()
  micStream?.getTracks().forEach((track) => track.stop())
  processor = null
  source = null
  audioContext = null
  micStream = null
  micOn.value = false
  socket?.close()
  socket = null
  status.value = 'idle'
}

function interrupt(): void {
  if (engine.value === 'pipeline') {
    socket?.send(new ArrayBuffer(0))
  } else {
    socket?.send(JSON.stringify({ type: 'response.cancel' }))
  }
  reply.value = ''
}

onMounted(() => {
  if (sceneId.value) {
    void api
      .get<ApiEnvelope<Scene[]>>('/scenes', { params: { size: 100 } })
      .then((response) => {
        scene.value = response.data.data.find((item) => item.id === sceneId.value) ?? null
      })
      .catch(() => {
        scene.value = null
      })
  }
  void api
    .get<ApiEnvelope<{ enabled: boolean }>>('/voice/status')
    .then((response) => {
      if (!response.data.data.enabled) error.value = '语音服务未配置，请检查后端环境变量'
    })
    .catch(() => {
      error.value = '无法读取语音服务状态'
    })
})

onBeforeUnmount(stop)
</script>

<template>
  <div class="page voice-page">
    <RouterLink class="back" to="/scenes"><ArrowLeft :size="13" :stroke-width="1.8" aria-hidden="true" /> 返回场景训练</RouterLink>

    <header class="page-heading">
      <div>
        <p class="eyebrow">语音对练{{ scene ? ` · ${scene.category}` : '' }}</p>
        <h1 class="page-title">{{ scene ? scene.title : '像打电话一样' }}</h1>
        <p class="page-lead">直接说话，{{ scene ? scene.roleName : '面试官' }}会实时回应；打断他说话也没关系。</p>
      </div>
      <div class="engine-switch" role="group" aria-label="语音引擎">
        <button type="button" :class="{ active: engine === 'doubao' }" :disabled="status !== 'idle' && status !== 'error'" @click="engine = 'doubao'">标准引擎</button>
        <button type="button" :class="{ active: engine === 'pipeline' }" :disabled="status !== 'idle' && status !== 'error'" @click="engine = 'pipeline'">本地管线</button>
      </div>
      <span class="status" :class="status">{{ status === 'live' ? '通话中' : status === 'connecting' ? '接通中' : '未开始' }}</span>
    </header>

    <p v-if="error" class="error-banner">{{ error }}</p>

    <section class="call panel">
      <div class="wave" :class="{ active: status === 'live' }" aria-hidden="true">
        <i v-for="index in 24" :key="index" :style="{ animationDelay: `${index * 40}ms` }" />
      </div>

      <div class="transcript">
        <div class="line">
          <span class="who">我</span>
          <p>{{ heard || (status === 'live' ? '请开始说话…' : '点击开始后对着麦克风说话') }}</p>
        </div>
        <div class="line reply">
          <span class="who">面试官</span>
          <p>{{ reply || '—' }}</p>
        </div>
      </div>

      <div class="controls">
        <button v-if="canStart" class="button call-btn" type="button" @click="start">
          <Mic :size="16" :stroke-width="1.8" aria-hidden="true" />
          开始语音对练
        </button>
        <template v-else>
          <button class="button secondary" type="button" :disabled="!reply" @click="interrupt">打断</button>
          <button class="button call-btn end" type="button" :disabled="saving" @click="stopAndReport">
            <PhoneOff :size="16" :stroke-width="1.8" aria-hidden="true" />
            {{ saving ? '生成报告中…' : '结束并生成报告' }}
          </button>
        </template>
      </div>

      <p class="hint">
        {{ micOn ? '麦克风已开启，直接说话即可；说完停一下，面试官会接话。' : '需要浏览器麦克风权限。' }}
        <span v-if="rounds">已进行 {{ rounds }} 轮</span>
        <span class="privacy">本次通话会被录音，仅用于生成评分报告</span>
      </p>
    </section>
  </div>
</template>

<style scoped>
.voice-page { max-width: 880px; }
.back { display: inline-flex; align-items: center; gap: 6px; margin-bottom: 18px; color: var(--text-3); font-size: 12px; }
.engine-switch { display: inline-flex; gap: 6px; align-self: flex-start; margin-top: 6px; padding: 4px; border: 1px solid var(--border); border-radius: 999px; }
.engine-switch button { padding: 5px 14px; border: 0; border-radius: 999px; background: transparent; color: var(--text-3); font-size: 12px; cursor: pointer; }
.engine-switch button.active { background: var(--accent); color: #fff; }
.engine-switch button:disabled { opacity: .5; cursor: not-allowed; }
.status { align-self: flex-start; margin-top: 6px; padding: 6px 14px; border: 1px solid var(--border); border-radius: 999px; color: var(--text-3); font-size: 12px; }
.status.live { border-color: var(--accent); color: var(--accent-strong); }
.call { margin-top: 8px; padding: 28px; display: grid; gap: 22px; }
.wave { display: flex; align-items: center; justify-content: center; gap: 4px; height: 78px; }
.wave i { width: 3px; height: 12px; border-radius: 99px; background: var(--text-3); opacity: .35; }
.wave.active i { opacity: 1; background: var(--accent); animation: pulse 1.1s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { height: 10px; } 50% { height: 46px; } }
@media (prefers-reduced-motion: reduce) { .wave.active i { animation: none; height: 24px; } }
.transcript { display: grid; gap: 14px; }
.line { display: grid; grid-template-columns: 52px minmax(0, 1fr); gap: 12px; align-items: start; }
.who { color: var(--text-3); font-size: 12px; padding-top: 4px; }
.line p { margin: 0; padding: 14px 16px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-2); color: var(--text); line-height: 1.8; min-height: 48px; }
.line.reply p { background: var(--card); }
.controls { display: flex; gap: 12px; }
.call-btn { display: inline-flex; align-items: center; gap: 8px; }
.call-btn.end { background: var(--accent); border-color: var(--accent); }
.hint { margin: 0; color: var(--text-3); font-size: 12px; display: flex; gap: 12px; }
.privacy { margin-left: auto; color: var(--text-3); }
</style>
