<script setup lang="ts">
import { Check, ChevronLeft, ChevronRight, Search, Star } from 'lucide-vue-next'
import { computed, onMounted, shallowRef, watch } from 'vue'

import SelectField from '@/components/ui/SelectField.vue'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope } from '@/lib/types'

interface BankItem {
  id: string
  text: string
  dimension: string | null
  difficulty: string | null
  sceneId: string
  sceneTitle: string
  category: string
  industry: string
  position: string
  favorite: boolean
  mastered: boolean
}

interface BankResponse {
  items: BankItem[]
  total: number
  page: number
  size: number
  facets: { industries: string[]; positions: string[]; categories: string[]; difficulties: string[] }
  counts: { total: number; favorite: number; mastered: number }
}

const items = shallowRef<BankItem[]>([])
const total = shallowRef(0)
const page = shallowRef(1)
const size = 24
const loading = shallowRef(true)
const error = shallowRef('')
const busy = shallowRef('')
const industry = shallowRef('')
const position = shallowRef('')
const category = shallowRef('')
const difficulty = shallowRef('')
const keyword = shallowRef('')
const favoriteOnly = shallowRef(false)
const state = shallowRef<'all' | 'unmastered' | 'mastered'>('all')
const facets = shallowRef<BankResponse['facets']>({ industries: [], positions: [], categories: [], difficulties: [] })
const counts = shallowRef<BankResponse['counts']>({ total: 0, favorite: 0, mastered: 0 })
const maxPage = computed(() => Math.max(1, Math.ceil(total.value / size)))

function optionList(label: string, values: string[]): Array<{ value: string; label: string }> {
  return [{ value: '', label: `全部${label}` }, ...values.map((value) => ({ value, label: value }))]
}

async function load(target = page.value): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const response = await api.get<ApiEnvelope<BankResponse>>('/question-bank', {
      params: {
        industry: industry.value || undefined,
        position: position.value || undefined,
        category: category.value || undefined,
        difficulty: difficulty.value || undefined,
        query: keyword.value.trim() || undefined,
        favorite: favoriteOnly.value || undefined,
        state: state.value,
        page: target,
        size,
      },
    })
    const data = response.data.data
    items.value = data.items
    total.value = data.total
    page.value = data.page
    facets.value = data.facets
    counts.value = data.counts
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

async function toggle(item: BankItem, field: 'favorite' | 'mastered'): Promise<void> {
  const next = !item[field]
  busy.value = item.id
  try {
    await api.put(`/question-bank/${item.id}`, { [field]: next })
    item[field] = next
    counts.value = {
      ...counts.value,
      favorite: counts.value.favorite + (field === 'favorite' ? (next ? 1 : -1) : 0),
      mastered: counts.value.mastered + (field === 'mastered' ? (next ? 1 : -1) : 0),
    }
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    busy.value = ''
  }
}

function reset(): void {
  industry.value = ''
  position.value = ''
  category.value = ''
  difficulty.value = ''
  keyword.value = ''
  favoriteOnly.value = false
  state.value = 'all'
}

watch([industry, position, category, difficulty, favoriteOnly, state], () => { void load(1) })
let timer: ReturnType<typeof setTimeout> | null = null
watch(keyword, () => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => { void load(1) }, 300)
})

onMounted(() => { void load(1) })
</script>

