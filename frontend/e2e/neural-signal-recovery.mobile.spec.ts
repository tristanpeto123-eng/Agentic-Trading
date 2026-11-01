import { expect, test } from '@playwright/test'
const email = 'ci@example.invalid'
const password = process.env.CEO_TEST_PASSWORD

test('mobile: a legacy neural run is replaced by compatible checkpoint and displays saved model signal', async ({page}) => {
  if (!password) throw Error('CEO_TEST_PASSWORD required')
  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button',{name:'Access console'}).click()
  await page.locator('nav.bottom-nav').getByRole('button',{name:'Students'}).click()
  await page.getByRole('button',{name:'Create student',exact:true}).click()
  const dialog=page.getByRole('dialog')
  await dialog.getByLabel('Student name').fill('Neural Signal CI')
  await dialog.getByRole('button',{name:/CEO-directed/}).click()
  await dialog.getByRole('button',{name:/Gold.*Commodities/}).click()
  await dialog.getByRole('button',{name:/Trend trading/}).click()
  await dialog.getByRole('button',{name:'Create student'}).click()
  await page.locator('nav.bottom-nav').getByRole('button',{name:'Trading'}).click()
  const student=page.getByLabel('Choose student to train')
  await student.selectOption({label:'Neural Signal CI'})
  const sid=await student.inputValue()
  const legacy={run_id:'legacy',student_id:sid,model_schema:'research_m15_outcome_mlp8x16x2.v1',
    market:'XAUUSD',tactic:'trend',epoch:20,epochs_planned:80,train_examples:140,
    development_examples:40,state:'research_training',metrics:[],snapshot_sha256:'a'.repeat(64),
    latest_weights_sha256:'b'.repeat(64),weights_persisted:true,can_resume:true,
    trained_neural_model:true,qualification:'unqualified',independent_holdout_evaluated:false,
    paper_trading_enabled:false,live_trading_enabled:false}
  const v2={...legacy,run_id:'new-v2',model_schema:'research_m15_outcome_mlp8x16x2.v2',
    epoch:80,state:'complete',can_resume:false,latest_weights_sha256:'c'.repeat(64),
    metrics:[{epoch:80,train_loss:.34,development_loss:.41}]}
  let newRunRequested=false
  let predictionRequests=0
  await page.route('**/v1/students/*/neural/latest',async route=>
    route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({run:legacy})}))
  await page.route('**/v1/students/*/neural/start',async route=>{
    newRunRequested=true
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(v2)})
  })
  const origin=Date.parse('2025-04-07T00:00:00Z')
  const bars=Array.from({length:1100},(_,i)=>{
    const o=2500+i*.25
    return {open_time:new Date(origin+i*900000).toISOString(),
      available_at:new Date(origin+(i+1)*900000).toISOString(),
      open:o.toFixed(3), high:(o+.95).toFixed(3),
      low:(o-.45).toFixed(3),close:(o+.4).toFixed(3),volume:'10'}
  })
  await page.route('**/v1/students/*/train-data',async route=>
    route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
      student_id:sid,market:'XAUUSD',provider:'CI synthetic research fixture',
      source_sha256:'d'.repeat(64),bars,gap_count:0,source_verified:false,
      training_kind:'historical_policy_replay',neural_training_performed:false,
      persisted:false,paper_trading_enabled:false,live_trading_enabled:false,
    })}))
  await page.route('**/v1/students/*/neural/predict',async route=>{
    predictionRequests++
    const post=route.request().postDataJSON()
    expect(post.candles).toHaveLength(5)
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({
      model:{status:'INFERENCE_AVAILABLE',recommendation:'ABSTAIN',
        probability_profit_raw:.436,expected_net_pct_raw:-.032,
        candidate_direction:'LONG',checkpoint_sha256:'c'.repeat(64),
        epoch:80,time_scope:'TRAINING_PERIOD_DIAGNOSTIC'},
      research_only:true,guardian:'NOT_EVALUATED',decision:'NO_TRADE',
      paper_trading_enabled:false,live_trading_enabled:false,
    })})
  })
  await page.getByRole('button',{name:'Train',exact:true}).click()
  await expect(page.getByLabel('Neural model signal').getByText('43.6%')).toBeVisible({timeout:12000})
  await expect(page.getByLabel('Neural model signal').getByText('-0.032%')).toBeVisible()
  expect(newRunRequested).toBe(true)
  expect(predictionRequests).toBeGreaterThan(0)
  await expect(page.getByLabel('Neural model signal')).toContainText('Final decision:')
  await expect(page.getByLabel('Neural model signal')).toContainText('NO TRADE')
})
