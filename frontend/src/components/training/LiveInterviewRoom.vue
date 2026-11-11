<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { Mic, PhoneOff } from 'lucide-vue-next'

import PermissionDialog from '@/components/media/PermissionDialog.vue'
import { api } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'

type Status = 'connecting' | 'live' | 'error' | 'saving'
type Engine = 'doubao' | 'pipeline'
type MicIssue = '' | 'permission' | 'device' | 'busy' | 'unsupported'

const props = defineProps<{
  mode: 'voice' | 'video'
  scene: Scene | null
  engine: Engine
  durationMinutes: number
  depth?: 'STANDARD' | 'THREE_LAYER' | 'PRESSURE'
  language?: 'zh' | 'en'
}>()

const emit = defineEmits<{ ended: [sessionId: string]; failed: [message: string]; switchVoice: [] }>()

const status = shallowRef<Status>('connecting')
const effectiveEngine = shallowRef<Engine>(props.engine)
const fallbackNotice = shallowRef('')
let fallbackTried = false
const turnState = shallowRef<'idle' | 'heard' | 'thinking' | 'speaking'>('idle')
const error = shallowRef('')
const heard = shallowRef('')
const reply = shallowRef('')
const rounds = shallowRef(0)
const micOn = shallowRef(false)
// 麦克风为什么没声音：一律给用户可执行的原因，不做静默失败
const micIssue = shallowRef<MicIssue>('')
const micLevel = shallowRef(0)
const silentSeconds = shallowRef(0)
const remaining = shallowRef(props.durationMinutes * 60)
const preview = ref<HTMLVideoElement | null>(null)
// 申请麦克风/摄像头的两步交互：先明说「请求已发出」，被拒绝时换成三步引导
const micWaiting = ref(false)
const showMicGuide = ref(false)
const micDevices = computed<Array<'camera' | 'microphone'>>(() =>
  isVideo.value ? ['camera', 'microphone'] : ['microphone'],
)

const turns = shallowRef<Array<{ question: string; answer: string; startMs?: number; endMs?: number }>>([])
let wsTicket = ''
let lastAnswer = ''
let lastQuestion = ''
let startedAt = 0
let turnStartedAt = 0
let pendingTiming: { startMs: number; endMs: number } | null = null

let socket: WebSocket | null = null
let audioContext: AudioContext | null = null
let playbackContext: AudioContext | null = null
let micStream: MediaStream | null = null
let processor: ScriptProcessorNode | null = null
let source: MediaStreamAudioSourceNode | null = null
let playbackAt = 0
let audioPlayingUntil = 0
let lastLevelAt = 0
let pending = new Float32Array(0)
let recorder: MediaRecorder | null = null
const recordedChunks: Blob[] = []
let countdown: ReturnType<typeof setInterval> | null = null
let closing = false
let sessionSeq = 0

const isVideo = computed(() => props.mode === 'video')
const timeLabel = computed(() => {
  const total = Math.max(0, remaining.value)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
})
const turnHint = computed(() => {
  if (status.value !== 'live') return ''
  if (turnState.value === 'heard') return '已收到你的回答，面试官正在想下一个问题…'
  if (turnState.value === 'thinking') return '面试官正在思考…'
  if (turnState.value === 'speaking') return '面试官在说，想补充可以点「打断」'
  return rounds.value === 0 ? '听清问题后直接回答，说完停一下' : '轮到你了，直接说；说完停一下'
})

const liveStatus = computed(() => {
  if (status.value === 'connecting') return '正在接通面试官…'
  if (status.value === 'saving') return '正在整理报告…'
  if (status.value === 'error') return '连接中断'
  if (turnState.value === 'speaking') return '面试官正在说…'
  if (turnState.value === 'heard' || turnState.value === 'thinking') return '已收到你的回答，面试官正在想下一个问题…'
  if (!micOn.value) return '等待麦克风'
  if (silentSeconds.value >= 8) return '还没听到声音：确认麦克风没静音、没选错设备'
  if (micLevel.value > 0.03) return '正在听你说…'
  return rounds.value === 0 ? '请直接开口回答' : '轮到你了，直接说'
})

