<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Camera, Mic, Volume2 } from 'lucide-vue-next'

import LiveInterviewRoom from '@/components/training/LiveInterviewRoom.vue'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'

const route = useRoute()
const router = useRouter()
const sceneId = computed(() => (typeof route.query.sceneId === 'string' ? route.query.sceneId : ''))
const planId = computed(() => (typeof route.query.planId === 'string' ? route.query.planId : ''))
const taskKey = computed(() => (typeof route.query.taskKey === 'string' ? route.query.taskKey : ''))

const scene = shallowRef<Scene | null>(null)
const started = shallowRef(false)
const duration = shallowRef(30)
const engine = shallowRef<'doubao' | 'pipeline'>('doubao')
const advanced = shallowRef(false)
const error = shallowRef('')
const preview = ref<HTMLVideoElement | null>(null)

const cameraOn = ref(false)
const cameraLabel = shallowRef('未授权')
const micLevel = ref(0)
const micHeard = ref(false)
const speakerOk = ref(false)
const networkLabel = shallowRef('检测中')
const checking = ref(false)

const ready = computed(() => cameraOn.value && micHeard.value)

let stream: MediaStream | null = null
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let levelFrame = 0

async function openCamera(): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) {
    error.value = '当前浏览器不支持摄像头，请使用 Chrome / Edge 最新版，或改用语音面试'
    return
  }
  checking.value = true
  error.value = ''
  try {
    closeCamera()
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: true })
    if (preview.value) {
      preview.value.srcObject = stream
      await preview.value.play().catch(() => undefined)
    }
    cameraOn.value = true
    const track = stream.getVideoTracks()[0]
    cameraLabel.value = `已就绪 ${track?.getSettings().width ?? 1280}×${track?.getSettings().height ?? 720}`
    watchMicrophone()
  } catch (reason) {
    const name = (reason as DOMException)?.name
    error.value = name === 'NotAllowedError'
      ? '摄像头或麦克风权限被拒绝：允许后重试，或改用语音面试'
      : name === 'NotFoundError'
        ? '没有找到摄像头或麦克风：插好设备后重试，或改用语音面试'
        : '无法打开摄像头或麦克风，请检查浏览器权限'
  } finally {
    checking.value = false
  }
}

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
      error.value = '设备已断开，请重新插好设备后再试'
    })
  } catch {
    // 电平检测失败不影响开始
  }
}

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

function closeCamera(): void {
  if (levelFrame) cancelAnimationFrame(levelFrame)
  levelFrame = 0
  analyser = null
  if (audioContext) { void audioContext.close().catch(() => undefined); audioContext = null }
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
  cameraOn.value = false
}

function start(): void {
  if (!ready.value) {
    error.value = '还没检测到麦克风声音：先对着麦克风说一句话，确认电平有反应'
    return
  }
  closeCamera()
  started.value = true
}

function switchToVoice(): void {
  closeCamera()
  void router.push({ name: 'voice', query: { sceneId: sceneId.value, ...(planId.value ? { planId: planId.value, taskKey: taskKey.value } : {}) } })
}

function onEnded(sessionId: string): void {
  if (planId.value && taskKey.value) {
    void api
      .post(`/training-plans/${planId.value}/tasks/${taskKey.value}/complete`, { evidence: sessionId })
      .catch(() => undefined)
  }
  void router.push(`/report/${sessionId}`)
}

onMounted(async () => {
  const connection = (navigator as unknown as { connection?: { effectiveType?: string; downlink?: number } }).connection
  networkLabel.value = navigator.onLine
    ? `${connection?.effectiveType ?? 'online'}${connection?.downlink ? ` · ${Math.round(connection.downlink)} Mbps` : ''}`
    : '离线'
  if (sceneId.value) {
    try {
      const response = await api.get<ApiEnvelope<Scene[]>>('/scenes', { params: { size: 100 } })
      scene.value = response.data.data.find((item) => item.id === sceneId.value) ?? null
    } catch {
      scene.value = null
    }
  }
})

onBeforeUnmount(closeCamera)

// 防止未使用变量告警
void errorMessage
</script>

