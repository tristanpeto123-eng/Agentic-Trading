// Mobile end-to-end: imported historical candles drive a real student study,
// not fabricated P&L or a paper/live trading operation.
import { expect, test } from '@playwright/test'
import { Buffer } from 'node:buffer'
import { mkdirSync } from 'node:fs'

const email = 'ci@example.invalid'
const password = process.env.CEO_TEST_PASSWORD

test('iPhone Academy uses a saved XAUUSD dataset for five-batch progression', async ({ page }, testInfo) => {
  if (!password) throw new Error('CEO_TEST_PASSWORD required')
  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Access console' }).click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()

  // Research environment uses a locally generated integration fixture,
  // never claims it is licensed market data, and never places trades.
  const start = Date.parse('2025-04-01T00:00:00Z')
  const tick = Date.now() % 1000
  const lines = ['time,open,high,low,close']
  for (let i = 0; i < 1800; i++) {
    const p = 3200 + tick / 10000 + Math.floor(i / 19) / 8 + (i % 19) / 6
    const dt = new Date(start + i * 900000).toISOString().replace('.000Z', 'Z')
    lines.push(`${dt},${p.toFixed(4)},${(p + 1).toFixed(4)},${(p - 1).toFixed(4)},${(p + 0.2).toFixed(4)}`)
  }
  await page.locator('nav.bottom-nav').getByRole('button', { name: 'Trading' }).click()
  await page.getByRole('button', { name: 'Import CSV' }).click()
  await page.locator('.data-import-form input[type="file"]').setInputFiles({
    name: 'academy-ci-m15.csv', mimeType: 'text/csv', buffer: Buffer.from(lines.join('\n') + '\n')
  })
  await expect(page.getByLabel('Owner-supplied private file')).toBeChecked()
  await page.getByRole('button', { name: 'Validate & freeze dataset' }).click()
  await expect(page.getByText(/Import recorded: 1,800 bars/)).toBeVisible({ timeout: 20000 })

  await page.locator('nav.bottom-nav').getByRole('button', { name: 'Students' }).click()
  await page.getByRole('button', { name: 'Create student', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const name = `Study CI ${testInfo.workerIndex} ${testInfo.retry} ${tick}`
  await dialog.getByLabel('Student name').fill(name)
  // Autonomous curriculum defaults to XAUUSD with three fixed research tactics.
  await dialog.getByRole('button', { name: 'Create student' }).click()
  await expect(page.getByRole('heading', { name })).toBeVisible()
  await page.getByRole('tab', { name: 'Academy' }).click()
  await expect(page.getByRole('heading', { name: 'Student Candle Study' })).toBeVisible()
  await expect(page.getByRole('combobox', { name: 'Saved gold dataset' })).toContainText('1,800 candles')
  await page.getByRole('button', { name: 'Start study' }).click()
  await expect(page.getByRole('img', { name: /M15 price checkpoints/ })).toBeVisible({ timeout: 20000 })
  await expect(page.getByRole('img', { name: /Cumulative directional accuracy/ })).toBeVisible()
  await expect(page.getByText(/Final holdout:/)).toBeVisible()
  await expect(page.getByText(/Neural training, Registrar qualification, paper trading and live trading remain disabled/)).toBeVisible()
  const pause = page.getByRole('button', { name: 'Pause' })
  if (await pause.isVisible()) await pause.click()
  mkdirSync('screenshots', { recursive: true })
  await page.screenshot({ path: 'screenshots/05-academy-study-mobile.png', fullPage: true })
})
