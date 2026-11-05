<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'
import { useRoute } from 'vue-router'

import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

interface SharedPayload {
  sceneTitle: string
  channel: string
  startedAt: string
  overallScore: number | null
  scores: { logic: number; relevance: number; correctness: number; concision: number } | null
  summary: string | null
  recordingUrl: string | null
  transcript: Array<{ roundNo: number; question: string; text: string; confidence: number | null }>
  annotations: Array<{ atMs: number; comment: string; author: string; createdAt: string }>
}

const route = useRoute()
const token = computed(() => String(route.params.token ?? ''))
const data = shallowRef<SharedPayload | null>(null)
const error = shallowRef('')
const loading = shallowRef(true)
const author = ref('')
const comment = ref('')
const atMs = ref(0)
const saving = ref(false)
const video = ref<HTMLVideoElement | null>(null)

const dimensions = computed(() => {
  const scores = data.value?.scores
  if (!scores) return []
  return [
    ['内容与逻辑', scores.logic],
    ['贴合问题', scores.relevance],
    ['信息完整', scores.correctness],
    ['表达干净', scores.concision],
  ] as Array<[string, number]>
})

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const response = await fetch(`/api/v1/share/${token.value}`)
    const body = await response.json()
    if (!response.ok) throw new Error(body?.title || body?.detail || '链接不可用')
    data.value = body.data
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

function seek(ms: number): void {
  atMs.value = ms
  if (video.value) {
    video.value.currentTime = ms / 1000
    void video.value.play().catch(() => undefined)
  }
}

function captureTime(): void {
  if (video.value) atMs.value = Math.round(video.value.currentTime * 1000)
}

async function submit(): Promise<void> {
  if (!comment.value.trim() || saving.value) return
  saving.value = true
  try {
    const response = await api.post<ApiEnvelope<{ annotations: SharedPayload['annotations'] }>>(
      `/share/${token.value}/annotations`,
      { atMs: atMs.value, comment: comment.value.trim(), author: author.value.trim() || undefined },
    )
    if (data.value) data.value = { ...data.value, annotations: response.data.data.annotations }
    comment.value = ''
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    saving.value = false
  }
}

function stamp(ms: number): string {
  const total = Math.round(ms / 1000)
  return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

onMounted(load)
</script>

<template>
  <main class="share-page">
    <header class="share-head">
      <p class="eyebrow">教练查看 · 只读</p>
      <h1>{{ data?.sceneTitle ?? '训练片段' }}</h1>
      <p class="meta">
        <template v-if="data">综合分 {{ data.overallScore ?? '—' }} · {{ new Date(data.startedAt).toLocaleString('zh-CN') }}</template>
        <template v-else>链接可查看评分摘要与录像，不能修改评分</template>
      </p>
    </header>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="loading" class="hint">正在打开…</p>

    <template v-else-if="data">
      <section v-if="dimensions.length" class="panel summary">
        <dl>
          <div v-for="[label, value] in dimensions" :key="label">
            <dt>{{ label }}</dt>
            <dd>{{ value }}<small> / 5</small></dd>
          </div>
        </dl>
        <p v-if="data.summary" class="coach-summary">{{ data.summary }}</p>
      </section>

      <section v-if="data.recordingUrl" class="panel">
        <h2>录像</h2>
        <video ref="video" :src="data.recordingUrl" controls playsinline preload="metadata" @pause="captureTime" />
      </section>

      <section v-if="data.transcript.length" class="panel">
        <h2>逐题转写</h2>
        <ol class="transcript">
          <li v-for="item in data.transcript" :key="item.roundNo">
            <span class="num">第 {{ item.roundNo }} 题</span>
            <p class="q">{{ item.question }}</p>
            <p class="a">{{ item.text }}</p>
          </li>
        </ol>
      </section>

      <section class="panel">
        <h2>批注</h2>
        <ul v-if="data.annotations.length" class="annotations">
          <li v-for="(item, index) in data.annotations" :key="index">
            <button type="button" class="stamp" @click="seek(item.atMs)">{{ stamp(item.atMs) }}</button>
            <p>{{ item.comment }}</p>
            <span>{{ item.author }} · {{ new Date(item.createdAt).toLocaleString('zh-CN') }}</span>
          </li>
        </ul>
        <p v-else class="hint">还没有批注。回放到关键位置，点「记录当前时间」再写一条。</p>

        <div class="annotation-form">
          <div class="row">
            <label>时间点</label>
            <span class="stamp-view">{{ stamp(atMs) }}</span>
            <button type="button" class="mini" @click="captureTime">记录当前时间</button>
          </div>
          <input v-model="author" class="field" maxlength="40" placeholder="你的称呼（可选）" />
          <textarea v-model="comment" class="field" rows="3" maxlength="500" placeholder="这段的问题 / 建议，例如：结论太晚，前 10 秒没有回应问题" />
          <button class="button" type="button" :disabled="saving || !comment.trim()" @click="submit">
            {{ saving ? '保存中…' : '保存批注' }}
          </button>
        </div>
      </section>
    </template>
  </main>
</template>

<style scoped>
.share-page { max-width: 860px; margin: 0 auto; padding: 40px 22px 80px; display: grid; gap: 18px; }
.eyebrow { margin: 0; color: var(--accent-strong); font-size: 11px; letter-spacing: .16em; }
.share-head h1 { margin: 8px 0 6px; font-family: var(--font-display); font-size: clamp(24px, 3vw, 32px); }
.meta { margin: 0; color: var(--text-3); font-size: 12.5px; }
.error { margin: 0; padding: 10px 14px; border-radius: 8px; background: rgba(180,58,42,.08); color: #a4342a; font-size: 13px; }
.hint { margin: 0; color: var(--text-3); font-size: 12.5px; }
.panel { padding: 20px; border: 1px solid var(--border); border-radius: 12px; background: var(--card); display: grid; gap: 12px; }
.panel h2 { margin: 0; font-size: 16px; }
.summary dl { margin: 0; display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.summary dt { color: var(--text-3); font-size: 11.5px; }
.summary dd { margin: 4px 0 0; font-size: 20px; font-family: var(--font-num); }
.summary dd small { font-size: 11px; color: var(--text-3); }
.coach-summary { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.8; }
video { width: 100%; max-height: 46vh; border-radius: 8px; background: #0b0b0e; }
.transcript { margin: 0; padding-left: 18px; display: grid; gap: 10px; }
.transcript .num { color: var(--text-3); font-size: 11.5px; }
.transcript .q { margin: 4px 0 2px; color: var(--text-3); font-size: 12px; }
.transcript .a { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.75; }
.annotations { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.annotations li { padding: 10px 12px; border: 1px solid var(--border); border-radius: 8px; display: grid; gap: 4px; }
.annotations p { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.7; }
.annotations span { color: var(--text-3); font-size: 11px; }
.stamp { width: fit-content; padding: 2px 8px; border: 1px solid var(--accent); border-radius: 999px; background: transparent; color: var(--accent-strong); font-size: 11px; cursor: pointer; }
.annotation-form { display: grid; gap: 8px; padding-top: 8px; border-top: 1px solid var(--divider); }
.annotation-form .row { display: flex; align-items: center; gap: 10px; color: var(--text-3); font-size: 12px; }
.stamp-view { color: var(--text); font-family: var(--font-num); }
.mini { padding: 2px 8px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-2); font-size: 11px; cursor: pointer; }
.annotation-form .button { width: fit-content; }
</style>
