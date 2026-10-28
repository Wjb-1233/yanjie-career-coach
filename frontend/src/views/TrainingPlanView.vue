<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useTrainingPlan } from '@/composables/useTrainingPlan'
import { api } from '@/lib/api'
import { taskRoute } from '@/lib/planActions'
import type { ApiEnvelope, Evaluation, Scores, TrainingPlanTask, TrainingSession } from '@/lib/types'

const route = useRoute()
const trainingPlan = useTrainingPlan(String(route.params.id))

const plan = computed(() => trainingPlan.plan.value)
const completedCount = computed(() => plan.value ? plan.value.tasks.filter((task) => task.completed).length : 0)
const totalCount = computed(() => plan.value?.tasks.length ?? 0)

const labels: Record<keyof Scores, string> = { logic: '逻辑性', appropriateness: '得体性', impact: '感染力', relevance: '针对性', concision: '简洁度' }
const baseline = shallowRef<Evaluation | null>(null)
const reviewSession = shallowRef<TrainingSession | null>(null)
const baselineSessionId = computed(() => plan.value?.tasks.find((task) => task.sourceSessionId)?.sourceSessionId ?? '')
const fallbackSessionId = shallowRef('')
const reviewSessionId = computed(() => baselineSessionId.value || fallbackSessionId.value)
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
  const result: Round[] = []
  let question = ''
  for (const message of session.messages) {
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
const courseTask = computed(() => plan.value?.tasks.find((task) => task.actionType === 'COURSE') ?? null)
const courseRoute = computed(() => (plan.value && courseTask.value ? taskRoute(plan.value.id, courseTask.value) : null))

onMounted(trainingPlan.load)

watch(reviewSessionId, async (sessionId) => {
  if (!sessionId) {
    // 旧计划没有关联会话时，退回到最近一次已评分的训练
    try {
      const history = await api.get<ApiEnvelope<Array<{ id: string; overallScore: number | null }>>>('/training-sessions')
      fallbackSessionId.value = history.data.data.find((item) => item.overallScore !== null)?.id ?? ''
    } catch {
      // 忽略，复盘区域留空
    }
    return
  }
  try {
    baseline.value = (await api.get<ApiEnvelope<Evaluation>>(`/evaluations/${sessionId}`)).data.data
    reviewSession.value = (await api.get<ApiEnvelope<TrainingSession>>(`/training-sessions/${sessionId}`)).data.data
  } catch {
    // 复盘是补充信息，取不到不影响后续学习
  }
}, { immediate: true })

interface TaskState { label: string; tone: 'done' | 'doing' | 'todo' }

function stateOf(task: TrainingPlanTask | null): TaskState {
  if (!task) return { label: '', tone: 'todo' }
  if (task.completed) return { label: '已完成', tone: 'done' }
  if (task.learningProgress > 0) return { label: `进行中 ${task.learningProgress}%`, tone: 'doing' }
  return { label: '待完成', tone: 'todo' }
}
</script>

<template>
  <div class="page plan-page">
    <RouterLink class="back" to="/plans">← 返回能力提升</RouterLink>

    <div v-if="trainingPlan.error.value" class="error-banner">{{ trainingPlan.error.value }}</div>
    <div v-if="trainingPlan.loading.value" class="skeleton plan-loading" />

    <template v-else-if="plan">
      <header class="plan-head">
        <div class="head-copy">
          <p class="eyebrow">训练计划 · 针对{{ plan.focusDimension }}</p>
          <h1>{{ plan.title }}</h1>
        </div>
        <div class="head-progress">
          <span class="count num">{{ completedCount }}<i>/</i>{{ totalCount }}</span>
          <span class="status">{{ plan.status === 'COMPLETED' ? '已完成' : plan.status === 'SUPERSEDED' ? '已被替代' : '进行中' }}</span>
        </div>
      </header>

      <div class="progress-line"><i :style="{ width: `${plan.progress}%` }" /></div>

      <section class="review" aria-label="复盘批注">
        <header class="section-head">
          <div class="section-title">
            <span class="section-no num">01</span>
            <h2>复盘优化</h2>
            <span class="section-hint">逐轮批注 + 建议改法</span>
          </div>
          <span class="section-state">参考</span>
        </header>

        <template v-if="baseline">
          <dl class="summary">
            <div class="metric">
              <dt>综合分</dt>
              <dd class="num">{{ baseline.overallScore }}<small>/ 100</small></dd>
            </div>
            <div class="metric">
              <dt>最低项</dt>
              <dd>{{ plan.focusDimension }}<small>{{ focusScore }} / 5</small></dd>
            </div>
            <div class="metric">
              <dt>待优化轮次</dt>
              <dd class="num">{{ annotatedCount }}<small>共 {{ rounds.length }} 轮</small></dd>
            </div>
          </dl>

          <p class="judgement">{{ baseline.summary }}</p>
          <RouterLink class="report-link" :to="`/report/${reviewSessionId}`">查看完整评分报告 →</RouterLink>
        </template>

        <div v-if="rounds.length" class="rounds">
          <article v-for="round in rounds" :key="round.roundNo" class="round" :class="{ flagged: round.problem || round.flags.length }">
            <span class="rail-dot" aria-hidden="true" />
            <header class="round-head">
              <span class="round-no num">第 {{ round.roundNo }} 轮</span>
              <span class="round-q">{{ round.question || '场景开场' }}</span>
            </header>
            <p class="round-a">{{ round.answer }}</p>
            <div v-if="round.problem || round.advice" class="note">
              <span class="note-label">批注</span>
              <p v-if="round.problem">{{ round.problem }}</p>
              <p v-if="round.advice" class="note-fix">{{ round.advice }}</p>
            </div>
            <p v-else class="note-empty">未列入重点问题</p>
            <p v-if="round.flags.length" class="note-warn">表达提醒：{{ round.flags.join('、') }}</p>
          </article>
        </div>
      </section>

      <section v-if="courseTask" class="lesson" aria-label="学习微课">
        <header class="section-head">
          <div class="section-title">
            <span class="section-no num">02</span>
            <h2>学习微课</h2>
            <span class="section-hint">{{ courseTask.lesson?.title ?? '针对性短课' }}</span>
          </div>
          <span class="section-state" :class="stateOf(courseTask).tone"><i aria-hidden="true" />{{ stateOf(courseTask).label }}</span>
        </header>

        <div v-if="courseTask.lesson" class="course">
          <div class="course-meta">
            <span>{{ courseTask.lesson.steps.length }} 个步骤 + 1 道练习</span>
            <span class="num">{{ courseTask.learningProgress }}%</span>
          </div>
          <i class="bar"><b :style="{ width: `${courseTask.learningProgress}%` }" /></i>
          <ol class="course-steps">
            <li v-for="(item, index) in courseTask.lesson.steps" :key="index">
              <span class="step-index num">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="step-name">{{ item.title }}</span>
            </li>
          </ol>
        </div>

        <RouterLink v-if="!courseTask.completed && courseRoute" class="button" :to="courseRoute ?? '/plans'">
          {{ courseTask.learningProgress > 0 ? '继续学习微课 →' : '开始学习微课 →' }}
        </RouterLink>
        <p v-else-if="courseTask.completed" class="done-note">✓ 微课与练习已完成</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.plan-page { max-width: 860px; }

.back { display: inline-block; margin-bottom: 26px; color: var(--text-3); font-size: 12px; letter-spacing: .04em; transition: color var(--ease); }
.back:hover { color: var(--text); }
.error-banner { margin-bottom: 18px; }
.plan-loading { min-height: 380px; }

/* ---------- 头部 ---------- */
.plan-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 32px; }
.head-copy { min-width: 0; }
.plan-head h1 { margin: 10px 0 0; color: var(--text); font-size: clamp(24px, 3vw, 30px); font-weight: 600; line-height: 1.35; letter-spacing: -.015em; }
.head-progress { flex: none; display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.head-progress .count { color: var(--text); font-family: var(--font-num); font-size: 26px; font-weight: 300; line-height: 1; letter-spacing: -.02em; }
.head-progress .count i { margin: 0 4px; color: var(--text-3); font-style: normal; font-size: 16px; }
.head-progress .status { color: var(--text-3); font-size: 11px; letter-spacing: .1em; }

.progress-line { height: 2px; margin-top: 18px; background: var(--track); }
.progress-line i { display: block; height: 100%; background: var(--accent); transition: width .4s var(--ease); }

/* ---------- 区块头 ---------- */
.section-head { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-top: 46px; padding-bottom: 16px; border-bottom: 1px solid var(--divider); }
.section-title { display: flex; align-items: baseline; gap: 12px; min-width: 0; }
.section-no { color: var(--text-3); font-size: 11px; letter-spacing: .1em; }
.section-title h2 { margin: 0; color: var(--text); font-size: 17px; font-weight: 500; letter-spacing: .01em; }
.section-hint { color: var(--text-3); font-size: 12px; letter-spacing: .02em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.section-state { flex: none; display: inline-flex; align-items: center; gap: 6px; color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.section-state i { width: 6px; height: 6px; border-radius: 50%; border: 1px solid var(--text-3); }
.section-state.done { color: var(--text-2); }
.section-state.done i { border-color: var(--accent); background: var(--accent); }
.section-state.doing { color: var(--accent-strong); }
.section-state.doing i { border-color: var(--accent); background: var(--accent); }

/* ---------- 复盘摘要 ---------- */
.summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 24px 0 0; }
.metric { padding: 0 28px; border-left: 1px solid var(--divider); }
.metric:first-child { padding-left: 0; border-left: 0; }
.metric dt { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.metric dd { display: flex; align-items: baseline; gap: 8px; margin: 10px 0 0; color: var(--text); font-size: 18px; font-weight: 400; letter-spacing: -.01em; }
.metric dd.num { font-family: var(--font-num); font-size: 32px; font-weight: 300; letter-spacing: -.03em; line-height: 1; }
.metric dd small { color: var(--text-3); font-family: var(--font-ui); font-size: 11px; font-weight: 400; letter-spacing: .04em; }

.judgement { max-width: 70ch; margin: 22px 0 0; color: var(--text-2); font-size: 13px; line-height: 2; }
.report-link { display: inline-block; margin-top: 12px; color: var(--text-2); font-size: 12px; border-bottom: 1px solid var(--border-bright); padding-bottom: 1px; transition: color var(--ease), border-color var(--ease); }
.report-link:hover { color: var(--accent-strong); border-color: var(--accent); }

/* ---------- 逐轮时间线 ---------- */
.rounds { position: relative; margin: 26px 0 0; padding-left: 26px; }
.rounds::before { content: ''; position: absolute; top: 10px; bottom: 10px; left: 8px; width: 1px; background: var(--divider); }
.round { position: relative; padding: 16px 0; }
.round + .round { border-top: 1px solid var(--divider); }
.rail-dot { position: absolute; top: 23px; left: -22px; width: 7px; height: 7px; border: 1px solid var(--text-3); border-radius: 50%; background: var(--bg); }
.round.flagged .rail-dot { border-color: var(--accent); background: var(--accent); }

.round-head { display: flex; align-items: baseline; gap: 12px; }
.round-no { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .06em; }
.round-q { color: var(--text-2); font-size: 13px; line-height: 1.75; }
.round.flagged .round-q { color: var(--text); }
.round-a { margin: 8px 0 0 50px; color: var(--text-2); font-size: 13px; line-height: 1.9; white-space: pre-wrap; }
.round.flagged .round-a { color: var(--text); }

.note { position: relative; margin: 12px 0 0 50px; padding: 12px 16px; border-radius: var(--radius-sm); background: var(--bg-2); }
.note::before { content: ''; position: absolute; top: 12px; bottom: 12px; left: 0; width: 2px; background: var(--accent); }
.note-label { display: block; margin-bottom: 6px; color: var(--accent-strong); font-size: 10px; letter-spacing: .2em; }
.note p { margin: 0; color: var(--text-2); font-size: 12.5px; line-height: 1.9; }
.note p + p { margin-top: 6px; }
.note-fix { color: var(--text); }
.note-empty { margin: 8px 0 0 50px; color: var(--text-3); font-size: 12px; }
.note-warn { margin: 8px 0 0 50px; color: var(--warning); font-size: 11px; letter-spacing: .02em; }

/* ---------- 微课 ---------- */
.course { margin-top: 22px; }
.course-meta { display: flex; justify-content: space-between; gap: 16px; color: var(--text-3); font-size: 12px; letter-spacing: .02em; }
.course .bar { display: block; height: 2px; margin-top: 10px; background: var(--track); }
.course .bar b { display: block; height: 100%; background: var(--accent); }
.course-steps { margin: 18px 0 0; padding: 0; list-style: none; }
.course-steps li { display: flex; align-items: baseline; gap: 16px; padding: 11px 0; border-top: 1px solid var(--divider); }
.course-steps .step-index { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.course-steps .step-name { color: var(--text-2); font-size: 13px; line-height: 1.6; }

.lesson .button { margin-top: 22px; }
.done-note { margin: 20px 0 0; color: var(--text-2); font-size: 13px; }

@media (max-width: 640px) {
  .plan-head { align-items: flex-start; flex-direction: column; gap: 14px; }
  .head-progress { align-items: flex-start; flex-direction: row; gap: 12px; }
  .summary { grid-template-columns: 1fr; gap: 16px; }
  .metric { padding: 0; border-left: 0; }
  .round-a, .note, .note-empty, .note-warn { margin-left: 0; }
}
</style>
