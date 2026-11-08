import { expect, test } from '@playwright/test'

/** 编程笔试：题目、运行判题、历史记录。 */

test('编程题可运行并记录提交', async ({ page }) => {
  test.setTimeout(120_000)
  const email = `coding-${Date.now()}@example.com`
  const password = 'CodingE2E123!'

  await page.goto('/login')
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('编程测试')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.locator('input[name="confirmPassword"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '编程笔试' })).toBeVisible()

  await page.getByRole('link', { name: '编程笔试' }).click()
  await expect(page.getByRole('heading', { name: '两数之和' })).toBeVisible()
  await expect(page.locator('.problem-item')).toHaveCount(3)

  await page.getByRole('button', { name: '运行代码' }).click()
  await expect(page.locator('.run-head strong')).toHaveText('全部通过', { timeout: 30_000 })
  await expect(page.locator('.run-head span')).toContainText('3 / 3')
  await expect(page.locator('.cases li.pass')).toHaveCount(3)
  await expect(page.locator('.history li')).toHaveCount(1)

  // 切换 JavaScript 也能跑同样的题
  await page.getByRole('button', { name: 'JavaScript' }).click()
  await page.getByRole('button', { name: '运行代码' }).click()
  await expect(page.locator('.run-head strong')).toHaveText('全部通过', { timeout: 30_000 })
})
