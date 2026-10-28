<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useTrainingPlan } from '@/composables/useTrainingPlan'
import { api, errorMessage } from '@/lib/api'
import { taskRoute } from '@/lib/planActions'
import type { ApiEnvelope, Evaluation, Scores, TrainingPlanTask, TrainingSession } from '@/lib/types'

const route = useRoute()
const trainingPlan = useTrainingPlan(String(route.params.id))

const plan = computed(() => trainingPlan.plan.value)
const submitting = computed(() => trainingPlan.submitting.value)
const completedCount = computed(() => plan.value ? plan.value.tasks.filter((task) => task.completed).length : 0)
const totalCount = computed(() => plan.value?.tasks.length ?? 0)
const currentIndex = computed(() => plan.value ? plan.value.tasks.findIndex((task) => !task.completed) : -1)

const labels: Record<keyof Scores, string> = { logic: '逻辑性', appropriateness: '得体性', impact: '感染力', relevance: '针对性', concision: '简洁度' }
const baseline = shallowRef<Evaluation | null>(null)
const reviewSession = shallowRef<TrainingSession | null>(null)
const baselineSessionId = computed(() => plan.value?.tasks.find((task) => task.sourceSessionId)?.sourceSessionId ?? '')
const focusKey = computed(() => (Object.entries(labels) as Array<[keyof Scores, string]>)
  .find(([, label]) => label === plan.value?.focusDimension)?.[0])
const focusScore = computed(() => (focusKey.value && baseline.value ? baseline.value.scores[focusKey.value] : 0))

interface Round {
  roundNo: number
  question: string
  answer: string
  flags: readonly string[]
  problem: string
  advice: string
}
const rounds = computed<Round[]>(() => {
  const session = reviewSession.value
  if (!session) return []
  const messages = session.messages
  const result: Round[] = []
  let question = ''
  for (const message of messages) {
    if (message.speaker === 'AI') { question = message.content; continue }
    if (message.speaker !== 'USER') continue
    const suggestion = baseline.value?.suggestions.find((item) => item.roundNo === message.roundNo)
    const evidence = baseline.value?.evidence.find((item) => item.roundNo === message.roundNo)
    result.push({
      roundNo: message.roundNo,
      question,
      answer: message.content,
      flags: message.flags,
      problem: suggestion?.problem ?? evidence?.reason ?? '',
      advice: suggestion?.rewrite ?? evidence?.nextAction ?? '',
    })
  }
  return result
})

const annotatedCount = computed(() => rounds.value.filter((round) => round.problem || round.advice).length)
const reviewTask = computed(() => plan.value?.tasks.find((task) => task.actionType === 'REWRITE') ?? null)
const courseTask = computed(() => plan.value?.tasks.find((task) => task.actionType === 'COURSE') ?? null)
const courseRoute = computed(() => (plan.value && courseTask.value ? taskRoute(plan.value.id, courseTask.value) : null))

const ackError = shallowRef('')

onMounted(trainingPlan.load)

watch(baselineSessionId, async (sessionId) => {
  if (!sessionId) return
  try {
    baseline.value = (await api.get<ApiEnvelope<Evaluation>>(`/evaluations/${sessionId}`)).data.data
    reviewSession.value = (await api.get<ApiEnvelope<TrainingSession>>(`/training-sessions/${sessionId}`)).data.data
  } catch {
    // 复盘是补充信息，取不到不影响后续学习
  }
}, { immediate: true })

function stateOf(task: TrainingPlanTask | null): string {
  if (!task) return ''
  return task.completed ? '已完成' : '待完成'
}

