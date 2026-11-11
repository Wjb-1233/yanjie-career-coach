<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Camera, Mic, Volume2 } from 'lucide-vue-next'

import PermissionDialog from '@/components/media/PermissionDialog.vue'
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
const initialDepth = (useRoute().query.depth as 'STANDARD' | 'THREE_LAYER' | 'PRESSURE') || 'STANDARD'
const language = (useRoute().query.lang as 'zh' | 'en') || 'zh'
const engine = shallowRef<'doubao' | 'pipeline'>('doubao')
const depth = shallowRef<'STANDARD' | 'THREE_LAYER' | 'PRESSURE'>(initialDepth)
const advanced = shallowRef(false)
const error = shallowRef('')
// 权限/设备问题要能指出具体原因，才谈得上“可执行的处理”
const deviceIssue = shallowRef<'' | 'permission' | 'device' | 'busy' | 'insecure' | 'unsupported'>('')
const preview = ref<HTMLVideoElement | null>(null)

const cameraOn = ref(false)
const cameraLabel = shallowRef('未授权')
const micLevel = ref(0)
const micHeard = ref(false)
const speakerOk = ref(false)
const networkLabel = shallowRef('检测中')
const checking = ref(false)

// 权限状态要能自己显示出来，用户才知道该点按钮还是该去改站点设置
type PermState = 'unknown' | 'prompt' | 'granted' | 'denied' | 'unsupported'
const cameraPerm = shallowRef<PermState>('unknown')
const microphonePerm = shallowRef<PermState>('unknown')
const waitingForAllow = ref(false)
const showGuide = ref(false)
const mediaDevices = ['camera', 'microphone'] as Array<'camera' | 'microphone'>

const ready = computed(() => cameraOn.value && micHeard.value)

function permLabel(state: PermState): string {
  if (state === 'granted') return '已允许'
  if (state === 'denied') return '已被拒绝'
  if (state === 'prompt') return '未申请'
  if (state === 'unsupported') return '无法探测'
  return '未检测'
}

const permissionText = computed(
  () => `摄像头权限：${permLabel(cameraPerm.value)} · 麦克风权限：${permLabel(microphonePerm.value)}`,
)

const guideDevices = computed<Array<'camera' | 'microphone'>>(() => {
  const denied: Array<'camera' | 'microphone'> = []
  if (cameraPerm.value === 'denied') denied.push('camera')
  if (microphonePerm.value === 'denied') denied.push('microphone')
  return denied.length ? denied : mediaDevices
})

const deviceSteps = computed<string[]>(() => {
  if (deviceIssue.value === 'permission') {
    return [
      '点浏览器地址栏左侧的图标（锁形或调节滑块）',
      '打开「站点设置」，把「摄像头」和「麦克风」都改成「允许」',
      '回到本页点「重新申请权限」；如果仍然读不到设备，刷新页面后重来',
    ]
  }
  if (deviceIssue.value === 'busy') return ['关掉正在占用摄像头的程序（会议、录屏、直播软件）', '点「重新申请权限」重新检测']
  if (deviceIssue.value === 'device') return ['确认摄像头和麦克风已连接，并在系统设置里可见', '点「重新申请权限」重新检测']
  if (deviceIssue.value === 'insecure') return ['用 http://localhost 或 https 地址打开本页，浏览器才允许使用摄像头']
  return []
})

function deviceReason(reason: unknown): '' | 'permission' | 'device' | 'busy' | 'insecure' | 'unsupported' {
  const name = (reason as DOMException)?.name ?? ''
  if (!window.isSecureContext) return 'insecure'
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'permission'
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError' || name === 'OverconstrainedError') return 'device'
  if (name === 'NotReadableError' || name === 'TrackStartError') return 'busy'
  return 'unsupported'
}

function deviceMessage(kind: '' | 'permission' | 'device' | 'busy' | 'insecure' | 'unsupported'): string {
  if (kind === 'permission') return '摄像头或麦克风权限被拒绝，视频面试无法开始'
  if (kind === 'device') return '没有找到摄像头或麦克风'
  if (kind === 'busy') return '摄像头被其他程序占用，视频面试无法开始'
  if (kind === 'insecure') return '当前地址不能使用摄像头：需要 localhost 或 https'
  return '这个浏览器不支持摄像头，请用 Chrome / Edge 最新版'
}

