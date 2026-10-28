<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import PlanTaskCard from '@/components/plans/PlanTaskCard.vue'
import PlanComparison from '@/components/plans/PlanComparison.vue'
import { useTrainingPlan } from '@/composables/useTrainingPlan'
import { api } from '@/lib/api'
import { stepTitle, taskActionLabel, taskRoute } from '@/lib/planActions'
import type { ApiEnvelope, Evaluation, Scores, TrainingSession } from '@/lib/types'

const route = useRoute()
const trainingPlan = useTrainingPlan(String(route.params.id))

const plan = computed(() => trainingPlan.plan.value)
const completedCount = computed(() => plan.value ? plan.value.tasks.filter((task) => task.completed).length : 0)
const totalCount = computed(() => plan.value?.tasks.length ?? 0)

const labels: Record<keyof Scores, string> = { logic: '逻辑性', appropriateness: '得体性', impact: '感染力', relevance: '针对性', concision: '简洁度' }
const baseline = shallowRef<Evaluation | null>(null)
const baselineSessionId = computed(() => plan.value?.tasks.find((task) => task.sourceSessionId)?.sourceSessionId ?? '')
const focusKey = computed(() => (Object.entries(labels) as Array<[keyof Scores, string]>)
  .find(([, label]) => label === plan.value?.focusDimension)?.[0])
const focusScore = computed(() => (focusKey.value && baseline.value ? baseline.value.scores[focusKey.value] : 0))
const reviewSession = shallowRef<TrainingSession | null>(null)
const rounds = computed(() => {
  const messages = reviewSession.value?.messages ?? []
  const result: Array<{ roundNo: number; question: string; answer: string; flags: readonly string[] }> = []
  let question = ''
  for (const message of messages) {
    if (message.speaker === 'AI') question = message.content
    else if (message.speaker === 'USER') result.push({ roundNo: message.roundNo, question, answer: message.content, flags: message.flags })
  }
  return result
})

const nextTask = computed(() => plan.value?.tasks.find((task) => !task.completed) ?? null)
const nextRoute = computed(() => (plan.value && nextTask.value ? taskRoute(plan.value.id, nextTask.value) : null))
const currentIndex = computed(() => plan.value ? plan.value.tasks.findIndex((task) => !task.completed) : -1)

onMounted(trainingPlan.load)

watch(baselineSessionId, async (sessionId) => {
  if (!sessionId) return
  try {
    baseline.value = (await api.get<ApiEnvelope<Evaluation>>(`/evaluations/${sessionId}`)).data.data
    reviewSession.value = (await api.get<ApiEnvelope<TrainingSession>>(`/training-sessions/${sessionId}`)).data.data
  } catch {
    // 复盘只是补充信息，取不到不影响任务执行
  }
}, { immediate: true })

async function complete(taskKey: string, evidence?: string): Promise<void> {
  try {
    await trainingPlan.complete(taskKey, evidence)
  } catch {
    // 错误信息由 composable 统一展示。
  }
}
</script>

<template>
  <div class="page plan-page">
    <RouterLink class="back" to="/plans">← 返回能力提升</RouterLink>

    <div v-if="trainingPlan.error.value" class="error-banner">{{ trainingPlan.error.value }}</div>
    <div v-if="trainingPlan.loading.value" class="skeleton plan-loading" />

    <template v-else-if="plan">
      <header class="plan-head">
        <p class="eyebrow">训练计划 · 针对{{ plan.focusDimension }}</p>
        <h1>{{ plan.title }}</h1>
        <div class="progress-row">
          <span class="num">{{ completedCount }} / {{ totalCount }}</span>
          <i class="bar"><b :style="{ width: `${plan.progress}%` }" /></i>
          <span class="status">{{ plan.status === 'COMPLETED' ? '已完成' : plan.status === 'SUPERSEDED' ? '已被替代' : '进行中' }}</span>
        </div>

      </header>
      <div v-if="nextTask" class="next-action">
        <span class="next-copy">
          <span class="k">下一步</span>
          <strong>{{ stepTitle(nextTask) }}</strong>
        </span>
        <RouterLink v-if="nextRoute" class="button" :to="nextRoute">{{ taskActionLabel(nextTask) }} →</RouterLink>
        <a v-else class="button" :href="'#task-' + nextTask.key">去逐轮改写 ↓</a>
      </div>

      <section v-if="baseline" class="review" aria-label="计划依据的评分复盘">
        <header class="section-head">
          <h2 class="label">复盘</h2>
          <RouterLink class="text-link" :to="`/report/${baselineSessionId}`">查看完整评分报告 →</RouterLink>
        </header>

        <div class="review-stats">
          <div>
            <span class="k">综合分</span>
            <strong class="num">{{ baseline.overallScore }}</strong>
          </div>
          <div>
            <span class="k">最低项</span>
            <strong>{{ plan.focusDimension }}</strong>
          </div>
          <div>
            <span class="k">该维度得分</span>
            <strong class="num">{{ focusScore }} / 5</strong>
          </div>
        </div>

        <p class="review-summary">{{ baseline.summary }}</p>
        <p v-if="baseline.styleTags.length" class="review-tags">表达风格：{{ baseline.styleTags.join(' · ') }}</p>

        <details v-if="rounds.length" class="turns-block">
          <summary class="turns-head">逐轮回看 · 共 {{ rounds.length }} 轮回答</summary>
          <div class="turns">
          <details v-for="turn in rounds" :key="turn.roundNo" class="turn">
            <summary>
              <span class="turn-no num">第 {{ turn.roundNo }} 轮</span>
              <span class="turn-question">{{ turn.question || "场景开场" }}</span>
            </summary>
            <div class="turn-body">
              <p class="turn-answer">{{ turn.answer }}</p>
              <p v-if="turn.flags.length" class="turn-flags">表达提醒：{{ turn.flags.join("、") }}</p>
            </div>
          </details>
          </div>
        </details>
      </section>

      <section class="task-list" aria-label="训练计划任务">
        <header class="section-head">
          <h2 class="label">提升</h2>
          <span class="note">按顺序完成四项</span>
        </header>
        <PlanTaskCard
          v-for="(task, index) in plan.tasks"
          :key="task.key"
          :plan-id="plan.id"
          :task="task"
          :submitting="trainingPlan.submitting.value"
          :locked="plan.tasks.slice(0, index).some((previous) => !previous.completed)"
          :step-number="index + 1"
          :show-action="currentIndex !== index"
          @complete="complete"
        />
      </section>

      <PlanComparison
        v-if="plan.comparison"
        :comparison="plan.comparison"
        :focus-dimension="plan.focusDimension"
      />
    </template>
  </div>
