import { expect, test } from '@playwright/test'
const email = 'ci@example.invalid'
const password = process.env.CEO_TEST_PASSWORD

function trainingHistory(studentId: string) {
  const origin = Date.parse('2025-04-07T00:00:00Z')
  const bars = Array.from({ length: 1100 }, (_, i) => {
    const open=2500+i*.1, close=open+(i%11===0?-.4:.16)
    return {open_time:new Date(origin+i*900000).toISOString(),
      available_at:new Date(origin+(i+1)*900000).toISOString(),
      open:open.toFixed(4),high:(Math.max(open,close)+.3).toFixed(4),
      low:(Math.min(open,close)-.3).toFixed(4),close:close.toFixed(4),volume:'12'}
  })
  return {
    student_id:studentId,market:'XAUUSD',provider:'CI verified synthetic test fixture',
    source_sha256:'a'.repeat(64),bars,gap_count:0,source_verified:false,
    training_kind:'historical_policy_replay',neural_training_performed:false,
    persisted:false,paper_trading_enabled:false,live_trading_enabled:false,
    note:'Test fixture only'
  }
}

test('one click Trading: choose student, train, watch stats tick without CSV', async ({page})=>{
  if(!password)throw Error('CEO_TEST_PASSWORD required')
  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button',{name:'Access console'}).click()
  await page.locator('nav.bottom-nav').getByRole('button',{name:'Students'}).click()
  await page.getByRole('button',{name:'Create student',exact:true}).click()
  const dialog=page.getByRole('dialog')
  await dialog.getByLabel('Student name').fill('Training Demo CI')
  await dialog.getByRole('button',{name:/CEO-directed/}).click()
  await dialog.getByRole('button',{name:/Gold.*Commodities/}).click()
  await dialog.getByRole('button',{name:/Trend trading/}).click()
  await dialog.getByRole('button',{name:'Create student'}).click()
  await page.locator('nav.bottom-nav').getByRole('button',{name:'Trading'}).click()
  await expect(page.getByRole('heading',{name:'Train a student'})).toBeVisible()
  const selector=page.getByLabel('Choose student to train')
  await selector.selectOption({label:'Training Demo CI'})
  const id=await selector.inputValue()
  await page.route('**/v1/students/*/train-data',async route=>{
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(trainingHistory(id))})
  })
  await page.getByRole('button',{name:'Train',exact:true}).click()
  await expect(page.getByLabel('Student training cockpit').getByText('Research batches')).toBeVisible()
  await expect(page.getByRole('img',{name:'Training research hypothetical equity progression'})).toBeVisible()
  await expect(page.getByRole('button',{name:'Stop'})).toBeVisible()
  const before=await page.locator('.tc-progress-top strong').textContent()
  await expect.poll(async()=>page.locator('.tc-progress-top strong').textContent()).not.toBe(before)
  await page.getByRole('button',{name:'Stop'}).click()
  await expect(page.getByRole('button',{name:'Resume'})).toBeVisible()
  await expect(page.getByText(/not a trained neural checkpoint/)).toBeVisible()
  await expect(page.getByText(/does not create persistent learning memories/)).toBeVisible()
})
