<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'

import DeleteTrainingDialog from '@/components/training/DeleteTrainingDialog.vue'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

interface HistoryItem {
  id: string
  sceneId: string
  sceneTitle: string
  status: 'ACTIVE' | 'FINISHED'
  currentRound: number
  maxRounds: number
  startedAt: string
  finishedAt: string | null
  overallScore: number | null
  evaluationDegraded: boolean
  archivedAt: string | null
}

const items = shallowRef<HistoryItem[]>([])
const loading = shallowRef(true)
const error = shallowRef('')
const query = shallowRef('')
const status = shallowRef('全部记录')
const archivedMode = shallowRef(false)
const deletingItem = shallowRef<HistoryItem | null>(null)
const deleting = shallowRef(false)
const deleteError = shallowRef('')
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
      <select v-model="status" class="field" aria-label="筛选训练状态"><option>全部记录</option><option>进行中</option><option>已完成</option></select>
      <button class="button secondary" type="button" @click="load">刷新</button>
      <label class="archive-toggle"><input v-model="archivedMode" type="checkbox" @change="load"> 查看归档记录</label>
    </section>
    <div v-if="loading" class="panel skeleton history-loading" />
    <div v-else-if="visibleItems.length" class="history-list">
      <article v-for="item in visibleItems" :key="item.id" class="history-item panel">
        <div class="history-copy">
          <div class="history-meta"><span class="tag">{{ item.status === 'FINISHED' ? '已完成' : '进行中' }}</span><span>{{ new Date(item.startedAt).toLocaleString('zh-CN') }}</span></div>
          <h2>{{ item.sceneTitle }}</h2>
          <p>完成 {{ item.currentRound }} / {{ item.maxRounds }} 轮{{ item.evaluationDegraded ? ' · 暂定评分' : '' }}</p>
        </div>
        <strong v-if="item.overallScore !== null" class="score">{{ item.overallScore }}<small> / 100</small></strong>
        <div class="history-actions">
          <RouterLink class="button" :to="item.overallScore !== null ? `/report/${item.id}` : `/training/${item.id}`">
            {{ item.overallScore !== null ? '查看评分报告' : '回到训练' }} →
          </RouterLink>
          <RouterLink v-if="item.status === 'FINISHED'" class="replay-link" :to="`/training/${item.id}`">回放对话</RouterLink>
          <button v-if="item.status === 'FINISHED'" class="archive-button" type="button" @click="toggleArchive(item)">{{ item.archivedAt ? '恢复记录' : '归档' }}</button>
          <button class="delete-button" type="button" :aria-label="`彻底删除${item.sceneTitle}训练记录`" @click="askDelete(item)">彻底删除</button>
        </div>
      </article>
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
</template>

<style scoped>
.history-page { max-width: 1040px; }
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
</style>
