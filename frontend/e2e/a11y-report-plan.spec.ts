import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

/** 报告页与训练计划页的无障碍基线（serious / critical 为 0）。 */

const RULES = {
  'color-contrast': { enabled: true },
  'label': { enabled: true },
  'button-name': { enabled: true },
  'link-name': { enabled: true },
  'html-has-lang': { enabled: true },
  'document-title': { enabled: true },
  'heading-order': { enabled: true },
  'image-alt': { enabled: true },
  'aria-allowed-attr': { enabled: true },
  'aria-hidden-focus': { enabled: true },
}

async function scan(page: import('@playwright/test').Page, name: string) {
  await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important}' })
  await page.waitForTimeout(400)
  const results = await new AxeBuilder({ page }).options({ rules: RULES }).analyze()
  const blocking = results.violations.filter((item) => item.impact === 'serious' || item.impact === 'critical')
  const summary = blocking.map((item) => ({
    id: item.id,
    impact: item.impact,
    nodes: item.nodes.length,
    help: item.help,
    targets: item.nodes.slice(0, 3).map((node) => node.target.join(' ')),
  }))
  expect(summary, `${name} 存在无障碍问题`).toEqual([])
}

test('报告页与计划页无障碍', async ({ page, request }) => {
  test.setTimeout(180_000)
  const email = `a11y-rp-${Date.now()}@example.com`
  const password = 'AxeReport123!'

  await page.goto('/login')
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('报告无障碍')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.locator('input[name="confirmPassword"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '场景训练' })).toBeVisible()

  const login = await request.post('/api/v1/auth/login', { data: { email, password } })
  const token = (await login.json()).data.accessToken
  const headers = { Authorization: `Bearer ${token}` }
  const scenes = await (await request.get('/api/v1/scenes?size=1', { headers })).json()
  const sceneId = scenes.data[0].id
  const created = await request.post('/api/v1/training-sessions', { data: { sceneId }, headers })
  const sessionId = (await created.json()).data.id

  for (const content of [
    '我有三段实习，主要做后端开发，最近做过订单系统的性能优化。',
    '项目的难点是缓存一致性和慢查询，我把接口从 800 毫秒降到了 200 毫秒。',
  ]) {
    const reply = await request.post(`/api/v1/training-sessions/${sessionId}/messages/complete`, {
      data: { content },
      headers,
      timeout: 90_000,
    })
    expect(reply.status()).toBe(200)
  }
  const finished = await request.post(`/api/v1/training-sessions/${sessionId}/finish`, { headers, timeout: 120_000 })
  expect(finished.status()).toBe(200)

  await page.goto(`/report/${sessionId}`)
  await expect(page.getByRole('heading', { name: /训练报告|这次表达/ }).first()).toBeVisible()
  await scan(page, '训练报告页')

  await page.goto('/plan')
  await expect(page.locator('main')).toBeVisible()
  await scan(page, '训练计划页')
})
