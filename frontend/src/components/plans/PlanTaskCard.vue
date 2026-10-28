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
    return { name: 'legacy-lesson', query: { ...query, courseId: props.task.courseId ?? undefined } }
  }
  if (props.task.actionType === 'TRAINING' || props.task.actionType === 'RETEST') {
    return { name: 'scenes', query: { ...query, sceneId: props.task.sceneId ?? undefined } }
  }
  return null
})

function submitRewrite(): void {
  emit('complete', props.task.key, rewrite.value)
}
</script>

<template>
  <article class="task-card" :class="{ completed: task.completed }">
    <div class="day">{{ stepNumber }}</div>
    <div class="task-body">
      <div class="task-heading">
        <h2>{{ task.task }}</h2>
        <span class="state">{{ task.completed ? '已完成' : locked ? '等待前一项' : '待完成' }}</span>
      </div>
      <p v-if="task.completedAt" class="meta">完成时间：{{ new Date(task.completedAt).toLocaleString('zh-CN') }}</p>
      <div v-if="task.actionType === 'COURSE' && task.lesson" class="course-status">
        <span>{{ task.lesson.title }}</span>
        <strong>{{ task.learningProgress }}%</strong>
        <div class="course-meter" role="progressbar" :aria-valuenow="task.learningProgress" aria-valuemin="0" aria-valuemax="100"><i :style="{ width: `${task.learningProgress}%` }" /></div>
      </div>

      <p v-if="locked && !task.completed" class="meta">请先完成计划中的前一项任务。</p>
      <template v-else-if="!task.completed">
        <div v-if="task.actionType === 'REWRITE'" class="rewrite-area">
          <RouterLink
            v-if="task.sourceSessionId"
            class="report-link"
            :to="`/report/${task.sourceSessionId}`"
          >先查看原评分建议 →</RouterLink>
          <textarea
            v-model="rewrite"
            class="field"
            rows="5"
            maxlength="2000"
            placeholder="把改写后的完整表达写在这里，至少 10 个字"
          />
          <button class="button signal" type="button" :disabled="submitting" @click="submitRewrite">
            {{ submitting ? '提交中…' : actionLabel }}
          </button>
          <p v-if="task.rewriteFeedback" class="review" :class="{ pending: task.rewriteDegraded }">
            {{ task.rewriteDegraded ? '待评价：' : task.rewritePassed ? '改写通过：' : '还需改进：' }}{{ task.rewriteFeedback }}
          </p>
        </div>
        <RouterLink v-else-if="actionRoute" class="button signal" :to="actionRoute">
          {{ actionLabel }}
        </RouterLink>
      </template>
      <template v-else-if="task.evidence">
        <RouterLink v-if="task.actionType === 'TRAINING' || task.actionType === 'RETEST'" class="report-link" :to="`/report/${task.evidence}`">查看本次评分报告 →</RouterLink>
        <p v-else class="evidence">完成记录：{{ task.evidence }}</p>
        <p v-if="task.rewriteFeedback" class="review">改写反馈：{{ task.rewriteFeedback }}</p>
      </template>
    </div>
  </article>
</template>

<style scoped>
.task-card { display: grid; grid-template-columns: 70px 1fr; gap: 20px; padding: 24px; border: 1px solid var(--line); border-radius:var(--radius); background:var(--card); }
.task-card.completed { background: #f5faf8; }
.day { display: grid; place-items: center; width: 64px; height: 64px; border-radius: 50%; background: var(--sky); color: var(--mint-dark); font: 700 20px/1 var(--font-ui); }
.task-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.task-heading h2 { margin: 3px 0 16px; font-size: 19px; line-height: 1.55; }
.state { flex: none; padding: 5px 9px; border-radius: 999px; background: var(--overlay-2); color: var(--ink-soft); font-size: 12px; }
.completed .state { background: var(--sky); color: var(--mint-dark); }
.meta, .evidence { margin: 0 0 16px; color: var(--ink-soft); font-size: 13px; line-height: 1.7; }
.rewrite-area { display: grid; justify-items: start; gap: 12px; }
.rewrite-area .field { resize: vertical; }
.report-link { color: var(--mint-dark); font-size: 13px; font-weight: 700; }
.review { margin: 0; padding: 10px 12px; border-radius:var(--radius-sm); background: var(--sky); color: var(--mint-dark); font-size: 13px; line-height: 1.7; }
.review.pending { background: rgba(194,168,119,.14); color: var(--warning); }
.course-status { display: grid; grid-template-columns: 1fr auto; gap: 8px; margin: 0 0 16px; color: var(--ink-soft); font-size: 13px; }
.course-status strong { color: var(--mint-dark); }
.course-meter { grid-column: 1 / -1; height: 6px; overflow: hidden; border-radius: 99px; background: var(--track); }
.course-meter i { display: block; height: 100%; background: var(--mint); }
@media (max-width: 600px) { .task-card { grid-template-columns: 1fr; } .day { width: 52px; height: 52px; } }
.task-card,.task-card.completed { border-color:var(--border);background:var(--glass);box-shadow:var(--shadow); }
.day { border:1px solid var(--border);background:var(--bg-2);color:var(--text-2); }
.state { background:var(--overlay-2); }
.completed .state,.review { background:var(--bg-2);color:var(--text-2); }
.review.pending { background:var(--bg-2);color:var(--text-2); }
.report-link,.course-status strong { color:var(--text-2); }
.course-meter { background:var(--track); }
.course-meter i { background:var(--muted-progress);box-shadow:none; }
</style>