</template>

<style scoped>
.plan-page { max-width: 900px; }
.back {
  display: inline-block;
  margin-bottom: 22px;
  color: var(--text-3);
  font-size: 12px;
  letter-spacing: .04em;
  transition: color var(--ease);
}
.back:hover { color: var(--text); }
.error-banner { margin-bottom: 18px; }
.plan-loading { min-height: 380px; }

.plan-head { padding-bottom: 22px; border-bottom: 1px solid var(--divider); }
.plan-head h1 {
  margin: 10px 0 0;
  color: var(--text);
  font-size: clamp(22px, 3vw, 28px);
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: -.01em;
}
.progress-row { display: flex; align-items: center; gap: 16px; margin-top: 20px; }
.progress-row .num { color: var(--text-2); font-family: var(--font-num); font-size: 13px; letter-spacing: .02em; }
.progress-row .bar { flex: 1; height: 2px; background: var(--track); }
.progress-row .bar b { display: block; height: 100%; background: var(--accent); }
.progress-row .status { color: var(--text-3); font-size: 11px; letter-spacing: .08em; }

.next-action { position: sticky; top: 70px; z-index: 6; display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-top: 22px; padding: 14px 18px; border: 1px solid var(--border); border-radius: var(--radius); background: var(--card); }
.next-copy { display: flex; align-items: baseline; gap: 12px; min-width: 0; }
.next-copy .k { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.next-copy strong { color: var(--text); font-size: 14px; font-weight: 500; line-height: 1.5; }
.turns-block { margin-top: 24px; border-top: 1px solid var(--divider); }
.turns-block > summary { padding: 14px 0; color: var(--text-2); font-size: 12px; letter-spacing: .06em; cursor: pointer; list-style: none; }
.turns-block > summary::-webkit-details-marker { display: none; }
.turns-block > summary::before { content: "+"; margin-right: 8px; color: var(--text-3); }
.turns-block[open] > summary::before { content: "−"; }

.section-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--divider);
}
.section-head h2 { margin: 0; color: var(--text-3); font-size: 11px; font-weight: 400; letter-spacing: .2em; }
.section-head .note { color: var(--text-3); font-size: 11px; letter-spacing: .06em; }

.review { margin-top: 34px; }
.review-stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px; padding: 22px 0 4px; }
.review-stats .k { display: block; color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.review-stats strong { display: block; margin-top: 10px; color: var(--text); font-size: 24px; font-weight: 400; letter-spacing: -.01em; }
.review-stats strong.num { font-family: var(--font-num); }
.review-summary { max-width: 72ch; margin: 18px 0 0; color: var(--text-2); font-size: 13px; line-height: 1.95; }
.review-tags { margin: 10px 0 0; color: var(--text-3); font-size: 11px; letter-spacing: .06em; }

.turns { margin-top: 26px; }
.turns-head { margin: 0 0 10px; color: var(--text-3); font-size: 11px; letter-spacing: .12em; }
.turn { border-bottom: 1px solid var(--divider); }
.turn summary { display: flex; align-items: baseline; gap: 14px; padding: 12px 2px; cursor: pointer; list-style: none; }
.turn summary::-webkit-details-marker { display: none; }
.turn-no { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .06em; }
.turn-question { color: var(--text-2); font-size: 13px; line-height: 1.7; }
.turn[open] .turn-question { color: var(--text); }
.turn-body { padding: 0 2px 16px 62px; }
.turn-answer { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.9; white-space: pre-wrap; }
.turn-flags { margin: 8px 0 0; color: var(--warning); font-size: 11px; letter-spacing: .04em; }

.text-link {
  color: var(--text-2);
  font-size: 12px;
  letter-spacing: .04em;
  border-bottom: 1px solid var(--border-bright);
  padding-bottom: 1px;
  transition: color var(--ease), border-color var(--ease);
}
.text-link:hover { color: var(--accent-strong); border-color: var(--accent); }

.task-list { margin-top: 34px; }

@media (max-width: 640px) {
  .review-stats { grid-template-columns: 1fr 1fr; gap: 18px; }
  .review-stats > div:last-child { grid-column: 1 / -1; }
}
</style>
