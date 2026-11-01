import { expect, test } from '@playwright/test'
import { Buffer } from 'node:buffer'

const email = 'ci@example.invalid'
const password = process.env.CEO_TEST_PASSWORD

function history() {
  const lines = ['timestamp_open,open,high,low,close,volume']
  const origin = Date.parse('2025-04-07T09:00:00Z')
  for (let i = 0; i < 60; i++) {
    const open = 2000 + i * .5
    const close = open + .5
    lines.push([new Date(origin + i * 900000).toISOString(),
      open.toFixed(2), (close + .2).toFixed(2),
      (open - .2).toFixed(2), close.toFixed(2), 100].join(','))
  }
  return lines.join('\n') + '\n'
}

test('iPhone simulator: load local M15 data and inspect stepwise BUY decisions, no broker orders', async ({ page }) => {
  if (!password) throw new Error('CEO_TEST_PASSWORD required')
  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Access console' }).click()
  await page.locator('nav.bottom-nav').getByRole('button', { name: 'Trading' }).click()
  await page.getByText('Advanced tools · historical replay, data & paper account').click()
  await expect(page.getByRole('heading', { name: 'Historical Simulation' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Trade and P&L replay' })).toBeHidden()
  await page.getByLabel('Load M15 historical CSV').setInputFiles({
    name: 'ci-history.csv', mimeType: 'text/csv', buffer: Buffer.from(history())
  })
  await expect(page.getByText('ci-history.csv')).toBeVisible()
  await expect(page.getByRole('img', { name: 'Historical price chart with research BUY and SELL decisions' })).toBeVisible()
  await page.getByRole('button', { name: 'Reset' }).click()
  await expect(page.getByText('Collecting four completed candles before evaluating signals.')).toBeVisible()
  await page.getByRole('button', { name: 'Next decision' }).click()
  await expect(page.locator('.sim-decision .sim-action')).toHaveText('BUY')
  await expect(page.locator('.sim-decision')).toContainText('previous four completed candles')
  await expect(page.locator('.sim-journal-row').first()).toContainText('Pending')
  await page.getByRole('button', { name: 'Step', exact: true }).click()
  await expect(page.locator('.sim-journal-row').nth(1)).not.toContainText('Pending')
  await page.getByRole('button', { name: 'Start replay' }).click()
  await expect(page.getByRole('button', { name: 'Pause replay' })).toBeVisible()
  await page.getByRole('button', { name: 'Pause replay' }).click()
  await expect(page.getByText(/writes NO student training memories/)).toBeVisible()
})
