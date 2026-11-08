<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import { ArrowRight } from 'lucide-vue-next'

import EmptyState from '@/components/ui/EmptyState.vue'
import { stepTitle } from '@/lib/planActions'

import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, TrainingPlan } from '@/lib/types'

const plans = shallowRef<TrainingPlan[]>([])
const loading = shallowRef(true)
const error = shallowRef('')

const activePlans = computed(() => plans.value.filter((plan) => plan.status === 'ACTIVE'))
const finishedPlans = computed(() => plans.value.filter((plan) => plan.status === 'COMPLETED'))
const archivedPlans = computed(() => plans.value.filter((plan) => plan.status === 'ARCHIVED'))
const primaryPlan = computed(() => activePlans.value[0] ?? null)
const otherActivePlans = computed(() => activePlans.value.slice(1))

onMounted(load)

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const response = await api.get<ApiEnvelope<TrainingPlan[]>>('/training-plans')
    plans.value = response.data.data
  } catch (reason) {
    error.value = errorMessage(reason)
  } finally {
    loading.value = false
  }
}

function planCta(plan: TrainingPlan): string {
  if (plan.progress >= 100) return '查看复盘记录'
  return plan.progress > 0 ? '继续复盘优化' : '开始复盘优化'
}

function completedCount(plan: TrainingPlan): number {
  return plan.tasks.filter((task) => task.completed).length
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return `${date.getFullYear()} 年 ${date.getMonth() + 1} 月 ${date.getDate()} 日`
}
</script>

<template>
  <div class="page plans-page">
    <header class="head">
      <p class="eyebrow">能力提升</p>
      <h1>把评分，变成下一步。</h1>
      <p class="lead">每次训练后生成一份计划：看复盘、改表达、学微课。</p>
      <RouterLink class="button secondary" to="/scenes">开始新训练</RouterLink>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-if="loading" class="skeleton plan-loading" />

    <EmptyState
      v-else-if="!plans.length"
      title="还没有训练计划"
      description="完成一次场景训练并生成评分后，这里会出现第一步。"
    >
      <RouterLink class="button secondary" to="/scenes">选择场景 →</RouterLink>
    </EmptyState>

    <template v-else>
      <RouterLink v-if="primaryPlan" class="current" :to="`/plans/${primaryPlan.id}`">
        <div class="current-top">
          <span class="focus">{{ primaryPlan.focusDimension }}</span>
          <span class="pct">{{ primaryPlan.progress }}%</span>
        </div>
        <h2>{{ primaryPlan.title }}</h2>
        <ul class="tasks">
          <li v-for="task in primaryPlan.tasks.slice(0, 4)" :key="task.key" :class="{ done: task.completed }">
            <span>{{ stepTitle(task) }}</span>
            <em>{{ task.completed ? '已完成' : task.learningProgress > 0 ? '进行中' : '待完成' }}</em>
          </li>
        </ul>
        <div class="current-foot">
          <span class="bar"><i :style="{ width: `${primaryPlan.progress}%` }" /></span>
          <span class="go">{{ planCta(primaryPlan) }} <ArrowRight :size="15" :stroke-width="1.8" aria-hidden="true" /></span>
        </div>
      </RouterLink>

      <section v-if="otherActivePlans.length" class="list-block">
        <h3>其他计划</h3>
        <ul class="rows">
          <li v-for="plan in otherActivePlans" :key="plan.id">
            <RouterLink :to="`/plans/${plan.id}`">
              <span class="row-title">{{ plan.title }}</span>
              <span class="row-meta">{{ completedCount(plan) }} / {{ plan.tasks.length }} 项 · {{ plan.progress }}%</span>
            </RouterLink>
          </li>
        </ul>
      </section>

      <section v-if="finishedPlans.length || archivedPlans.length" class="list-block">
        <h3>历史计划</h3>
        <ul class="rows">
          <li v-for="plan in [...finishedPlans, ...archivedPlans]" :key="plan.id">
            <RouterLink :to="`/plans/${plan.id}`">
              <span class="row-title">{{ plan.title }}</span>
              <span class="row-meta">{{ formatDate(plan.createdAt) }} · {{ plan.progress }}%</span>
            </RouterLink>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<style scoped>
.plans-page { max-width: 720px; }
.head { position: relative; padding-bottom: 28px; margin-bottom: 8px; }
.head .eyebrow { margin: 0 0 10px; }
.head h1 { margin: 0; font-size: clamp(30px, 3.4vw, 40px); font-weight: 650; letter-spacing: -.02em; line-height: 1.2; color: var(--text); }
.head .lead { margin: 12px 0 0; color: var(--text-3); font-size: 14px; line-height: 1.8; }
.head .button { position: absolute; right: 0; bottom: 28px; }
.plan-loading { min-height: 200px; }

.current { display: block; margin-top: 28px; padding: 26px 28px; border: 1px solid var(--border); border-radius: 16px; background: var(--card); transition: border-color .16s var(--ease); }
.current:hover { border-color: var(--border-bright); }
.current-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.focus { font-size: 13px; color: var(--text-3); }
.pct { font-size: 13px; color: var(--text-3); font-variant-numeric: tabular-nums; }
.current h2 { margin: 10px 0 0; font-size: 22px; font-weight: 600; line-height: 1.4; color: var(--text); }
.tasks { list-style: none; margin: 20px 0 0; padding: 0; display: grid; gap: 10px; }
.tasks li { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; font-size: 14px; color: var(--text-2); }
.tasks li em { flex: none; font-style: normal; font-size: 12.5px; color: var(--text-3); }
.tasks li.done { color: var(--text-3); }
.current-foot { display: flex; align-items: center; gap: 18px; margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--divider); }
.bar { flex: 1; height: 3px; border-radius: 999px; background: var(--track); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent); }
.go { display: inline-flex; align-items: center; gap: 6px; font-size: 13.5px; color: var(--text); }
.go svg { transition: transform .16s var(--ease); }
.current:hover .go svg { transform: translateX(3px); }

.list-block { margin-top: 36px; }
.list-block h3 { margin: 0 0 8px; font-size: 13px; font-weight: 500; color: var(--text-3); }
.rows { list-style: none; margin: 0; padding: 0; }
.rows a { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; padding: 14px 0; border-bottom: 1px solid var(--divider); }
.rows a:hover .row-title { color: var(--text); }
.row-title { font-size: 14px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-meta { flex: none; font-size: 12.5px; color: var(--text-3); }
@media (max-width: 640px) { .head .button { position: static; margin-top: 16px; } }
</style>
