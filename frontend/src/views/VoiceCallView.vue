<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'

import LiveInterviewRoom from '@/components/training/LiveInterviewRoom.vue'
import { api } from '@/lib/api'
import type { ApiEnvelope, Scene } from '@/lib/types'

const route = useRoute()
const router = useRouter()
const scene = shallowRef<Scene | null>(null)
const sceneId = computed(() => (typeof route.query.sceneId === 'string' ? route.query.sceneId : ''))
const planId = computed(() => (typeof route.query.planId === 'string' ? route.query.planId : ''))
const taskKey = computed(() => (typeof route.query.taskKey === 'string' ? route.query.taskKey : ''))

const started = shallowRef(false)
const duration = shallowRef(30)
const initialDepth = (useRoute().query.depth as 'STANDARD' | 'THREE_LAYER' | 'PRESSURE') || 'STANDARD'
const language = (useRoute().query.lang as 'zh' | 'en') || 'zh'
const depth = shallowRef<'STANDARD' | 'THREE_LAYER' | 'PRESSURE'>(initialDepth)
const engine = shallowRef<'doubao' | 'pipeline'>('doubao')
const advanced = shallowRef(false)
const serviceError = shallowRef('')

onMounted(async () => {
  if (sceneId.value) {
    try {
      const response = await api.get<ApiEnvelope<Scene[]>>('/scenes', { params: { size: 100 } })
      scene.value = response.data.data.find((item) => item.id === sceneId.value) ?? null
    } catch {
      scene.value = null
    }
  }
  try {
    const status = await api.get<ApiEnvelope<{ enabled: boolean }>>('/voice/status')
    if (!status.data.data.enabled) serviceError.value = '语音服务未配置，暂时无法开始面试'
  } catch {
    serviceError.value = '无法读取语音服务状态'
  }
})

function onEnded(sessionId: string): void {
  if (planId.value && taskKey.value) {
    void api
      .post(`/training-plans/${planId.value}/tasks/${taskKey.value}/complete`, { evidence: sessionId })
      .catch(() => undefined)
  }
  void router.push(`/report/${sessionId}`)
}
</script>

<template>
  <div class="page voice-page">
    <RouterLink class="back" to="/scenes"><ArrowLeft :size="13" :stroke-width="1.8" aria-hidden="true" /> 返回场景训练</RouterLink>

    <template v-if="!started">
      <header class="page-heading">
        <div>
          <p class="eyebrow">语音面试{{ scene ? ` · ${scene.category}` : '' }}</p>
          <h1 class="page-title">{{ scene ? scene.title : '像打电话一样面试' }}</h1>
          <p class="page-lead">
            {{ scene ? scene.roleName : '面试官' }}会先开口提问，你直接说话回答，像真实电话面试一样自然往返。
          </p>
        </div>
      </header>

      <p v-if="serviceError" class="error-banner">{{ serviceError }}</p>

      <section class="setup panel">
        <div class="setup-block">
          <p class="label">面试时长</p>
          <div class="chip-group" role="group" aria-label="面试时长">
            <button v-for="minutes in [30, 60]" :key="minutes" type="button" class="chip" :class="{ active: duration === minutes }" @click="duration = minutes">
              {{ minutes }} 分钟
            </button>
          </div>
          <p class="hint">到时间会自动结束并生成报告；也可以随时提前结束。</p>
        </div>

        <div v-if="scene" class="setup-block scene-brief">
          <p class="label">本场信息</p>
          <p class="brief-line"><strong>{{ scene.roleName }}</strong> · {{ scene.category }} · {{ scene.difficulty }}</p>
          <p class="brief-text">{{ scene.background }}</p>
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

        <div class="setup-block">
          <span class="block-label">追问强度</span>
          <div class="chip-group" role="group" aria-label="追问强度">
            <button type="button" class="chip" :class="{ active: depth === 'STANDARD' }" @click="depth = 'STANDARD'">标准</button>
            <button type="button" class="chip" :class="{ active: depth === 'THREE_LAYER' }" @click="depth = 'THREE_LAYER'">三层深挖</button>
            <button type="button" class="chip" :class="{ active: depth === 'PRESSURE' }" @click="depth = 'PRESSURE'">压力面</button>
          </div>
        </div>

        <footer class="setup-actions">
          <button class="button start" type="button" :disabled="Boolean(serviceError)" @click="started = true">
            <span class="dot" aria-hidden="true" />
            开始面试
          </button>
          <span class="hint">开始后浏览器会请求麦克风权限</span>
        </footer>
      </section>
    </template>

    <LiveInterviewRoom
      v-else
      mode="voice"
      :scene="scene"
      :engine="engine"
      :duration-minutes="duration"
        :depth="depth"
        :language="language"
      @ended="onEnded"
    />
  </div>
</template>

<style scoped>
.block-label { display: block; margin-bottom: 8px; color: var(--text-3); font-size: 12px; }
.voice-page { max-width: 880px; }
.back { display: inline-flex; align-items: center; gap: 6px; margin-bottom: 18px; color: var(--text-3); font-size: 12px; }
.setup { margin-top: 10px; padding: 26px; display: grid; gap: 22px; }
.setup-block { display: grid; gap: 10px; }
.label { margin: 0; color: var(--text-3); font-size: 11px; letter-spacing: .12em; }
.chip-group { display: flex; gap: 10px; flex-wrap: wrap; }
.chip { padding: 9px 20px; border: 1px solid var(--border); border-radius: 999px; background: var(--card); color: var(--text-2); font-size: 13px; cursor: pointer; }
.chip.active { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); }
.hint { margin: 0; color: var(--text-3); font-size: 12px; }
.scene-brief { padding: 16px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg-2); }
.brief-line { margin: 0; font-size: 13px; }
.brief-text { margin: 6px 0 0; color: var(--text-2); font-size: 12.5px; line-height: 1.8; }
.advanced-toggle { width: fit-content; border: 0; background: transparent; color: var(--text-3); font-size: 12px; cursor: pointer; padding: 0; }
.setup-actions { display: flex; align-items: center; gap: 14px; padding-top: 6px; border-top: 1px solid var(--divider); }
.button.start { display: inline-flex; align-items: center; gap: 8px; padding: 0 24px; min-height: 44px; font-size: 14px; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: #fff; }
</style>
