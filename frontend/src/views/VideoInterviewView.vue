<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'

interface Question {
  text: string
}

const route = useRoute()
const router = useRouter()
const sceneId = computed(() => (typeof route.query.sceneId === 'string' ? route.query.sceneId : ''))
const planId = computed(() => (typeof route.query.planId === 'string' ? route.query.planId : ''))
const taskKey = computed(() => (typeof route.query.taskKey === 'string' ? route.query.taskKey : ''))

const scene = shallowRef<Scene | null>(null)
const questions = shallowRef<Question[]>([])
const index = ref(0)
const stage = ref<'idle' | 'ready' | 'recording' | 'uploading' | 'error'>('idle')
const error = shallowRef('')
const elapsed = ref(0)
const preview = ref<HTMLVideoElement | null>(null)
const cameraOn = ref(false)
const rounds = shallowRef<Array<{ text: string; start: number; end: number }>>([])
const taskProgress = ref(0)
const taskStage = shallowRef('')
const queueHint = shallowRef('')
// V-01 设备预检状态
const micLevel = ref(0)
const micHeard = ref(false)
const speakerOk = ref(false)
const networkLabel = shallowRef('检测中')
const cameraLabel = shallowRef('未授权')
const checked = computed(() => cameraOn.value && micHeard.value)

let stream: MediaStream | null = null
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let levelFrame = 0
let recorder: MediaRecorder | null = null
let chunks: Blob[] = []
let timer: ReturnType<typeof setInterval> | null = null
let startedAt = 0

const current = computed(() => questions.value[index.value]?.text ?? '')
const total = computed(() => questions.value.length)
async function openCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    stage.value = 'error'
    error.value = '当前浏览器不支持摄像头采集，请使用 Chrome / Edge 最新版，或改用语音面试'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: true })
    if (preview.value) {
      preview.value.srcObject = stream
      await preview.value.play().catch(() => undefined)
    }
    cameraOn.value = true
    cameraLabel.value = `已就绪 ${stream.getVideoTracks()[0]?.getSettings().width ?? 1280}×${stream.getVideoTracks()[0]?.getSettings().height ?? 720}`
    stage.value = 'ready'
    watchMicrophone()
  } catch (reason) {
    stage.value = 'error'
    const name = (reason as DOMException)?.name
    error.value = name === 'NotAllowedError'
      ? '摄像头或麦克风权限被拒绝：允许后可重试，或使用下面的语音模式'
      : name === 'NotFoundError'
        ? '没有找到摄像头或麦克风：插好设备后重试，或使用语音模式'
        : '无法打开摄像头或麦克风，请检查浏览器权限'
  }
}

/** 麦克风电平：有声音后把 micHeard 置为 true，作为开始录制的前置条件 */
function watchMicrophone(): void {
  if (!stream) return
  const track = stream.getAudioTracks()[0]
  if (!track) return
  try {
    audioContext = new AudioContext()
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 1024
    audioContext.createMediaStreamSource(stream).connect(analyser)
    const data = new Uint8Array(analyser.fftSize)
    const loop = () => {
      if (!analyser) return
      analyser.getByteTimeDomainData(data)
      let peak = 0
      for (const value of data) peak = Math.max(peak, Math.abs(value - 128))
      micLevel.value = Math.min(1, peak / 64)
      if (micLevel.value > 0.18) micHeard.value = true
      levelFrame = requestAnimationFrame(loop)
    }
    loop()
    track.addEventListener('ended', () => {
      cameraOn.value = false
      error.value = '设备已断开，请重新插好设备后重新检测'
      stage.value = 'error'
    })
  } catch {
    // 电平检测失败不影响录制
  }
}

/** 扬声器测试：播放一段 0.4 秒提示音 */
function testSpeaker(): void {
  try {
    const context = new AudioContext()
    const oscillator = context.createOscillator()
    const gain = context.createGain()
    oscillator.frequency.value = 660
    gain.gain.value = 0.08
    oscillator.connect(gain).connect(context.destination)
    oscillator.start()
    oscillator.stop(context.currentTime + 0.4)
    oscillator.onended = () => {
      void context.close()
      speakerOk.value = true
    }
  } catch {
    speakerOk.value = false
  }
}

