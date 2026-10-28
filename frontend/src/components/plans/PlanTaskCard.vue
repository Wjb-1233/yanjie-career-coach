<script setup lang="ts">
import { computed, shallowRef } from 'vue'

import type { TrainingPlanTask } from '@/lib/types'

const props = defineProps<{
  planId: string
  task: TrainingPlanTask
  submitting: boolean
  locked: boolean
  stepNumber: number
}>()
const emit = defineEmits<{ complete: [taskKey: string, evidence?: string] }>()

const rewrite = shallowRef(props.task.evidence ?? '')
const actionLabel = computed(() => ({
  COURSE: '去学习微课',
  TRAINING: '开始强化训练',
  REWRITE: '提交改写',
  RETEST: '开始复测',
}[props.task.actionType]))
const actionRoute = computed(() => {
  const query = { planId: props.planId, taskKey: props.task.key }
  if (props.task.actionType === 'COURSE') {
    return { name: 'plan-lesson', query: { ...query, courseId: props.task.courseId ?? undefined } }
  }
  if (props.task.actionType === 'TRAINING' || props.task.actionType === 'RETEST') {
    return { name: 'scenes', query: { ...query, sceneId: props.task.sceneId ?? undefined } }
  }
  return null
})
const stateLabel = computed(() => props.task.completed ? '已完成' : props.locked ? '等待前一项' : '待完成')

function submitRewrite(): void {
  emit('complete', props.task.key, rewrite.value)
}
</script>

<template>
  <article class="task-row" :class="{ completed: task.completed, locked }">
    <div class="step num">{{ String(stepNumber).padStart(2, '0') }}</div>

    <div class="body">
      <header class="head">
        <h2>{{ task.task }}</h2>
        <span class="state">{{ stateLabel }}</span>
      </header>

      <p v-if="task.completedAt" class="meta">完成于 {{ new Date(task.completedAt).toLocaleString('zh-CN') }}</p>

      <div v-if="task.actionType === 'COURSE' && task.lesson" class="course">
        <div class="course-line">
          <span>{{ task.lesson.title }}</span>
          <span class="num">{{ task.learningProgress }}%</span>
        </div>
        <i class="bar"><b :style="{ width: `${task.learningProgress}%` }" /></i>
      </div>

      <p v-if="locked && !task.completed" class="hint">请先完成前一项任务。</p>

      <template v-else-if="!task.completed">
        <div v-if="task.actionType === 'REWRITE'" class="rewrite">
          <RouterLink v-if="task.sourceSessionId" class="text-link" :to="`/report/${task.sourceSessionId}`">先看原评分建议 →</RouterLink>
          <textarea
            v-model="rewrite"
            class="field"
            rows="4"
            maxlength="2000"
            placeholder="写下改写后的完整表达，至少 10 个字"
          />
          <button class="button action" type="button" :disabled="submitting" @click="submitRewrite">
            {{ submitting ? '提交中…' : actionLabel }}
          </button>
          <p v-if="task.rewriteFeedback" class="feedback" :class="{ pending: task.rewriteDegraded }">
            {{ task.rewriteDegraded ? '待评价：' : task.rewritePassed ? '改写通过：' : '还需改进：' }}{{ task.rewriteFeedback }}
          </p>
        </div>
        <RouterLink v-else-if="actionRoute" class="button action" :to="actionRoute">{{ actionLabel }}</RouterLink>
      </template>

      <template v-else>
        <RouterLink v-if="task.actionType === 'TRAINING' || task.actionType === 'RETEST'" class="text-link" :to="`/report/${task.evidence}`">查看本次评分报告 →</RouterLink>
        <p v-else-if="task.evidence" class="meta">完成记录：{{ task.evidence }}</p>
        <p v-if="task.rewriteFeedback" class="feedback">改写反馈：{{ task.rewriteFeedback }}</p>
      </template>
    </div>
  </article>
</template>

<style scoped>
.task-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 18px;
  padding: 20px 2px;
  border-bottom: 1px solid var(--divider);
}
.step { padding-top: 3px; color: var(--text-3); font-family: var(--font-num); font-size: 11px; letter-spacing: .08em; }
.body { min-width: 0; }

.head { display: flex; align-items: baseline; justify-content: space-between; gap: 18px; }
.head h2 { margin: 0; color: var(--text); font-size: 15px; font-weight: 500; line-height: 1.75; letter-spacing: .01em; }
.state { flex: none; color: var(--text-3); font-size: 11px; letter-spacing: .08em; }
.completed .state { color: var(--text-2); }
.locked .head h2 { color: var(--text-2); }

.meta { margin: 8px 0 0; color: var(--text-3); font-size: 12px; line-height: 1.7; }
.hint { margin: 8px 0 0; color: var(--text-3); font-size: 12px; }
.text-link { display: inline-block; margin-top: 12px; color: var(--text-2); font-size: 12px; letter-spacing: .04em; border-bottom: 1px solid var(--border-bright); padding-bottom: 1px; transition: color var(--ease), border-color var(--ease); }
.text-link:hover { color: var(--accent-strong); border-color: var(--accent); }

.course { margin-top: 12px; }
.course-line { display: flex; justify-content: space-between; gap: 16px; color: var(--text-3); font-size: 12px; }
.course-line .num { color: var(--text-2); }
.bar { display: block; height: 2px; margin-top: 8px; background: var(--track); }
.bar b { display: block; height: 100%; background: var(--accent); }

.action { margin-top: 14px; min-height: 34px; padding: 0 16px; font-size: 12px; }
.rewrite { display: grid; gap: 10px; margin-top: 12px; }
.rewrite .field { resize: vertical; }
.feedback { margin: 12px 0 0; color: var(--text-2); font-size: 12px; line-height: 1.8; }
.feedback.pending { color: var(--warning); }

@media (max-width: 600px) {
  .task-row { grid-template-columns: 1fr; gap: 6px; }
  .head { flex-direction: column; gap: 4px; }
}
</style>