const statusLabel = computed(() => {
  if (status.value === 'connecting') return '正在接通面试官'
  if (status.value === 'saving') return '正在整理报告'
  if (status.value === 'error') return '连接异常'
  return isVideo.value ? '视频面试进行中' : '语音面试进行中'
})

function instructions(): string {
  const current = props.scene
  let base = props.language === 'en'
    ? 'You are an English-speaking interviewer. Ask one question at a time in English, briefly acknowledge the answer, then ask one specific follow-up. Keep every reply under 40 words. Do not answer for the candidate.'
    : '你是一名中文面试官，正在模拟真实面试。候选人说话后，你先简短回应，再追问一个具体问题，每次不超过 60 字。不要自问自答，不要长时间独白。开场白已由系统播报，你不需要再自我介绍或重新问候，直接回应候选人的回答。'
  if (props.depth === 'THREE_LAYER') {
    base += ' 本场启用三层追问：先确认基础知识与事实，再让候选人比较方案优劣，最后给出复杂或异常场景；每轮只推进一层。'
  } else if (props.depth === 'PRESSURE') {
    base += ' 本场是压力面：节奏快、连续追问证据和数字，不接客套，但保持专业尊重。'
  }
  if (!current) return base
  return `${base}本场场景：${current.title}（${current.category}）。你的角色：${current.roleName}。场景背景：${current.background}。考察目标：${current.goal}。请始终围绕这个场景提问。`
}

function openingLine(): string {
  const current = props.scene
  const fallback = props.language === 'en'
    ? "Hello, I'm your interviewer today. Please start with a brief self-introduction."
    : '你好，我是今天的面试官，请先做个自我介绍。'
  if (!current) return fallback
  // 场景开场白本身就是完整一句（常含自己的问候），不能再用模板前缀拼一遍，否则会被念/显示两遍
  const scripted = (current.openingLine ?? '').trim()
  if (scripted) return scripted
  if (props.language === 'en') return "Hello, I'm your interviewer today. Please start with a brief self-introduction."
  return `你好，我是${current.roleName}，今天这场是${current.category}。请先简单介绍一下自己。`
}

function wsUrl(): string {
  const base = import.meta.env.VITE_API_BASE ?? '/api/v1'
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws'
  // WS 带不了 Authorization 头，用登录后取到的短时票据换连
  const query = new URLSearchParams({ ticket: wsTicket })
  if (effectiveEngine.value === 'pipeline') {
    query.set('depth', props.depth ?? 'STANDARD')
    query.set('lang', props.language ?? 'zh')
    if (props.scene?.id) query.set('sceneId', props.scene.id)
    return `${scheme}://${location.host}${base}/voice/ws/pipeline?${query.toString()}`
  }
  return `${scheme}://${location.host}${base}/voice/ws?${query.toString()}`
}

async function fetchTicket(): Promise<boolean> {
  try {
    const issued = await api.post<ApiEnvelope<{ ticket: string; expiresIn: number }>>('/voice/ws-ticket')
    wsTicket = issued.data.data.ticket
    return Boolean(wsTicket)
  } catch {
    return false
  }
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

function playback(): AudioContext {
  if (!playbackContext) playbackContext = new AudioContext({ sampleRate: 24000 })
  // 自动播放策略下新建的上下文可能是 suspended，不 resume 就没有声音
  if (playbackContext.state === 'suspended') void playbackContext.resume()
  return playbackContext
}

function queuePcm(samples: Float32Array): void {
  if (!samples.length) return
  const context = playback()
  const buffer = context.createBuffer(1, samples.length, 24000)
  buffer.copyToChannel(samples, 0)
  const node = context.createBufferSource()
  node.buffer = buffer
  node.connect(context.destination)
  playbackAt = Math.max(playbackAt, context.currentTime + 0.05)
  node.start(playbackAt)
  playbackAt += buffer.duration
  audioPlayingUntil = playbackAt
  if (turnState.value !== 'speaking') turnState.value = 'speaking'
}

function toSamples(data: Uint8Array): Float32Array {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength)
  const samples = new Float32Array(Math.floor(data.byteLength / 2))
  for (let i = 0; i < samples.length; i += 1) samples[i] = view.getInt16(i * 2, true) / 32768
  return samples
}

