import { expect, test } from '@playwright/test'
import { Buffer } from 'node:buffer'

const email = 'ci@example.invalid'
const password = process.env.CEO_TEST_PASSWORD

test('iPhone Historical: import quarantined XAUUSD M15, inspect and play candles', async ({ page }) => {
  if (!password) throw new Error('CEO_TEST_PASSWORD required')
  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Access console' }).click()
  await expect(page.getByRole('heading', { name: 'Overview', exact: true })).toBeVisible()
  await page.locator('nav.bottom-nav').getByRole('button', { name: 'Trading' }).click()
  await page.getByText('Advanced tools · historical replay, data & paper account').click()
  await page.getByText('Advanced tools · saved data, M1 quotes & engine demonstrations').click()
  await expect(page.getByRole('heading', { name: 'Candle Replay' })).toBeVisible()

  await page.getByRole('button', { name: 'Import CSV' }).click()
  const rows = ['timestamp_open,open,high,low,close,volume']
  for (let i = 0; i < 32; i++) {
    const hours = String(Math.floor(i / 4)).padStart(2, '0')
    const minutes = String((i % 4) * 15).padStart(2, '0')
    rows.push(`2025-04-08T${hours}:${minutes}:00Z,3010.00,3015.00,3000.00,3012.00,${i}`)
  }
  await page.locator('.data-import-form input[type="file"]').setInputFiles({
    name: 'ci-synthetic-m15.csv', mimeType: 'text/csv', buffer: Buffer.from(rows.join('\n') + '\n')
  })
  await page.getByLabel('Owner-supplied private file').uncheck()
  await page.getByLabel('Source provider').fill('CI Synthetic Replay Fixture')
  await page.getByLabel('Export or source URL (HTTPS)').fill('https://example.org/ci-fixture')
  await page.getByLabel('Export reference').fill('synthetic-ci-e2e-001')
  await page.getByLabel('Usage rights reference').fill('Synthetic CI data for testing only')
  await page.getByRole('button', { name: 'Validate & freeze dataset' }).click()
  await expect(page.getByText(/Import recorded: 32 bars/)).toBeVisible()
  await expect(page.getByText(/Quarantined until provenance verification/)).toBeVisible()
  await page.getByRole('button', { name: 'Refresh datasets' }).click()

  await expect(page.getByRole('img', { name: /Historical XAUUSD M15 candlestick price chart/ })).toBeVisible()
  await expect(page.getByText(/QUARANTINED — NOT VERIFIED/)).toBeVisible()
  await expect(page.getByText(/No simulated orders, trades, win rate or equity curves/)).toBeVisible()
  await page.getByRole('button', { name: 'Play candles' }).click()
  await expect(page.getByRole('button', { name: 'Pause replay' })).toBeVisible()
  await page.getByRole('button', { name: 'Pause replay' }).click()
  await page.screenshot({ path: 'screenshots/04-historical-replay-mobile.png', fullPage: true })

  // Owner-supplied private archives do not need fabricated provider URLs.
  await page.getByRole('button', { name: 'Import CSV' }).click()
  await page.locator('.data-import-form input[type="file"]').setInputFiles({
    name: 'owner-native-time.csv', mimeType: 'text/csv',
    buffer: Buffer.from('time,open,high,low,close\n2025-04-09T09:00:00Z,4000,4002,3998,4001\n2025-04-09T09:15:00Z,4001,4003,3999,4002\n')
  })
  await page.getByLabel('Owner-supplied private file').check()
  await page.getByRole('button', { name: 'Validate & freeze dataset' }).click()
  await expect(page.getByText(/Import recorded: 2 bars/)).toBeVisible()
  await expect(page.locator('.dataset-row').filter({ hasText: 'USER_SUPPLIED_UNVERIFIED' }).first()).toBeVisible()
})
