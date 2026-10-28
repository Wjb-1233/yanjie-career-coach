import { readonly, shallowRef } from 'vue'

import { api, errorMessage, MODEL_REQUEST_TIMEOUT_MS } from '@/lib/api'
import type { ApiEnvelope, Evaluation, TrainingMessage, TrainingSession } from '@/lib/types'

export function useTrainingSession(sessionId: string) {
  const session = shallowRef<TrainingSession | null>(null)
  const sending = shallowRef(false)
  const error = shallowRef('')
  const liveFlags = shallowRef<string[]>([])
  const degraded = shallowRef(false)

  async function load(): Promise<void> {
    const response = await api.get<ApiEnvelope<TrainingSession>>(`/training-sessions/${sessionId}`)
    session.value = response.data.data
  }

  async function send(content: string, finishAfterReply = false): Promise<void> {
    if (!session.value || sending.value) return
    error.value = ''
    liveFlags.value = []
    degraded.value = false
    sending.value = true
    const roundNo = session.value.currentRound + 1
    const userMessage: TrainingMessage = {
      id: `local-user-${Date.now()}`,
      roundNo,
      speaker: 'USER',
      content,
      flagged: false,
      flags: [],
      createdAt: new Date().toISOString(),
    }
    const aiMessage: TrainingMessage = {
      id: `local-ai-${Date.now()}`,
      roundNo,
      speaker: 'AI',
      content: '',
      flagged: false,
      flags: [],
      createdAt: new Date().toISOString(),
    }
    session.value = { ...session.value, messages: [...session.value.messages, userMessage, aiMessage] }
    try {
      const response = await api.post<ApiEnvelope<{
        roundNo: number; stage: string; flags: string[]; messageId: string
        content: string; finished: boolean; degraded: boolean
      }>>(`/training-sessions/${sessionId}/messages/complete`, { content, finishAfterReply }, { timeout: MODEL_REQUEST_TIMEOUT_MS })
      const turn = response.data.data
      liveFlags.value = turn.flags
      degraded.value = turn.degraded
      if (session.value) session.value = {
        ...session.value,
        currentRound: turn.roundNo,
        stage: turn.stage,
        status: turn.finished ? 'FINISHED' : session.value.status,
        messages: session.value.messages.map((message) => {
          if (message.id === userMessage.id) return { ...message, roundNo: turn.roundNo, flagged: turn.flags.length > 0, flags: turn.flags }
          if (message.id === aiMessage.id) return { ...message, id: turn.messageId, roundNo: turn.roundNo, content: turn.content }
          return message
        }),
      }
    } catch (reason) {
      error.value = errorMessage(reason)
      try { await load() } catch { /* Preserve the visible draft if reconnection also fails. */ }
    } finally {
      sending.value = false
    }
  }

  async function finish(createPlan = true): Promise<Evaluation> {
    const response = await api.post<ApiEnvelope<Evaluation>>(
      `/training-sessions/${sessionId}/finish`,
      null,
      { params: { create_plan: createPlan }, timeout: MODEL_REQUEST_TIMEOUT_MS },
    )
    if (session.value) session.value = { ...session.value, status: 'FINISHED' }
    return response.data.data
  }

  async function restart(): Promise<string> {
    const response = await api.post<ApiEnvelope<TrainingSession>>(`/training-sessions/${sessionId}/restart`, null)
    return response.data.data.id
  }

  return { session: readonly(session), sending: readonly(sending), error: readonly(error), liveFlags: readonly(liveFlags), degraded: readonly(degraded), load, send, finish, restart }
}