function playPcm(base64: string): void {
  queuePcm(toSamples(fromBase64(base64)))
}

function playPcmBinary(data: ArrayBuffer): void {
  // 本地管线发的是 24k s16le 裸 PCM，之前这段被当成 JSON 丢掉了，用户听不到面试官说话
  queuePcm(toSamples(new Uint8Array(data)))
}

function handleEvent(raw: string): void {
  let event: Record<string, unknown>
  try {
    event = JSON.parse(raw)
  } catch {
    return
  }
  const type = String(event.type ?? '')
  if (effectiveEngine.value === 'pipeline') {
    if (type === 'user' && event.text) {
      heard.value = String(event.text)
      reply.value = ''
      turnState.value = 'heard'
      lastAnswer = String(event.text)
      pendingTiming = { startMs: turnStartedAt || startedAt, endMs: Date.now() }
      turnStartedAt = Date.now()
    } else if (type === 'assistant_delta' && event.text) {
      const wasEmpty = !reply.value
      reply.value = `${reply.value}${event.text}`
      if (wasEmpty) turnState.value = 'speaking'
    } else if (type === 'assistant_end') {
      lastQuestion = reply.value
      if (lastAnswer.trim()) {
        turns.value = [...turns.value, {
          question: lastQuestion,
          answer: lastAnswer,
          startMs: pendingTiming?.startMs,
          endMs: pendingTiming?.endMs,
        }]
        lastAnswer = ''
        pendingTiming = null
        turnStartedAt = Date.now()
      }
      rounds.value += 1
      turnState.value = 'idle'
    }
    return
  }
  if (type === 'session.created') {
    // 一接通就让面试官先开口，用户听到问题再回答
    socket?.send(JSON.stringify({ type: 'speech_text_buffer.commit', text: openingLine() }))
  }
  if (type.endsWith('transcription.delta')) {
    // 豆包的 delta 是“当前这一句的最新转写”，累积拼接会把同一句重复十几遍
    heard.value = String(event.delta ?? '')
  } else if (type.endsWith('transcription.completed')) {
    lastAnswer = String(event.transcript ?? heard.value)
    heard.value = lastAnswer
    reply.value = ''
    turnState.value = 'heard'
    pendingTiming = { startMs: turnStartedAt || startedAt, endMs: Date.now() }
    turnStartedAt = Date.now()
  } else if (type === 'response.output_text.done') {
    turnState.value = 'speaking'
    reply.value = String(event.text ?? '')
    lastQuestion = reply.value
    if (lastAnswer.trim()) {
      turns.value = [...turns.value, {
        question: lastQuestion,
        answer: lastAnswer,
        startMs: pendingTiming?.startMs,
        endMs: pendingTiming?.endMs,
      }]
      lastAnswer = ''
      pendingTiming = null
      turnStartedAt = Date.now()
    }
    rounds.value += 1
    turnState.value = 'idle'
  } else if (type === 'response.output_audio.delta') {
    playPcm(String(event.delta ?? ''))
  } else if (type === 'error') {
    error.value = JSON.stringify(event.error ?? event).slice(0, 200)
  }
}

