<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { Mic, PhoneOff } from 'lucide-vue-next'

import { api } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'

type Status = 'connecting' | 'live' | 'error' | 'saving'
type Engine = 'doubao' | 'pipeline'

const props = defineProps<{
  mode: 'voice' | 'video'
  scene: Scene | null
  engine: Engine
  durationMinutes: number
}>()

const emit = defineEmits<{ ended: [sessionId: string]; failed: [message: string] }>()

const status = shallowRef<Status>('connecting')
const error = shallowRef('')
const heard = shallowRef('')
const reply = shallowRef('')
const rounds = shallowRef(0)
const micOn = shallowRef(false)
const remaining = shallowRef(props.durationMinutes * 60)
const preview = ref<HTMLVideoElement | null>(null)

const turns = shallowRef<Array<{ question: string; answer: string }>>([])
let lastAnswer = ''
let lastQuestion = ''
let startedAt = 0

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
let countdown: ReturnType<typeof setInterval> | null = null
let closing = false

const isVideo = computed(() => props.mode === 'video')
const timeLabel = computed(() => {
  const total = Math.max(0, remaining.value)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
})
const statusLabel = computed(() => {
  if (status.value === 'connecting') return '正在接通面试官'
  if (status.value === 'saving') return '正在整理报告'
  if (status.value === 'error') return '连接异常'
  return isVideo.value ? '视频面试进行中' : '语音面试进行中'
})

function instructions(): string {
  const current = props.scene
  const base = '你是一名中文面试官，正在模拟真实面试。候选人说话后，你先简短回应，再追问一个具体问题，每次不超过 60 字。不要自问自答，不要长时间独白。'
  if (!current) return base
  return `${base}本场场景：${current.title}（${current.category}）。你的角色：${current.roleName}。场景背景：${current.background}。考察目标：${current.goal}。请始终围绕这个场景提问。`
}

function openingLine(): string {
  const current = props.scene
  if (!current) return '你好，我是今天的面试官，请先做个自我介绍。'
  return `你好，我是${current.roleName}，今天这场是${current.category}。${current.openingLine || '请先简单介绍一下自己。'}`
}

