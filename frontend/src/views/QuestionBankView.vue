<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'

import SelectField from '@/components/ui/SelectField.vue'
import { api, errorMessage } from '@/lib/api'
import type {
  ApiEnvelope,
  MistakeItem,
  QuestionBankItem,
  QuestionBankPage,
  QuestionBankState,
  QuestionBankSummary,
} from '@/lib/types'

const PAGE_SIZE = 10
const items = shallowRef<QuestionBankItem[]>([])
const summary = shallowRef<QuestionBankSummary | null>(null)
const mistakes = shallowRef<MistakeItem[]>([])
const total = shallowRef(0)
const page = shallowRef(1)
const loading = shallowRef(true)
const error = shallowRef('')
const saving = shallowRef('')
const dimension = shallowRef('')
const sceneId = shallowRef('')
const onlyUnmastered = shallowRef(false)

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const rate = computed(() => summary.value?.rate ?? 0)
const dimensionOptions = computed(() => [
  { value: '', label: '全部维度' },
  ...(summary.value?.dimensions ?? []).map((row) => ({
    value: row.dimension,
    label: row.dimension,
    hint: `已掌握 ${row.mastered}/${row.total}`,
  })),
])
const sceneOptions = computed(() => [
  { value: '', label: '全部场景' },
  ...(summary.value?.scenes ?? []).map((row) => ({
    value: row.sceneId,
    label: row.sceneTitle,
    hint: `已掌握 ${row.mastered}/${row.total}`,
  })),
])