async function start(): Promise<void> {
  closing = false
  status.value = 'connecting'
  error.value = ''
  heard.value = ''
  reply.value = ''
  rounds.value = 0
  turnState.value = 'idle'
  micIssue.value = ''
  micLevel.value = 0
  silentSeconds.value = 0
  remaining.value = props.durationMinutes * 60

  const seq = ++sessionSeq

  try {
    const info = await api.get<ApiEnvelope<{ enabled: boolean; voice: string }>>('/voice/status')
    if (!info.data.data.enabled) {
      fail('语音服务未配置，请联系管理员')
      return
    }

    if (!(await fetchTicket())) {
      if (seq === sessionSeq) fail('获取语音会话票据失败，请点「重新连接」再试')
      return
    }

    socket = new WebSocket(wsUrl())
    // 本地管线回的是裸 PCM 二进制帧；不收成 ArrayBuffer 就没法播放
    socket.binaryType = 'arraybuffer'
    socket.onopen = async () => {
      if (seq !== sessionSeq) return
      if (effectiveEngine.value === 'doubao') {
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
      turnStartedAt = startedAt
      beginCountdown()
      // 拿不到麦克风就必须停下来告诉用户原因，否则界面显示“进行中”却永远没有反应
      await startMic()
      if (micIssue.value) {
        fail(micIssueMessage(micIssue.value))
        return
      }
      silentSeconds.value = 0
    }
    socket.onmessage = (message) => {
      if (seq !== sessionSeq) return
      if (message.data instanceof ArrayBuffer) {
        playPcmBinary(message.data)
        return
      }
      handleEvent(String(message.data))
    }
    socket.onerror = () => {
      if (seq !== sessionSeq) return
      if (!maybeFallback()) fail('连接语音服务失败')
    }
    socket.onclose = (event) => {
      if (closing || seq !== sessionSeq) return
      micOn.value = false
      if (maybeFallback(event.code)) return
      const reasons: Record<number, string> = {
        4001: '语音服务未配置，请联系管理员',
        4003: '语音会话未授权或已断开，请重新开始',
        4004: '语音服务暂时不可用，请稍后重试',
        4005: '语音管线启动失败，可换标准引擎再试',
        4029: '当前语音并发已满，请稍后再试',
      }
      // 服务端 close reason 里带的是可读原因（如“语音管线启动失败：模型未配置”），优先用它
      const reason = (event.reason ?? '').trim()
      fail(reason || reasons[event.code] || '连接已断开，请重新开始面试')
    }
  } catch {
    fail('无法读取语音服务状态')
  }
}

function retry(): void {
  fallbackTried = false
  fallbackNotice.value = ''
  stop()
  closing = false
  void start()
}

// 权限被拒后浏览器不会再弹框，用户改完站点设置再点这里重试一次
function retryMic(): void {
  showMicGuide.value = false
  micIssue.value = ''
  error.value = ''
  retry()
}

let micWaitTimer = 0

function endMicWaiting(): void {
  if (micWaitTimer) {
    window.clearTimeout(micWaitTimer)
    micWaitTimer = 0
  }
  micWaiting.value = false
}

function maybeFallback(code?: number): boolean {
  // 标准引擎连不上上游时，自动用本地管线重开一次；只尝试一次，避免死循环
  const retryable = code === undefined || [1006, 1011, 4003, 4004, 4005].includes(code)
  if (effectiveEngine.value !== 'doubao' || fallbackTried || !retryable) return false
  fallbackTried = true
  effectiveEngine.value = 'pipeline'
  fallbackNotice.value = '标准引擎暂时不可用，已自动切换到本地管线'
  stop()
  window.setTimeout(() => { void start() }, 500)
  return true
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
    // 浏览器把音频上下文挂起时（自动播放策略），用户会以为“没反应”，这里自动恢复
    if (audioContext && audioContext.state === 'suspended') void audioContext.resume()
    if (playbackContext && playbackContext.state === 'suspended') void playbackContext.resume()
    if (turnState.value === 'speaking' && audioPlayingUntil <= (playbackContext?.currentTime ?? 0)) turnState.value = 'idle'
    silentSeconds.value = micLevel.value > 0.03 || !micOn.value ? 0 : silentSeconds.value + 1
    if (remaining.value <= 0) {
      stopAndReport(true)
    }
  }, 1000)
}

function micIssueKind(reason: unknown): MicIssue {
  const name = (reason as DOMException)?.name ?? ''
  if (!window.isSecureContext) return 'permission'
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'permission'
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError' || name === 'OverconstrainedError') return 'device'
  if (name === 'NotReadableError' || name === 'TrackStartError') return 'busy'
  return 'unsupported'
}

