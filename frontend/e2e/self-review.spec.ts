import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

/** 视频报告：逐题自评可勾选、保存、刷新后仍在。 */

test('视频报告逐题自评可保存并回显', async ({ page, request }) => {
  test.setTimeout(180_000)
  const email = `self-review-${Date.now()}@example.com`
  const password = 'SelfReview123!'

  await page.goto('/login')
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('自评测试')
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

  const turns = [
    { question: '先做个自我介绍。', answer: '我有三段实习，主要做后端开发。', startMs: 1000, endMs: 5000 },
    { question: '你最有挑战的项目是什么？', answer: '订单系统性能优化，接口从 800ms 降到 200ms。', startMs: 6000, endMs: 10500 },
  ]
  const video = readFileSync(new URL('./fixtures/room.mp4', import.meta.url))
  const uploaded = await request.post('/api/v1/voice/sessions', {
    headers,
    multipart: {
      sceneId,
      turns: JSON.stringify(turns),
      durationSeconds: '12',
      engine: 'pipeline',
      video: { name: 'room.mp4', mimeType: 'video/mp4', buffer: video },
    },
    timeout: 120_000,
  })
  expect(uploaded.status()).toBe(201)
  const sessionId = (await uploaded.json()).data.id

  const finished = await request.post(`/api/v1/training-sessions/${sessionId}/finish`, {
    headers,
    timeout: 150_000,
  })
  expect(finished.status()).toBe(200)

  await page.goto(`/report/${sessionId}`)
  await expect(page.getByRole('heading', { name: '逐题自评' })).toBeVisible()

  const camera = page.getByLabel('镜头位置合适').first()
  await camera.check()
  const note = page.locator('.self-review input.note').first()
  await note.fill('开场可以再直接一点')
  await page.getByRole('button', { name: '保存自评' }).click()
  await expect(page.getByRole('button', { name: /已保存/ })).toBeVisible()

  await page.reload()
  await expect(page.getByLabel('镜头位置合适').first()).toBeChecked()
  await expect(page.locator('.self-review input.note').first()).toHaveValue('开场可以再直接一点')
})