let stream: MediaStream | null = null
let audioContext: AudioContext | null = null
let analyser: AnalyserNode | null = null
let levelFrame = 0

async function permissionState(name: 'camera' | 'microphone'): Promise<PermState> {
  if (!navigator.permissions?.query) return 'unsupported'
  try {
    // Chrome 支持 camera / microphone 两个名字，但 TS 的 PermissionName 联合类型里还没收录
    const status = await navigator.permissions.query({ name } as unknown as PermissionDescriptor)
    return status.state as PermState
  } catch {
    return 'unsupported'
  }
}

async function probePermissions(): Promise<void> {
  cameraPerm.value = await permissionState('camera')
  microphonePerm.value = await permissionState('microphone')
}

let waitTimer = 0
// 超时之后旧请求可能才回来，用序号让它作废，避免状态被迟到的结果覆盖
let attemptNo = 0

function endWaiting(): void {
  if (waitTimer) {
    window.clearTimeout(waitTimer)
    waitTimer = 0
  }
  waitingForAllow.value = false
}

async function openCamera(): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) {
    deviceIssue.value = window.isSecureContext ? 'unsupported' : 'insecure'
    error.value = deviceMessage(deviceIssue.value)
    return
  }
  checking.value = true
  error.value = ''
  showGuide.value = false
  // (1) 先探测并展示权限状态，用户不用自己去浏览器菜单里猜
  await probePermissions()
  // (2) 发起请求的同时把「已经发出去了」明说在页面上，否则用户会以为按钮没反应
  waitingForAllow.value = true
  const seq = ++attemptNo
  waitTimer = window.setTimeout(() => {
    waitTimer = 0
    attemptNo += 1
    waitingForAllow.value = false
    checking.value = false
    if (cameraOn.value) return
    error.value = '20 秒内没有等到浏览器的授权结果。如果没看到授权弹窗，点「重新申请权限」再试，或按下面的步骤改站点设置'
  }, 20000)
  try {
    closeCamera()
    const next = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: true })
    if (seq !== attemptNo) {
      next.getTracks().forEach((track) => track.stop())
      return
    }
    stream = next
    endWaiting()
    error.value = ''
    if (preview.value) {
      preview.value.srcObject = stream
      await preview.value.play().catch(() => undefined)
    }
    cameraOn.value = true
    deviceIssue.value = ''
    const track = stream.getVideoTracks()[0]
    cameraLabel.value = `已就绪 ${track?.getSettings().width ?? 1280}×${track?.getSettings().height ?? 720}`
    watchMicrophone()
    // (5) 授权成功后刷新状态文字；查询结果可能滞后，真实拿到的流才是准的
    await probePermissions()
    cameraPerm.value = 'granted'
    microphonePerm.value = 'granted'
  } catch (reason) {
    if (seq !== attemptNo) return
    endWaiting()
    deviceIssue.value = deviceReason(reason)
    error.value = deviceMessage(deviceIssue.value)
    if (deviceIssue.value === 'permission') {
      // (4) 浏览器不会再弹窗：交给三步引导弹窗，而不是只留一行报错
      cameraPerm.value = 'denied'
      microphonePerm.value = 'denied'
      showGuide.value = true
    }
  } finally {
    checking.value = false
  }
}