async function loadList(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const response = await api.get<ApiEnvelope<QuestionBankPage>>('/question-bank', {
      params: {
        page: page.value,
        size: PAGE_SIZE,
        ...(dimension.value ? { dimension: dimension.value } : {}),
        ...(sceneId.value ? { sceneId: sceneId.value } : {}),
        ...(onlyUnmastered.value ? { mastered: false } : {}),
      },
    })
    items.value = response.data.data.items
    total.value = response.data.data.total
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

async function loadSummary(): Promise<void> {
  try {
    const response = await api.get<ApiEnvelope<QuestionBankSummary>>('/question-bank/summary')
    summary.value = response.data.data
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

async function loadMistakes(): Promise<void> {
  try {
    const response = await api.get<ApiEnvelope<{ items: MistakeItem[]; total: number } | MistakeItem[]>>(
      '/training-sessions/mistakes',
      { params: { page: 1, size: 5, include_resolved: false } },
    )
    const payload = response.data.data
    // 兼容旧版直接返回数组的接口
    mistakes.value = (Array.isArray(payload) ? payload : payload.items).filter((item) => item.status !== 'RESOLVED')
  } catch (reason) {
    error.value = errorMessage(reason)
  }
}

async function toggle(item: QuestionBankItem, field: 'favorite' | 'mastered'): Promise<void> {
  if (saving.value) return
  saving.value = item.id
  error.value = ''
  try {
    const response = await api.patch<ApiEnvelope<QuestionBankState>>(`/question-bank/${item.id}/state`, {
      [field]: !item[field],
    })
    const state = response.data.data
    items.value = items.value.map((row) => (
      row.id === state.questionId ? { ...row, favorite: state.favorite, mastered: state.mastered } : row
    ))
    // 概览只在本地按增量更新，避免每次勾选都整页重取
    if (summary.value) {
      const mastered = summary.value.mastered + Number(state.mastered) - Number(item.mastered)
      summary.value = {
        ...summary.value,
        mastered,
        favorite: summary.value.favorite + Number(state.favorite) - Number(item.favorite),
        rate: summary.value.total ? Math.round((mastered / summary.value.total) * 1000) / 10 : 0,
      }
    }
    if (field === 'mastered' && onlyUnmastered.value && state.mastered) {
      items.value = items.value.filter((row) => row.id !== state.questionId)
      total.value = Math.max(0, total.value - 1)
      if (!items.value.length && page.value > 1) page.value -= 1
    }
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    saving.value = ''
  }
}

function reload(): void {
  void Promise.all([loadList(), loadSummary(), loadMistakes()])
}

watch([dimension, sceneId, onlyUnmastered], () => {
  // 页码变化会自己触发加载，这里只负责回到第 1 页
  if (page.value !== 1) {
    page.value = 1
    return
  }
  void loadList()
})
watch(page, () => { void loadList() })

onMounted(reload)
</script>

<template>
  <div class="page bank-page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">题库</p>
        <h1 class="page-title">题库刷题</h1>
        <p class="page-lead">按维度和场景挑题练习，勾选掌握后自动更新顶部概览。</p>
      </div>
    </header>

    <div v-if="error" class="error-banner" role="alert">{{ error }} <button type="button" @click="reload">重试</button></div>

    <section class="overview" aria-label="掌握概览">
      <div class="overview-main">
        <p class="overview-value">{{ summary?.mastered ?? 0 }}<span> / {{ summary?.total ?? 0 }}</span></p>
        <p class="overview-label">已掌握题目</p>
      </div>
      <div class="overview-meta">
        <p>掌握率 <b>{{ rate }}%</b></p>
        <p>已收藏 <b>{{ summary?.favorite ?? 0 }}</b> 题</p>
      </div>
      <div class="meter" role="img" :aria-label="`掌握率 ${rate}%`">
        <span class="meter-fill" :style="{ width: `${Math.min(100, Math.max(0, rate))}%` }" />
      </div>
    </section>

    <section class="bank-filters" aria-label="筛选">
      <div class="bank-filter"><SelectField v-model="dimension" :options="dimensionOptions" aria-label="按维度筛选" /></div>
      <div class="bank-filter"><SelectField v-model="sceneId" :options="sceneOptions" aria-label="按场景筛选" /></div>
      <label class="only-unmastered"><input v-model="onlyUnmastered" type="checkbox"> 只看未掌握</label>
    </section>

    <section class="block">
      <div class="block-head"><h2>题目</h2><span>{{ total }} 题</span></div>
      <div v-if="loading" class="skeleton loading" />
      <p v-else-if="!items.length" class="empty-note">这个筛选下没有题目，换个维度或场景试试。</p>
      <ul v-else class="question-list">
        <li v-for="item in items" :key="item.id" class="question">
          <p class="question-meta">
            <span>{{ item.sceneTitle }}</span>
            <template v-if="item.dimension"><span class="dot">·</span><span>{{ item.dimension }}</span></template>
          </p>
          <p class="question-text">{{ item.text }}</p>
          <div class="question-actions">
            <button
              type="button"
              class="chip"
              :class="{ on: item.favorite }"
              :aria-pressed="item.favorite"
              :disabled="saving === item.id"
              @click="toggle(item, 'favorite')"
            >{{ item.favorite ? '已收藏' : '收藏' }}</button>
            <button
              type="button"
              class="chip"
              :class="{ on: item.mastered }"
              :aria-pressed="item.mastered"
              :disabled="saving === item.id"
              @click="toggle(item, 'mastered')"
            >{{ item.mastered ? '已掌握' : '标记掌握' }}</button>
          </div>
        </li>
      </ul>
      <nav v-if="pageCount > 1" class="pager" aria-label="题库分页">
        <button class="text-btn" type="button" :disabled="page <= 1" @click="page -= 1">上一页</button>
        <span class="num">{{ page }} / {{ pageCount }}</span>
        <button class="text-btn" type="button" :disabled="page >= pageCount" @click="page += 1">下一页</button>
      </nav>
    </section>

    <section class="block">
      <div class="block-head"><h2>错题复习</h2><span>{{ mistakes.length }} 条待复习</span></div>
      <p v-if="!mistakes.length" class="empty-note">暂无未掌握的错题，完成一次训练评估后会出现在这里。</p>
      <ul v-else class="mistake-list">
        <li v-for="item in mistakes" :key="`${item.sessionId}-${item.roundNo}-${item.dimension}`" class="mistake">
          <p class="question-meta">
            <span>{{ item.sceneTitle }}</span><span class="dot">·</span><span>{{ item.dimension }}</span>
            <span class="dot">·</span><span>第 {{ item.roundNo + 1 }} 轮</span>
          </p>
          <p class="question-text">{{ item.question || item.quote }}</p>
          <p class="mistake-reason">{{ item.reason }}</p>
          <RouterLink class="text-btn" :to="`/report/${item.sessionId}`">查看训练记录 →</RouterLink>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.bank-page { max-width: 860px; }
.overview { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 8px 28px; padding: 22px 0 20px; border-bottom: 1px solid var(--divider); }
.overview-main { display: grid; gap: 4px; }
.overview-value { margin: 0; color: var(--text); font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
.overview-value span { color: var(--text-3); font-size: 15px; font-weight: 400; }
.overview-label { margin: 0; color: var(--text-3); font-size: 12.5px; }
.overview-meta { display: flex; flex-wrap: wrap; gap: 6px 20px; color: var(--text-3); font-size: 13px; }
.overview-meta p { margin: 0; }
.overview-meta b { color: var(--text); font-weight: 600; font-variant-numeric: tabular-nums; }
.meter { grid-column: 1 / -1; height: 3px; margin-top: 6px; border-radius: 999px; background: var(--track); overflow: hidden; }
.meter-fill { display: block; height: 100%; background: var(--accent); transition: width .2s var(--ease); }
.bank-filters { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) auto; align-items: center; gap: 12px; padding: 18px 0; border-bottom: 1px solid var(--divider); }
.bank-filter { min-width: 0; }
.only-unmastered { display: inline-flex; align-items: center; gap: 7px; color: var(--text-2); font-size: 13px; white-space: nowrap; cursor: pointer; }
.only-unmastered input { width: 15px; height: 15px; accent-color: var(--accent); }
.block { margin-top: 34px; }
.block-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; padding-bottom: 10px; border-bottom: 1px solid var(--divider); }
.block-head h2 { margin: 0; color: var(--text); font-size: 16px; font-weight: 600; }
.block-head > span { color: var(--text-3); font-size: 12.5px; font-variant-numeric: tabular-nums; }
.loading { min-height: 180px; margin-top: 12px; }
.empty-note { padding: 20px 0; color: var(--text-3); font-size: 13.5px; line-height: 1.8; }
.question-list, .mistake-list { margin: 0; padding: 0; list-style: none; }
.question, .mistake { display: grid; gap: 8px; padding: 18px 0; border-bottom: 1px solid var(--divider); }
.question-meta { margin: 0; display: flex; flex-wrap: wrap; gap: 6px; color: var(--text-3); font-size: 12.5px; line-height: 1.5; }
.dot { color: var(--border-bright); }
.question-text { margin: 0; color: var(--text); font-size: 15px; line-height: 1.75; overflow-wrap: anywhere; }
.question-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { padding: 5px 12px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--text-3); font-size: 12.5px; cursor: pointer; transition: color .16s var(--ease), border-color .16s var(--ease), background .16s var(--ease); }
.chip:hover { border-color: var(--border-bright); color: var(--text-2); }
.chip.on { border-color: var(--accent); background: var(--accent-soft); color: var(--accent-strong); }
.chip:disabled { opacity: .5; cursor: default; }
.chip:focus-visible { outline: none; box-shadow: 0 0 0 3px var(--accent-soft); }
.mistake-reason { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.75; overflow-wrap: anywhere; }
.pager { display: flex; align-items: center; justify-content: center; gap: 18px; padding-top: 20px; color: var(--text-3); font-size: 12.5px; }
.pager .num { font-variant-numeric: tabular-nums; }
.text-btn { border: 0; padding: 0; background: transparent; color: var(--text-2); font-size: 12.5px; cursor: pointer; text-decoration: none; }
.text-btn:hover { color: var(--text); }
.text-btn:disabled { opacity: .38; cursor: default; }
a.text-btn { justify-self: start; }
@media (max-width: 680px) {
  .overview { grid-template-columns: minmax(0, 1fr); }
  .bank-filters { grid-template-columns: minmax(0, 1fr); align-items: stretch; }
  .question-text { font-size: 14.5px; }
}
</style>
