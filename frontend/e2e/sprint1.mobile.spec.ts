import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'

test.beforeAll(() => mkdirSync('screenshots', { recursive: true }))

const email = 'ci@example.invalid'
const password = process.env.CEO_TEST_PASSWORD

test('mobile CEO login, student lifecycle, and disabled trading', async ({ page }) => {
  if (!password) throw new Error('CEO_TEST_PASSWORD required for e2e')
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Welcome back.' })).toBeVisible()
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Access console' }).click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await expect(page.getByText(/No market feed, broker account or trading permission is active/)).toBeVisible()
  await page.screenshot({ path: 'screenshots/01-home-mobile.png', fullPage: true })

  const nav = page.locator('nav.bottom-nav')
  await nav.getByRole('button', { name: 'Students' }).click()
  await expect(page.getByRole('heading', { name: 'Students', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Create student', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Student name').fill('Orion')
  await dialog.getByRole('button', { name: /CEO-directed/ }).click()
  await dialog.getByRole('button', { name: /Gold.*Commodities/ }).click()
  await dialog.getByRole('button', { name: /Trend trading/ }).click()
  await dialog.getByRole('button', { name: 'Create student' }).click()
  await expect(page.getByRole('heading', { name: 'Orion' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Learning plan v1' })).toBeVisible()
  await page.screenshot({ path: 'screenshots/02-student-mobile.png', fullPage: true })

  await page.getByRole('button', { name: 'Change direction' }).click()
  await page.getByRole('dialog').getByRole('button', { name: /Autonomous/ }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Save new plan' }).click()
  await expect(page.getByRole('heading', { name: 'Learning plan v2' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await nav.getByRole('button', { name: 'Students' }).click()
  await page.locator('button.student-card').filter({ hasText: 'Orion' }).click()
  await expect(page.getByRole('heading', { name: 'Learning plan v2' })).toBeVisible()
  await expect(page.getByText('Learning plan v1')).toBeVisible()

  await nav.getByRole('button', { name: 'Trading' }).click()
  await expect(page.getByRole('heading', { name: 'Trading', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historical testing not yet available' })).toBeVisible()
  await page.getByRole('tab', { name: /Paper/ }).click()
  await expect(page.getByRole('heading', { name: 'Paper trading is disabled' })).toBeVisible()
  await page.getByRole('tab', { name: /Live/ }).click()
  await expect(page.getByRole('heading', { name: 'Live trading is disabled' })).toBeVisible()
  await page.screenshot({ path: 'screenshots/03-trading-mobile.png', fullPage: true })
})
