import { expect, test } from '@playwright/test'

/** 题库：筛选、收藏、掌握度与刷新后持久化。 */

test('题库可筛选、收藏并标记掌握', async ({ page }) => {
  const email = `bank-${Date.now()}@example.com`
  const password = 'BankE2E123!'

  await page.goto('/login')
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('题库测试')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.locator('input[name="confirmPassword"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '刷题' })).toBeVisible()

  await page.getByRole('link', { name: '刷题' }).click()
  await expect(page.getByRole('heading', { name: /把常见问题/ })).toBeVisible()
  const cards = page.locator('.bank-card')
  await expect(cards.first()).toBeVisible()
  expect(await cards.count()).toBeGreaterThan(10)

  const stats = page.locator('.bank-stats strong')
  await expect(stats.nth(0)).toHaveText('152')

  await cards.first().locator('.star').click()
  await expect(stats.nth(2)).toHaveText('1')

  await cards.first().getByRole('button', { name: /标记掌握/ }).click()
  await expect(stats.nth(1)).toHaveText('1')

  await page.getByRole('button', { name: /只看收藏/ }).click()
  await expect(page.locator('.bank-card')).toHaveCount(1)

  await page.reload()
  await expect(page.locator('.bank-stats strong').nth(2)).toHaveText('1')
})