function micIssueMessage(kind: MicIssue): string {
  if (kind === 'permission') return '麦克风权限被拒绝，面试官听不到你说话'
  if (kind === 'device') return '没有找到可用的麦克风：插好设备后点「重新申请权限」'
  if (kind === 'busy') return '麦克风被其他程序占用（会议软件/录音工具），关掉后点「重新申请权限」'
  return '当前页面无法使用麦克风：请用 Chrome / Edge 打开 localhost 或 https 地址'
}

const micSteps = computed<string[]>(() => {
  if (micIssue.value !== 'permission') return []
  return [
    '点浏览器地址栏左侧的图标（锁形或调节滑块）',
    '打开「站点设置」，把「麦克风」' + (isVideo.value ? '和「摄像头」' : '') + '改成「允许」',
    '回到本页点「重新申请权限」；改不动就刷新页面后重新开始',
  ]
})

async function startMic(): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) {
    micIssue.value = 'unsupported'
    return
  }
  micWaiting.value = true
  micWaitTimer = window.setTimeout(() => {
    micWaitTimer = 0
    if (micOn.value) {
      micWaiting.value = false
      return
    }
    endMicWaiting()
    fail('20 秒内没有等到浏览器的授权结果：如果没看到授权弹窗，点「重新申请权限」再试，或按提示改站点设置')
  }, 20000)
  try {
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      ...(isVideo.value ? { video: { width: 1280, height: 720, facingMode: 'user' } } : {}),
    })
  } catch (reason) {
    endMicWaiting()
    micIssue.value = micIssueKind(reason)
    // 已被拒绝时浏览器不会再弹窗，直接把三步引导摆出来
    if (micIssue.value === 'permission') showMicGuide.value = true
    return
  }
  endMicWaiting()
  if (isVideo.value && preview.value) {
    preview.value.srcObject = micStream
    await preview.value.play().catch(() => undefined)
  }
  audioContext = new AudioContext()
  // Chrome 里新建的上下文可能是 suspended，不 resume 就收不到 onaudioprocess
  if (audioContext.state === 'suspended') await audioContext.resume()
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
    // 电平是用户唯一能立刻看到的“麦克风在工作”的证据
    let peak = 0
    for (let i = 0; i < input.length; i += 8) peak = Math.max(peak, Math.abs(input[i]))
    const now = performance.now()
    if (now - lastLevelAt > 100) {
      micLevel.value = Math.min(1, peak * 4)
      lastLevelAt = now
    }
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
      if (effectiveEngine.value === 'pipeline') {
        // 本地管线走裸 PCM 二进制帧；标准引擎走 JSON base64
        socket.send(pcm.buffer)
      } else {
        socket.send(JSON.stringify({ type: 'input_audio_buffer.append', audio: toBase64(pcm.buffer) }))
      }
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
    ? [...turns.value, {
        question: lastQuestion,
        answer: lastAnswer,
        startMs: pendingTiming?.startMs ?? (turnStartedAt || startedAt),
        endMs: pendingTiming?.endMs ?? Date.now(),
      }]
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
    form.append('engine', effectiveEngine.value)
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

