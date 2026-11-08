<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

interface Topic { id: string; category: string; title: string; prompt: string }
interface Turn { role: string; text: string }
interface Dimension { name: string; score: number; comment: string }
interface Result { score: number; dimensions: Dimension[]; summary: string; suggestions: string[] }
interface GroupItem {
  id: string
  topicTitle: string
  topicPrompt: string
  status: string
  turns: Turn[]
  result: Result | null
  createdAt: string
}
interface HistoryItem { id: string; topicTitle: string; status: string; score: number | null; createdAt: string }

const route = useRoute()
const router = useRouter()
const topics = shallowRef<Topic[]>([])
const history = shallowRef<HistoryItem[]>([])
const group = shallowRef<GroupItem | null>(null)
const input = shallowRef('')
const loading = shallowRef(true)
const busy = shallowRef(false)
const error = shallowRef('')

const groupId = computed(() => String(route.params.id || ''))
const roleLabel: Record<string, string> = { host: '主持人', '候选人 A': '候选人 A', '候选人 B': '候选人 B', user: '我' }
const roleClass: Record<string, string> = { host: 'host', '候选人 A': 'peer', '候选人 B': 'peer', user: 'me' }

async function loadTopics(): Promise<void> {
  loading.value = true
  try {
    const [topicResponse, historyResponse] = await Promise.all([
      api.get<ApiEnvelope<Topic[]>>('/group-interviews/topics'),
      api.get<ApiEnvelope<HistoryItem[]>>('/group-interviews', { params: { limit: 8 } }),
    ])
    topics.value = topicResponse.data.data
    history.value = historyResponse.data.data
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

async function loadGroup(id: string): Promise<void> {
  loading.value = true
  try {
    const response = await api.get<ApiEnvelope<GroupItem>>(`/group-interviews/${id}`)
    group.value = response.data.data
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

async function start(topic: Topic): Promise<void> {
  if (busy.value) return
  busy.value = true
  try {
    const response = await api.post<ApiEnvelope<GroupItem>>('/group-interviews', { topicId: topic.id })
    await router.push(`/group-interview/${response.data.data.id}`)
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = false
  }
}

async function send(): Promise<void> {
  if (!group.value || busy.value || !input.value.trim()) return
  busy.value = true
  error.value = ''
  try {
    const response = await api.post<ApiEnvelope<GroupItem>>(`/group-interviews/${group.value.id}/messages`, {
      content: input.value.trim(),
    })
    group.value = response.data.data
    input.value = ''
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = false
  }
}

async function finish(): Promise<void> {
  if (!group.value || busy.value) return
  busy.value = true
  try {
    const response = await api.post<ApiEnvelope<GroupItem>>(`/group-interviews/${group.value.id}/finish`)
    group.value = response.data.data
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = false
  }
}

watch(groupId, (id) => {
  if (id) void loadGroup(id)
  else void loadTopics()
})

onMounted(() => {
  if (groupId.value) void loadGroup(groupId.value)
  else void loadTopics()
})
</script>

<template>
  <div class="page">
    <div v-if="error" class="error-banner">{{ error }}</div>

    <template v-if="!group">
      <header class="page-heading">
        <div>
          <p class="eyebrow">群面模拟</p>
          <h1 class="page-title">无领导小组讨论，<br /><span>先学会在多人里说话。</span></h1>
          <p class="page-lead">一位主持人、两位虚拟候选人，和你一起讨论同一个题目；结束后评估观点、倾听、协作与表达。</p>
        </div>
        <div class="participants" aria-label="参与角色">
          <span>主持人</span><span>候选人 A</span><span>候选人 B</span><span class="me">我</span>
        </div>
      </header>

      <section v-if="loading" class="topic-grid"><div v-for="n in 4" :key="n" class="topic-card panel skeleton" /></section>
      <section v-else class="topic-grid">
        <article v-for="topic in topics" :key="topic.id" class="topic-card panel">
          <span class="tag">{{ topic.category }}</span>
          <h2>{{ topic.title }}</h2>
          <p class="prompt">{{ topic.prompt }}</p>
          <button type="button" class="button primary" :disabled="busy" @click="start(topic)">开始讨论</button>
        </article>
      </section>

      <section v-if="history.length" class="history panel">
        <h2>历史群面</h2>
        <ul>
          <li v-for="item in history" :key="item.id">
            <button type="button" @click="router.push(`/group-interview/${item.id}`)">
              <span>{{ item.topicTitle }}</span>
              <small>{{ item.status === 'FINISHED' ? `${item.score ?? '—'} 分` : '进行中' }}</small>
              <small>{{ new Date(item.createdAt).toLocaleDateString('zh-CN') }}</small>
            </button>
          </li>
        </ul>
      </section>
    </template>

    <template v-else>
      <header class="chat-head">
        <button type="button" class="back" @click="router.push('/group-interview')">← 返回群面列表</button>
        <h1>{{ group.topicTitle }}</h1>
        <p class="prompt">{{ group.topicPrompt }}</p>
      </header>

      <section class="chat panel" aria-live="polite">
        <ol class="turns">
          <li v-for="(turn, index) in group.turns" :key="index" class="turn" :class="roleClass[turn.role] || 'peer'">
            <span class="who">{{ roleLabel[turn.role] || turn.role }}</span>
            <p>{{ turn.text }}</p>
          </li>
        </ol>
        <div v-if="group.status === 'ACTIVE'" class="composer">
          <textarea v-model="input" rows="3" class="field" placeholder="回应刚才的观点，或补充你的判断…" @keydown.ctrl.enter="send" />
          <div class="composer-actions">
            <span class="hint">Ctrl + Enter 发送</span>
            <button type="button" class="button primary" :disabled="busy || !input.trim()" @click="send">{{ busy ? '等待发言…' : '发送' }}</button>
            <button type="button" class="button secondary" :disabled="busy" @click="finish">结束讨论</button>
          </div>
        </div>
      </section>

      <section v-if="group.result" class="result panel">
        <div class="score"><strong>{{ group.result.score }}</strong><span>/ 100</span></div>
        <p class="summary">{{ group.result.summary }}</p>
        <ul class="dimensions">
          <li v-for="dimension in group.result.dimensions" :key="dimension.name">
            <div class="dimension-head"><span>{{ dimension.name }}</span><b>{{ dimension.score }}</b></div>
            <div class="bar"><i :style="{ width: `${dimension.score}%` }" /></div>
            <p>{{ dimension.comment }}</p>
          </li>
        </ul>
        <div v-if="group.result.suggestions.length" class="suggestions">
          <h3>下一次可以这样改</h3>
          <ul><li v-for="tip in group.result.suggestions" :key="tip">{{ tip }}</li></ul>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page-heading { display: flex; justify-content: space-between; gap: 26px; align-items: end; margin-bottom: 24px; }
.page-title span { color: var(--accent-strong); }
.participants { display: flex; gap: 6px; flex-wrap: wrap; max-width: 260px; }
.participants span { padding: 5px 10px; border: 1px solid var(--border); border-radius: 999px; font-size: 11.5px; color: var(--text-2); }
.participants .me { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.topic-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; }
.topic-card { display: grid; gap: 10px; padding: 16px; align-content: start; }
.topic-card h2 { margin: 0; font-size: 16px; }
.prompt { margin: 0; color: var(--text-2); font-size: 12.5px; line-height: 1.7; }
.topic-card .button { justify-self: start; margin-top: 4px; }
.history { margin-top: 20px; padding: 16px; }
.history h2 { margin: 0 0 10px; font-size: 14px; }
.history ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.history button { width: 100%; display: flex; gap: 10px; align-items: center; border: 1px solid var(--border); background: transparent; border-radius: 10px; padding: 8px 10px; cursor: pointer; text-align: left; color: var(--text); }
.history small { margin-left: auto; color: var(--text-3); font-size: 11.5px; }
.chat-head { margin-bottom: 16px; }
.back { border: 0; background: transparent; color: var(--text-3); font-size: 12px; cursor: pointer; padding: 0; }
.chat-head h1 { margin: 8px 0 6px; font-size: 22px; }
.chat { padding: 16px; display: grid; gap: 14px; }
.turns { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; max-height: 520px; overflow: auto; }
.turn { display: grid; gap: 4px; padding: 10px 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); max-width: 86%; }
.turn.me { justify-self: end; background: var(--accent-soft); border-color: var(--accent); }
.turn.host { background: color-mix(in srgb, var(--accent) 6%, var(--surface)); }
.turn p { margin: 0; font-size: 13.5px; line-height: 1.65; }
.who { font-size: 11px; color: var(--text-3); }
.composer { display: grid; gap: 8px; border-top: 1px solid var(--border); padding-top: 12px; }
.composer-actions { display: flex; align-items: center; gap: 8px; }
.composer-actions .hint { margin-right: auto; color: var(--text-3); font-size: 11.5px; }
.result { margin-top: 16px; padding: 18px; }
.result .score strong { font: 700 40px/1 var(--font-ui); color: var(--accent-strong); }
.result .score span { color: var(--text-3); font-size: 12px; margin-left: 4px; }
.summary { margin: 8px 0 14px; color: var(--text-2); font-size: 12.5px; }
.dimensions { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.dimension-head { display: flex; justify-content: space-between; font-size: 12.5px; color: var(--text); }
.bar { height: 6px; border-radius: 999px; background: var(--border); overflow: hidden; margin: 4px 0; }
.bar i { display: block; height: 100%; background: var(--accent); }
.dimensions p { margin: 0; color: var(--text-3); font-size: 11.5px; }
.suggestions { margin-top: 14px; border-top: 1px solid var(--border); padding-top: 10px; }
.suggestions h3 { margin: 0 0 6px; font-size: 12.5px; }
.suggestions ul { margin: 0; padding-left: 18px; color: var(--text-2); font-size: 12.5px; display: grid; gap: 4px; }
.skeleton { min-height: 160px; }
@media (max-width: 800px) { .page-heading { flex-direction: column; align-items: start; } }
</style>
