import { expect, test } from '@playwright/test'

/**
 * 上线前的浏览器端到端冒烟：
 * 注册 → 看板 → 场景库 → 我的场景（创建/删除）→ 个人资料 → 未登录跳转。
 * 不依赖大模型：模型相关链路由 scripts/smoke_test.py 覆盖。
 */

test('注册后可以走完场景库、我的场景与个人资料', async ({ page }) => {
  const stamp = Date.now()
  const email = `e2e-${stamp}@example.com`
  const password = 'E2eTest12345!'

  await page.goto('/login')

  // 切换到注册模式
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('端到端测试')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill(password)
  await page.locator('input[name="confirmPassword"]').fill(password)
  await page.locator('button[type="submit"]').click()

  // 登录态：侧边栏出现，看板标题可见
  await expect(page.getByRole('link', { name: '场景训练' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '成长看板' })).toBeVisible()

  // 场景库至少有一张场景卡
  await page.goto('/scenes')
  await expect(page.locator('.scene-card').first()).toBeVisible()

  // 我的场景：创建 → 看到 → 删除
  await page.goto('/my-scenes')
  await page.getByRole('button', { name: '新建场景' }).click()
  const title = `端到端-后端开发-${stamp}`
  await page.locator('.editor input').nth(0).fill(title)
  await page.locator('.editor input').nth(2).fill('后端开发工程师')
  const questions = page.locator('.question-row input')
  await questions.nth(0).fill('介绍一下你做过的最复杂的接口设计')
  await questions.nth(1).fill('线上接口超时你会怎么排查')
  await page.getByRole('button', { name: '保存场景' }).click()
  await expect(page.getByText(title)).toBeVisible()

  page.on('dialog', (dialog) => void dialog.accept())
  await page.getByRole('button', { name: '删除' }).first().click()
  await expect(page.getByText(title)).toHaveCount(0)

  // 个人资料：数据导出与注销入口都在
  await page.goto('/profile')
  await expect(page.getByRole('heading', { name: '我的数据' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '注销账号' })).toBeVisible()
})

test('未登录访问受保护页面会回到登录', async ({ page }) => {
  await page.context().clearCookies()
  await page.goto('/my-scenes')
  await expect(page).toHaveURL(/\/login/)
})