function switchToVoice(): void {
  closeCamera()
  void router.push({ name: 'voice', query: { sceneId: sceneId.value } })
}

function closeCamera() {
  if (levelFrame) cancelAnimationFrame(levelFrame)
  levelFrame = 0
  analyser = null
  if (audioContext) { void audioContext.close().catch(() => undefined); audioContext = null }
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
  cameraOn.value = false
}

function startRecording() {
  if (!stream) return
  if (!checked.value) {
    error.value = '还没检测到麦克风声音：请对着麦克风说一句话，确认电平条有反应'
    return
  }
  chunks = []
  rounds.value = []
  index.value = 0
  const mime = MediaRecorder.isTypeSupported('video/webm;codecs=vp8,opus') ? 'video/webm;codecs=vp8,opus' : 'video/webm'
  recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 1_600_000 })
  recorder.ondataavailable = (event) => {
    if (event.data.size) chunks.push(event.data)
  }
  recorder.start(1000)
  startedAt = performance.now()
  stage.value = 'recording'
  elapsed.value = 0
  timer = setInterval(() => {
    elapsed.value = Math.round((performance.now() - startedAt) / 1000)
  }, 500)
  marks.value = [{ text: current.value, start: 0 }]
}

const marks = ref<Array<{ text: string; start: number; end?: number }>>([])

function nextQuestion() {
  if (!recorder || recorder.state !== 'recording') return
  const at = round((performance.now() - startedAt) / 1000)
  marks.value[marks.value.length - 1].end = at
  if (index.value + 1 < total.value) {
    index.value += 1
    marks.value.push({ text: current.value, start: at })
  } else {
    void submit()
  }
}

function round(value: number): number {
  return Math.round(value * 10) / 10
}

/** 轮询后台任务，直到分析完成 */
async function waitForTask(taskId: string): Promise<string> {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1500))
    const response = await api.get<ApiEnvelope<{ status: string; progress: number; stage: string | null; sessionId: string | null; error: string | null; queue?: { ahead: number; etaSeconds: number } }>>(`/tasks/${taskId}`)
    const task = response.data.data
    taskProgress.value = task.progress
    taskStage.value = task.stage ?? '分析中'
    queueHint.value = task.queue && task.queue.ahead > 0
      ? `前面还有 ${task.queue.ahead} 个任务，预计 ${task.queue.etaSeconds} 秒`
      : ''
    if (task.status === 'DONE' && task.sessionId) return task.sessionId
    if (task.status === 'FAILED') throw new Error(task.error || '分析失败，请重新录制')
  }
  throw new Error('分析超时，请稍后在训练记录里查看')
}

async function submit() {
  if (!recorder) return
  stage.value = 'uploading'
  if (timer) clearInterval(timer)
  const stopped = new Promise<void>((resolve) => {
    recorder!.onstop = () => resolve()
  })
  recorder.stop()
  await stopped
  const blob = new Blob(chunks, { type: 'video/webm' })
  const duration = round((performance.now() - startedAt) / 1000)
  marks.value[marks.value.length - 1].end = marks.value[marks.value.length - 1].end ?? duration

  const form = new FormData()
  form.append('sceneId', sceneId.value)
  form.append('questions', JSON.stringify(marks.value))
  form.append('durationSeconds', String(duration))
  form.append('video', blob, 'answer.webm')
  try {
    const created = await api.post<ApiEnvelope<{ taskId: string }>>('/video-interviews', form, { timeout: 60_000 })
    const taskId = created.data.data.taskId
    const sessionId = await waitForTask(taskId)
    if (planId.value && taskKey.value) {
      await api
        .post(`/training-plans/${planId.value}/tasks/${taskKey.value}/complete`, { evidence: sessionId })
        .catch(() => undefined)
    }
    closeCamera()
    await router.push(`/report/${sessionId}`)
  } catch (reason) {
    stage.value = 'error'
    error.value = errorMessage(reason)
  }
}

