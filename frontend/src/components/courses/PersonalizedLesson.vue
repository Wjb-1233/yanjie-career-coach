<script setup lang="ts">
import { computed, shallowRef } from 'vue'

import type { TrainingPlan, TrainingPlanTask } from '@/lib/types'

const props = defineProps<{
  plan: TrainingPlan
  task: TrainingPlanTask
  submitting: boolean
}>()
const emit = defineEmits<{
  completeStep: [index: number]
  submitPractice: [answer: string]
}>()

const answer = shallowRef(props.task.practiceAnswer ?? '')
const lesson = computed(() => props.task.lesson)
const nextStep = computed(() => props.task.completedSteps.length)
const readyToPractice = computed(() => nextStep.value === lesson.value?.steps.length)
const canSubmit = computed(() => readyToPractice.value && answer.value.trim().length >= 40 && !props.submitting)
</script>

<template>
  <section v-if="lesson" class="personalized panel" aria-label="个性化沟通微课">
    <div class="lesson-header">
      <div>
        <p class="eyebrow">学习路径 · {{ plan.focusDimension }}</p>
        <h2>{{ lesson.title }}</h2>
        <p>{{ lesson.intro }}</p>
      </div>
      <span class="source-tag">{{ lesson.aiGenerated ? '基于本次评分生成' : '离线示例课程' }}</span>
    </div>
    <div class="learning-status">
      <span>学习进度 {{ task.learningProgress }}%</span>
      <span>{{ task.completed ? '课程与练习已完成' : `已完成 ${task.completedSteps.length}/3 个方法${task.practiceDegraded ? ' · 练习待评价' : ''}` }}</span>
    </div>
    <div class="learning-meter" role="progressbar" :aria-valuenow="task.learningProgress" aria-valuemin="0" aria-valuemax="100">
      <span :style="{ width: `${task.learningProgress}%` }" />
    </div>

    <div class="steps">
      <article v-for="(step, index) in lesson.steps" :key="index" class="step" :class="{ done: task.completedSteps.includes(index) }">
        <div class="step-number">0{{ index + 1 }}</div>
        <div class="step-body">
          <h3>{{ step.title }}</h3>
          <p>{{ step.explanation }}</p>
          <blockquote>{{ step.example }}</blockquote>
          <button
            v-if="!task.completedSteps.includes(index)"
            class="button step-button"
            type="button"
            :disabled="index !== nextStep || submitting"
            @click="emit('completeStep', index)"
          >{{ index === nextStep ? '我理解了，学习下一步' : '请先完成上一步' }}</button>
          <span v-else class="done-label">✓ 已学习</span>
        </div>
      </article>
    </div>

    <div class="practice">
      <p class="eyebrow">表达练习</p>
      <h3>{{ lesson.exercise }}</h3>
      <p class="hint">用自己的话作答，至少 40 字。完成三个步骤后提交；模型会给出针对性反馈。</p>
      <textarea v-model="answer" class="field" rows="5" maxlength="2000" :disabled="!readyToPractice || task.completed" placeholder="在这里写下你的回答……" />
      <p v-if="task.practiceFeedback" class="feedback" :class="{ degraded: task.practiceDegraded }">
        {{ task.practiceDegraded ? '待评价：' : task.practicePassed ? '练习反馈：' : '还需改进：' }}{{ task.practiceFeedback }}
      </p>
      <button v-if="!task.completed" class="button signal" type="button" :disabled="!canSubmit" @click="emit('submitPractice', answer.trim())">
        {{ submitting ? '正在评价…' : '提交练习并获取反馈' }}
      </button>
      <RouterLink v-else class="button signal" :to="`/plans/${plan.id}`">查看下一项训练任务 →</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.personalized { padding: clamp(22px, 4vw, 42px); }
.lesson-header { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; }
.lesson-header h2 { margin: 12px 0; font: 700 clamp(28px, 4vw, 42px)/1.2 var(--font-ui); }
.lesson-header p:last-child { max-width: 720px; line-height: 1.8; color: var(--ink-soft); }
.source-tag { flex: none; padding: 8px 12px; border-radius: 99px; background: var(--sky); color: var(--mint-dark); font-size: 12px; }
.learning-status { display: flex; justify-content: space-between; margin-top: 26px; font-size: 13px; color: var(--ink-soft); }
.learning-meter { height: 8px; margin: 10px 0 28px; border-radius: 99px; overflow: hidden; background: var(--track); }
.learning-meter span { display: block; height: 100%; background: var(--mint); transition: width .25s ease; }
.steps { display: grid; gap: 14px; }
.step { display: grid; grid-template-columns: 54px 1fr; gap: 18px; padding: 22px; border: 1px solid var(--line); border-radius:var(--radius); background:var(--card); }
.step.done { background: #f6faf8; }
.step-number { color: var(--mint-dark); font: 700 28px/1 var(--font-ui); }
.step-body h3 { margin: 0 0 10px; font-size: 20px; }
.step-body p { margin: 0 0 12px; color: var(--ink-soft); line-height: 1.7; }
.step-body blockquote { margin: 0 0 14px; padding: 12px 16px; border-left: 3px solid var(--mint); background: var(--sky); line-height: 1.7; }
.step-button { font-size: 13px; }
.done-label { color: var(--mint-dark); font-size: 13px; font-weight: 700; }
.practice { margin-top: 28px; padding: 24px; border-radius:var(--radius); background: var(--bg-2); }
.practice h3 { margin: 10px 0; font-size: 19px; line-height: 1.6; }
.hint { font-size: 13px; color: var(--ink-soft); }
.practice textarea { width: 100%; resize: vertical; margin: 10px 0 12px; }
.feedback { padding: 12px; border-radius:var(--radius-sm); color: var(--mint-dark); background: #dff4ef; line-height: 1.7; }
.feedback.degraded { color: var(--warning); background: rgba(194,168,119,.14); }
@media (max-width: 650px) { .lesson-header { flex-direction: column; } .step { grid-template-columns: 1fr; } }
.source-tag { border:1px solid var(--border);background:var(--bg-2);color:var(--text-2); }
.learning-meter { background:var(--track); }
.learning-meter span { background:var(--muted-progress);box-shadow:none; }
.step,.step.done { border-color:var(--border);background:var(--card); }
.step-number,.done-label { color:var(--text-2); }
.step-body blockquote { border-color:var(--divider);background:var(--bg-2); }
.practice { border:1px solid var(--border);background:var(--card); }
.feedback { color:var(--text-2);background:var(--bg-2); }
.feedback.degraded { color:var(--text-2);background:var(--bg-2); }
</style>
