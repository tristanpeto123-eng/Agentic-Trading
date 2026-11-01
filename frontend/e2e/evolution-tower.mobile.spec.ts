import { expect, test } from '@playwright/test'

test('iPhone research tower creates population, advances generations and displays genuine persisted events',async({page})=>{
  const password=process.env.CEO_TEST_PASSWORD
  if(!password)throw Error('CEO_TEST_PASSWORD required')
  await page.goto('/')
  await page.getByLabel('Email address').fill('ci@example.invalid')
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button',{name:'Access console'}).click()
  await page.locator('nav.bottom-nav').getByRole('button',{name:'Trading'}).click()
  const tower=page.getByLabel('Evolution Tower research arena')
  await expect(tower.getByRole('heading',{name:/Evolution Tower/})).toBeVisible()
  await expect(tower.getByText('SYNTHETIC RESEARCH')).toBeVisible()
  // Tests share one ephemeral SQLite file across Playwright retries. A retry
  // may encounter the cohort already created by the first attempt.
  const generate = tower.getByRole('button',{name:'Generate 16 agents'})
  if (await generate.isVisible()) await generate.click()
  await expect(tower.getByText('16 robots')).toBeVisible({timeout:15000})
  // First view distinguishes selection B from diagnostic C even if entries=0.
  await expect(tower.getByText(/ENTRIES · TOY B \(SELECTION\)/).first()).toBeVisible()
  await expect(tower.getByRole('img',{name:/Interactive three-dimensional research trading skyscraper/})).toBeVisible()
  const ids = tower.locator('.evo-agent-row .evo-agent-copy strong')
  const before = await ids.allTextContents()
  expect(before).toHaveLength(16)
  await tower.getByRole('button',{name:'Run next generation'}).click()
  await expect(tower.locator('.evo-event')).toContainText(/Generation [0-9]+:/,{timeout:15000})
  await expect(tower.locator('.evo-event')).toContainText('No compulsory bottom-half purge.')
  await expect(tower.getByText(/Training B: [0-9]+ hypothetical entries/)).toBeVisible()
  await expect(tower.getByText(/Diagnostic C: [0-9]+ hypothetical entries/)).toBeVisible()
  await expect(ids).toHaveCount(16)
  const after = await ids.allTextContents()
  // Rank order can change without any ID being deleted.
  expect(new Set(after).size).toBe(16)
  expect(before).toHaveLength(16)
  await tower.getByRole('button',{name:/View failure archive/}).click()
  await expect(tower.getByLabel('Evolution failure archive')).toBeVisible()
  await expect(tower.getByText(/penthouse/i).first()).toBeVisible()
  await page.reload()
  // The existing app intentionally opens Home after a full reload.
  // Navigate back to Trading to verify that the server persisted the cohort.
  await page.locator('nav.bottom-nav').getByRole('button',{name:'Trading'}).click()
  await expect(tower.getByText('16 robots')).toBeVisible()
  await expect.poll(async()=>tower.locator('.evo-agent-row .evo-agent-copy strong').allTextContents()).toEqual(after)
  await expect(tower.getByText('Auto-evolve in this tab')).toBeVisible()
  await expect(tower.getByText(/No 24\/7 worker is deployed/)).toBeVisible()
  // Existing current student training remains accessible lower down.
  await expect(page.getByRole('heading',{name:'Train a student'})).toBeVisible()
})
