import { expect, test } from '@playwright/test'

/** 提示卡：文本训练里给出结构、关键词与提醒。 */

test('文本训练可以打开提示卡', async ({ page }) => {
  test.setTimeout(120_000)
  const email = `hint-${Date.now()}@example.com`
  const password = 'HintE2E123!'

  await page.goto('/login')
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('提示卡测试')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.locator('input[name="confirmPassword"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '场景训练' })).toBeVisible()

  await page.goto('/scenes')
  await page.getByRole('button', { name: '文字对练' }).first().click()
  await page.getByRole('button', { name: '直接开始' }).click()
  await expect(page).toHaveURL(/\/training\//, { timeout: 20_000 })

  await page.getByRole('button', { name: '提示卡' }).click()
  await expect(page.locator('.hint-card')).toBeVisible()
  await expect(page.locator('.hint-steps li').first()).toBeVisible()
  expect(await page.locator('.hint-steps li').count()).toBeGreaterThanOrEqual(3)
  expect(await page.locator('.hint-keywords span').count()).toBeGreaterThan(0)
  await expect(page.locator('.hint-card')).toContainText('当前问题')
  await page.screenshot({ path: '../.design/shots/hint-card.png', fullPage: true })
})
