<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import SelectField from '@/components/ui/SelectField.vue'
import DeleteTrainingDialog from '@/components/training/DeleteTrainingDialog.vue'
import { api, errorMessage, MODEL_REQUEST_TIMEOUT_MS } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

const router = useRouter()

interface HistoryItem {
  id: string
  sceneId: string
  sceneTitle: string
  status: 'ACTIVE' | 'FINISHED'
  channel?: 'TEXT' | 'VOICE' | 'VIDEO'
  recordingUrl?: string | null
  delivery?: { engine?: string } | null
  durationSeconds?: number | null
  currentRound: number
  maxRounds: number
  startedAt: string
  finishedAt: string | null
  overallScore: number | null
  evaluationDegraded: boolean
  archivedAt: string | null
}

const replay = shallowRef<{ url: string; channel: string; title: string; sessionId: string } | null>(null)
const replayMarks = shallowRef<Array<{ text: string; start: number; end: number }>>([])
const replayMedia = ref<HTMLVideoElement | HTMLAudioElement | null>(null)
const replayError = shallowRef('')


async function openReplay(item: HistoryItem): Promise<void> {
  if (!item.recordingUrl) return
  replayError.value = ''
  replayMarks.value = []
  replay.value = { url: item.recordingUrl, channel: item.channel ?? 'VOICE', title: item.sceneTitle, sessionId: item.id }
  try {
    const detail = await api.get<ApiEnvelope<{ delivery?: { marks?: Array<{ text: string; start: number; end: number }> } }>>(
      `/training-sessions/${item.id}`,
    )
    replayMarks.value = detail.data.data.delivery?.marks ?? []
  } catch {
    replayMarks.value = []
  }
}

function seekTo(seconds: number): void {
  if (replayMedia.value) {
    replayMedia.value.currentTime = seconds
    void replayMedia.value.play().catch(() => undefined)
  }
}

const items = shallowRef<HistoryItem[]>([])
const visibleCount = shallowRef(10)
const shownItems = computed(() => visibleItems.value.slice(0, visibleCount.value))
const remaining = computed(() => Math.max(0, visibleItems.value.length - visibleCount.value))
const loading = shallowRef(true)
const error = shallowRef('')
const query = shallowRef('')
const status = shallowRef('全部记录')
const archivedMode = shallowRef(false)
const deletingItem = shallowRef<HistoryItem | null>(null)
const deleting = shallowRef(false)
const deleteError = shallowRef('')
const scoringId = shallowRef('')
const visibleItems = computed(() => items.value.filter((item) => {
  const matchesQuery = `${item.sceneTitle} ${item.status}`.toLowerCase().includes(query.value.trim().toLowerCase())
  const matchesStatus = status.value === '全部记录' || (status.value === '进行中' ? item.status === 'ACTIVE' : item.status === 'FINISHED')
  return matchesQuery && matchesStatus
}))

onMounted(load)

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const response = await api.get<ApiEnvelope<HistoryItem[]>>('/training-sessions', { params: { archived: archivedMode.value } })
    items.value = response.data.data
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

async function toggleArchive(item: HistoryItem): Promise<void> {
  try {
    await api.post(`/training-sessions/${item.id}/${item.archivedAt ? 'restore' : 'archive'}`)
    await load()
  } catch (reason) { error.value = errorMessage(reason) }
}

function askDelete(item: HistoryItem): void {
  deleteError.value = ''
  deletingItem.value = item
}

async function confirmDelete(): Promise<void> {
  const item = deletingItem.value
  if (!item || deleting.value) return
  deleting.value = true
  deleteError.value = ''
  try {
    await api.delete(`/training-sessions/${item.id}`)
    items.value = items.value.filter((candidate) => candidate.id !== item.id)
    deletingItem.value = null
  } catch (reason) {
    deleteError.value = errorMessage(reason)
  } finally {
    deleting.value = false
  }
}

async function generateScore(item: HistoryItem): Promise<void> {
  if (scoringId.value) return
  scoringId.value = item.id
  error.value = ''
  try {
    await api.post(
      `/training-sessions/${item.id}/finish`,
      null,
      { params: { create_plan: true }, timeout: MODEL_REQUEST_TIMEOUT_MS },
    )
    await router.push(`/report/${item.id}`)
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    scoringId.value = ''
  }
}

