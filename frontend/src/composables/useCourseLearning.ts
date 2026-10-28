import { computed, readonly, shallowRef } from 'vue'

import { api, errorMessage, MODEL_REQUEST_TIMEOUT_MS } from '@/lib/api'
import type { ApiEnvelope, TrainingPlan } from '@/lib/types'

export function useCourseLearning() {
  const plan = shallowRef<TrainingPlan | null>(null)
  const loading = shallowRef(true)
  const submitting = shallowRef(false)
  const error = shallowRef('')
  const courseTask = computed(() => plan.value?.tasks.find((task) => task.actionType === 'COURSE') ?? null)

  async function load(preferredPlanId = ''): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      if (preferredPlanId) {
        plan.value = (await api.get<ApiEnvelope<TrainingPlan>>(`/training-plans/${preferredPlanId}`)).data.data
      } else {
        const plans = (await api.get<ApiEnvelope<TrainingPlan[]>>('/training-plans')).data.data
        plan.value = plans.find((item) => item.status === 'ACTIVE' && item.tasks.some((task) => task.lesson))
          ?? plans.find((item) => item.tasks.some((task) => task.lesson))
          ?? null
      }
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loading.value = false
    }
  }

  async function completeStep(index: number): Promise<void> {
    if (!plan.value || !courseTask.value || submitting.value) return
    submitting.value = true
    error.value = ''
    try {
      const path = `/training-plans/${plan.value.id}/tasks/${courseTask.value.key}/steps/${index}/complete`
      plan.value = (await api.post<ApiEnvelope<TrainingPlan>>(path)).data.data
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      submitting.value = false
    }
  }

  async function submitPractice(answer: string): Promise<void> {
    if (!plan.value || !courseTask.value || submitting.value) return
    submitting.value = true
    error.value = ''
    try {
      const path = `/training-plans/${plan.value.id}/tasks/${courseTask.value.key}/practice`
      plan.value = (await api.post<ApiEnvelope<TrainingPlan>>(path, { answer }, { timeout: MODEL_REQUEST_TIMEOUT_MS })).data.data
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      submitting.value = false
    }
  }

  return {
    plan: readonly(plan), courseTask, loading: readonly(loading), submitting: readonly(submitting),
    error: readonly(error), load, completeStep, submitPractice,
  }
}