function watchMicrophone(): void {
  if (!stream) return
  const track = stream.getAudioTracks()[0]
  if (!track) {
    deviceIssue.value = 'device'
    error.value = '没有检测到麦克风：视频面试需要麦克风，插好后点「重新申请权限」'
    return
  }
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
  // 一键切语音：场景、追问强度、语言、训练计划任务原样带过去，用户不用重选
  closeCamera()
  void router.push({
    name: 'voice',
    query: {
      sceneId: sceneId.value,
      depth: depth.value,
      lang: language,
      ...(planId.value ? { planId: planId.value, taskKey: taskKey.value } : {}),
    },
  })
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
  // 进页面就先摆出权限状态：「未申请 / 已允许 / 已被拒绝」，别让用户自己去浏览器菜单里找
  await probePermissions()
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

      <div v-if="error" class="device-error" role="alert">
        <p class="error-banner">{{ error }}</p>
        <ol v-if="deviceSteps.length && !showGuide" class="device-steps">
          <li v-for="(step, index) in deviceSteps" :key="index">{{ step }}</li>
        </ol>
        <div class="device-actions">
          <button class="button secondary" type="button" :disabled="checking" @click="openCamera">
            {{ checking ? '正在检测…' : '重新申请权限' }}
          </button>
          <button class="button secondary" type="button" @click="switchToVoice">改用语音面试</button>
        </div>
      </div>

      <section class="setup panel">
        <div class="preview-wrap">
          <video ref="preview" class="preview" muted playsinline />
          <div v-if="!cameraOn" class="preview-empty">
            <Camera :size="22" :stroke-width="1.6" aria-hidden="true" />
            <span>摄像头未开启</span>
            <button class="button" type="button" :disabled="checking" @click="openCamera">
              {{ checking ? '正在申请…' : '开启摄像头和麦克风' }}
            </button>
            <small class="perm-tip">点击后浏览器会弹出授权窗口，在里面点「允许」即可。</small>
          </div>
        </div>
        <p class="perm-status">{{ permissionText }}</p>

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
          <span class="block-label">追问强度</span>
          <div class="chip-group" role="group" aria-label="追问强度">
            <button type="button" class="chip" :class="{ active: depth === 'STANDARD' }" @click="depth = 'STANDARD'">标准</button>
            <button type="button" class="chip" :class="{ active: depth === 'THREE_LAYER' }" @click="depth = 'THREE_LAYER'">三层深挖</button>
            <button type="button" class="chip" :class="{ active: depth === 'PRESSURE' }" @click="depth = 'PRESSURE'">压力面</button>
          </div>
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
          <span class="hint">{{ ready ? '准备好就坐下开始' : deviceIssue ? '设备未就绪：按上面的步骤处理后再开始' : '先检测设备并说一句话' }}</span>
        </footer>
      </section>

      <PermissionDialog v-if="waitingForAllow" variant="waiting" :devices="mediaDevices" />
      <PermissionDialog v-if="showGuide" variant="denied" :devices="guideDevices" @retry="openCamera" @close="showGuide = false" />
    </template>

    <LiveInterviewRoom
      v-else
      mode="video"
      :scene="scene"
      :engine="engine"
      :duration-minutes="duration"
        :depth="depth"
        :language="language"
      @ended="onEnded"
      @switch-voice="switchToVoice"
    />
  </div>
</template>

<style scoped>
.block-label { display: block; margin-bottom: 8px; color: var(--text-3); font-size: 12px; }
.video-page { max-width: 980px; }
.back { display: inline-flex; align-items: center; gap: 6px; margin-bottom: 18px; color: var(--text-3); font-size: 12px; }
.setup { margin-top: 10px; padding: 24px; display: grid; gap: 20px; }
.preview-wrap { position: relative; border-radius: 14px; overflow: hidden; background: #0b0b0e; aspect-ratio: 16 / 9; }
.preview { width: 100%; height: 100%; object-fit: cover; transform: scaleX(-1); }
.preview-empty { position: absolute; inset: 0; display: grid; place-items: center; align-content: center; gap: 10px; padding: 20px; color: rgba(255, 255, 255, .78); font-size: 13px; text-align: center; }
.perm-status { margin: -6px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.6; }
.perm-tip { max-width: 320px; color: rgba(255, 255, 255, .45); font-size: 11.5px; line-height: 1.7; }
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
.device-error { display: grid; gap: 10px; padding: 14px 16px; border: 1px solid var(--danger); border-radius: 12px; background: var(--bg-2); }
.device-error .error-banner { margin: 0; }
.device-steps { margin: 0; padding-left: 18px; color: var(--text-2); font-size: 12.5px; line-height: 1.9; }
.device-actions { display: flex; gap: 10px; flex-wrap: wrap; }
@media (max-width: 720px) { .checks { grid-template-columns: 1fr; } }
</style>