<template>
  <div class="page">
    <header class="page-heading">
      <div>
        <p class="eyebrow">刷题</p>
        <h1 class="page-title">把常见问题，<br /><span>先练成条件反射。</span></h1>
        <p class="page-lead">按岗位、阶段和难度筛选题目，收藏要反复练的，标记已经掌握的。</p>
      </div>
      <div class="bank-stats" aria-label="题库概览">
        <div><span>题目</span><strong>{{ counts.total }}</strong></div>
        <div><span>已掌握</span><strong>{{ counts.mastered }}</strong></div>
        <div><span>收藏</span><strong>{{ counts.favorite }}</strong></div>
      </div>
    </header>

    <section class="bank-filters panel" aria-label="筛选题目">
      <div class="filter-row">
        <SelectField :model-value="industry" :options="optionList('行业', facets.industries)" aria-label="按行业筛选" @update:model-value="industry = $event" />
        <SelectField :model-value="position" :options="optionList('岗位', facets.positions)" aria-label="按岗位筛选" @update:model-value="position = $event" />
        <SelectField :model-value="category" :options="optionList('阶段', facets.categories)" aria-label="按面试阶段筛选" @update:model-value="category = $event" />
        <SelectField :model-value="difficulty" :options="optionList('难度', facets.difficulties)" aria-label="按难度筛选" @update:model-value="difficulty = $event" />
        <SelectField
          :model-value="state"
          :options="[{ value: 'all', label: '全部状态' }, { value: 'unmastered', label: '未掌握' }, { value: 'mastered', label: '已掌握' }]"
          aria-label="按掌握状态筛选"
          @update:model-value="state = $event as 'all' | 'unmastered' | 'mastered'"
        />
      </div>
      <div class="filter-row secondary">
        <label class="search-box">
          <Search :size="14" aria-hidden="true" />
          <input v-model="keyword" type="search" placeholder="搜索题目、场景或维度" aria-label="搜索题目" />
        </label>
        <button type="button" class="toggle" :class="{ active: favoriteOnly }" @click="favoriteOnly = !favoriteOnly">
          <Star :size="14" aria-hidden="true" /> 只看收藏
        </button>
        <button type="button" class="reset" @click="reset">清除筛选</button>
      </div>
    </section>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <section v-if="loading" class="bank-grid" aria-hidden="true">
      <div v-for="n in 6" :key="n" class="bank-card skeleton" />
    </section>
    <section v-else-if="items.length" class="bank-grid">
      <article v-for="item in items" :key="item.id" class="bank-card panel" :class="{ mastered: item.mastered }">
        <div class="card-top">
          <span class="tag">{{ item.category }}</span>
          <span class="tag muted">{{ item.difficulty }}</span>
          <button
            type="button"
            class="star"
            :class="{ active: item.favorite }"
            :aria-label="item.favorite ? '取消收藏' : '收藏这道题'"
            :disabled="busy === item.id"
            @click="toggle(item, 'favorite')"
          >
            <Star :size="15" :fill="item.favorite ? 'currentColor' : 'none'" aria-hidden="true" />
          </button>
        </div>
        <p class="question">{{ item.text }}</p>
        <p class="meta">{{ item.industry }} · {{ item.position }} · {{ item.sceneTitle }}</p>
        <div class="card-bottom">
          <span v-if="item.dimension" class="dimension">{{ item.dimension }}</span>
          <button
            type="button"
            class="master"
            :class="{ active: item.mastered }"
            :disabled="busy === item.id"
            @click="toggle(item, 'mastered')"
          >
            <Check :size="14" aria-hidden="true" /> {{ item.mastered ? '已掌握' : '标记掌握' }}
          </button>
        </div>
      </article>
    </section>
    <div v-else class="empty panel">没有匹配的题目，换个筛选条件试试。</div>

    <nav v-if="maxPage > 1" class="pager" aria-label="分页">
      <button type="button" :disabled="page <= 1" @click="load(page - 1)"><ChevronLeft :size="16" /> 上一页</button>
      <span>{{ page }} / {{ maxPage }}</span>
      <button type="button" :disabled="page >= maxPage" @click="load(page + 1)">下一页 <ChevronRight :size="16" /></button>
    </nav>
  </div>
</template>

<style scoped>
.page-heading { display: flex; justify-content: space-between; gap: 28px; align-items: end; margin-bottom: 26px; }
.page-title span { color: var(--accent-strong); }
.bank-stats { display: flex; gap: 26px; padding: 14px 20px; border: 1px solid var(--border); border-radius: var(--radius-sm, 14px); background: var(--surface); }
.bank-stats div { display: grid; gap: 2px; }
.bank-stats span { color: var(--text-3); font-size: 11px; }
.bank-stats strong { font: 700 26px/1 var(--font-ui); }
.bank-filters { display: grid; gap: 12px; padding: 16px; margin-bottom: 20px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.filter-row :deep(.select-trigger) { width: auto; min-width: 138px; }
.search-box { display: flex; align-items: center; gap: 8px; flex: 1 1 260px; padding: 8px 12px; border: 1px solid var(--border); border-radius: 10px; background: var(--surface); color: var(--text-3); }
.search-box input { border: 0; outline: 0; background: transparent; color: var(--text); font-size: 13px; width: 100%; }
.toggle, .reset { border: 1px solid var(--border); background: transparent; color: var(--text-2); border-radius: 999px; padding: 7px 14px; font-size: 12.5px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
.toggle.active { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.reset { border-color: transparent; color: var(--text-3); }
.bank-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 14px; }
.bank-card { display: grid; gap: 10px; padding: 16px; align-content: start; }
.bank-card.mastered { border-color: var(--accent); }
.card-top { display: flex; align-items: center; gap: 6px; }
.card-top .star { margin-left: auto; border: 0; background: transparent; color: var(--text-3); cursor: pointer; padding: 4px; }
.card-top .star.active { color: var(--accent-strong); }
.question { margin: 0; font-size: 14.5px; line-height: 1.6; color: var(--text); }
.meta { margin: 0; color: var(--text-3); font-size: 11.5px; }
.card-bottom { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.dimension { color: var(--text-2); font-size: 11.5px; }
.master { border: 1px solid var(--border); background: transparent; color: var(--text-2); border-radius: 999px; padding: 5px 10px; font-size: 11.5px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.master.active { border-color: var(--accent); color: var(--accent-strong); background: var(--accent-soft); }
.pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 20px; color: var(--text-2); font-size: 12.5px; }
.pager button { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--border); background: transparent; color: var(--text-2); border-radius: 999px; padding: 6px 12px; cursor: pointer; }
.pager button:disabled { opacity: .4; cursor: default; }
.skeleton { min-height: 150px; }
@media (max-width: 720px) { .page-heading { flex-direction: column; align-items: start; } }
</style>
