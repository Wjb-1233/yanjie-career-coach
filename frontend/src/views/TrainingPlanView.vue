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

const staleDays = computed(() => {
  const current = plan.value
  if (!current || current.status !== 'ACTIVE' || current.progress >= 100) return 0
  const created = new Date(current.createdAt).getTime()
  if (!created) return 0
  return Math.floor((Date.now() - created) / 86400000)
})
const totalCount = computed(() => plan.value?.tasks.length ?? 0)

const labels: Record<keyof Scores, string> = { logic: '内容与逻辑', relevance: '贴合问题', correctness: '信息完整', concision: '表达干净' }
const baseline = shallowRef<Evaluation | null>(null)
const busyTask = shallowRef('')

async function completeReview(taskKey: string): Promise<void> {
  if (!plan.value || busyTask.value) return
  busyTask.value = taskKey
  try {
    await trainingPlan.complete(taskKey)
  } catch {
    // 错误已由 composable 写入 plan 级错误提示
  } finally {
    busyTask.value = ''
  }
}

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
  reference: string
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
      reference: suggestion?.reference ?? '',
    })
  }
  return result
})

const annotatedCount = computed(() => rounds.value.filter((round) => round.problem || round.advice).length)
const reviewChannel = computed(() => reviewSession.value?.channel ?? 'TEXT')
const channelLabel = computed(() => ({ TEXT: '文字面试', VOICE: '语音面试', VIDEO: '视频面试' })[reviewChannel.value] ?? '文字面试')
const delivery = computed(() => (reviewSession.value?.delivery ?? {}) as Record<string, unknown>)
const vision = computed(() => (delivery.value.vision ?? null) as null | {
  available: boolean
  faceRatio?: number
  eyeContactRatio?: number
  headStability?: number
  brightness?: number
  tips?: string[]
  reason?: string
})
const deliveryStats = computed(() => {
  const stats = delivery.value as Record<string, unknown>
  if (reviewChannel.value !== 'VOICE' || stats.speechRate === undefined) return null
  return {
    speechRate: Math.round(Number(stats.speechRate ?? 0)),
    pauseCount: Number(stats.pauseCount ?? 0),
    longestPause: Number(stats.longestPause ?? 0),
    fillerTotal: Number(stats.fillerTotal ?? 0),
  }
})
const sceneTasks = computed(() =>
  (plan.value?.tasks ?? []).filter((task) => ['SCENE', 'VIDEO', 'VOICE', 'REWRITE', 'REPORT', 'REVIEW', 'TRAINING', 'RETEST'].includes(task.actionType)),
)

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
      <header class="head">
        <p class="eyebrow">{{ plan.focusDimension }}</p>
        <h1>{{ plan.title }}</h1>
        <p class="meta">{{ completedCount }} / {{ totalCount }} 已完成 · {{ plan.progress }}%</p>
        <div class="bar"><i :style="{ width: `${plan.progress}%` }" /></div>
      </header>

      <p v-if="staleDays >= 7" class="stale-note">这份计划放了 {{ staleDays }} 天还没走完，先做一项也好。</p>

      <section v-if="sceneTasks.length" class="block">
        <h2>接下来</h2>
        <ul class="todo">
          <li v-for="task in sceneTasks" :key="task.key">
            <span class="task-name">{{ task.task }}</span>
            <button
              v-if="task.actionType === 'REVIEW' && !task.completed"
              type="button"
              class="text-action"
              :disabled="busyTask === task.key"
              @click="completeReview(task.key)"
            >{{ busyTask === task.key ? '处理中…' : '标记已复习' }}</button>
            <RouterLink v-else-if="!task.completed" class="text-action" :to="taskRoute(plan.id, task) ?? { name: 'scenes' }">去做 →</RouterLink>
            <span v-else class="done">已完成</span>
          </li>
        </ul>
      </section>

      <section v-if="baseline" class="block">
        <h2>本场复盘 <span class="sub">{{ channelLabel }}</span></h2>

        <div class="stats">
          <div><span>综合分</span><strong>{{ baseline.overallScore }}</strong></div>
          <div><span>最低项</span><strong>{{ plan.focusDimension }} · {{ focusScore }}/5</strong></div>
          <div><span>待优化</span><strong>{{ annotatedCount }} 轮</strong></div>
        </div>

        <div v-if="deliveryStats" class="inline-stats">
          <span>语速 {{ deliveryStats.speechRate }} 字/分</span>
          <span>停顿 {{ deliveryStats.pauseCount }} 次</span>
          <span>最长 {{ deliveryStats.longestPause }} 秒</span>
          <span>口头禅 {{ deliveryStats.fillerTotal }} 次</span>
        </div>

        <div v-if="reviewChannel === 'VIDEO' && vision" class="vision">
          <template v-if="vision.available">
            <div class="inline-stats">
              <span>出镜率 {{ Math.round((vision.faceRatio ?? 0) * 100) }}%</span>
              <span>看镜头 {{ Math.round((vision.eyeContactRatio ?? 0) * 100) }}%</span>
              <span>头部稳定 {{ Math.round((vision.headStability ?? 0) * 100) }}%</span>
            </div>
            <ul v-if="vision.tips?.length" class="tips"><li v-for="tip in vision.tips" :key="tip">{{ tip }}</li></ul>
          </template>
          <p v-else class="muted">{{ vision.reason || '这一场没有可用的镜头分析。' }}</p>
        </div>

        <p class="summary-text">{{ baseline.summary }}</p>
        <RouterLink class="report-link" :to="`/report/${reviewSessionId}`">查看完整评分报告 →</RouterLink>

        <div v-if="rounds.length" class="rounds">
          <article v-for="round in rounds" :key="round.roundNo" class="round">
            <p class="q">第 {{ round.roundNo }} 轮 · {{ round.question || '场景开场' }}</p>
            <p class="a">{{ round.answer }}</p>
            <div v-if="round.problem || round.advice" class="note">
              <p v-if="round.problem">{{ round.problem }}</p>
              <p v-if="round.advice" class="fix">改法：{{ round.advice }}</p>
              <p v-if="round.reference" class="ref">{{ round.reference }}</p>
            </div>
            <p v-if="round.flags.length" class="muted">表达提醒：{{ round.flags.join('、') }}</p>
          </article>
        </div>
      </section>

      <section v-if="courseTask" class="block">
        <h2>微课</h2>
        <div class="course-row">
          <div class="course-copy">
            <strong>{{ courseTask.lesson?.title ?? '针对性视频课' }}</strong>
            <span>{{ stateOf(courseTask).label }} · {{ courseTask.learningProgress }}%</span>
          </div>
          <RouterLink v-if="courseRoute" class="text-action" :to="courseRoute ?? '/plans'">
            {{ courseTask.completed ? '回看 →' : courseTask.learningProgress > 0 ? '继续学习 →' : '开始学习 →' }}
          </RouterLink>
          <span v-else class="done">已完成</span>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.plan-page { max-width: 760px; }
