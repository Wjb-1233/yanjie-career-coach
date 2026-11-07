/** 前端错误上报：白屏、未捕获异常、Promise 拒绝都留下信号。 */

interface ReportPayload {
  message: string
  stack?: string
  route?: string
  userAgent?: string
}

const seen = new Set<string>()
const MAX_REPORTS_PER_LOAD = 10

function send(payload: ReportPayload): void {
  const key = `${payload.message}|${payload.route ?? ''}`.slice(0, 200)
  if (seen.has(key) || seen.size >= MAX_REPORTS_PER_LOAD) return
  seen.add(key)

  try {
    void fetch('/api/v1/client-errors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Referer: location.origin + '/' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => undefined)
  } catch {
    // 上报失败不能影响页面
  }
}

export function reportClientError(error: unknown, context = ''): void {
  const route = typeof location !== 'undefined' ? location.pathname : undefined
  if (error instanceof Error) {
    send({ message: `${context}${error.message}`.slice(0, 300), stack: error.stack?.slice(0, 2000), route, userAgent: navigator.userAgent.slice(0, 300) })
  } else {
    send({ message: `${context}${String(error)}`.slice(0, 300), route, userAgent: navigator.userAgent.slice(0, 300) })
  }
}

export function installErrorReporting(): void {
  if (typeof window === 'undefined') return

  window.addEventListener('error', (event) => {
    // 资源加载失败没有 error 对象，也要记录
    const target = event.target as HTMLElement | null
    if (target && target !== (window as unknown as HTMLElement) && target.tagName) {
      reportClientError(`资源加载失败: ${target.tagName}`, '')
      return
    }
    reportClientError(event.error ?? event.message, 'window.error: ')
  })

  window.addEventListener('unhandledrejection', (event) => {
    reportClientError(event.reason, 'unhandledrejection: ')
  })
}
