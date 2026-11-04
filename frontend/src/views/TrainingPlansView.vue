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
    <header class="page-heading">
      <div>
        <p class="eyebrow">能力提升</p>
        <h1 class="page-title">把一次评分，<br />变成一条练习线。</h1>
        <p class="page-lead">每次评分都会生成一份带编号的计划：先按复盘点再练一场，再看视频面试示范，最后学一门微课。没走完的计划会保留在下面。</p>
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
      <EmptyState
        v-else-if="!plans.length"
        title="还没有训练计划"
        description="完成一次场景训练并生成评分后，系统会按最弱的一维为你排好练习顺序。"
      >
        <RouterLink class="button secondary" to="/scenes">选择场景 →</RouterLink>
      </EmptyState>

      <template v-else>
        <RouterLink v-if="primaryPlan" class="plan-featured" :to="`/plans/${primaryPlan.id}`">
          <header class="plan-top">
            <span class="focus-tag">#{{ primaryPlan.sequence }} · {{ primaryPlan.focusDimension }}</span>
            <span class="plan-date">{{ formatDate(primaryPlan.createdAt) }}</span>
            <span class="plan-pct num">{{ primaryPlan.progress }}%</span>
          </header>
          <h3>{{ primaryPlan.title }}</h3>
          <ol class="plan-steps">
            <li v-for="(task, index) in primaryPlan.tasks.slice(0, 4)" :key="task.key" :class="{ done: task.completed }">
              <span class="num">0{{ index + 1 }}</span>
              <span class="step-name">{{ stepTitle(task) }}</span>
              <span class="step-state">{{ task.completed ? '已完成' : task.learningProgress > 0 ? `进行中 ${task.learningProgress}%` : '待完成' }}</span>
            </li>
          </ol>
          <footer class="plan-foot">
            <span class="progress"><i><b :style="{ width: `${primaryPlan.progress}%` }" /></i></span>
            <span class="cta">{{ planCta(primaryPlan) }}<ArrowRight :size="14" :stroke-width="1.8" aria-hidden="true" /></span>
          </footer>
        </RouterLink>

        <div v-if="otherActivePlans.length" class="plan-more">
          <p class="sub-label">其他进行中的计划</p>
          <ul class="compact-list">
            <li v-for="plan in otherActivePlans" :key="plan.id">
              <RouterLink :to="`/plans/${plan.id}`">
                <span class="compact-title">#{{ plan.sequence }} {{ plan.title }}</span>
                <span class="compact-meta">{{ plan.focusDimension }} · {{ completedCount(plan) }} / {{ plan.tasks.length }} 项</span>
                <span class="num compact-percent">{{ plan.progress }}%</span>
                <span class="chev" aria-hidden="true">→</span>
              </RouterLink>
            </li>
          </ul>
        </div>

        <div v-if="finishedPlans.length || archivedPlans.length" class="plan-more">
          <p class="sub-label">历史计划</p>
          <ul class="compact-list">
            <li v-for="plan in [...finishedPlans, ...archivedPlans]" :key="plan.id">
              <RouterLink :to="`/plans/${plan.id}`">
                <span class="compact-title">#{{ plan.sequence }} {{ plan.title }}</span>
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
.plans-page { max-width: 820px; }
.plans-page .page-title { font-size: clamp(24px, 2.4vw, 30px); }

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

.plan-featured:hover { border-color: var(--border-bright); transform: translateY(-2px); box-shadow: 0 14px 34px rgba(0, 0, 0, .22); }
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
/* 当前计划：本页唯一的重点块 */
.plan-featured { display: grid; gap: 0; margin-top: 20px; padding: 24px 26px 20px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--card); transition: border-color .18s var(--ease), transform .18s var(--ease), box-shadow .18s var(--ease); }
.plan-featured:hover { border-color: var(--border-bright); }

.plan-top { display: flex; align-items: baseline; gap: 12px; }
.focus-tag { padding: 3px 8px; border: 1px solid var(--border-bright); border-radius: 3px; color: var(--text-2); font-size: 11px; letter-spacing: .06em; }
.plan-date { color: var(--text-3); font-size: 11px; letter-spacing: .06em; }
.plan-pct { margin-left: auto; color: var(--text-2); font-family: var(--font-num); font-size: 12px; }

.plan-featured h3 { margin: 14px 0 0; color: var(--text); font-size: 18px; font-weight: 500; line-height: 1.5; letter-spacing: .01em; }

.plan-steps { margin: 16px 0 0; padding: 14px 0 0; border-top: 1px solid var(--divider); list-style: none; display: grid; gap: 8px; }
.plan-steps li { display: flex; align-items: baseline; gap: 12px; color: var(--text-2); font-size: 13px; }
.plan-steps .num { color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.plan-steps .step-name { flex: 1; }
.plan-steps .step-state { color: var(--text-3); font-size: 11px; letter-spacing: .06em; }
.plan-steps li.done .step-name { color: var(--text-3); }
.plan-steps li.muted .step-name, .plan-steps li.muted .num, .plan-steps li.muted .step-state { color: var(--text-3); }

.plan-foot { display: flex; align-items: center; gap: 20px; margin-top: 18px; }
.progress { flex: 1; height: 2px; background: var(--track); }
.progress b { display: block; height: 100%; background: var(--accent); }
.cta { display: inline-flex; align-items: center; gap: 8px; min-height: 34px; padding: 0 14px; border: 1px solid var(--border-bright); border-radius: var(--radius-sm); color: var(--text); font-size: 12.5px; font-weight: 500; letter-spacing: .02em; transition: border-color .14s var(--ease), background .14s var(--ease); }
.plan-featured:hover .cta { border-color: var(--text-3); background: var(--overlay-1); }
.cta svg { transition: transform .18s var(--ease); }
.plan-featured:hover .cta svg { transform: translateX(3px); }

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
