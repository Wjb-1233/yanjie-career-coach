import { defineConfig } from '@playwright/test'

// E2E 默认打在本地开发/预览服务上；CI 用环境变量覆盖。
// 本地没有 Playwright 浏览器时，可 PW_CHANNEL=chrome 复用系统 Chrome。
export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: process.env.E2E_BASE || 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    channel: process.env.PW_CHANNEL || undefined,
  },
})
