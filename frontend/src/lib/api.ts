import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

import type { ApiEnvelope, User } from './types'

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
let accessToken = ''
let refreshPromise: Promise<string> | null = null

export const api = axios.create({ baseURL, withCredentials: true, timeout: 30_000 })
export const MODEL_REQUEST_TIMEOUT_MS = 75_000

export function setAccessToken(token: string): void {
  accessToken = token
}

export function authorizedFetch(path: string, init: RequestInit): Promise<Response> {
  return fetch(`${baseURL}${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...init.headers,
    },
  })
}

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    if (error.response?.status !== 401 || !config || config._retried || config.url?.includes('/auth/refresh')) {
      throw error
    }
    config._retried = true
    refreshPromise ??= refreshToken().finally(() => { refreshPromise = null })
    config.headers.Authorization = `Bearer ${await refreshPromise}`
    return api(config)
  },
)

async function refreshToken(): Promise<string> {
  const response = await axios.post<ApiEnvelope<{ accessToken: string; user: User }>>(
    `${baseURL}/auth/refresh`,
    {},
    { withCredentials: true },
  )
  setAccessToken(response.data.data.accessToken)
  return response.data.data.accessToken
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail
    if (detail) return detail
    if (error.code === 'ECONNABORTED') return '大模型处理超时，操作可能已完成。请稍后刷新页面查看结果。'
    if (!error.response) return '无法连接服务，请确认后端已经启动。'
  }
  return '操作没有完成，请稍后重试。'
}

