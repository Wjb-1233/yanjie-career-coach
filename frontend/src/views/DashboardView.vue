<script setup lang="ts">
import { computed, onMounted, shallowRef } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

import DashboardAbilityPanel from '@/components/dashboard/DashboardAbilityPanel.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import DashboardScoreFeature from '@/components/dashboard/DashboardScoreFeature.vue'
import ScoreTrend from '@/components/report/ScoreTrend.vue'
import { useAuth } from '@/composables/useAuth'
import { api, errorMessage } from '@/lib/api'
import { stepTitle, taskRoute } from '@/lib/planActions'
import type { ApiEnvelope, Scores, TrainingPlan } from '@/lib/types'

interface DashboardData {
  trainingCount: number
  latestScore: number
  latestDegraded?: boolean
  dimensions: Scores
  styleTags: string[]
  trends: Array<{ date: string; score: number; dimensions: Scores }>
  weaknesses: Array<{ dimension: string; averageScore: number; sampleCount: number }>
}

const auth = useAuth()
const verifyBanner = computed(() => auth.user.value?.emailVerified === false)
const resendState = shallowRef('')
const resendBusy = shallowRef(false)

async function resendVerification() {
  if (resendBusy.value) return
  resendBusy.value = true
  try {
    const response = await api.post('/auth/verify-email/request')
    resendState.value = response.data.data.sent ? '验证邮件已发送，请查收' : '邮件服务未配置，请联系管理员'
  } catch (reason) {
    resendState.value = errorMessage(reason)
  } finally {
    resendBusy.value = false
  }
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
  try {
    const [planResponse, mistakeResponse] = await Promise.all([
      api.get<ApiEnvelope<TrainingPlan[]>>('/training-plans'),
      api.get<ApiEnvelope<{ items?: Array<{ status: string }>; total?: number } | Array<{ status: string }>>>('/training-sessions/mistakes', { params: { size: 1 } }),
    ])
    plans.value = planResponse.data.data
    const payload = mistakeResponse.data.data
    mistakeCount.value = Array.isArray(payload) ? payload.length : (payload.total ?? payload.items?.length ?? 0)
  } catch {
    // 今日建议取不到不影响看板主体
  }
})

// ⑤ 每日一练：把「下一个该做的事」直接放到看板
const plans = shallowRef<TrainingPlan[]>([])
const mistakeCount = shallowRef(0)

const todayAction = computed<{ eyebrow: string; title: string; detail: string; label: string; to: RouteLocationRaw } | null>(() => {
  const active = plans.value.filter((plan) => plan.status === 'ACTIVE')
  for (const plan of active) {
    const task = plan.tasks.find((item) => !item.completed)
    if (!task) continue
    const route = taskRoute(plan.id, task)
    if (!route) continue
    return {
      eyebrow: `计划 #${plan.sequence} · 下一步`,
      title: stepTitle(task),
      detail: task.task,
      label: task.actionType === 'COURSE' ? '去上课' : '去练习',
      to: route,
    }
  }
  if (mistakeCount.value > 0) {
    return {
      eyebrow: '今日复习',
      title: `有 ${mistakeCount.value} 条错题到期`,
      detail: '先把上次没答好的原话改写一遍，再决定要不要重练。',
      label: '去改话术',
      to: { name: 'scripts' },
    }
  }
  return null
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
      <section v-if="verifyBanner" class="verify-banner panel">
        <div>
          <strong>还差一步：验证邮箱</strong>
          <p>验证后即可开始训练。没收到邮件可以重新发送。</p>
        </div>
        <button class="button secondary" type="button" :disabled="resendBusy" @click="resendVerification">
          {{ resendBusy ? '发送中…' : '重发验证邮件' }}
        </button>
        <span v-if="resendState" class="verify-state">{{ resendState }}</span>
      </section>

      <DashboardScoreFeature
        :training-count="data.trainingCount"
        :latest-score="data.latestScore"
        :latest-degraded="Boolean(data.latestDegraded)"
        :focus="weakest"
        :style-tags="data.styleTags"
        :last-trained-at="lastTrainedAt"
        :trends="data.trends"
      />

      <DashboardAbilityPanel
        v-if="data.trainingCount"
        :scores="data.dimensions"
        :focus="weakest"
        :training-count="data.trainingCount"
        :weaknesses="data.weaknesses"
      />

      <section v-if="todayAction" class="today-card panel" aria-label="今天练什么">
        <div class="today-copy">
          <p class="eyebrow">{{ todayAction.eyebrow }}</p>
          <h2>{{ todayAction.title }}</h2>
          <p>{{ todayAction.detail }}</p>
        </div>
        <RouterLink class="button" :to="todayAction.to">{{ todayAction.label }} →</RouterLink>
      </section>

      <EmptyState
        v-else
        eyebrow="开始之前"
        title="先完成一场对练，看板才会有数据"
        description="一场 10 分钟的场景对练就能拿到四维评分、逐轮证据和下一步练什么。不需要先准备简历。"
        :steps="[
          { title: '选一个场景', detail: '从 HR 初面到终面共 25 场，按难度分层' },
          { title: '对着 AI 面试官回答', detail: '文字、语音或视频都行，看自己的习惯' },
          { title: '拿到可追溯的报告', detail: '每个分数都对应你原话里的证据' },
        ]"
        action-label="去选场景"
        action-to="/scenes"
      />

      <section class="trend panel" aria-labelledby="trend-title">
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
.dashboard { max-width: 1040px; }
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

.trend { margin-top: 40px; padding: 22px 24px 24px; }
.trend-empty { margin: 26px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.9; }

@media (max-width: 760px) {
  .page-head .date { display: none; }
  .trend { margin-top: 38px; }
}
.degraded-note { margin: 8px 0 0; color: var(--accent-strong); font-size: 12px; }
.today-card { margin-top: 20px; display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 18px 22px; }
.today-copy .eyebrow { margin: 0 0 6px; color: var(--accent-strong); font-size: 11px; letter-spacing: .12em; }
.today-copy h2 { margin: 0; font-size: 16px; font-weight: 600; }
.today-copy p { margin: 6px 0 0; color: var(--text-2); font-size: 12.5px; line-height: 1.7; }
@media (max-width: 720px) { .today-card { flex-direction: column; align-items: flex-start; } }

.verify-banner { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 18px; padding: 14px 18px; border: 1px solid var(--accent); background: var(--accent-soft); }
.verify-banner strong { display: block; font-size: 13.5px; }
.verify-banner p { margin: 4px 0 0; color: var(--text-2); font-size: 12px; }
.verify-state { color: var(--text-3); font-size: 11.5px; }
</style>
