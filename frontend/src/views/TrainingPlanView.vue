<script setup lang="ts">
import { computed, onMounted, shallowRef, watch } from 'vue'
import { useRoute } from 'vue-router'

import PlanComparison from '@/components/plans/PlanComparison.vue'
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
const nextTask = computed<TrainingPlanTask | null>(() =>
  currentIndex.value >= 0 ? plan.value?.tasks[currentIndex.value] ?? null : null)
const nextRoute = computed(() => (plan.value && nextTask.value ? taskRoute(plan.value.id, nextTask.value) : null))

const labels: Record<keyof Scores, string> = { logic: '逻辑性', appropriateness: '得体性', impact: '感染力', relevance: '针对性', concision: '简洁度' }
const baseline = shallowRef<Evaluation | null>(null)
const reviewSession = shallowRef<TrainingSession | null>(null)
const baselineSessionId = computed(() => plan.value?.tasks.find((task) => task.sourceSessionId)?.sourceSessionId ?? '')
const focusKey = computed(() => (Object.entries(labels) as Array<[keyof Scores, string]>)
  .find(([, label]) => label === plan.value?.focusDimension)?.[0])
const focusScore = computed(() => (focusKey.value && baseline.value ? baseline.value.scores[focusKey.value] : 0))

interface Round { roundNo: number; question: string; answer: string; flags: readonly string[] }
const rounds = computed<Round[]>(() => {
  const messages = reviewSession.value?.messages ?? []
  const result: Round[] = []
  let question = ''
  for (const message of messages) {
    if (message.speaker === 'AI') question = message.content
    else if (message.speaker === 'USER') result.push({ roundNo: message.roundNo, question, answer: message.content, flags: message.flags })
  }
  return result
})

const rewriteTask = computed(() => plan.value?.tasks.find((task) => task.actionType === 'REWRITE') ?? null)
const courseTask = computed(() => plan.value?.tasks.find((task) => task.actionType === 'COURSE') ?? null)
const practiceTask = computed(() => plan.value?.tasks.find((task) => task.actionType === 'TRAINING') ?? null)
const retestTask = computed(() => plan.value?.tasks.find((task) => task.actionType === 'RETEST') ?? null)

const rewriteText = shallowRef('')
const rewriteError = shallowRef('')

onMounted(trainingPlan.load)

watch(baselineSessionId, async (sessionId) => {
  if (!sessionId) return
  try {
    baseline.value = (await api.get<ApiEnvelope<Evaluation>>(`/evaluations/${sessionId}`)).data.data
    reviewSession.value = (await api.get<ApiEnvelope<TrainingSession>>(`/training-sessions/${sessionId}`)).data.data
  } catch {
    // 复盘是补充信息，取不到不影响任务执行
  }
}, { immediate: true })

function annotation(roundNo: number) {
  return baseline.value?.suggestions.find((item) => item.roundNo === roundNo) ?? null
}

function stateOf(task: TrainingPlanTask | null): string {
  if (!task) return ''
  return task.completed ? '已完成' : '待完成'
}

function routeFor(task: TrainingPlanTask | null) {
  return plan.value && task ? taskRoute(plan.value.id, task) : null
}

