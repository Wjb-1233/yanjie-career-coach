import { onMounted, onUnmounted, readonly, shallowRef } from 'vue'

export function useNetworkStatus() {
  const isOnline = shallowRef(navigator.onLine)

  function markOnline() {
    isOnline.value = true
  }

  function markOffline() {
    isOnline.value = false
  }

  onMounted(() => {
    window.addEventListener('online', markOnline)
    window.addEventListener('offline', markOffline)
  })

  onUnmounted(() => {
    window.removeEventListener('online', markOnline)
    window.removeEventListener('offline', markOffline)
  })

  return { isOnline: readonly(isOnline) }
}
