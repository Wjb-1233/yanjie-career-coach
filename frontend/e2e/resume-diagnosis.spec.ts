import { expect, test } from '@playwright/test'

/** 简历诊断：粘贴 JD 与简历，得到分数、关键词覆盖与历史。 */

test('简历诊断可出分并保存历史', async ({ page }) => {
  const email = `resume-${Date.now()}@example.com`
  const password = 'ResumeE2E123!'

  await page.goto('/login')
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('简历测试')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.locator('input[name="confirmPassword"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '简历诊断' })).toBeVisible()

  await page.getByRole('link', { name: '简历诊断' }).click()
  const areas = page.locator('textarea')
  await areas.nth(0).fill('负责后端开发。任职要求：熟悉 Java、Spring Boot、MySQL、Redis、消息队列，有 Agent 项目经验优先。')
  await areas.nth(1).fill(
    ('项目经历：订单协同 Agent 系统，使用 Java 与 Spring Boot，接口延迟从 800ms 降到 200ms，覆盖 3 个工厂。').repeat(4),
  )
  await page.getByRole('button', { name: '开始诊断' }).click()

  await expect(page.locator('.score strong')).toBeVisible()
  await expect(page.locator('.score strong')).not.toHaveText('')
  await expect(page.locator('.chips-block').first()).toContainText('已覆盖')
  await expect(page.locator('.suggestions li').first()).toBeVisible()
  await expect(page.locator('.history li')).toHaveCount(1)

  await page.reload()
  await expect(page.locator('.history li')).toHaveCount(1)
})