async function submitRewrite(): Promise<void> {
  const text = rewriteText.value.trim()
  if (text.length < 10) { rewriteError.value = '至少写 10 个字'; return }
  rewriteError.value = ''
  try {
    await trainingPlan.complete('rewrite', text)
    rewriteText.value = ''
  } catch (reason) {
    rewriteError.value = errorMessage(reason)
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
          <strong>第 {{ currentIndex + 1 }} 步 · {{ nextTask.actionType === 'REWRITE' ? '看复盘并改写你的回答' : nextTask.actionType === 'COURSE' ? '学习微课' : nextTask.actionType === 'TRAINING' ? '进入专项场景对练' : '旧题重写 · 复测' }}</strong>
        </span>
        <RouterLink v-if="nextRoute" class="button" :to="nextRoute">去完成 →</RouterLink>
        <a v-else class="button" href="#step-rewrite">向下看复盘 ↓</a>
      </div>

      <ol class="steps">
        <!-- 01 复盘与改写 -->
        <li id="step-rewrite" class="step" :class="{ done: rewriteTask?.completed, current: currentIndex === 0 }">
          <header class="step-head">
            <span class="step-no num">01</span>
            <div class="step-title">
              <h2>复盘 · 逐轮批注</h2>
              <p>看清这 {{ rounds.length }} 轮里哪几轮问题最大，再写下你的改写</p>
            </div>
            <span class="state">{{ stateOf(rewriteTask) }}</span>
          </header>

          <div v-if="baseline">
            <dl class="stats">
              <div><dt>综合分</dt><dd class="num">{{ baseline.overallScore }}</dd></div>
              <div><dt>最低项</dt><dd>{{ plan.focusDimension }}</dd></div>
              <div><dt>该维度得分</dt><dd class="num">{{ focusScore }} / 5</dd></div>
            </dl>
            <p class="judgement">{{ baseline.summary }}</p>
            <RouterLink class="report-link" :to="`/report/${baselineSessionId}`">查看完整评分报告 →</RouterLink>
          </div>

          <div v-if="rounds.length" class="rounds">
            <p class="rounds-head">共 {{ rounds.length }} 轮对话 · 有批注的轮次已展开</p>
            <details
              v-for="round in rounds"
              :key="round.roundNo"
              class="round"
              :class="{ flagged: annotation(round.roundNo) || round.flags.length }"
              :open="Boolean(annotation(round.roundNo))"
            >
              <summary>
                <span class="round-no num">第 {{ round.roundNo }} 轮</span>
                <span class="round-q">{{ round.question || '场景开场' }}</span>
                <span v-if="annotation(round.roundNo)" class="badge">有批注</span>
                <span v-else-if="round.flags.length" class="badge warn">表达提醒</span>
              </summary>
              <div class="round-body">
                <p class="answer"><b>我的回答</b>{{ round.answer }}</p>
                <p v-if="round.flags.length" class="warn-line">表达提醒：{{ round.flags.join('、') }}</p>
                <div v-if="annotation(round.roundNo)" class="annotation">
                  <p><b>问题</b>{{ annotation(round.roundNo)?.problem }}</p>
                  <p class="an-fix"><b>建议改为</b>{{ annotation(round.roundNo)?.rewrite }}</p>
                </div>
              </div>
            </details>
          </div>

          <div v-if="!rewriteTask?.completed" class="rewrite-form">
            <label for="rewrite-input">挑 1–2 轮问题最大的，写下你改后的说法</label>
            <textarea id="rewrite-input" v-model="rewriteText" class="field" rows="5" maxlength="2000" placeholder="不用写完全部轮次，挑最想改的几轮，重写完整说法即可（至少 10 字）。" />
            <div class="form-foot">
              <span>{{ rewriteText.trim().length }} / 2000 字</span>
              <button class="button" type="button" :disabled="submitting || rewriteText.trim().length < 10" @click="submitRewrite">
                {{ submitting ? '提交中…' : '提交改写 →' }}
              </button>
            </div>
            <p v-if="rewriteError" class="form-error">{{ rewriteError }}</p>
          </div>
          <p v-else class="done-note">已完成改写：{{ rewriteTask.evidence }}</p>
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
            <RouterLink v-if="!courseTask.completed && routeFor(courseTask)" class="button" :to="routeFor(courseTask) ?? '/plans'">
              {{ courseTask.learningProgress > 0 ? '继续学习微课 →' : '开始学习微课 →' }}
            </RouterLink>
            <p v-else-if="courseTask.completed" class="done-note">微课与练习已完成</p>
          </div>
        </li>

        <!-- 03 专项对练 -->
        <li v-if="practiceTask" class="step" :class="{ done: practiceTask.completed, current: currentIndex === 2 }">
          <header class="step-head">
            <span class="step-no num">03</span>
            <div class="step-title">
              <h2>专项场景对练</h2>
              <p>{{ practiceTask.task }}</p>
            </div>
            <span class="state">{{ stateOf(practiceTask) }}</span>
          </header>
          <div class="step-body">
            <RouterLink v-if="!practiceTask.completed && routeFor(practiceTask)" class="button" :to="routeFor(practiceTask) ?? '/scenes'">进入专项场景对练 →</RouterLink>
            <RouterLink v-else-if="practiceTask.completed && practiceTask.evidence" class="text-link" :to="`/report/${practiceTask.evidence}`">查看这次训练的评分报告 →</RouterLink>
          </div>
        </li>

        <!-- 04 旧题重写 -->
        <li v-if="retestTask" class="step" :class="{ done: retestTask.completed, current: currentIndex === 3 }">
          <header class="step-head">
            <span class="step-no num">04</span>
            <div class="step-title">
              <h2>旧题重写 · 复测</h2>
              <p>{{ retestTask.task }}</p>
            </div>
            <span class="state">{{ stateOf(retestTask) }}</span>
          </header>
          <div class="step-body">
            <RouterLink v-if="!retestTask.completed && routeFor(retestTask)" class="button" :to="routeFor(retestTask) ?? '/scenes'">开始复测 →</RouterLink>
            <RouterLink v-else-if="retestTask.completed && retestTask.evidence" class="text-link" :to="`/report/${retestTask.evidence}`">查看复测评分报告 →</RouterLink>
          </div>
        </li>
      </ol>

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

.next-action {
  position: sticky;
  top: 70px;
  z-index: 6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-top: 18px;
  padding: 14px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--card);
}
.next-copy { display: flex; align-items: baseline; gap: 12px; min-width: 0; }
.next-copy .k { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.next-copy strong { color: var(--text); font-size: 14px; font-weight: 500; }

.steps { margin: 34px 0 0; padding: 0; list-style: none; }
.step { padding: 24px 0 28px; border-bottom: 1px solid var(--divider); }
.step-head { display: flex; align-items: baseline; gap: 16px; }
.step-no { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.step-title { flex: 1; min-width: 0; }
.step-title h2 { margin: 0; color: var(--text); font-size: 17px; font-weight: 500; line-height: 1.5; }
.step-title p { margin: 6px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.7; }
.step.done .step-no, .step.done .step-title h2 { color: var(--text-3); }
.state { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.step-body { padding-left: 32px; margin-top: 16px; }

.stats { display: flex; gap: 40px; margin: 18px 0 0 32px; }
.stats dt { color: var(--text-3); font-size: 11px; letter-spacing: .14em; }
.stats dd { margin: 8px 0 0; color: var(--text); font-size: 20px; font-weight: 400; }
.stats dd.num { font-family: var(--font-num); }
.judgement { max-width: 72ch; margin: 16px 0 0 32px; color: var(--text-2); font-size: 13px; line-height: 1.95; }
.report-link { display: inline-block; margin: 10px 0 0 32px; color: var(--text-2); font-size: 12px; border-bottom: 1px solid var(--border-bright); padding-bottom: 1px; }
.report-link:hover { color: var(--accent-strong); border-color: var(--accent); }

.rounds { margin-top: 22px; padding-left: 32px; }
.rounds-head { margin: 0 0 8px; color: var(--text-3); font-size: 11px; letter-spacing: .1em; }
.round { border-bottom: 1px solid var(--divider); }
.round summary { display: flex; align-items: baseline; gap: 14px; padding: 12px 2px; cursor: pointer; list-style: none; }
.round summary::-webkit-details-marker { display: none; }
.round-no { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .06em; }
.round-q { flex: 1; min-width: 0; color: var(--text-2); font-size: 13px; line-height: 1.7; }
.round[open] .round-q { color: var(--text); }
.badge { flex: none; color: var(--accent-strong); font-size: 11px; letter-spacing: .04em; }
.badge.warn { color: var(--warning); }
.round-body { padding: 2px 2px 16px 62px; }
.answer { margin: 0; color: var(--text-2); font-size: 13px; line-height: 1.9; white-space: pre-wrap; }
.answer b { display: inline-block; margin-right: 8px; color: var(--text-3); font-weight: 400; letter-spacing: .08em; }
.warn-line { margin: 8px 0 0; color: var(--warning); font-size: 11px; }
.annotation { margin-top: 12px; padding: 12px 14px; border-left: 2px solid var(--accent); background: var(--bg-2); }
.annotation p { margin: 0; color: var(--text-2); font-size: 12px; line-height: 1.85; }
.annotation p + p { margin-top: 6px; }
.annotation b { display: inline-block; margin-right: 8px; color: var(--text-3); font-weight: 400; letter-spacing: .08em; }
.an-fix { color: var(--text); }

.rewrite-form { display: grid; gap: 10px; margin: 22px 0 0 32px; }
.rewrite-form label { color: var(--text-2); font-size: 12px; letter-spacing: .04em; }
.rewrite-form textarea { resize: vertical; }
.form-foot { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.form-foot span { color: var(--text-3); font-size: 11px; }
.form-error { margin: 0; color: var(--danger); font-size: 12px; }
.done-note { margin: 18px 0 0 32px; color: var(--text-2); font-size: 13px; line-height: 1.8; white-space: pre-wrap; }

.course-meta { display: flex; justify-content: space-between; gap: 16px; color: var(--text-3); font-size: 12px; }
.course .bar { display: block; height: 2px; margin-top: 10px; background: var(--track); }
.course .bar b { display: block; height: 100%; background: var(--accent); }
.course-steps { margin: 14px 0 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.course-steps li { display: flex; gap: 12px; color: var(--text-2); font-size: 13px; line-height: 1.6; }
.course-steps .num { color: var(--text-3); font-size: 11px; }

.text-link { display: inline-block; margin-top: 12px; color: var(--text-2); font-size: 12px; border-bottom: 1px solid var(--border-bright); padding-bottom: 1px; }
.text-link:hover { color: var(--accent-strong); border-color: var(--accent); }

@media (max-width: 640px) {
  .step-body, .stats, .judgement, .report-link, .rounds, .rewrite-form, .done-note { padding-left: 0; margin-left: 0; }
  .stats { gap: 24px; }
  .next-action { flex-direction: column; align-items: stretch; gap: 12px; }
}
</style>
