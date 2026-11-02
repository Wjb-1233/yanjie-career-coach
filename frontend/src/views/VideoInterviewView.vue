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

let stream: MediaStream | null = null
let recorder: MediaRecorder | null = null
let chunks: Blob[] = []
let timer: ReturnType<typeof setInterval> | null = null
let startedAt = 0

const current = computed(() => questions.value[index.value]?.text ?? '')
const total = computed(() => questions.value.length)
async function openCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: true })
    if (preview.value) {
      preview.value.srcObject = stream
      await preview.value.play().catch(() => undefined)
    }
    cameraOn.value = true
    stage.value = 'ready'
  } catch (reason) {
    stage.value = 'error'
    error.value = '无法打开摄像头或麦克风，请检查浏览器权限'
    void reason
  }
}

function closeCamera() {
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
  cameraOn.value = false
}

function startRecording() {
  if (!stream) return
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
    const created = await api.post<ApiEnvelope<{ id: string }>>('/video-interviews', form, { timeout: 300_000 })
    const sessionId = created.data.data.id
    await api.post(`/training-sessions/${sessionId}/finish`)
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
          <template v-if="stage === 'idle'">点「开启摄像头」检查画面，再开始回答。</template>
          <template v-else-if="stage === 'ready'">共有 {{ total }} 道题，答完一道点「下一题」。</template>
          <template v-else-if="stage === 'recording'">说完这题点「下一题」，最后一题会直接提交。</template>
          <template v-else-if="stage === 'uploading'">正在上传并分析录像，大约需要 30–60 秒…</template>
        </p>

        <div class="actions">
          <button v-if="stage === 'ready'" class="primary" type="button" @click="startRecording">开始录制</button>
          <button v-if="stage === 'recording'" class="primary" type="button" @click="nextQuestion">
            {{ index + 1 < total ? '下一题' : '结束并生成报告' }}
          </button>
          <button v-if="stage === 'uploading'" class="primary" type="button" disabled>分析中…</button>
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
</style>
