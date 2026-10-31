import { expect, test } from '@playwright/test'
import { Buffer } from 'node:buffer'

const email = 'ci@example.invalid'
const password = process.env.CEO_TEST_PASSWORD

function m1Csv(side: 'bid' | 'ask', offsetMinutes = 0) {
  const rows = ['Etc/UTC,Open,High,Low,Close,Volume']
  const premium = side === 'ask' ? 0.6 : 0
  for (let i = 0; i < 6; i++) {
    const minute = String(i + offsetMinutes).padStart(2, '0')
    const op = 4000 + i + premium
    rows.push('2026-10-28T00:' + minute + ':00+00:00,' +
      [op, op + 1, op - 1, op + 0.2, 300].join(','))
  }
  return rows.join('\n') + '\n'
}

test('iPhone M1 BID/ASK quote inspector is local, aligned and explicitly unqualified', async ({ page }) => {
  if (!password) throw new Error('CEO_TEST_PASSWORD required for mobile test')
  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Access console' }).click()
  await page.locator('nav.bottom-nav').getByRole('button', { name: 'Trading' }).click()
  await page.getByText('Advanced tools · saved data, M1 quotes & engine demonstrations').click()
  await expect(page.getByRole('heading', { name: 'Inspect matching XAU/USD M1 quotes' })).toBeVisible()
  await page.getByLabel('BID · M1 CSV').setInputFiles({
    name: 'ci-bid.csv', mimeType: 'text/csv', buffer: Buffer.from(m1Csv('bid')),
  })
  await page.getByLabel('ASK · M1 CSV').setInputFiles({
    name: 'ci-ask.csv', mimeType: 'text/csv', buffer: Buffer.from(m1Csv('ask')),
  })
  await page.getByRole('button', { name: 'Inspect M1 pair locally' }).click()
  await expect(page.getByText('6 aligned M1 candles')).toBeVisible()
  await expect(page.getByText('$0.600/oz').first()).toBeVisible()
  await expect(page.getByText(/LOCAL · UNVERIFIED/).last()).toBeVisible()
  await expect(page.getByText(/not an executable simultaneous tick/)).toBeVisible()
})

test('iPhone M1 BID/ASK refuses nonmatching and crossed opening quotes', async ({ page }) => {
  if (!password) throw new Error('CEO_TEST_PASSWORD required for mobile test')
  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Access console' }).click()
  await page.locator('nav.bottom-nav').getByRole('button', { name: 'Trading' }).click()
  await page.getByText('Advanced tools · saved data, M1 quotes & engine demonstrations').click()

  await page.getByLabel('BID · M1 CSV').setInputFiles({
    name: 'ci-bid.csv', mimeType: 'text/csv', buffer: Buffer.from(m1Csv('bid')),
  })
  await page.getByLabel('ASK · M1 CSV').setInputFiles({
    name: 'ci-ask-other-day.csv', mimeType: 'text/csv',
    buffer: Buffer.from(m1Csv('ask').replaceAll('2026-10-28', '2026-10-29')),
  })
  await page.getByRole('button', { name: 'Inspect M1 pair locally' }).click()
  await expect(page.getByRole('alert')).toContainText('do not contain any matching')
  await page.getByLabel('ASK · M1 CSV').setInputFiles({
    name: 'ci-crossed-ask.csv', mimeType: 'text/csv',
    buffer: Buffer.from(m1Csv('ask').split('\n').map((line, index) => {
      if (index !== 1) return line
      const fields = line.split(',')
      fields[1] = '3999'; fields[2] = '4002'; fields[3] = '3998'
      return fields.join(',')
    }).join('\n')),
  })
  await page.getByRole('button', { name: 'Inspect M1 pair locally' }).click()
  await expect(page.getByRole('alert')).toContainText('Crossed or non-positive opening')
})
