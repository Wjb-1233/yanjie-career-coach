import { expect, test } from '@playwright/test'

/** 管理台独立题库管理：按场景编辑题目。 */

test('管理台题库管理可打开并编辑题目', async ({ page }) => {
  await page.goto('/login')
  await page.locator('input[name="email"]').fill('admin@example.com')
  await page.locator('input[name="password"]').fill('Admin123!')
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '管理工作台' })).toBeVisible({ timeout: 15_000 })

  await page.getByRole('link', { name: '管理工作台' }).click()
  await page.getByRole('button', { name: '题库管理' }).click()
  await expect(page.getByRole('heading', { name: '题库管理' })).toBeVisible()
  await expect(page.locator('.bank-list li').first()).toBeVisible()

  await page.locator('.bank-list li button').first().click()
  await expect(page.locator('.question-list li').first()).toBeVisible()
  const before = await page.locator('.question-list li').count()
  expect(before).toBeGreaterThan(0)

  await page.getByRole('button', { name: '添加题目' }).click()
  await expect(page.locator('.question-list li')).toHaveCount(before + 1)
  await page.locator('.question-list li').last().locator('textarea').fill('这是一道新加的题目，用来验证题库管理。')
  await expect(page.getByRole('button', { name: '保存题库' })).toBeEnabled()
  await page.screenshot({ path: '../.design/shots/admin-bank.png', fullPage: true })
})
