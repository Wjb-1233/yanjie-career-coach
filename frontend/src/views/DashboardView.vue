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

      <section class="trend" aria-labelledby="trend-title">
        <header class="section-head">
          <h2 id="trend-title" class="label">评分变化</h2>
          <span class="note">综合分 / 100</span>
        </header>
        <ScoreTrend v-if="hasTrend" compact :points="data.trends" />
        <p v-else class="trend-empty">再完成 {{ trendGap }} 次训练，这里会显示评分曲线。</p>
      </section>
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

.trend { margin-top: 46px; }
.trend-empty { margin: 26px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.9; }

@media (max-width: 760px) {
  .page-head { margin-bottom: 18px; }
  .page-head .date { display: none; }
  .trend { margin-top: 38px; }
}
</style>
