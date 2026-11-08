import { expect, test } from '@playwright/test'

/** 语音 / 视频面试入口：沉浸式设置页，不出现“录制”字样。 */

async function login(page: import('@playwright/test').Page, request: import('@playwright/test').APIRequestContext) {
  const stamp = Date.now()
  const email = `imm-${stamp}@example.com`
  const password = 'ImmTest12345!'
  const created = await request.post('/api/v1/auth/register', {
    data: { email, password, displayName: '沉浸测试' },
    headers: { Referer: 'http://127.0.0.1:5173/' },
  })
  const token = (await created.json()).data.accessToken
  const scenes = await request.get('/api/v1/scenes?size=1', {
    headers: { Authorization: `Bearer ${token}`, Referer: 'http://127.0.0.1:5173/' },
  })
  const sceneId = (await scenes.json()).data[0].id

  await page.goto('/login')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '场景训练' })).toBeVisible()
  return sceneId
}

test('语音面试：时长挡位与开始入口，无录制字样', async ({ page, request }) => {
  const sceneId = await login(page, request)
  await page.goto(`/voice?sceneId=${sceneId}`)
  await expect(page.getByRole('button', { name: '30 分钟' })).toBeVisible()
  await expect(page.getByRole('button', { name: '60 分钟' })).toBeVisible()
  await expect(page.getByRole('button', { name: '开始面试' })).toBeVisible()
  await expect(page.getByText(/录制/)).toHaveCount(0)
})

test('视频面试：设备预检、时长挡位，无“开始录制”', async ({ page, request }) => {
  const sceneId = await login(page, request)
  await page.goto(`/video?sceneId=${sceneId}`)
  await expect(page.getByRole('button', { name: '检测设备' })).toBeVisible()
  await expect(page.getByRole('button', { name: '30 分钟' })).toBeVisible()
  await expect(page.getByRole('button', { name: '60 分钟' })).toBeVisible()
  await expect(page.getByText(/开始录制|录答模式/)).toHaveCount(0)
})


test('语音入口可切换追问强度并记住选择', async ({ page, request }) => {
  const sceneId = await login(page, request)
  await page.goto(`/voice?sceneId=${sceneId}&depth=THREE_LAYER`)
  const deep = page.getByRole('button', { name: '三层深挖' })
  await expect(deep).toHaveClass(/active/)
  await page.getByRole('button', { name: '压力面' }).click()
  await expect(page.getByRole('button', { name: '压力面' })).toHaveClass(/active/)
})

test('场景页可切换面试语言并记住', async ({ page, request }) => {
  const sceneId = await login(page, request)
  await page.goto(`/scenes?focus=${sceneId}`)
  await page.getByRole('button', { name: '更多设置' }).click()
  const english = page.getByRole('button', { name: 'English' })
  await expect(english).toBeVisible()
  await english.click()
  await expect(page.evaluate(() => localStorage.getItem('yanjie-interview-language'))).resolves.toBe('en')
  await page.reload()
  await page.getByRole('button', { name: '更多设置' }).click()
  await expect(page.getByRole('button', { name: 'English' })).toHaveClass(/active/)
})
