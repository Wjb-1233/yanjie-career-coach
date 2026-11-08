import { expect, test } from '@playwright/test'

/** 侧边栏与模块调整：新入口存在，已删模块不再出现。 */

test('侧边栏保留自建场景并移除已删模块', async ({ page }) => {
  const email = `nav-${Date.now()}@example.com`
  const password = 'NavE2E123!'

  await page.goto('/login')
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('导航测试')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.locator('input[name="confirmPassword"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '场景训练' })).toBeVisible()

  await expect(page.getByRole('link', { name: '我的场景' })).toBeVisible()
  await expect(page.getByRole('link', { name: '群面' })).toBeVisible()
  await expect(page.getByRole('link', { name: '话术优化' })).toBeVisible()

  for (const removed of ['通用练习', '故事库', '编程笔试', '简历诊断', '刷题']) {
    await expect(page.getByRole('link', { name: removed })).toHaveCount(0)
  }
})
