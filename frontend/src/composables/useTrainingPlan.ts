import { readonly, shallowRef } from 'vue'

import { api, errorMessage } from '@/lib/api'
import type { ApiEnvelope, TrainingPlan } from '@/lib/types'

export function useTrainingPlan(planId: string) {
  const plan = shallowRef<TrainingPlan | null>(null)
  const loading = shallowRef(false)
  const submitting = shallowRef(false)
  const error = shallowRef('')

  async function load(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const response = await api.get<ApiEnvelope<TrainingPlan>>(`/training-plans/${planId}`)
      plan.value = response.data.data
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loading.value = false
    }
  }

  async function complete(taskKey: string, evidence?: string): Promise<void> {
    submitting.value = true
    error.value = ''
    try {
      const response = await api.post<ApiEnvelope<TrainingPlan>>(
        `/training-plans/${planId}/tasks/${taskKey}/complete`,
        { evidence: evidence || null },
      )
      plan.value = response.data.data
    } catch (reason) {
      error.value = errorMessage(reason)
      throw reason
    } finally {
      submitting.value = false
    }
  }

  return {
    plan: readonly(plan),
    loading: readonly(loading),
    submitting: readonly(submitting),
    error: readonly(error),
    load,
    complete,
  }
}
