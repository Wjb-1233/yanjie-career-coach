import { computed, onMounted, onUnmounted, readonly, shallowRef } from 'vue'

interface InstallPromptEvent extends Event {
  prompt: () => Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>
}

interface NavigatorWithStandalone extends Navigator {
  standalone?: boolean
}

const DISMISS_KEY = 'pwa-install-dismissed'

export function usePwaInstall() {
  const installPrompt = shallowRef<InstallPromptEvent | null>(null)
  const dismissed = shallowRef(sessionStorage.getItem(DISMISS_KEY) === 'true')
  const isInstalled = shallowRef(
    window.matchMedia('(display-mode: standalone)').matches
      || Boolean((navigator as NavigatorWithStandalone).standalone),
  )

  const isIos = computed(() => {
    const userAgent = navigator.userAgent.toLowerCase()
    const isAppleMobile = /iphone|ipad|ipod/.test(userAgent)
    const isTouchMac = userAgent.includes('macintosh') && navigator.maxTouchPoints > 1
    return isAppleMobile || isTouchMac
  })

  const shouldShowInstall = computed(
    () => !dismissed.value && !isInstalled.value && (installPrompt.value !== null || isIos.value),
  )

  function captureInstallPrompt(event: Event) {
    event.preventDefault()
    installPrompt.value = event as InstallPromptEvent
  }

  function markInstalled() {
    isInstalled.value = true
    installPrompt.value = null
  }

  async function install() {
    if (isIos.value || !installPrompt.value) return
    const result = await installPrompt.value.prompt()
    installPrompt.value = null
    if (result.outcome === 'accepted') isInstalled.value = true
  }

  function dismiss() {
    dismissed.value = true
    sessionStorage.setItem(DISMISS_KEY, 'true')
  }

  onMounted(() => {
    window.addEventListener('beforeinstallprompt', captureInstallPrompt)
    window.addEventListener('appinstalled', markInstalled)
  })

  onUnmounted(() => {
    window.removeEventListener('beforeinstallprompt', captureInstallPrompt)
    window.removeEventListener('appinstalled', markInstalled)
  })

  return {
    isIos,
    isInstalled: readonly(isInstalled),
    shouldShowInstall,
    install,
    dismiss,
  }
}
