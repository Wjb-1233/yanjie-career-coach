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
  config.withCredentials = true
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    const isAuthPath = /\/auth\/(login|register|demo-login|refresh|logout|password)/.test(config?.url ?? '')
    if (error.response?.status !== 401 || !config || config._retried || isAuthPath) {
      throw error
    }
    config._retried = true
    refreshPromise ??= refreshToken().finally(() => { refreshPromise = null })
    try {
      config.headers.Authorization = `Bearer ${await refreshPromise}`
    } catch {
      // 刷新令牌缺失或已过期：清理本地登录态，交给路由跳回登录页
      setAccessToken('')
      if (typeof window !== 'undefined') window.dispatchEvent(new Event('auth:expired'))
      throw new Error('登录状态已过期，请重新登录')
    }
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

const FIELD_HINTS: Record<string, string> = {
  email: '邮箱格式不正确，例如 name@example.com',
  password: '密码至少 8 位',
  display_name: '请输入称呼',
  displayName: '请输入称呼',
  current_password: '请输入当前密码',
  new_password: '新密码至少 8 位，且包含字母和数字',
  jd_text: '岗位描述至少 20 字',
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as { detail?: string; errors?: Array<{ field?: string; message?: string }> } | undefined
    const firstField = data?.errors?.find((item) => item.field)?.field
    if (firstField && FIELD_HINTS[firstField]) return FIELD_HINTS[firstField]
    const detail = data?.detail
    if (detail && detail !== 'Not Found' && detail !== 'Method Not Allowed') return detail
    if (error.response?.status === 404) return '服务暂不可用，可能是后端版本较旧，请重启后端后重试'
    if (error.response?.status === 405) return '服务暂不可用，请重启后端后重试'
    if (error.code === 'ECONNABORTED') return '大模型处理超时，操作可能已完成。请稍后刷新页面查看结果。'
    if (!error.response) return '无法连接服务，请确认后端已经启动。'
  }
  if (error instanceof Error && error.message) return error.message
  return '操作没有完成，请稍后重试。'
}

