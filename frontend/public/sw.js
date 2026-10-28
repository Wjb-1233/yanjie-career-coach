const CACHE_VERSION = 'yanjie-pwa-v1'
const STATIC_CACHE = `${CACHE_VERSION}-static`
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`
const APP_SHELL = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/favicon.svg',
  '/icons/pwa-192.png',
  '/icons/pwa-512.png',
  '/icons/pwa-maskable-512.png',
  '/icons/apple-touch-icon-180.png',
]

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((cache) => cache.addAll(APP_SHELL)))
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith('yanjie-pwa-') && ![STATIC_CACHE, RUNTIME_CACHE].includes(key))
          .map((key) => caches.delete(key)),
      ))
      .then(() => self.clients.claim()),
  )
})

async function networkFirst(request) {
  try {
    const response = await fetch(request)
    if (response.ok) {
      const cache = await caches.open(RUNTIME_CACHE)
      await cache.put(request, response.clone())
    }
    return response
  } catch {
    return (await caches.match(request)) || (await caches.match('/index.html'))
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request)
  if (cached) return cached
  const response = await fetch(request)
  if (response.ok) {
    const cache = await caches.open(RUNTIME_CACHE)
    await cache.put(request, response.clone())
  }
  return response
}

self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request))
    return
  }

  if (['script', 'style', 'font', 'image'].includes(request.destination)) {
    event.respondWith(cacheFirst(request))
  }
})
