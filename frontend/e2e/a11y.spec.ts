import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

/**
 * 无障碍基线：关键页面不允许出现 serious / critical 级别问题。
 * 只扫常见结构性规则，避免把第三方依赖的历史问题全部算进来。
 */

const RULES = {
  'color-contrast': { enabled: true },
  'label': { enabled: true },
  'button-name': { enabled: true },
  'link-name': { enabled: true },
  'html-has-lang': { enabled: true },
  'document-title': { enabled: true },
  'heading-order': { enabled: true },
  'image-alt': { enabled: true },
  'aria-allowed-attr': { enabled: true },
  'aria-hidden-focus': { enabled: true },
}

async function scan(page: import('@playwright/test').Page, name: string) {
  // 入场动画未结束时，axe 会把半透明状态算成对比度问题，先关掉动画并等一帧
  await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important}' })
  await page.waitForTimeout(400)

  const results = await new AxeBuilder({ page }).options({ rules: RULES }).analyze()
  const blocking = results.violations.filter((item) => item.impact === 'serious' || item.impact === 'critical')
  const summary = blocking.map((item) => ({
    id: item.id,
    impact: item.impact,
    nodes: item.nodes.length,
    help: item.help,
    targets: item.nodes.slice(0, 3).map((node) => node.target.join(' ')),
  }))
  expect(summary, `${name} 存在无障碍问题`).toEqual([])
}

test('登录页无障碍', async ({ page }) => {
  await page.goto('/login')
  await expect(page.locator('form')).toBeVisible()
  await scan(page, '登录页')
})

test('注册后的看板与场景库无障碍', async ({ page }) => {
  const stamp = Date.now()
  const email = `a11y-${stamp}@example.com`

  await page.goto('/login')
  await page.getByRole('button', { name: '注册' }).first().click()
  await page.locator('input[name="displayName"]').fill('无障碍测试')
  await page.locator('input[name="email"]').fill(email)
  await page.locator('input[name="password"]').fill('AxeTest12345!')
  await page.locator('input[name="confirmPassword"]').fill('AxeTest12345!')
  await page.locator('button[type="submit"]').click()
  await expect(page.getByRole('link', { name: '场景训练' })).toBeVisible()

  await scan(page, '成长看板')

  await page.goto('/scenes')
  await expect(page.locator('.scene-card').first()).toBeVisible()
  await scan(page, '场景库')

  await page.goto('/my-scenes')
  await expect(page.getByRole('button', { name: '新建场景' })).toBeVisible()
  await scan(page, '我的场景')
})
