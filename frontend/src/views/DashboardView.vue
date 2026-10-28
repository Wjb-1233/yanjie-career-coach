<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'

import DashboardAbilityPanel from '@/components/dashboard/DashboardAbilityPanel.vue'
import DashboardScoreFeature from '@/components/dashboard/DashboardScoreFeature.vue'
import ScoreTrend from '@/components/report/ScoreTrend.vue'
import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, Scores } from '@/lib/types'

interface DashboardData {
  trainingCount: number
  latestScore: number
  dimensions: Scores
  styleTags: string[]
  trends: Array<{ date: string; score: number; dimensions: Scores }>
  weaknesses: Array<{ dimension: string; averageScore: number; sampleCount: number }>
  plans: Array<{ id: string; title: string; focusDimension: string; tasks: Array<{ day: number; task: string }> }>
}

const data = shallowRef<DashboardData | null>(null)
const error = shallowRef('')

const weakest = computed(() => data.value?.weaknesses[0]?.dimension ?? '等待训练')
const lastTrainedAt = computed(() => {
  const trends = data.value?.trends ?? []
  return trends.length ? trends[trends.length - 1].date : null
})
const hasTrend = computed(() => (data.value?.trends.length ?? 0) >= 2)
const trendGap = computed(() => Math.max(0, 2 - (data.value?.trends.length ?? 0)))
const today = computed(() => {
  const date = new Date()
  return `${date.getFullYear()} 年 ${date.getMonth() + 1} 月 ${date.getDate()} 日`
})

onMounted(async () => {
  try {
    const response = await api.get<ApiEnvelope<DashboardData>>('/dashboard')
    data.value = response.data.data
  } catch (reason) { error.value = errorMessage(reason) }
})
</script>

<template>
  <div class="page dashboard">
    <div class="page-head">
      <span class="label">成长看板</span>
      <span class="date">{{ today }}</span>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <div v-else-if="!data" class="loading" aria-label="正在加载训练概览">
      <div class="skeleton loading-hero" />
      <div class="skeleton loading-block" />
      <div class="skeleton loading-block" />
    </div>

    <template v-else>
      <DashboardScoreFeature
        :training-count="data.trainingCount"
        :latest-score="data.latestScore"
        :focus="weakest"
        :style-tags="data.styleTags"
        :last-trained-at="lastTrainedAt"
      />

      <DashboardAbilityPanel
        :scores="data.dimensions"
        :focus="weakest"
        :training-count="data.trainingCount"
        :weaknesses="data.weaknesses"
      />

      <div class="duo">
        <section class="plans" aria-labelledby="plan-title">
          <header class="section-head">
            <h2 id="plan-title" class="label">训练计划</h2>
            <span class="note">{{ data.plans.length ? `针对${data.plans[0].focusDimension}` : '待生成' }}</span>
          </header>

          <div v-if="!data.plans.length" class="plan-empty">
            <p>完成一次场景训练后，这里会生成针对性的练习计划。</p>
            <RouterLink to="/scenes">选择场景<span class="arrow" aria-hidden="true">↗</span></RouterLink>
          </div>

          <article v-for="plan in data.plans" :key="plan.id" class="plan">
            <h3>{{ plan.title }}</h3>
            <ol class="plan-list">
              <li v-for="(task, index) in plan.tasks" :key="`${plan.id}-${index}`">
                <span class="idx num">{{ String(index + 1).padStart(2, '0') }}</span>
                <span class="task">{{ task.task }}</span>
              </li>
            </ol>
            <div class="plan-foot">
              <span>{{ plan.tasks.length }} 项</span>
              <RouterLink :to="`/plans/${plan.id}`">查看完整计划<span class="arrow" aria-hidden="true">↗</span></RouterLink>
            </div>
          </article>
        </section>

        <section class="trend" aria-labelledby="trend-title">
          <header class="section-head">
            <h2 id="trend-title" class="label">评分变化</h2>
            <span class="note">综合分 / 100</span>
          </header>
          <ScoreTrend v-if="hasTrend" compact :points="data.trends" />
          <div v-else class="trend-empty">
            <p>再完成 {{ trendGap }} 次训练，这里会显示评分曲线。</p>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.dashboard { max-width: 1080px; }
.page-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}
.page-head .date { color: var(--text-3); font-size: 11px; letter-spacing: .06em; }

.loading { display: grid; gap: 24px; }
.loading-hero { min-height: 300px; }
.loading-block { min-height: 190px; }

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 15px;
  border-bottom: 1px solid var(--divider);
}
.section-head h2 { margin: 0; color: var(--text-3); font-size: 11px; font-weight: 400; letter-spacing: .2em; }
.section-head .note { color: var(--text-3); font-size: 11px; letter-spacing: .06em; white-space: nowrap; }

.duo { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); gap: 56px; margin-top: 46px; }

.plan { padding-top: 4px; }
.plan h3 { margin: 20px 0 4px; color: var(--text); font-size: 15px; font-weight: 500; letter-spacing: .01em; line-height: 1.5; }
.plan-list { margin: 8px 0 0; padding: 0; list-style: none; }
.plan-list li {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 16px;
  align-items: baseline;
  padding: 13px 0;
  border-bottom: 1px solid var(--divider);
}
.plan-list li:last-child { border-bottom: 0; }
.plan-list .idx { color: var(--text-3); font-family: var(--font-num); font-size: 11px; letter-spacing: .08em; }
.plan-list .task { color: var(--text-2); font-size: 13px; line-height: 1.7; transition: color var(--ease); }
.plan-list li:hover .task { color: var(--text); }

.plan-foot {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-top: 16px;
  border-top: 1px solid var(--divider);
  color: var(--text-3);
  font-size: 11px;
  letter-spacing: .06em;
}
.plan-foot a { color: var(--text-2); letter-spacing: .04em; transition: color var(--ease); }
.plan-foot a:hover { color: var(--text); }
.arrow { margin-left: 6px; }

.plan-empty { padding-top: 22px; }
.plan-empty p { margin: 0; color: var(--text-3); font-size: 13px; line-height: 1.9; }
.plan-empty a {
  display: inline-block;
  margin-top: 18px;
  color: var(--text-2);
  font-size: 12px;
  letter-spacing: .04em;
  border-bottom: 1px solid var(--border-bright);
  padding-bottom: 2px;
  transition: color var(--ease), border-color var(--ease);
}
.plan-empty a:hover { color: var(--accent-strong); border-color: var(--accent); }

.trend-empty { padding: 26px 0 0; }
.trend-empty p { margin: 0; color: var(--text-3); font-size: 12px; line-height: 1.9; }

@media (max-width: 900px) {
  .duo { grid-template-columns: 1fr; gap: 40px; margin-top: 38px; }
}
@media (max-width: 760px) {
  .page-head { margin-bottom: 18px; }
  .page-head .date { display: none; }
}
</style>