async function exportReports(): Promise<void> {
  try {
    const response = await api.get<Blob>('/training-sessions/export', { responseType: 'blob' })
    const url = URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = '面试训练报告.csv'
    link.click()
    URL.revokeObjectURL(url)
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}
</script>

<template>
  <div class="page history-page">
    <header class="page-heading">
      <div><p class="eyebrow">训练档案</p><h1 class="page-title">每次练习，<br>都有迹可循。</h1><p class="page-lead">回看历史对话和评分报告，也可以导出训练记录。</p></div>
      <button class="button signal" type="button" :disabled="!items.length" @click="exportReports">导出训练报告</button>
    </header>
    <div v-if="error" class="error-banner">{{ error }}</div>
    <section class="history-tools">
      <input v-model="query" class="field" type="search" placeholder="搜索面试场景" aria-label="搜索面试场景">
      <SelectField
        :model-value="status"
        :options="['全部记录', '进行中', '已完成'].map((item) => ({ value: item, label: item }))"
        aria-label="筛选训练状态"
        @update:model-value="status = $event"
      />
      <button class="button secondary" type="button" @click="load">刷新</button>
      <label class="archive-toggle"><input v-model="archivedMode" type="checkbox" @change="load"> 查看归档记录</label>
    </section>
    <div v-if="loading" class="panel skeleton history-loading" />
    <div v-else-if="visibleItems.length" class="history-list">
      <article v-for="item in shownItems" :key="item.id" class="history-item panel">
        <div class="history-copy">
          <div class="history-meta">
            <span class="tag" :class="{ voice: item.channel === 'VOICE', video: item.channel === 'VIDEO' }">{{ item.channel === 'VIDEO' ? '视频面试' : item.channel === 'VOICE' ? (item.delivery?.engine === 'pipeline' ? '语音对练 · 本地' : '语音对练') : '文字对练' }}</span>
            <span class="tag">{{ item.status === 'FINISHED' ? '已完成' : '进行中' }}</span>
            <span>{{ new Date(item.startedAt).toLocaleString('zh-CN') }}</span>
          </div>
          <h2>{{ item.sceneTitle }}</h2>
          <p>完成 {{ item.currentRound }} / {{ item.maxRounds }} 轮{{ item.durationSeconds ? ' · 通话 ' + Math.max(1, Math.round(item.durationSeconds / 60)) + ' 分钟' : '' }}{{ item.evaluationDegraded ? ' · 暂定评分' : '' }}{{ item.status === 'FINISHED' && item.overallScore === null ? ' · 未生成评分' : '' }}</p>
        </div>
        <strong v-if="item.overallScore !== null" class="score">{{ item.overallScore }}<small> / 100</small></strong>
        <div class="history-actions">
          <button v-if="item.recordingUrl" class="button ghost" type="button" @click="openReplay(item)">回放</button>
          <RouterLink v-if="item.overallScore !== null" class="button" :to="`/report/${item.id}`">查看评分报告 →</RouterLink>
          <button
            v-else-if="item.status === 'FINISHED'"
            class="button"
            type="button"
            :disabled="Boolean(scoringId)"
            :title="scoringId === item.id ? '正在生成五维评分' : '为这场已结束的训练补生成评分报告'"
            @click="generateScore(item)"
          >{{ scoringId === item.id ? '正在评分…' : '生成评分 →' }}</button>
          <RouterLink v-else class="button" :to="`/training/${item.id}`">继续训练 →</RouterLink>
          <RouterLink v-if="item.status === 'FINISHED'" class="replay-link" :to="`/training/${item.id}`">回放对话</RouterLink>
          <button v-if="item.status === 'FINISHED'" class="archive-button" type="button" @click="toggleArchive(item)">{{ item.archivedAt ? '恢复记录' : '归档' }}</button>
          <button class="delete-button" type="button" :aria-label="`彻底删除${item.sceneTitle}训练记录`" @click="askDelete(item)">彻底删除</button>
        </div>
      </article>
      <button v-if="remaining" class="button secondary load-more" type="button" @click="visibleCount += 10">显示更多（还有 {{ remaining }} 条）</button>
    </div>
    <div v-else class="empty panel">没有符合条件的训练记录。完成一次面试模拟后，记录会显示在这里。</div>
    <DeleteTrainingDialog
      v-if="deletingItem"
      :scene-title="deletingItem.sceneTitle"
      :current-round="deletingItem.currentRound"
      :max-rounds="deletingItem.maxRounds"
      :busy="deleting"
      :error="deleteError"
      @confirm="confirmDelete"
      @cancel="deletingItem = null"
    />
  </div>
  <div v-if="replay" class="replay-mask" @click.self="replay = null">
    <div class="replay-box">
      <header>
        <strong>{{ replay.title }}</strong>
        <button type="button" class="close" @click="replay = null">×</button>
      </header>
      <video
        v-if="replay.channel === 'VIDEO'"
        ref="replayMedia"
        :src="replay.url"
        controls
        autoplay
        playsinline
        @error="replayError = '这段录像已被清理，无法回放'"
      />
      <audio v-else ref="replayMedia" :src="replay.url" controls autoplay @error="replayError = '这段录音已被清理，无法回放'" />
      <div v-if="replayMarks.length" class="marks">
        <button v-for="(mark, index) in replayMarks" :key="index" type="button" @click="seekTo(mark.start)">
          {{ String(index + 1).padStart(2, '0') }} {{ mark.text }}
        </button>
      </div>
      <p v-if="replayError" class="replay-error">{{ replayError }}</p>
      <p class="replay-hint">回放的是本次{{ replay.channel === 'VIDEO' ? '视频面试' : '语音对练' }}的原始录音，不对外分享。</p>
    </div>
  </div>
</template>

<style scoped>
.history-page { max-width: 1040px; }
.load-more { margin: 18px auto 0; display: flex; }
.history-tools { margin-bottom: 18px; display: grid; grid-template-columns: 1fr 190px auto; gap: 10px; }
.history-list { display: grid; gap: 12px; }
.history-item { padding: 22px 24px; display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 24px; }
.history-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 12px; }
.history-meta { display: flex; align-items: center; gap: 12px; color: var(--ink-soft); font-size: 12px; }
.history-copy h2 { margin: 12px 0 5px; font: 700 22px/1.3 var(--font-ui); }
.history-copy p { margin: 0; color: var(--ink-soft); font-size: 13px; }
.score { color: var(--signal); font: 700 30px/1 var(--font-ui); white-space: nowrap; }
.score small { color: var(--ink-soft); font: 400 12px/1 sans-serif; }
.history-loading { min-height: 200px; }
.archive-toggle { display:flex; align-items:center; gap:8px; color:var(--ink-soft); font-size:12px; white-space:nowrap; }
.replay-link,.archive-button { border:0; background:transparent; color:var(--mint-dark); cursor:pointer; font-size:12px; font-weight:700; }
.delete-button { border: 0; background: transparent; color: var(--danger); cursor: pointer; font-size: 12px; font-weight: 700; }
.delete-button:hover { text-decoration: underline; }
@media (max-width: 700px) { .history-item { grid-template-columns: 1fr; gap: 14px; } .history-actions { justify-content: flex-start; } .history-tools { grid-template-columns: 1fr; } }
.history-item { background:var(--glass); }
.score { background:none;color:var(--text);font-weight:500; }
.replay-link,.archive-button { color:var(--text-2); }
.delete-button { color:#cf9a92; }
.tag.voice { border-color: var(--accent); color: var(--accent-strong); }
.button.ghost { background: transparent; border: 1px solid var(--line); color: var(--text-2); }
.tag.video { border-color: #8a6bbf; color: #6b4fa0; }
.replay-mask { position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; padding: 24px; background: rgba(20,16,13,.62); }
.replay-box { width: min(860px, 100%); max-height: 90vh; display: flex; flex-direction: column; padding: 18px; border-radius: 16px; background: var(--card); box-shadow: 0 30px 70px rgba(0,0,0,.35); }
.replay-box header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.replay-box video { width: 100%; max-height: 64vh; border-radius: 10px; background: #12100e; object-fit: contain; }
.replay-box audio { width: 100%; border-radius: 10px; }
.replay-box .close { width: 30px; height: 30px; border: 0; border-radius: 50%; background: var(--bg-2); color: var(--text-2); font-size: 18px; cursor: pointer; }
.marks { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.marks button { padding: 6px 12px; border: 1px solid var(--line); border-radius: 999px; background: var(--bg-2); color: var(--text-2); font-size: 12px; cursor: pointer; }
.marks button:hover { border-color: var(--accent); color: var(--accent-strong); }
.replay-hint { margin: 10px 0 0; color: var(--text-3); font-size: 12px; }
.replay-error { margin: 10px 0 0; color: #a4342a; font-size: 12px; }
</style>
