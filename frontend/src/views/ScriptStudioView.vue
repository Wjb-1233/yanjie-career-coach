<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'
import { MessageSquareText } from 'lucide-vue-next'

import ScriptVersionCard from '@/components/scenes/ScriptVersionCard.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import { api, errorMessage, MODEL_REQUEST_TIMEOUT_MS } from '@/lib/api'
import type { ApiEnvelope, MistakeItem, ScriptVersion } from '@/lib/types'

interface ScriptResult { versions: ScriptVersion[]; coachNote: string; degraded: boolean }

const mistakes = shallowRef<MistakeItem[]>([])
const total = shallowRef(0)
const history = shallowRef<ScriptVersion[]>([])
const loading = shallowRef(true)
let audio: HTMLAudioElement | null = null
const error = shallowRef('')
const generating = shallowRef<string | null>(null)
const results = shallowRef<Record<string, ScriptResult>>({})
const showResolved = shallowRef(false)
const deepRewrite = shallowRef<{ sceneId: string; original: string; dimension: string; objective: string } | null>(null)
const deepBusy = shallowRef(false)
const deepResult = shallowRef<ScriptResult | null>(null)
const freeOriginal = shallowRef('')
const freeObjective = shallowRef('')

async function startFreeRewrite(): Promise<void> {
  if (!freeOriginal.value.trim() || deepBusy.value) return
  deepRewrite.value = {
    sceneId: mattersFirstScene.value,
    original: freeOriginal.value.trim(),
    dimension: '',
    objective: freeObjective.value.trim() || '把这句话改得更具体、更可核查',
  }
  await generateDeep()
  freeOriginal.value = ''
}

const page = shallowRef(1)
const PAGE_SIZE = 6

const route = useRoute()
const keyOf = (item: MistakeItem) => `${item.sessionId}-${item.roundNo}-${item.dimension}`
const pending = computed(() => mistakes.value)
const resolvedCount = computed(() => mistakes.value.filter((item) => item.status === 'RESOLVED').length)
const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const pagedPending = computed(() => pending.value)

onMounted(async () => {
  await load()
  const { sceneId, original, dimension, objective } = route.query
  if (typeof original === 'string' && original.trim()) {
    deepRewrite.value = {
      sceneId: typeof sceneId === 'string' ? sceneId : mattersFirstScene.value,
      original: original.slice(0, 2000),
      dimension: typeof dimension === 'string' ? dimension : '',
      objective: typeof objective === 'string' ? objective : '把这句话改得更具体、更可核查',
    }
  }
})

const mattersFirstScene = computed(() => mistakes.value[0]?.sceneId ?? '')
watch([page, showResolved], () => { void load() })

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [mistakeResponse, scriptResponse] = await Promise.all([
      api.get<ApiEnvelope<{ items: MistakeItem[]; total: number } | MistakeItem[]>>('/training-sessions/mistakes', { params: { page: page.value, size: PAGE_SIZE, include_resolved: showResolved.value } }),
      // 已保存版本仅用于右上角入口的计数，失败不影响待优化列表
      api.get<ApiEnvelope<ScriptVersion[]>>('/scripts').catch(() => null),
    ])
    const payload = mistakeResponse.data.data
    // 兼容旧版直接返回数组的接口
    const isLegacy = Array.isArray(payload)
    const list = isLegacy ? payload : payload.items
    // 旧接口直接返回全部数组时，前端自己分页
    mistakes.value = isLegacy
      ? list.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE)
      : list
    total.value = isLegacy ? list.length : payload.total
    history.value = scriptResponse ? scriptResponse.data.data : []
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

async function generate(item: MistakeItem): Promise<void> {
  const key = keyOf(item)
  if (generating.value) return
  generating.value = key
  error.value = ''
  try {
    const response = await api.post<ApiEnvelope<ScriptResult>>('/scripts/generate', {
      sceneId: item.sceneId,
      objective: item.question ? `回应面试官的问题：${item.question}` : `回应第 ${item.roundNo} 轮问题`,
      originalText: item.quote,
      dimension: item.dimension,
      sourceSessionId: item.sessionId,
      sourceRound: item.roundNo,
    }, { timeout: MODEL_REQUEST_TIMEOUT_MS })
    results.value = { ...results.value, [key]: response.data.data }
    await load()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    generating.value = null
  }
}