<template>
  <div class="page video-page">
    <RouterLink class="back" to="/scenes"><ArrowLeft :size="13" :stroke-width="1.8" aria-hidden="true" /> 返回场景训练</RouterLink>

    <template v-if="!started">
      <header class="page-heading">
        <div>
          <p class="eyebrow">视频面试{{ scene ? ` · ${scene.category}` : '' }}</p>
          <h1 class="page-title">{{ scene ? scene.title : '坐在对面，像真面试一样' }}</h1>
          <p class="page-lead">打开摄像头，面试官会先开口提问，你正常说话回答；画面和声音会在结束后给出评分。</p>
        </div>
      </header>

      <p v-if="error" class="error-banner">{{ error }}</p>

      <section class="setup panel">
        <div class="preview-wrap">
          <video ref="preview" class="preview" muted playsinline />
          <div v-if="!cameraOn" class="preview-empty">
            <Camera :size="22" :stroke-width="1.6" aria-hidden="true" />
            <span>摄像头未开启</span>
            <button class="button secondary" type="button" :disabled="checking" @click="openCamera">
              {{ checking ? '正在检测…' : '检测设备' }}
            </button>
          </div>
        </div>

        <div class="checks">
          <div class="check">
            <span class="check-icon"><Camera :size="14" :stroke-width="1.8" aria-hidden="true" /></span>
            <div><strong>摄像头</strong><small>{{ cameraOn ? cameraLabel : '未检测' }}</small></div>
          </div>
          <div class="check">
            <span class="check-icon"><Mic :size="14" :stroke-width="1.8" aria-hidden="true" /></span>
            <div>
              <strong>麦克风</strong>
              <small>{{ micHeard ? '已收到声音' : '请说一句话' }}</small>
              <span class="meter" aria-hidden="true"><i :style="{ width: `${Math.round(micLevel * 100)}%` }" /></span>
            </div>
          </div>
          <div class="check">
            <span class="check-icon"><Volume2 :size="14" :stroke-width="1.8" aria-hidden="true" /></span>
            <div><strong>扬声器</strong><small>{{ speakerOk ? '已确认' : '点一下测试音' }}</small></div>
            <button class="mini" type="button" @click="testSpeaker">播放测试音</button>
          </div>
          <div class="check">
            <span class="check-icon">网</span>
            <div><strong>网络</strong><small>{{ networkLabel }}</small></div>
          </div>
        </div>

        <div class="setup-block">
          <p class="label">面试时长</p>
          <div class="chip-group" role="group" aria-label="面试时长">
            <button v-for="minutes in [30, 60]" :key="minutes" type="button" class="chip" :class="{ active: duration === minutes }" @click="duration = minutes">
              {{ minutes }} 分钟
            </button>
          </div>
          <p class="hint">到时间会自动结束并生成报告；也可以随时提前结束。</p>
        </div>

        <div class="setup-block">
          <button type="button" class="advanced-toggle" @click="advanced = !advanced">
            {{ advanced ? '收起高级选项' : '高级选项' }}
          </button>
          <div v-if="advanced" class="chip-group" role="group" aria-label="语音引擎">
            <button type="button" class="chip" :class="{ active: engine === 'doubao' }" @click="engine = 'doubao'">标准引擎</button>
            <button type="button" class="chip" :class="{ active: engine === 'pipeline' }" @click="engine = 'pipeline'">本地管线</button>
          </div>
        </div>

        <footer class="setup-actions">
          <button class="button start" type="button" :disabled="!ready" @click="start">
            <span class="dot" aria-hidden="true" />
            开始面试
          </button>
          <button class="link" type="button" @click="switchToVoice">改用语音面试 →</button>
          <span class="hint">{{ ready ? '准备好就坐下开始' : '先检测设备并说一句话' }}</span>
        </footer>
      </section>
    </template>

    <LiveInterviewRoom
      v-else
      mode="video"
      :scene="scene"
      :engine="engine"
      :duration-minutes="duration"
      @ended="onEnded"
    />
  </div>
</template>

<style scoped>
.video-page { max-width: 980px; }
.back { display: inline-flex; align-items: center; gap: 6px; margin-bottom: 18px; color: var(--text-3); font-size: 12px; }
.setup { margin-top: 10px; padding: 24px; display: grid; gap: 20px; }
.preview-wrap { position: relative; border-radius: 14px; overflow: hidden; background: #0b0b0e; aspect-ratio: 16 / 9; }
.preview { width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); }
.preview-empty { position: absolute; inset: 0; display: grid; place-items: center; gap: 10px; color: rgba(255, 255, 255, .78); font-size: 13px; }
.checks { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.check { display: flex; align-items: center; gap: 10px; padding: 12px 14px; border: 1px solid var(--border); border-radius: 10px; }
.check-icon { display: grid; place-items: center; width: 26px; height: 26px; border-radius: 8px; background: var(--overlay-2); color: var(--text-2); font-size: 11px; }
.check strong { display: block; font-size: 12.5px; }
.check small { color: var(--text-3); font-size: 11px; }
.meter { display: block; margin-top: 5px; width: 120px; height: 4px; border-radius: 99px; background: var(--track); overflow: hidden; }
.meter i { display: block; height: 100%; background: var(--accent); transition: width .12s linear; }
.mini { margin-left: auto; padding: 4px 10px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-2); font-size: 11px; cursor: pointer; }
.setup-block { display: grid; gap: 10px; }
.label { margin: 0; color: var(--text-3); font-size: 11px; letter-spacing: .12em; }
.chip-group { display: flex; gap: 10px; flex-wrap: wrap; }
.chip { padding: 9px 20px; border: 1px solid var(--border); border-radius: 999px; background: var(--card); color: var(--text-2); font-size: 13px; cursor: pointer; }
.chip.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); }
.hint { margin: 0; color: var(--text-3); font-size: 12px; }
.setup-actions { display: flex; align-items: center; gap: 16px; padding-top: 6px; border-top: 1px solid var(--divider); }
.button.start { display: inline-flex; align-items: center; gap: 8px; padding: 0 24px; min-height: 44px; font-size: 14px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #fff; }
.advanced-toggle { width: fit-content; border: 0; background: transparent; color: var(--text-3); font-size: 12px; cursor: pointer; padding: 0; }
.link { border: 0; background: transparent; color: var(--text-3); font-size: 12px; cursor: pointer; }
@media (max-width: 720px) { .checks { grid-template-columns: 1fr; } }
</style>
