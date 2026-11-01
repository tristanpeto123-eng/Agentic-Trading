import { expect, test } from '@playwright/test'
import { Buffer } from 'node:buffer'

const email = 'ci@example.invalid'
const password = process.env.CEO_TEST_PASSWORD

function trendCsv() {
  const start = Date.parse('2025-04-07T00:00:00Z')
  const rows = ['timestamp_open,open,high,low,close']
  for (let i = 0; i < 124; i++) {
    const open = 1800 + i * .4
    rows.push([new Date(start + i*900000).toISOString(), open.toFixed(3),
      (open + .9).toFixed(3), (open - .5).toFixed(3),
      (open + .4).toFixed(3)].join(','))
  }
  return rows.join('\n') + '\n'
}

test('iPhone S4 research trace reports real regime, withheld Scout B, and no broker orders', async ({ page }, testInfo) => {
  if (!password) throw new Error('CEO_TEST_PASSWORD required')
  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Access console' }).click()
  await page.locator('nav.bottom-nav').getByRole('button', { name: 'Students' }).click()
  await page.getByRole('button', { name: 'Create student', exact: true }).click()
  const dialog = page.getByRole('dialog')
  const name = 'Trace CI ' + testInfo.retry
  await dialog.getByLabel('Student name').fill(name)
  await dialog.getByRole('button', { name: /CEO-directed/ }).click()
  await dialog.getByRole('button', { name: /Gold.*Commodities/ }).click()
  await dialog.getByRole('button', { name: /Trend trading/ }).click()
  await dialog.getByRole('button', { name: 'Create student' }).click()
  await expect(page.getByRole('heading', { name })).toBeVisible()
  await page.locator('nav.bottom-nav').getByRole('button', { name: 'Trading' }).click()
  await page.getByText('Advanced tools · historical replay, data & paper account').click()
  await page.getByLabel('Load M15 historical CSV').setInputFiles({
    name: 'trace-m15.csv', mimeType: 'text/csv', buffer: Buffer.from(trendCsv())
  })
  await page.getByLabel('Simulation student').selectOption({ label: name + ' · research identity' })
  await expect(page.getByLabel('Simulation engine')).toHaveValue('agents')
  await expect(page.getByRole('img', { name: /Historical XAUUSD M15 candlestick price chart/ })).toBeVisible()
  await page.locator('#simulation-timeline').focus()
  await page.keyboard.press('End')
  const panel = page.getByLabel('Real research agent decision trace')
  await expect(panel.getByText('TREND_UP', { exact: true })).toBeVisible({ timeout: 15000 })
  await expect(panel.getByText('LONG PROPOSED', { exact: true })).toBeVisible()
  await expect(panel.getByText('UNTRAINED', { exact: true })).toBeVisible()
  await expect(panel.getByText('NOT REACHED', { exact: true })).toBeVisible()
  await expect(panel.getByText('Final result: NO TRADE')).toBeVisible()
  await expect(panel).toContainText('No independently matured, source-isolated Scout B')
})