function replayQuestion(): void {
  const text = (reply.value || openingLine()).trim()
  if (!text || !('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(text)
  utterance.lang = props.language === 'en' ? 'en-US' : 'zh-CN'
  utterance.rate = 0.92
  window.speechSynthesis.speak(utterance)
}

function interrupt(): void {
  if (effectiveEngine.value === 'pipeline') {
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
          <p class="voice-status" :class="{ speaking: turnState === 'speaking', hearing: micLevel > 0.03 }">{{ liveStatus }}</p>
          <div class="voice-meter" :class="{ hot: micLevel > 0.03 }" aria-hidden="true">
            <i :style="{ width: `${Math.max(3, Math.round(micLevel * 100))}%` }" />
          </div>
          <div class="wave" :class="{ active: status === 'live' }" aria-hidden="true">
            <i v-for="n in 28" :key="n" :style="{ animationDelay: `${n * 35}ms` }" />
          </div>
        </div>
      </template>
    </div>

    <!-- 纯语音不显示文字气泡：只保留状态，用户要的是“看不见字但听得见” -->
    <div v-if="isVideo" class="live-transcript" aria-live="polite">
      <div class="line"><span class="who">我</span><p>{{ heard || (status === 'live' ? '面试官问完后，直接说话即可…' : '正在准备…') }}</p></div>
      <div class="line reply"><span class="who">面试官</span><p>{{ reply || '—' }}</p></div>
    </div>
    <p v-else class="voice-note">语音面试不显示文字气泡；转写只在后台用于生成评分报告。</p>

    <p v-if="fallbackNotice" class="fallback">{{ fallbackNotice }}</p>
    <p v-if="turnHint && isVideo" class="turn-hint">
      <i class="dot" :class="turnState" aria-hidden="true" />
      {{ turnHint }}
    </p>

    <div v-if="error" class="room-error-block" role="alert">
      <p class="room-error">{{ error }}</p>
      <ol v-if="micSteps.length && !showMicGuide" class="room-steps">
        <li v-for="(step, index) in micSteps" :key="index">{{ step }}</li>
      </ol>
      <div class="room-fix">
        <button v-if="micIssue" class="button secondary" type="button" @click="retryMic">
          {{ micIssue === 'permission' ? '重新申请麦克风权限' : '重新申请权限' }}
        </button>
        <button v-else class="button secondary" type="button" @click="retry">重新连接</button>
        <button v-if="isVideo" class="button secondary" type="button" @click="emit('switchVoice')">改用语音面试</button>
      </div>
    </div>

    <div class="room-controls">
      <button class="button secondary" type="button" :disabled="status !== 'live'" @click="replayQuestion">重听问题</button>
      <button class="button secondary" type="button" :disabled="status !== 'live' || !reply" @click="interrupt">打断</button>
      <button class="button end" type="button" :disabled="status === 'saving' || status === 'connecting'" @click="stopAndReport(false)">
        <PhoneOff :size="15" :stroke-width="1.8" aria-hidden="true" />
        {{ status === 'saving' ? '正在生成报告…' : '结束面试' }}
      </button>
      <span class="mic-state"><Mic :size="13" :stroke-width="1.8" aria-hidden="true" />{{ micOn ? '麦克风已开启' : '等待麦克风' }} · 已进行 {{ rounds }} 轮</span>
    </div>

    <PermissionDialog v-if="micWaiting" variant="waiting" :devices="micDevices" />
    <PermissionDialog v-if="showMicGuide" variant="denied" :devices="micDevices" @retry="retryMic" @close="showMicGuide = false" />
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
.voice-status { font-size: 13px !important; color: rgba(255, 255, 255, .82) !important; }
.voice-status.hearing { color: #9be3b4 !important; }
.voice-status.speaking { color: var(--accent) !important; }
.voice-meter { width: 190px; height: 4px; border-radius: 99px; background: rgba(255, 255, 255, .16); overflow: hidden; }
.voice-meter i { display: block; height: 100%; background: var(--accent); transition: width .1s linear; }
.voice-meter.hot i { background: #48c97a; }
.voice-note { margin: 0; color: var(--text-3); font-size: 12px; }
.room-error-block { display: grid; gap: 10px; padding: 14px 16px; border: 1px solid var(--danger); border-radius: 12px; background: var(--bg-2); }
.room-error { margin: 0; color: var(--danger); font-size: 12.5px; }
.room-steps { margin: 0; padding-left: 18px; color: var(--text-2); font-size: 12.5px; line-height: 1.9; }
.room-fix { display: flex; gap: 10px; flex-wrap: wrap; }
.fallback { margin: 0; color: var(--accent-strong); font-size: 12px; }
.turn-hint { display: flex; align-items: center; gap: 8px; margin: 0; color: var(--text-2); font-size: 12.5px; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--text-3); }
.dot.heard { background: var(--accent); animation: blink 1s ease-in-out infinite; }
.dot.speaking { background: var(--success); }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }
.room-controls { display: flex; align-items: center; gap: 10px; }
.button.end { background: var(--accent); border-color: var(--accent); color: #fff; display: inline-flex; align-items: center; gap: 6px; }
.mic-state { display: inline-flex; align-items: center; gap: 5px; margin-left: auto; color: var(--text-3); font-size: 11.5px; }
</style>