async function generateDeep(): Promise<void> {
  const draft = deepRewrite.value
  if (!draft || deepBusy.value) return
  deepBusy.value = true
  error.value = ''
  try {
    const response = await api.post<ApiEnvelope<ScriptResult>>('/scripts/generate', {
      sceneId: draft.sceneId,
      objective: draft.objective,
      originalText: draft.original,
      dimension: draft.dimension || undefined,
    }, { timeout: MODEL_REQUEST_TIMEOUT_MS })
    deepResult.value = response.data.data
    await load()
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    deepBusy.value = false
  }
}

async function playPreview(version: ScriptVersion): Promise<void> {
  try {
    const response = await api.post<ApiEnvelope<{ url: string }>>('/scripts/preview', { text: version.content })
    audio?.pause()
    audio = new Audio(response.data.data.url)
    await audio.play().catch(() => undefined)
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

async function setStatus(item: MistakeItem, status: 'RESOLVED' | 'PENDING'): Promise<void> {
  try {
    await api.patch('/training-sessions/mistakes/state', {
      sessionId: item.sessionId,
      roundNo: item.roundNo,
      dimension: item.dimension,
      status,
    })
    await load()
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

async function favorite(version: ScriptVersion): Promise<void> {
  try {
    const response = await api.post<ApiEnvelope<{ favorite: boolean }>>(`/scripts/${version.id}/favorite`)
    const nextFavorite = response.data.data.favorite
    history.value = history.value.map((item) => item.id === version.id ? { ...item, favorite: nextFavorite } : item)
    results.value = Object.fromEntries(
      Object.entries(results.value).map(([key, result]) => [
        key,
        { ...result, versions: result.versions.map((item) => item.id === version.id ? { ...item, favorite: nextFavorite } : item) },
      ]),
    )
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}
</script>

<template>
  <div class="page studio-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">话术优化</p>
        <h1 class="page-title">把说过的话，改得更好。</h1>
        <p class="page-lead">训练里低于 3 分的回答会自动收进来，挑一条生成三种风格。</p>
      </div>
      <RouterLink class="saved-entry" to="/scripts/saved">已保存 {{ history.length }} 个 →</RouterLink>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <section v-if="!deepRewrite" class="block free-form">
      <header class="block-head">
        <div><h2>直接改一句</h2><span>不用等训练，把自己想改的句子贴进来</span></div>
      </header>
      <div class="deep-form panel">
        <label class="deep-field">
          <span>要改的原句</span>
          <textarea v-model="freeOriginal" class="field" rows="3" maxlength="2000" placeholder="例如：这个项目我负责后端，做了很多优化。" />
        </label>
        <label class="deep-field">
          <span>想达到的效果</span>
          <input v-model="freeObjective" class="field" maxlength="500" placeholder="例如：说清楚我具体做了什么、结果怎么样" />
        </label>
        <div class="deep-actions">
          <span class="deep-hint">会生成正式、亲和、简洁三种版本，可保存和试听。</span>
          <button class="button" type="button" :disabled="deepBusy || !freeOriginal.trim()" @click="startFreeRewrite">
            {{ deepBusy ? '生成中…' : '生成三种风格' }}
          </button>
        </div>
      </div>
      <div v-if="deepResult" class="versions deep-versions">
        <ScriptVersionCard v-for="version in deepResult.versions" :key="version.id" :version="version" :show-actions="true" @favorite="favorite" @preview="playPreview" />
        <p class="coach-note">{{ deepResult.coachNote }}</p>
      </div>
    </section>

    <section v-if="deepRewrite" class="block deep">
      <header class="block-head">
        <div><h2>深入改写</h2><span>来自报告中的措辞升级</span></div>
        <button class="text-btn" type="button" @click="deepRewrite = null; deepResult = null">收起</button>
      </header>

      <div class="deep-form panel">
        <label class="deep-field">
          <span>要改的原句</span>
          <textarea v-model="deepRewrite.original" class="field" rows="3" maxlength="2000" />
        </label>
        <label class="deep-field">
          <span>希望达到的效果</span>
          <input v-model="deepRewrite.objective" class="field" maxlength="500" placeholder="例如：把结果说清楚，带上可核实的数字" />
        </label>
        <div class="deep-actions">
          <button class="button" type="button" :disabled="deepBusy || !deepRewrite.original.trim()" @click="generateDeep">
            {{ deepBusy ? '生成中…' : '生成三种风格' }}
          </button>
        </div>
      </div>

      <div v-if="deepResult" class="versions deep-versions">
        <ScriptVersionCard
          v-for="version in deepResult.versions"
          :key="version.id"
          :version="version"
          :show-actions="true"
          @favorite="favorite"
          @preview="playPreview"
        />
        <p class="coach-note">{{ deepResult.coachNote }}</p>
      </div>
    </section>

    <section class="block">
      <header class="block-head">
        <div><h2>待优化</h2><span>{{ pending.length }} 条</span></div>
        <button v-if="resolvedCount" class="text-btn" type="button" @click="showResolved = !showResolved">
          {{ showResolved ? '隐藏已解决' : `显示已解决（${resolvedCount}）` }}
        </button>
      </header>

      <div v-if="loading" class="skeleton block-loading" />
      <EmptyState
        v-else-if="!pending.length"
        title="还没有待优化的句子"
        description="完成一次场景训练并生成评分后，低于 3 分的回答会自动出现在这里。"
      >
        <RouterLink class="button secondary" to="/scenes">去练一场</RouterLink>
      </EmptyState>

      <template v-else>
        <article v-for="item in pagedPending" :key="keyOf(item)" class="mistake" :class="{ resolved: item.status === 'RESOLVED' }">
          <header class="mistake-head">
            <span class="dim">{{ item.dimension }}</span>
            <span class="score num">{{ item.score }} / 5</span>
            <span class="meta">第 {{ item.roundNo }} 轮 · {{ item.sceneTitle }}</span>
            <span v-if="item.generatedCount" class="badge done">已生成 {{ item.generatedCount }} 版</span>
          </header>

          <p v-if="item.question" class="question"><b>问</b>{{ item.question }}</p>
          <p class="quote"><b>我的原话</b>{{ item.quote }}</p>
          <p class="reason"><b>问题</b>{{ item.reason }}</p>

          <div class="mistake-actions">
            <button class="button" type="button" :disabled="generating !== null" @click="generate(item)">
              <MessageSquareText :size="14" :stroke-width="1.8" aria-hidden="true" />
              {{ generating === keyOf(item) ? '生成中…' : item.generatedCount ? '再生成三种风格' : '生成三种风格' }}
            </button>
            <RouterLink class="text-btn" :to="`/report/${item.sessionId}`">查看报告</RouterLink>
            <button
              v-if="item.status !== 'RESOLVED'"
              class="text-btn"
              type="button"
              :disabled="!item.canResolve"
              :title="item.canResolve ? '标记为已解决' : '先再练一次，才能标记已解决'"
              @click="setStatus(item, 'RESOLVED')"
            >已解决</button>
          </div>

          <div v-if="results[keyOf(item)]" class="versions">
            <ScriptVersionCard
              v-for="version in results[keyOf(item)]?.versions ?? []"
              @preview="playPreview"
              :key="version.id"
              :version="version"
              :scene-title="item.sceneTitle"
              show-actions
              @favorite="favorite"
            />
          </div>
        </article>
      </template>

      <nav v-if="pageCount > 1" class="pager" aria-label="待优化分页">
        <button class="text-btn" type="button" :disabled="page <= 1" @click="page -= 1">上一页</button>
        <span class="num">{{ page }} / {{ pageCount }}</span>
        <button class="text-btn" type="button" :disabled="page >= pageCount" @click="page += 1">下一页</button>
      </nav>
    </section>

  </div>
</template>

<style scoped>
.free-form { margin-bottom: 18px; }
.deep-hint { color: var(--text-3); font-size: 12px; margin-right: auto; }
.deep-actions { display: flex; align-items: center; gap: 12px; }
.studio-page { max-width: 1040px; }
.block { margin-top: 38px; }
.block-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--divider); }
.block-head > div { display: flex; align-items: baseline; gap: 12px; }
.block-head h2 { margin: 0; color: var(--text); font-size: 14px; font-weight: 500; }
.block-head span { color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.block-loading { min-height: 180px; }
.block-empty { margin: 16px 0 0; color: var(--text-3); font-size: 12.5px; line-height: 1.9; }

.mistake { padding: 18px 20px; margin-bottom: 12px; }
.mistake.resolved { opacity: .55; }
.mistake-head { display: flex; align-items: baseline; flex-wrap: wrap; gap: 12px; }
.dim { color: var(--accent-strong); font-size: 12px; letter-spacing: .04em; }
.score { color: var(--text-3); font-size: 12px; }
.meta { color: var(--text-3); font-size: 11px; }
.badge { padding: 2px 7px; border: 1px solid var(--border); border-radius: 4px; color: var(--text-3); font-size: 10.5px; }
.badge.done { border-color: var(--accent); color: var(--accent-strong); }
.question { margin: 10px 0 0; color: var(--text-2); font-size: 13px; line-height: 1.8; }
.question b { display: inline-block; margin-right: 8px; color: var(--text-3); font-weight: 400; letter-spacing: .08em; }
.quote { margin: 8px 0 0; color: var(--text); font-size: 13.5px; line-height: 1.9; }
.quote b { display: inline-block; margin-right: 8px; color: var(--text-3); font-weight: 400; letter-spacing: .08em; font-size: 12px; }
.reason { margin: 8px 0 0; color: var(--text-2); font-size: 12.5px; line-height: 1.8; }
.reason b { display: inline-block; margin-right: 8px; color: var(--text-3); font-weight: 400; letter-spacing: .08em; }
.mistake-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 14px; margin-top: 14px; }
.text-btn { display: inline-flex; align-items: center; gap: 4px; padding: 0; border: 0; background: transparent; color: var(--text-3); font-size: 12px; cursor: pointer; transition: color .16s var(--ease); }
.text-btn:hover { color: var(--text); }
.text-btn:disabled { color: var(--text-3); opacity: .5; cursor: not-allowed; }
.resolve-hint { color: var(--text-3); font-size: 11px; }
.pager { display: flex; align-items: center; justify-content: center; gap: 18px; padding-top: 18px; color: var(--text-3); font-size: 12px; }
.versions { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-top: 16px; }
.saved-entry { align-self: flex-start; margin-top: 6px; padding: 8px 14px; border: 1px solid var(--border); border-radius: 999px; color: var(--text-2); font-size: 12.5px; white-space: nowrap; transition: border-color .16s var(--ease), color .16s var(--ease); }
.saved-entry:hover { border-color: var(--border-bright); color: var(--text); }

.deep .deep-form { padding: 18px; display: grid; gap: 12px; }
.deep-field { display: grid; gap: 6px; color: var(--text-3); font-size: 12px; }
.deep-actions { display: flex; align-items: center; justify-content: space-between; gap: 14px; flex-wrap: wrap; }
.deep-check { display: inline-flex; align-items: center; gap: 8px; color: var(--text-2); font-size: 12.5px; }
.deep-versions { margin-top: 14px; }
.coach-note { margin: 10px 0 0; color: var(--text-3); font-size: 12.5px; line-height: 1.8; }
</style>
<style scoped>
.studio-page { max-width: 820px; }
.page-title { font-size: clamp(28px, 3vw, 36px); line-height: 1.25; }
.page-lead { margin-top: 10px; font-size: 14px; }
.saved-entry { font-size: 13px; color: var(--text-3); }
.block { margin-top: 36px; }
.block-head h2 { font-size: 18px; }
.block-head span { font-size: 12.5px; color: var(--text-3); }
.deep-form { border: 0; padding: 0; background: transparent; }
.deep-field span { font-size: 12.5px; color: var(--text-3); }
.mistake { border: 0; border-bottom: 1px solid var(--divider); border-radius: 0; padding: 20px 0; background: transparent; }
.mistake:first-of-type { border-top: 1px solid var(--divider); }
.mistake-head .dim { font-size: 12.5px; color: var(--text-3); }
.mistake-head .score { font-size: 12.5px; color: var(--text-3); }
.mistake-head .meta { font-size: 12px; color: var(--text-3); }
.question, .quote, .reason { font-size: 14px; line-height: 1.8; }
.mistake-actions { gap: 14px; margin-top: 12px; }
.text-btn { font-size: 13px; color: var(--text-3); }
.mistake-actions .button { font-size: 13px; padding: 8px 14px; }
.coach-note { font-size: 13px; color: var(--text-2); }
@media (max-width: 640px) { .page-title { font-size: 26px; } }
</style>
