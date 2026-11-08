import type { TrainingPlanTask } from './types'

export function taskActionLabel(task: TrainingPlanTask): string {
  if (task.actionType === 'COURSE') {
    return task.learningProgress > 0 ? '继续学习微课' : '学习微课（3 个步骤）'
  }
  if (task.actionType === 'VOICE') return '用语音重答这一题'
  if (task.actionType === 'REPORT') return '回看本场复盘'
  if (task.actionType === 'TRAINING') return '进入专项场景对练'
  if (task.actionType === 'REWRITE') return '提交逐轮改写'
  return '旧题重写（复测）'
}

export function taskRoute(planId: string, task: TrainingPlanTask) {
  const query = { planId, taskKey: task.key }
  if (task.actionType === 'COURSE') {
    return { name: 'plan-lesson', query: { ...query, courseId: task.courseId ?? undefined } }
  }
  if (task.actionType === 'SCENE') {
    return { name: 'scenes', query: { ...query, sceneId: task.sceneId ?? undefined } }
  }
  if (task.actionType === 'VIDEO') {
    return { name: 'video', query: { ...query, sceneId: task.sceneId ?? undefined } }
  }
  if (task.actionType === 'VOICE') {
    return { name: 'voice', query: { ...query, sceneId: task.sceneId ?? undefined } }
  }
  if (task.actionType === 'REPORT' && task.sourceSessionId) {
    return { name: 'report', params: { id: task.sourceSessionId } }
  }
  if (task.actionType === 'REVIEW') {
    return { name: 'scripts' }
  }
  if (task.actionType === 'TRAINING' || task.actionType === 'RETEST') {
    return { name: 'scenes', query: { ...query, sceneId: task.sceneId ?? undefined } }
  }
  return null
}

export function stepTitle(task: TrainingPlanTask): string {
  if (task.actionType === 'COURSE') return '专项练习 · 学习微课'
  if (task.actionType === 'SCENE') return '能力匹配 · 场景复练'
  if (task.actionType === 'VIDEO') return '本场之后 · 视频重答'
  if (task.actionType === 'VOICE') return '本场之后 · 语音重答'
  if (task.actionType === 'REPORT') return '本场之后 · 回看复盘'
  if (task.actionType === 'REWRITE') return '本场之后 · 话术改写'
  if (task.actionType === 'REVIEW') return '间隔复习 · 到期错题'
  if (task.actionType === 'TRAINING') return '专项练习 · 场景对练'
  return '旧题重写 · 复测对比'
}
