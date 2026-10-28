import { readonly, shallowRef } from 'vue'

import { api, setAccessToken } from '@/lib/api'
import type { ApiEnvelope, User } from '@/lib/types'

type AuthResult = { accessToken: string; user: User }

const user = shallowRef<User | null>(null)
const initialized = shallowRef(false)
const loading = shallowRef(false)

export function useAuth() {
  function applyAuthResult(result: AuthResult): void {
    setAccessToken(result.accessToken)
    user.value = result.user
    initialized.value = true
  }

  async function login(email: string, password: string): Promise<void> {
    loading.value = true
    try {
      const response = await api.post<ApiEnvelope<AuthResult>>('/auth/login', { email, password })
      applyAuthResult(response.data.data)
    } finally {
      loading.value = false
    }
  }

  async function demoLogin(role: 'STUDENT' | 'ADMIN'): Promise<void> {
    loading.value = true
    try {
      const response = await api.post<ApiEnvelope<AuthResult>>('/auth/demo-login', { role })
      applyAuthResult(response.data.data)
    } finally {
      loading.value = false
    }
  }

  async function register(email: string, password: string, displayName: string): Promise<void> {
    loading.value = true
    try {
      const response = await api.post<ApiEnvelope<AuthResult>>('/auth/register', {
        email,
        password,
        displayName,
      })
      applyAuthResult(response.data.data)
    } finally {
      loading.value = false
    }
  }

  async function restore(): Promise<void> {
    if (initialized.value) return
    try {
      const refreshed = await api.post<ApiEnvelope<{ accessToken: string; user: User }>>('/auth/refresh')
      setAccessToken(refreshed.data.data.accessToken)
      user.value = refreshed.data.data.user
    } catch {
      user.value = null
      setAccessToken('')
    } finally {
      initialized.value = true
    }
  }

  async function logout(): Promise<void> {
    try {
      await api.post('/auth/logout')
    } finally {
      setAccessToken('')
      user.value = null
    }
  }

  async function updateProfile(displayName: string, bio: string | null): Promise<void> {
    const response = await api.patch<ApiEnvelope<User>>('/auth/me', { displayName, bio })
    user.value = response.data.data
  }

  return {
    user: readonly(user),
    initialized: readonly(initialized),
    loading: readonly(loading),
    login,
    demoLogin,
    register,
    restore,
    logout,
    updateProfile,
  }
}