.back { display: inline-block; margin-bottom: 28px; color: var(--text-3); font-size: 13px; }
.back:hover { color: var(--text); }
.plan-loading { min-height: 320px; }

.head { padding-bottom: 22px; }
.head .eyebrow { margin: 0 0 10px; }
.head h1 { margin: 0; font-size: clamp(28px, 3.2vw, 36px); font-weight: 650; letter-spacing: -.02em; line-height: 1.25; color: var(--text); }
.head .meta { margin: 12px 0 0; color: var(--text-3); font-size: 13.5px; }
.head .bar { height: 3px; margin-top: 16px; border-radius: 999px; background: var(--track); overflow: hidden; }
.head .bar i { display: block; height: 100%; background: var(--accent); }

.stale-note { margin: 0 0 8px; color: var(--text-3); font-size: 13px; }

.block { margin-top: 40px; }
.block h2 { display: flex; align-items: baseline; gap: 10px; margin: 0 0 14px; font-size: 18px; font-weight: 600; color: var(--text); }
.block h2 .sub { font-size: 13px; font-weight: 400; color: var(--text-3); }

.todo { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--divider); }
.todo li { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 15px 0; border-bottom: 1px solid var(--divider); }
.task-name { font-size: 14.5px; color: var(--text-2); line-height: 1.6; }
.text-action { flex: none; border: 0; background: transparent; color: var(--text); font-size: 13.5px; cursor: pointer; padding: 0; text-decoration: none; }
.text-action:hover { color: var(--accent-strong); }
.done { flex: none; color: var(--text-3); font-size: 13px; }

.stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.stats div { display: grid; gap: 6px; }
.stats span { color: var(--text-3); font-size: 12.5px; }
.stats strong { font-size: 24px; font-weight: 600; color: var(--text); font-variant-numeric: tabular-nums; }

.inline-stats { display: flex; flex-wrap: wrap; gap: 8px 18px; margin-top: 16px; color: var(--text-2); font-size: 13px; }
.vision { margin-top: 14px; }
.tips { margin: 10px 0 0; padding-left: 18px; color: var(--text-2); font-size: 13px; line-height: 1.8; display: grid; gap: 2px; }
.summary-text { margin: 20px 0 0; color: var(--text-2); font-size: 14px; line-height: 1.9; }
.report-link { display: inline-block; margin-top: 10px; color: var(--text-3); font-size: 13px; }
.report-link:hover { color: var(--accent-strong); }

.rounds { margin-top: 26px; display: grid; gap: 22px; }
.round { padding-top: 20px; border-top: 1px solid var(--divider); }
.round .q { margin: 0; color: var(--text-3); font-size: 12.5px; }
.round .a { margin: 6px 0 0; color: var(--text); font-size: 14.5px; line-height: 1.75; }
.round .note { margin-top: 10px; padding: 12px 14px; border-radius: 10px; background: var(--bg-2); display: grid; gap: 4px; }
.round .note p { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.7; }
.round .note .fix { color: var(--accent-strong); }
.round .note .ref { color: var(--text-3); }
.muted { color: var(--text-3); font-size: 12.5px; margin: 8px 0 0; }

.course-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 0; border-top: 1px solid var(--divider); border-bottom: 1px solid var(--divider); }
.course-copy { display: grid; gap: 4px; min-width: 0; }
.course-copy strong { font-size: 15px; color: var(--text); }
.course-copy span { font-size: 12.5px; color: var(--text-3); }
@media (max-width: 640px) { .stats { grid-template-columns: 1fr 1fr; } }
</style>