function wsUrl(): string {
  const base = import.meta.env.VITE_API_BASE ?? '/api/v1'
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  if (props.engine === 'pipeline') {
    const query = props.scene?.id ? `?sceneId=${props.scene.id}` : ''
    return `${scheme}://${location.host}${base}/voice/ws/pipeline${query}`
  }
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
  if (props.engine === 'pipeline') {
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
    // 一接通就让面试官先开口，用户听到问题再回答
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
  remaining.value = props.durationMinutes * 60

  try {
    const info = await api.get<ApiEnvelope<{ enabled: boolean; voice: string }>>('/voice/status')
    if (!info.data.data.enabled) {
      fail('语音服务未配置，请联系管理员')
      return
    }

    socket = new WebSocket(wsUrl())
    socket.onopen = async () => {
      if (props.engine === 'doubao') {
        reply.value = openingLine() // 开场白是纯语音，先把字幕补上
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
      beginCountdown()
    }
    socket.onmessage = (message) => handleEvent(String(message.data))
    socket.onerror = () => fail('连接语音服务失败')
    socket.onclose = (event) => {
      if (closing) return
      micOn.value = false
      const reasons: Record<number, string> = {
        4001: '语音服务未配置，请联系管理员',
        4003: '语音服务已断开，请重新开始',
        4004: '语音服务暂时不可用，请稍后重试',
        4005: '语音管线启动失败，可换标准引擎再试',
        4029: '当前语音并发已满，请稍后再试',
      }
      fail(reasons[event.code] ?? '连接已断开，请重新开始面试')
    }
  } catch {
    fail('无法读取语音服务状态')
  }
}

function fail(message: string): void {
  status.value = 'error'
  error.value = message
  stop()
}

function beginCountdown(): void {
  if (countdown) clearInterval(countdown)
  countdown = setInterval(() => {
    remaining.value -= 1
    if (remaining.value <= 0) {
      stopAndReport(true)
    }
  }, 1000)
}

async function startMic(): Promise<void> {
  micStream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    ...(isVideo.value ? { video: { width: 1280, height: 720, facingMode: 'user' } } : {}),
  })
  if (isVideo.value && preview.value) {
    preview.value.srcObject = micStream
    await preview.value.play().catch(() => undefined)
  }
  audioContext = new AudioContext()
  source = audioContext.createMediaStreamSource(micStream)
  if (typeof MediaRecorder !== 'undefined') {
    recordedChunks.length = 0
    const mime = isVideo.value && MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus')
      ? 'video/webm;codecs=vp8,opus'
      : undefined
    recorder = new MediaRecorder(micStream, mime ? { mimeType: mime } : undefined)
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

async function stopAndReport(timeUp = false): Promise<void> {
  if (status.value === 'saving') return
  if (countdown) { clearInterval(countdown); countdown = null }
  const pendingTurns = lastAnswer.trim()
    ? [...turns.value, { question: lastQuestion, answer: lastAnswer }]
    : turns.value
  if (!pendingTurns.length) {
    fail(timeUp ? '时间到了，但这次还没有可评分的内容' : '这次还没有可评分的内容')
    return
  }
  status.value = 'saving'
  closing = true
  error.value = ''
  try {
    const form = new FormData()
    form.append('sceneId', props.scene?.id ?? '')
    form.append('turns', JSON.stringify(pendingTurns))
    form.append('engine', props.engine)
    form.append('durationSeconds', String(startedAt ? Math.round((Date.now() - startedAt) / 1000) : 0))
    if (recordedChunks.length) {
      if (isVideo.value) {
        form.append('video', new Blob(recordedChunks, { type: 'video/webm' }), 'interview.webm')
      } else {
        form.append('audio', new Blob(recordedChunks, { type: 'audio/webm' }), 'interview.webm')
      }
    }
    const saved = await api.post<ApiEnvelope<{ id: string }>>('/voice/sessions', form, { timeout: 180000 })
    const sessionId = saved.data.data.id
    await api.post(`/training-sessions/${sessionId}/finish`)
    emit('ended', sessionId)
  } catch (reason) {
    closing = false
    status.value = 'error'
    error.value = reason instanceof Error ? reason.message : '生成报告失败，请重试'
  } finally {
    stop()
  }
}

function interrupt(): void {
  if (props.engine === 'pipeline') {
    socket?.send(new ArrayBuffer(0))
  } else {
    socket?.send(JSON.stringify({ type: 'response.cancel' }))
  }
  reply.value = ''
}

function stop(): void {
  if (countdown) { clearInterval(countdown); countdown = null }
  try { if (recorder && recorder.state !== 'inactive') recorder.stop() } catch { /* 忽略 */ }
  recorder = null
  processor?.disconnect()
  source?.disconnect()
  void audioContext?.close()
  micStream?.getTracks().forEach((track) => track.stop())
  processor = null
  source = null
  audioContext = null
  micStream = null
  micOn.value = false
  socket?.close()
  socket = null
  closing = true
}

onMounted(() => { void start() })
onBeforeUnmount(stop)
</script>

<template>
  <section class="room" :class="{ 'room-video': isVideo }">
    <div class="room-stage">
      <template v-if="isVideo">
        <video ref="preview" class="room-self" muted playsinline />
        <div class="room-overlay">
          <span class="badge">{{ statusLabel }}</span>
          <span class="clock" aria-label="剩余时间">{{ timeLabel }}</span>
        </div>
        <div class="interviewer">
          <span class="avatar">{{ (scene?.roleName ?? '面')[0] }}</span>
          <div>
            <strong>{{ scene?.roleName ?? 'AI 面试官' }}</strong>
            <small>{{ scene?.category ?? '模拟面试' }}</small>
          </div>
        </div>
      </template>
      <template v-else>
        <div class="voice-stage">
          <span class="voice-avatar">{{ (scene?.roleName ?? '面')[0] }}</span>
          <strong>{{ scene?.roleName ?? 'AI 面试官' }}</strong>
          <p>{{ statusLabel }} · 剩余 {{ timeLabel }}</p>
          <div class="wave" :class="{ active: status === 'live' }" aria-hidden="true">
            <i v-for="n in 28" :key="n" :style="{ animationDelay: `${n * 35}ms` }" />
          </div>
        </div>
      </template>
    </div>

    <div class="live-transcript" aria-live="polite">
      <div class="line"><span class="who">我</span><p>{{ heard || (status === 'live' ? '面试官问完后，直接说话即可…' : '正在准备…') }}</p></div>
      <div class="line reply"><span class="who">面试官</span><p>{{ reply || '—' }}</p></div>
    </div>

    <p v-if="error" class="room-error">{{ error }}</p>

    <div class="room-controls">
      <button class="button secondary" type="button" :disabled="status !== 'live' || !reply" @click="interrupt">打断</button>
      <button class="button end" type="button" :disabled="status === 'saving' || status === 'connecting'" @click="stopAndReport(false)">
        <PhoneOff :size="15" :stroke-width="1.8" aria-hidden="true" />
        {{ status === 'saving' ? '正在生成报告…' : '结束面试' }}
      </button>
      <span class="mic-state"><Mic :size="13" :stroke-width="1.8" aria-hidden="true" />{{ micOn ? '麦克风已开启' : '等待麦克风' }} · 已进行 {{ rounds }} 轮</span>
    </div>
  </section>
</template>

<style scoped>
.room { display: grid; gap: 16px; padding: 18px; border: 1px solid var(--border); border-radius: 16px; background: var(--card); }
.room-stage { position: relative; border-radius: 14px; overflow: hidden; background: #0b0b0e; }
.room-self { display: block; width: 100%; aspect-ratio: 16 / 9; object-fit: cover; transform: scaleX(-1); }
.room-overlay { position: absolute; inset: 12px 14px auto; display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #fff; }
.badge { padding: 5px 12px; border-radius: 999px; background: rgba(0, 0, 0, .5); font-size: 11.5px; backdrop-filter: blur(6px); }
.clock { padding: 5px 12px; border-radius: 999px; background: rgba(0, 0, 0, .5); font-variant-numeric: tabular-nums; font-size: 12px; }
.interviewer { position: absolute; left: 14px; bottom: 12px; display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 12px; background: rgba(0, 0, 0, .55); color: #fff; backdrop-filter: blur(6px); }
.avatar { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: var(--accent); font-size: 15px; }
.interviewer strong { display: block; font-size: 13px; }
.interviewer small { color: rgba(255, 255, 255, .7); font-size: 11px; }
.voice-stage { display: grid; justify-items: center; gap: 8px; padding: 44px 20px 30px; background: radial-gradient(circle at 50% 20%, rgba(164, 70, 31, .25), transparent 60%), #0b0b0e; color: #fff; }
.voice-avatar { display: grid; place-items: center; width: 74px; height: 74px; border-radius: 50%; background: var(--accent); font-size: 30px; }
.voice-stage strong { font-size: 18px; }
.voice-stage p { margin: 0; color: rgba(255, 255, 255, .65); font-size: 12px; }
.wave { display: flex; align-items: center; gap: 4px; height: 56px; margin-top: 8px; }
.wave i { width: 3px; height: 10px; border-radius: 99px; background: rgba(255, 255, 255, .35); }
.wave.active i { background: var(--accent); animation: pulse 1.1s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { height: 8px; } 50% { height: 34px; } }
@media (prefers-reduced-motion: reduce) { .wave.active i { animation: none; height: 18px; } }
.live-transcript { display: grid; gap: 10px; }
.line { display: grid; grid-template-columns: 52px minmax(0, 1fr); gap: 10px; align-items: start; }
.who { color: var(--text-3); font-size: 12px; padding-top: 4px; }
.line p { margin: 0; padding: 12px 14px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-2); color: var(--text); line-height: 1.8; min-height: 44px; }
.line.reply p { background: var(--card); }
.room-error { margin: 0; color: var(--danger); font-size: 12.5px; }
.room-controls { display: flex; align-items: center; gap: 10px; }
.button.end { background: var(--accent); border-color: var(--accent); color: #fff; display: inline-flex; align-items: center; gap: 6px; }
.mic-state { display: inline-flex; align-items: center; gap: 5px; margin-left: auto; color: var(--text-3); font-size: 11.5px; }
</style>
