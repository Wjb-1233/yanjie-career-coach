import type { TrainingPlanTask } from './types'

export function taskActionLabel(task: TrainingPlanTask): string {
  if (task.actionType === 'COURSE') {
    return task.learningProgress > 0 ? '继续学习微课' : '学习微课（3 个步骤）'
  }
  if (task.actionType === 'TRAINING') return '进入专项场景对练'
  if (task.actionType === 'REWRITE') return '提交逐轮改写'
  return '旧题重写（复测）'
}

export function taskRoute(planId: string, task: TrainingPlanTask) {
  const query = { planId, taskKey: task.key }
  if (task.actionType === 'COURSE') {
    return { name: 'plan-lesson', query: { ...query, courseId: task.courseId ?? undefined } }
  }
  if (task.actionType === 'TRAINING' || task.actionType === 'RETEST') {
    return { name: 'scenes', query: { ...query, sceneId: task.sceneId ?? undefined } }
  }
  return null
}

export function stepTitle(task: TrainingPlanTask): string {
  if (task.actionType === 'COURSE') return '专项练习 · 学习微课'
  if (task.actionType === 'TRAINING') return '专项练习 · 场景对练'
  if (task.actionType === 'REWRITE') return '逐轮修改 · 改写薄弱回答'
  return '旧题重写 · 复测对比'
}