onMounted(async () => {
  const connection = (navigator as unknown as { connection?: { effectiveType?: string; downlink?: number } }).connection
  networkLabel.value = navigator.onLine
    ? `${connection?.effectiveType ?? 'online'}${connection?.downlink ? ` · ${Math.round(connection.downlink)} Mbps` : ''}`
    : '离线'
  if (!sceneId.value) return
  try {
    const response = await api.get<ApiEnvelope<Scene>>(`/scenes/${sceneId.value}`)
    scene.value = response.data.data
    const bank = (response.data.data as unknown as { questionBank?: Array<{ text: string } | string> }).questionBank ?? []
    questions.value = bank
      .map((item) => ({ text: typeof item === 'string' ? item : item.text }))
      .filter((item) => item.text)
      .slice(0, 3)
    if (!questions.value.length) {
      questions.value = [{ text: '请做一段自我介绍' }, { text: '你为什么选择这个岗位' }]
    }
  } catch (reason) {
    stage.value = 'error'
    error.value = errorMessage(reason)
  }
})

onBeforeUnmount(closeCamera)
</script>

<template>
  <div class="video-page">
    <RouterLink class="back" to="/scenes">← 返回场景训练</RouterLink>

    <header class="head">
      <p class="kicker">视频面试 · {{ scene?.category ?? 'HR 初面' }}</p>
      <h1>{{ scene?.title ?? '视频面试' }}</h1>
      <p class="lead">摄像头对着自己回答，结束后会给出内容评分和镜头表现分析。</p>
      <RouterLink class="live-link" :to="{ name: 'voice', query: { sceneId, video: '1', ...(planId ? { planId, taskKey } : {}) } }">
        改用实时视频房间（面试官语音提问）→
      </RouterLink>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="panel">
      <div class="stage">
        <video ref="preview" class="preview" muted playsinline />
        <div v-if="!cameraOn" class="mask">
          <button class="primary" type="button" @click="openCamera">开启摄像头</button>
          <p>需要摄像头与麦克风权限，录像只用于生成报告</p>
        </div>
        <div v-else-if="stage === 'recording'" class="rec">
          <i class="dot" /> 录制中 {{ elapsed }}s
        </div>
      </div>

      <aside class="side">
        <p class="step num">{{ String(index + 1).padStart(2, '0') }} / {{ String(total || 3).padStart(2, '0') }}</p>
        <h2>{{ stage === 'recording' ? current : '准备好了就开始' }}</h2>
        <p class="hint">
          <template v-if="stage === 'idle'">点「开启摄像头」检查画面与麦克风，再开始回答。</template>
          <template v-else-if="stage === 'ready'">共有 {{ total }} 道题，答完一道点「下一题」。</template>
          <template v-else-if="stage === 'recording'">说完这题点「下一题」，最后一题会直接提交。</template>
          <template v-else-if="stage === 'uploading'">{{ taskStage || '正在上传录像' }} · {{ taskProgress }}%<template v-if="queueHint">（{{ queueHint }}）</template></template>
        </p>

        <ul v-if="stage !== 'recording' && stage !== 'uploading'" class="precheck" aria-label="设备预检">
          <li :class="{ ok: cameraOn }">
            <span class="dot" />
            摄像头
            <em>{{ cameraOn ? cameraLabel : '未检测' }}</em>
          </li>
          <li :class="{ ok: micHeard }">
            <span class="dot" />
            麦克风
            <em v-if="micHeard">已收到声音</em>
            <em v-else-if="cameraOn">请说一句话（电平 {{ Math.round(micLevel * 100) }}%）</em>
            <em v-else>未检测</em>
          </li>
          <li :class="{ ok: speakerOk }">
            <span class="dot" />
            扬声器
            <button type="button" class="mini" @click="testSpeaker">{{ speakerOk ? '再测一次' : '播放测试音' }}</button>
          </li>
          <li :class="{ ok: networkLabel !== '离线' }">
            <span class="dot" />
            网络
            <em>{{ networkLabel }}</em>
          </li>
        </ul>
        <button v-if="stage !== 'recording' && stage !== 'uploading'" type="button" class="voice-fallback" @click="switchToVoice">
          不方便开摄像头？改用语音面试 →
        </button>

        <div class="actions">
          <button v-if="stage === 'ready'" class="primary" type="button" :disabled="!checked" @click="startRecording">
            {{ checked ? '开始录制' : '先完成麦克风检测' }}
          </button>
          <button v-if="stage === 'recording'" class="primary" type="button" @click="nextQuestion">
            {{ index + 1 < total ? '下一题' : '结束并生成报告' }}
          </button>
          <button v-if="stage === 'uploading'" class="primary" type="button" disabled>分析中 {{ taskProgress }}%</button>
        </div>

        <ol v-if="stage === 'recording'" class="marks">
          <li v-for="(mark, i) in marks" :key="i" :class="{ active: i === index }">{{ mark.text }}</li>
        </ol>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.video-page { max-width: 1180px; margin: 0 auto; padding: 32px 24px 64px; display: grid; gap: 22px; }
