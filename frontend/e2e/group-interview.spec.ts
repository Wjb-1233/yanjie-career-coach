import { expect, test } from '@playwright/test'

/** 群面：选题、发言、虚拟候选人回应、结束评估。 */

test('群面可以发言并生成评估', async ({ page }) => {
  test.setTimeout(150_000)
  const email = `group-${Date.now()}@example.com`
  const password = 'GroupE2E123!'

  await page.goto('/login')
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('群面测试')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.locator('input[name="confirmPassword"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '群面' })).toBeVisible()

  await page.getByRole('link', { name: '群面' }).click()
  await expect(page.getByRole('heading', { name: /无领导小组讨论/ })).toBeVisible()
  await expect(page.locator('.topic-card').first()).toBeVisible()

  await page.locator('.topic-card').first().getByRole('button', { name: '开始讨论' }).click()
  await expect(page.locator('.chat')).toBeVisible()
  await expect(page.locator('.turn.host').first()).toContainText('无领导小组讨论')

  await page.locator('.chat textarea').fill('我同意先做性能优化，因为它影响所有用户；建议先做两周灰度，再决定是否全量。')
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.locator('.turn.me').first()).toContainText('性能优化')
  await expect(page.locator('.turn.peer').first()).toBeVisible({ timeout: 60_000 })

  await page.getByRole('button', { name: '结束讨论' }).click()
  await expect(page.locator('.result .score strong')).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.dimensions li')).toHaveCount(4)
})