async function acknowledgeReview(): Promise<void> {
  ackError.value = ''
  try {
    await trainingPlan.complete('rewrite', '已阅读逐轮批注，记下需要修改的表达。')
  } catch (reason) {
    ackError.value = errorMessage(reason)
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

      <ol class="steps">
        <!-- 01 复盘批注 -->
        <li id="step-review" class="step" :class="{ done: reviewTask?.completed, current: currentIndex === 0 }">
          <header class="step-head">
            <span class="step-no num">01</span>
            <div class="step-title">
              <h2>复盘优化</h2>
              <p>逐轮批注 + 建议改法，共 {{ rounds.length }} 轮，其中 {{ annotatedCount }} 轮需重点优化</p>
            </div>
            <span class="state">{{ stateOf(reviewTask) }}</span>
          </header>

          <div v-if="baseline" class="overview">
            <dl class="stats">
              <div><dt>综合分</dt><dd class="num">{{ baseline.overallScore }}</dd></div>
              <div><dt>最低项</dt><dd>{{ plan.focusDimension }}</dd></div>
              <div><dt>该维度得分</dt><dd class="num">{{ focusScore }} / 5</dd></div>
            </dl>
            <p class="judgement">{{ baseline.summary }}</p>
            <RouterLink class="report-link" :to="`/report/${baselineSessionId}`">查看完整评分报告 →</RouterLink>
          </div>

          <div class="rounds">
            <article v-for="round in rounds" :key="round.roundNo" class="round">
              <header class="round-head">
                <span class="round-no num">第 {{ round.roundNo }} 轮</span>
                <span class="round-q">{{ round.question || '场景开场' }}</span>
              </header>
              <p class="round-a">{{ round.answer }}</p>
              <div v-if="round.problem || round.advice" class="note">
                <p v-if="round.problem"><b>问题</b>{{ round.problem }}</p>
                <p v-if="round.advice" class="note-fix"><b>建议</b>{{ round.advice }}</p>
              </div>
              <p v-else class="note-empty">本轮未列入重点问题</p>
              <p v-if="round.flags.length" class="note-warn">表达提醒：{{ round.flags.join('、') }}</p>
            </article>
          </div>

          <div v-if="!reviewTask?.completed" class="ack">
            <button class="button" type="button" :disabled="submitting" @click="acknowledgeReview">
              {{ submitting ? '提交中…' : '看完了，去学微课 →' }}
            </button>
            <p v-if="ackError" class="ack-error">{{ ackError }}</p>
          </div>
          <p v-else class="done-note">✓ 已完成复盘</p>
        </li>

        <!-- 02 学习微课 -->
        <li v-if="courseTask" class="step" :class="{ done: courseTask.completed, current: currentIndex === 1 }">
          <header class="step-head">
            <span class="step-no num">02</span>
            <div class="step-title">
              <h2>学习微课</h2>
              <p>{{ courseTask.lesson?.title ?? '针对性短课' }}</p>
            </div>
            <span class="state">{{ stateOf(courseTask) }}</span>
          </header>
          <div class="step-body">
            <div v-if="courseTask.lesson" class="course">
              <div class="course-meta">
                <span>{{ courseTask.lesson.steps.length }} 个步骤 + 1 道练习</span>
                <span class="num">{{ courseTask.learningProgress }}%</span>
              </div>
              <i class="bar"><b :style="{ width: `${courseTask.learningProgress}%` }" /></i>
              <ol class="course-steps">
                <li v-for="(item, index) in courseTask.lesson.steps" :key="index">
                  <span class="num">{{ String(index + 1).padStart(2, '0') }}</span>
                  <span>{{ item.title }}</span>
                </li>
              </ol>
            </div>
            <RouterLink v-if="!courseTask.completed && courseRoute" class="button" :to="courseRoute ?? '/plans'">
              {{ courseTask.learningProgress > 0 ? '继续学习微课 →' : '开始学习微课 →' }}
            </RouterLink>
            <p v-else-if="courseTask.completed" class="done-note">✓ 微课与练习已完成</p>
          </div>
        </li>
      </ol>
    </template>
  </div>
</template>

<style scoped>
.plan-page { max-width: 900px; }
.back { display: inline-block; margin-bottom: 22px; color: var(--text-3); font-size: 12px; letter-spacing: .04em; transition: color var(--ease); }
.back:hover { color: var(--text); }
.error-banner { margin-bottom: 18px; }
.plan-loading { min-height: 380px; }

.plan-head { padding-bottom: 22px; border-bottom: 1px solid var(--divider); }
.plan-head h1 { margin: 10px 0 0; color: var(--text); font-size: clamp(22px, 3vw, 28px); font-weight: 600; line-height: 1.4; letter-spacing: -.01em; }
.progress-row { display: flex; align-items: center; gap: 16px; margin-top: 20px; }
.progress-row .num { color: var(--text-2); font-family: var(--font-num); font-size: 13px; }
.progress-row .bar { flex: 1; height: 2px; background: var(--track); }
.progress-row .bar b { display: block; height: 100%; background: var(--accent); }
.progress-row .status { color: var(--text-3); font-size: 11px; letter-spacing: .08em; }

.steps { margin: 34px 0 0; padding: 0; list-style: none; }
.step { padding: 24px 0 30px; border-bottom: 1px solid var(--divider); }
.step-head { display: flex; align-items: baseline; gap: 16px; }
.step-no { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.step-title { flex: 1; min-width: 0; }
.step-title h2 { margin: 0; color: var(--text); font-size: 17px; font-weight: 500; line-height: 1.5; }
.step-title p { margin: 6px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.7; }
.step.done .step-no, .step.done .step-title h2 { color: var(--text-3); }
.state { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.step-body { padding-left: 32px; margin-top: 16px; }

.overview { padding-left: 32px; }
.stats { display: flex; gap: 40px; margin: 18px 0 0; }
.stats dt { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.stats dd { margin: 8px 0 0; color: var(--text); font-size: 20px; font-weight: 400; }
.stats dd.num { font-family: var(--font-num); }
.judgement { max-width: 72ch; margin: 16px 0 0; color: var(--text-2); font-size: 13px; line-height: 1.95; }
.report-link { display: inline-block; margin-top: 10px; color: var(--text-2); font-size: 12px; border-bottom: 1px solid var(--border-bright); padding-bottom: 1px; }
.report-link:hover { color: var(--accent-strong); border-color: var(--accent); }

.rounds { margin-top: 24px; padding-left: 32px; display: grid; gap: 0; }
.round { padding: 16px 0; border-top: 1px solid var(--divider); }
.round-head { display: flex; align-items: baseline; gap: 14px; }
.round-no { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .06em; }
.round-q { color: var(--text-2); font-size: 13px; line-height: 1.7; }
.round-a { margin: 8px 0 0 51px; color: var(--text); font-size: 13px; line-height: 1.85; white-space: pre-wrap; }
.note { margin: 10px 0 0 51px; padding: 10px 14px; border-left: 2px solid var(--accent); background: var(--bg-2); }
.note p { margin: 0; color: var(--text-2); font-size: 12px; line-height: 1.85; }
.note p + p { margin-top: 6px; }
.note b { display: inline-block; margin-right: 8px; color: var(--text-3); font-weight: 400; letter-spacing: .08em; }
.note-fix { color: var(--text); }
.note-fix b { color: var(--text-3); }
.note-empty { margin: 8px 0 0 51px; color: var(--text-3); font-size: 12px; }
.note-warn { margin: 8px 0 0 51px; color: var(--warning); font-size: 11px; }

.ack { margin: 26px 0 0 32px; }
.ack-error { margin: 8px 0 0; color: var(--danger); font-size: 12px; }
.done-note { margin: 18px 0 0 32px; color: var(--text-2); font-size: 13px; line-height: 1.8; }

.course-meta { display: flex; justify-content: space-between; gap: 16px; color: var(--text-3); font-size: 12px; }
.course .bar { display: block; height: 2px; margin-top: 10px; background: var(--track); }
.course .bar b { display: block; height: 100%; background: var(--accent); }
.course-steps { margin: 14px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.course-steps li { display: flex; gap: 12px; color: var(--text-2); font-size: 13px; line-height: 1.6; }
.course-steps .num { color: var(--text-3); font-size: 11px; }
.step-body .button { margin-top: 18px; }

@media (max-width: 640px) {
  .overview, .rounds { padding-left: 0; }
  .round-a, .note, .note-empty, .note-warn { margin-left: 0; }
  .ack, .done-note { margin-left: 0; }
  .stats { gap: 24px; }
}
</style>
