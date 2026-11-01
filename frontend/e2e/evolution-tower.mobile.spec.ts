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
  await tower.getByRole('button',{name:'Generate 16 agents'}).click()
  await expect(tower.getByText('16 robots')).toBeVisible({timeout:15000})
  await expect(tower.getByRole('img',{name:/Interactive three-dimensional research trading skyscraper/})).toBeVisible()
  await expect(tower.locator('.evo-agent-list').getByText('ATL-G0-001',{exact:true})).toBeVisible()
  await tower.getByRole('button',{name:'Run next generation'}).click()
  await expect(tower.getByText(/Generation 1: .* eliminated/)).toBeVisible({timeout:15000})
  await expect(tower.locator('.evo-agent-list').getByText('ATL-G1-001',{exact:true})).toBeVisible()
  await tower.getByRole('button',{name:/View failure archive/}).click()
  await expect(tower.getByLabel('Evolution failure archive')).toBeVisible()
  await expect(tower.getByText(/penthouse/i).first()).toBeVisible()
  await page.reload()
  // The existing app intentionally opens Home after a full reload.
  // Navigate back to Trading to verify that the server persisted the cohort.
  await page.locator('nav.bottom-nav').getByRole('button',{name:'Trading'}).click()
  await expect(tower.getByText('16 robots')).toBeVisible()
  await expect(tower.locator('.evo-agent-list').getByText('ATL-G1-001',{exact:true})).toBeVisible()
  await expect(tower.getByText('Auto-evolve in this tab')).toBeVisible()
  await expect(tower.getByText(/No 24\/7 worker is deployed/)).toBeVisible()
  // Existing current student training remains accessible lower down.
  await expect(page.getByRole('heading',{name:'Train a student'})).toBeVisible()
})
