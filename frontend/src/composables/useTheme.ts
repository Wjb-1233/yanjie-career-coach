import { readonly, shallowRef } from 'vue'

type Theme = 'dark' | 'light'
type Scope = 'STUDENT' | 'ADMIN' | null

const BASE_KEY = 'yanjie-theme'
const theme = shallowRef<Theme>((document.documentElement.dataset.theme as Theme) || 'dark')
let scope: Scope = null

function storageKey(target: Scope): string {
  return target ? `${BASE_KEY}:${target}` : BASE_KEY
}

function readSaved(target: Scope): Theme | null {
  try {
    const value = localStorage.getItem(storageKey(target))
    return value === 'dark' || value === 'light' ? value : null
  } catch {
    return null
  }
}

function systemTheme(): Theme {
  try {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

function apply(next: Theme, persist = true): void {
  theme.value = next
  document.documentElement.dataset.theme = next
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) meta.setAttribute('content', next === 'light' ? '#f5f3ee' : '#0b0e13')
  if (!persist) return
  try {
    localStorage.setItem(storageKey(scope), next)
  } catch {
    // 隐私模式下忽略
  }
}

export function useTheme() {
  return {
    theme: readonly(theme),
    setScope: (next: Scope) => {
      scope = next
    },
    currentScope: () => scope,
    savedFor: readSaved,
    systemTheme,
    toggle: () => apply(theme.value === 'dark' ? 'light' : 'dark'),
    setTheme: apply,
    applyTemporary: (next: Theme) => apply(next, false),
    /** 切换登录角色时套用该角色自己的偏好 */
    applyScope: (next: Scope) => {
      scope = next
      const saved = readSaved(next)
      if (saved) apply(saved, false)
    },
  }
}
