<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'

import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, TrainingPlan } from '@/lib/types'

const plans = shallowRef<TrainingPlan[]>([])
const loading = shallowRef(true)
const error = shallowRef('')

const activePlans = computed(() => plans.value.filter((plan) => plan.status === 'ACTIVE'))
const finishedPlans = computed(() => plans.value.filter((plan) => plan.status === 'COMPLETED'))
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
        <p class="page-lead">每份计划由最近一次评分里最弱的一维生成：先逐轮复盘批注，再学习一门针对性微课。</p>
      </div>
      <RouterLink class="button secondary" to="/scenes">开始新训练</RouterLink>
    </header>

    <div v-if="error" class="error-banner">{{ error }}</div>

        <section class="section" aria-label="练习计划">
      <header class="section-head">
        <h2 class="label">训练计划</h2>
        <span class="note">{{ activePlans.length ? `${activePlans.length} 份进行中` : '暂无进行中的计划' }}</span>
      </header>

      <div v-if="loading" class="skeleton plan-loading" />
      <p v-else-if="!plans.length" class="section-empty">
        还没有训练计划。完成一次场景训练并生成评分后，系统会按最弱的一维为你排好练习顺序。
        <RouterLink to="/scenes">选择场景 →</RouterLink>
      </p>

      <template v-else>
        <RouterLink v-if="primaryPlan" class="plan-featured" :to="`/plans/${primaryPlan.id}`">
          <p class="plan-meta">{{ primaryPlan.focusDimension }} · 已完成 {{ completedCount(primaryPlan) }} / {{ primaryPlan.tasks.length }} 项 · {{ formatDate(primaryPlan.createdAt) }}</p>
          <h3>{{ primaryPlan.title }}</h3>
          <div class="plan-progress">
            <i><b :style="{ width: `${primaryPlan.progress}%` }" /></i>
            <span class="num">{{ primaryPlan.progress }}%</span>
          </div>
          <span class="cta-button">
            继续这份计划
            <svg width="14" height="10" viewBox="0 0 14 10" fill="none" aria-hidden="true">
              <path d="M1 5h11M8.5 1.5 12 5l-3.5 3.5" stroke="currentColor" stroke-width="1.1" />
            </svg>
          </span>
        </RouterLink>

        <div v-if="otherActivePlans.length" class="plan-more">
          <p class="sub-label">其他进行中的计划</p>
          <ul class="compact-list">
            <li v-for="plan in otherActivePlans" :key="plan.id">
              <RouterLink :to="`/plans/${plan.id}`">
                <span class="compact-title">{{ plan.title }}</span>
                <span class="compact-meta">{{ plan.focusDimension }} · {{ completedCount(plan) }} / {{ plan.tasks.length }} 项</span>
                <span class="num compact-percent">{{ plan.progress }}%</span>
                <span class="chev" aria-hidden="true">→</span>
              </RouterLink>
            </li>
          </ul>
        </div>

        <div v-if="finishedPlans.length" class="plan-more">
          <p class="sub-label">已完成的计划</p>
          <ul class="compact-list">
            <li v-for="plan in finishedPlans" :key="plan.id">
              <RouterLink :to="`/plans/${plan.id}`">
                <span class="compact-title">{{ plan.title }}</span>
                <span class="compact-meta">{{ plan.focusDimension }} · {{ formatDate(plan.createdAt) }}</span>
                <span class="num compact-percent">{{ plan.progress }}%</span>
                <span class="chev" aria-hidden="true">→</span>
              </RouterLink>
            </li>
          </ul>
        </div>

        <p v-if="!primaryPlan && !finishedPlans.length" class="section-empty">计划暂时为空。</p>
      </template>
    </section>

  </div>
</template>

<style scoped>
.plans-page { max-width: 1080px; }

.section { margin-top: 44px; }
.section:first-of-type { margin-top: 8px; }
.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--divider);
}
.section-head h2 { margin: 0; color: var(--text-3); font-size: 11px; font-weight: 400; letter-spacing: .2em; }
.section-head .note { color: var(--text-3); font-size: 11px; letter-spacing: .06em; white-space: nowrap; }

.review-loading { min-height: 180px; margin-top: 18px; }
.plan-loading { min-height: 140px; margin-top: 18px; }
.section-empty { margin: 20px 0 0; color: var(--text-3); font-size: 13px; line-height: 2; }
.section-empty a { margin-left: 12px; color: var(--text-2); border-bottom: 1px solid var(--border-bright); padding-bottom: 1px; }
.section-empty a:hover { color: var(--text); }

.plan-featured:hover { border-color: var(--border-bright); }
.plan-featured {
  display: block;
  transition: border-color var(--ease);
  margin-top: 20px;
  padding: 26px 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
}
.plan-meta { margin: 0; color: var(--text-3); font-size: 11px; letter-spacing: .06em; }
.plan-featured h3 { margin: 12px 0 0; color: var(--text); font-size: 19px; font-weight: 500; line-height: 1.5; letter-spacing: .01em; }
.plan-progress { display: flex; align-items: center; gap: 16px; margin-top: 22px; }
.plan-progress i { flex: 1; height: 2px; background: var(--track); }
.plan-progress i b { display: block; height: 100%; background: var(--accent); }
.plan-progress .num { color: var(--text-2); font-family: var(--font-num); font-size: 12px; letter-spacing: .02em; }
.cta-button {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 22px;
  padding: 10px 16px;
  border-radius: var(--radius-sm);
  background: var(--text);
  color: var(--on-solid);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: .04em;
  transition: background var(--ease), color var(--ease);
}
.cta-button svg { transition: transform var(--ease); }
.plan-featured:hover .cta-button { background: var(--accent); color: #fff; }
.plan-featured:hover .cta-button svg { transform: translateX(3px); }

.plan-more { margin-top: 32px; }
.sub-label { margin: 0 0 6px; color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.compact-list { margin: 0; padding: 0; list-style: none; }
.compact-list a {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto 46px 14px;
  align-items: baseline;
  gap: 18px;
  padding: 14px 2px;
  border-bottom: 1px solid var(--divider);
  transition: background var(--ease);
}
.compact-list a:hover { background: var(--overlay-1); }
.compact-title { color: var(--text-2); font-size: 13px; line-height: 1.6; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.compact-meta { color: var(--text-3); font-size: 11px; letter-spacing: .04em; white-space: nowrap; }
.compact-percent { color: var(--text-3); font-family: var(--font-num); font-size: 12px; text-align: right; white-space: nowrap; }
.compact-list a:hover .compact-title { color: var(--text); }
.chev { color: var(--text-3); font-size: 12px; text-align: right; transition: color var(--ease), transform var(--ease); }
.compact-list a:hover .chev { color: var(--text); transform: translateX(2px); }
.step { margin-right: 10px; color: var(--text-3); font-family: var(--font-num); letter-spacing: .08em; }

@media (max-width: 640px) {
  .plan-featured { padding: 22px; }
  .compact-list a { grid-template-columns: minmax(0, 1fr) auto; row-gap: 4px; }
  .compact-meta { grid-column: 1 / -1; order: 3; }
}
</style>
