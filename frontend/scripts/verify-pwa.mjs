import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = resolve(root, 'dist')

function assert(condition, message) {
  if (!condition) throw new Error(`PWA verification failed: ${message}`)
}

function readPngSize(path) {
  const bytes = readFileSync(path)
  assert(bytes.subarray(1, 4).toString('ascii') === 'PNG', `${path} is not a PNG`)
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) }
}

const manifestPath = resolve(dist, 'manifest.webmanifest')
const serviceWorkerPath = resolve(dist, 'sw.js')
assert(existsSync(manifestPath), 'manifest.webmanifest is missing')
assert(existsSync(serviceWorkerPath), 'sw.js is missing')

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
assert(manifest.name && manifest.short_name, 'manifest names are required')
assert(manifest.start_url && manifest.display === 'standalone', 'manifest launch settings are invalid')

for (const size of [192, 512]) {
  const icon = manifest.icons.find((item) => item.sizes === `${size}x${size}` && item.purpose === 'any')
  assert(icon, `${size}x${size} install icon is missing from manifest`)
  const iconPath = resolve(dist, icon.src.replace(/^\//, ''))
  assert(existsSync(iconPath), `${icon.src} is missing from build output`)
  const dimensions = readPngSize(iconPath)
  assert(dimensions.width === size && dimensions.height === size, `${icon.src} has wrong dimensions`)
}

const serviceWorker = readFileSync(serviceWorkerPath, 'utf8')
assert(serviceWorker.includes("url.pathname.startsWith('/api/')"), 'API requests must be excluded from caching')
const bundles = readdirSync(resolve(dist, 'assets')).filter((name) => name.endsWith('.js'))
assert(bundles.some((name) => readFileSync(resolve(dist, 'assets', name), 'utf8').includes('serviceWorker')), 'service worker registration is missing')
const bundledJavaScript = bundles.map((name) => readFileSync(resolve(dist, 'assets', name), 'utf8')).join('\n')
for (const forbiddenCredential of ['Student123!', 'Admin123!']) {
  assert(!bundledJavaScript.includes(forbiddenCredential), 'demo credentials must not ship in production bundles')
}

console.log('PWA verification passed: install assets, API cache exclusion and credential hygiene are valid.')
