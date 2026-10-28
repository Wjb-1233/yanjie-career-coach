<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'

import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, TrainingPlan } from '@/lib/types'

const plans = shallowRef<TrainingPlan[]>([])
const loading = shallowRef(true)
const error = shallowRef('')

const activePlans = computed(() => plans.value.filter((plan) => plan.status === 'ACTIVE'))
const finishedPlans = computed(() => plans.value.filter((plan) => plan.status === 'COMPLETED'))

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
    <header class="page-heading">
      <div>
        <p class="eyebrow">能力提升</p>
        <h1 class="page-title">把一次评分，<br />变成一条练习线。</h1>
        <p class="page-lead">每份计划由最近一次评分里最弱的一维生成：先专项对练，再回原场景复测，用两次真实回答比较变化。</p>
      </div>
      <RouterLink class="button secondary" to="/scenes">开始新训练</RouterLink>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>
    <div v-else-if="loading" class="loading">
      <div class="skeleton loading-row" />
      <div class="skeleton loading-row" />
    </div>

    <template v-else>
      <p v-if="!plans.length" class="empty-state">
        还没有训练计划。完成一次场景训练并生成评分后，系统会按最弱的一维为你排好练习顺序。
        <RouterLink to="/scenes">选择场景 →</RouterLink>
      </p>

      <template v-else>
        <section class="group">
          <header class="group-head">
            <h2 class="label">进行中</h2>
            <span class="note">{{ activePlans.length }} 份</span>
          </header>
          <ul class="plan-list">
            <li v-for="plan in activePlans" :key="plan.id">
              <RouterLink class="plan-row" :to="`/plans/${plan.id}`">
                <span class="plan-copy">
                  <span class="plan-meta">{{ plan.focusDimension }} · {{ completedCount(plan) }} / {{ plan.tasks.length }} 项 · {{ formatDate(plan.createdAt) }}</span>
                  <strong>{{ plan.title }}</strong>
                </span>
                <span class="plan-progress">
                  <span class="num">{{ plan.progress }}%</span>
                  <i><b :style="{ width: `${plan.progress}%` }" /></i>
                </span>
              </RouterLink>
            </li>
          </ul>
        </section>

        <section v-if="finishedPlans.length" class="group">
          <header class="group-head">
            <h2 class="label">已完成</h2>
            <span class="note">{{ finishedPlans.length }} 份</span>
          </header>
          <ul class="plan-list">
            <li v-for="plan in finishedPlans" :key="plan.id">
              <RouterLink class="plan-row" :to="`/plans/${plan.id}`">
                <span class="plan-copy">
                  <span class="plan-meta">{{ plan.focusDimension }} · {{ formatDate(plan.createdAt) }} · 已完成</span>
                  <strong>{{ plan.title }}</strong>
                </span>
                <span class="plan-open">查看 →</span>
              </RouterLink>
            </li>
          </ul>
        </section>
      </template>
    </template>
  </div>
</template>

<style scoped>
.plans-page { max-width: 1080px; }
.loading { display: grid; gap: 12px; }
.loading-row { min-height: 96px; }

.empty-state {
  margin: 40px 0 0;
  padding: 28px 0;
  border-top: 1px solid var(--divider);
  color: var(--text-3);
  font-size: 13px;
  line-height: 2;
}
.empty-state a { margin-left: 12px; color: var(--text-2); border-bottom: 1px solid var(--border-bright); padding-bottom: 1px; }
.empty-state a:hover { color: var(--text); }

.group { margin-top: 38px; }
.group:first-of-type { margin-top: 8px; }
.group-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--divider);
}
.group-head h2 { margin: 0; color: var(--text-3); font-size: 11px; font-weight: 400; letter-spacing: .2em; }
.group-head .note { color: var(--text-3); font-size: 11px; letter-spacing: .06em; }

.plan-list { margin: 0; padding: 0; list-style: none; }
.plan-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 150px;
  align-items: center;
  gap: 28px;
  padding: 20px 4px;
  border-bottom: 1px solid var(--divider);
  transition: background var(--ease);
}
.plan-row:hover { background: var(--overlay-1); }
.plan-copy { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.plan-meta { color: var(--text-3); font-size: 11px; letter-spacing: .06em; }
.plan-copy strong { color: var(--text); font-size: 15px; font-weight: 500; line-height: 1.5; }

.plan-progress { display: flex; flex-direction: column; gap: 8px; align-items: flex-end; }
.plan-progress .num { color: var(--text-2); font-family: var(--font-num); font-size: 13px; letter-spacing: .02em; }
.plan-progress i { display: block; width: 100%; height: 2px; background: var(--track); }
.plan-progress i b { display: block; height: 100%; background: var(--accent); }
.plan-open { color: var(--text-3); font-size: 12px; letter-spacing: .06em; text-align: right; transition: color var(--ease); }
.plan-row:hover .plan-open { color: var(--text); }

@media (max-width: 640px) {
  .plan-row { grid-template-columns: 1fr; gap: 12px; }
  .plan-progress { align-items: stretch; }
  .plan-open { text-align: left; }
}
</style>