.back { width: fit-content; color: var(--text-3); font-size: 13px; }
.head h1 { margin: 8px 0 10px; font-family: var(--font-display); font-size: 34px; }
.kicker { margin: 0; color: var(--accent-strong); font-size: 12px; letter-spacing: .12em; }
.lead { margin: 0; color: var(--text-2); font-size: 13.5px; }
.error { margin: 0; padding: 10px 14px; border-radius: 10px; background: rgba(180,58,42,.08); color: #a4342a; font-size: 13px; }
.panel { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); gap: 22px; padding: 22px; border: 1px solid var(--border); border-radius: 16px; background: var(--card); }
.stage { position: relative; aspect-ratio: 16 / 10; border-radius: 12px; overflow: hidden; background: #14100d; }
.preview { width: 100%; height: 100%; object-fit: cover; }
.mask { position: absolute; inset: 0; display: grid; place-content: center; gap: 12px; text-align: center; background: rgba(20,16,13,.82); color: #f3e9df; }
.mask p { margin: 0; font-size: 12px; color: #c8b8a9; }
.rec { position: absolute; left: 14px; top: 14px; display: inline-flex; align-items: center; gap: 8px; padding: 5px 12px; border-radius: 999px; background: rgba(0,0,0,.55); color: #fff; font-size: 12px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #e05a4a; animation: pulse 1.4s infinite; }
@keyframes pulse { 50% { opacity: .35; } }
.side { display: grid; align-content: start; gap: 12px; }
.step { margin: 0; color: var(--text-3); font-size: 12px; letter-spacing: .1em; }
.side h2 { margin: 0; font-family: var(--font-display); font-size: 21px; line-height: 1.45; }
.hint { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.8; }
.actions { margin-top: 6px; }
.primary { min-height: 44px; padding: 0 22px; border: 0; border-radius: 10px; background: var(--accent); color: #fff; font-weight: 600; cursor: pointer; }
.primary:disabled { opacity: .6; cursor: default; }
.marks { margin: 8px 0 0; padding-left: 18px; color: var(--text-3); font-size: 12.5px; line-height: 1.9; }
.marks li.active { color: var(--accent-strong); font-weight: 600; }
@media (max-width: 960px) { .panel { grid-template-columns: 1fr; } }

.precheck { list-style: none; margin: 4px 0 10px; padding: 0; display: grid; gap: 6px; }
.precheck li { display: flex; align-items: center; gap: 8px; color: var(--text-3); font-size: 12px; }
.precheck li .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--border-bright); flex: none; }
.precheck li.ok .dot { background: var(--accent); }
.precheck li em { margin-left: auto; color: var(--text-2); font-style: normal; }
.precheck .mini { margin-left: auto; padding: 2px 8px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-2); font-size: 11px; cursor: pointer; }
.voice-fallback { width: fit-content; margin: 0 0 12px; padding: 0; border: 0; background: none; color: var(--accent-strong); font-size: 12px; cursor: pointer; }

.live-link { display: inline-block; margin-top: 8px; color: var(--accent-strong); font-size: 12.5px; }
</style>
