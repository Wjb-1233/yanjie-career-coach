import { onMounted, shallowRef } from 'vue'

import { api, errorMessage, MODEL_REQUEST_TIMEOUT_MS } from '@/lib/api'
import type { AbilityAttempt, AbilityPractice, ApiEnvelope, Scores } from '@/lib/types'

interface DashboardSummary {
  latestScore: number
  dimensions: Scores
}

export function useAbilityPractice() {
  const practice = shallowRef<AbilityPractice | null>(null)
  const dashboard = shallowRef<DashboardSummary | null>(null)
  const loading = shallowRef(true)
  const sending = shallowRef(false)
  const error = shallowRef('')

  async function load(): Promise<void> {
    loading.value = true
    error.value = ''
    try {
      const [practiceResponse, dashboardResponse] = await Promise.all([
        api.get<ApiEnvelope<AbilityPractice | null>>('/ability/current'),
        api.get<ApiEnvelope<DashboardSummary>>('/dashboard'),
      ])
      practice.value = practiceResponse.data.data
      dashboard.value = dashboardResponse.data.data
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      loading.value = false
    }
  }

  async function submit(answer: string): Promise<void> {
    if (!practice.value || sending.value) return
    sending.value = true
    error.value = ''
    try {
      const response = await api.post<ApiEnvelope<AbilityAttempt>>('/ability/attempts', {
        evaluationId: practice.value.evaluationId,
        answer,
      }, { timeout: MODEL_REQUEST_TIMEOUT_MS })
      practice.value = {
        ...practice.value,
        attempts: [response.data.data, ...practice.value.attempts].slice(0, 10),
      }
    } catch (reason) {
      error.value = errorMessage(reason)
    } finally {
      sending.value = false
    }
  }

  onMounted(load)
  return { practice, dashboard, loading, sending, error, load, submit }
}
