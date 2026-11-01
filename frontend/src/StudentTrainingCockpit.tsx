import { useEffect, useMemo, useState } from 'react'
import { Activity, BarChart3, BrainCircuit, Play, ShieldAlert, Square } from 'lucide-react'
import { api } from './api'
import type { Student } from './api'
import type { Candle } from './HistoricalResearch'
import './StudentTrainingCockpit.css'
import { ResearchNeuralStatus } from './ResearchNeuralStatus'
import type { NeuralReport } from './ResearchNeuralStatus'
import { NeuralSignalForecast } from './NeuralSignalForecast'

type Rule = 'trend' | 'range' | 'breakout'
type History = {
  student_id: string; market: 'XAUUSD' | 'BTCUSD'; provider: string
  source_sha256: string; bars: Candle[]; gap_count: number; source_verified: false
  training_kind: 'historical_policy_replay'; neural_training_performed: false
  persisted: false; paper_trading_enabled: false; live_trading_enabled: false; note: string
}
type Trade = { index: number; rule: Rule; pnl: number }
type TrainingStep = {
  index: number; rule: Rule; batch: number; switchCount: number
  gross: number; pnl: number; trades: number; wins: number; drawdown: number
  equity: number; lastSignal: string
}
const BATCH = 96
const INITIAL_EQUITY = 1000
const RULES: Rule[] = ['trend', 'range', 'breakout']
const money = (x: number) => new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'USD' }).format(x)
const pct = (x: number) => x.toFixed(1) + '%'
function sign(bars: Candle[], at: number, tactic: Rule): number {
  if (at < 4) return 0
  for (let n = at - 3; n <= at; n++)
    if (Date.parse(bars[n].open_time) - Date.parse(bars[n-1].open_time) !== 900000) return 0
  const now = Number(bars[at].close), prior = Number(bars[at-1].close)
  if (Math.abs(now / prior - 1) > .04) return 0
  if (tactic === 'trend') return Math.sign(now - prior)
  if (tactic === 'range') return -Math.sign(now - prior)
  const high = Math.max(...bars.slice(at - 4, at).map(b => Number(b.high)))
  const low = Math.min(...bars.slice(at - 4, at).map(b => Number(b.low)))
  return Number(now > high) - Number(now < low)
}
function closeTrade(bars: Candle[], index: number, tactic: Rule, market: string): Trade | null {
  if (index < 5 || Date.parse(bars[index].open_time) !== Date.parse(bars[index - 1].available_at)) return null
  const side = sign(bars, index-1, tactic)
  if (!side) return null
  const qty = market === 'BTCUSD' ? .001 : .1
  const entry = Number(bars[index].open)
  const friction = market === 'BTCUSD' ? entry * qty * .002 : .1
  return { index, rule: tactic, pnl: side*(Number(bars[index].close)-entry)*qty-friction }
}
export function buildTrainingTimeline(bars: Candle[], market: string, allowedRules: Rule[]): TrainingStep[] {
  if (bars.length < BATCH || allowedRules.length === 0) return []
  const results: TrainingStep[] = []
  let rule = allowedRules[0], switchCount = 0, net = 0, gross = 0, trades = 0, wins = 0
  let equity = INITIAL_EQUITY, peak = equity, drawdown = 0
  let batches: Record<Rule, number>[] = []
  const batchTotals: Record<Rule, number> = { trend: 0, range: 0, breakout: 0 }
  for (let i = 0; i < bars.length; i++) {
    // Each hypothetical trade's outcome is recognised only when that next bar closes.
    const event = closeTrade(bars, i, rule, market)
    if (event) {
      net += event.pnl; gross += event.pnl
      trades++; if (event.pnl > 0) wins++
      equity = INITIAL_EQUITY + net
      peak = Math.max(peak, equity)
      drawdown = Math.max(drawdown, peak > 0 ? (peak - equity) / peak * 100 : 100)
    }
    for (const candidate of allowedRules) {
      const trial = closeTrade(bars, i, candidate, market)
      if (trial) batchTotals[candidate] += trial.pnl
    }
    const endedBatch = (i + 1) % BATCH === 0
    if (endedBatch) {
      batches.push({ ...batchTotals })
      for (const tactic of RULES) batchTotals[tactic] = 0
      if (batches.length % 5 === 0) {
        const recent = batches.slice(-5)
        const best = allowedRules.reduce((pick, tactic) =>
          recent.reduce((sum, batch) => sum + batch[tactic], 0) >
          recent.reduce((sum, batch) => sum + batch[pick], 0) ? tactic : pick, rule)
        if (best !== rule) { rule = best; switchCount++ }
      }
    }
    results.push({ index: i, rule, batch: Math.floor(i / BATCH) + 1, switchCount, gross,
      pnl: net, trades, wins, drawdown, equity, lastSignal: event ? (event.pnl >= 0 ? 'Hypothetical win' : 'Hypothetical loss') : 'Wait / observation' })
  }
  return results
}
function EquityChart({ points }: { points: TrainingStep[] }) {
  const sampled = points.filter((_, i) => i % 2 === 0 || i === points.length-1)
  if (!sampled.length) return null
  const min = Math.min(...sampled.map(x => x.equity))-1
  const max = Math.max(...sampled.map(x => x.equity))+1
  const coordinates = sampled.map((x, i) =>
    (24 + i * 744 / Math.max(sampled.length-1, 1)).toFixed(1)+','+
    (190-(x.equity-min)/(max-min)*145).toFixed(1)).join(' ')
  return <svg viewBox="0 0 820 230" className="tc-chart" role="img" aria-label="Training research hypothetical equity progression">
    <rect x="1" y="1" width="818" height="228" rx="12" fill="#0b1929" stroke="#304859"/>
    {[0,1,2,3,4].map(n=><line key={n} x1="24" x2="768" y1={25+n*42} y2={25+n*42} stroke="#284052" strokeDasharray="3 7"/>)}
    <polyline points={coordinates} stroke="#7ad1df" strokeWidth="3" fill="none" strokeLinejoin="round"/>
    <text x="24" y="217" fontSize="12" fill="#9ab0c0">Start</text><text x="768" y="217" textAnchor="end" fontSize="12" fill="#9ab0c0">Current replay</text>
    <text x="780" y="29" fill="#9ab0c0" fontSize="11">{max.toFixed(0)}</text>
    <text x="780" y="191" fill="#9ab0c0" fontSize="11">{min.toFixed(0)}</text>
  </svg>
}
export function StudentTrainingCockpit({ students }: { students: Student[] }) {
  const [studentId, setStudentId] = useState('')
  const [data, setData] = useState<History|null>(null)
  const [cursor, setCursor] = useState(0)
  const [stage, setStage] = useState<'idle'|'fetching'|'running'|'stopped'|'complete'>('idle')
  const [error, setError] = useState('')
  const [neural, setNeural] = useState<NeuralReport | null>(null)
  const [neuralActive, setNeuralActive] = useState(false)
  const [neuralError, setNeuralError] = useState('')
  const chosen = students.find(s=>s.id === studentId)
  useEffect(()=>{
    let valid=true
    setNeural(null);setNeuralError('');setNeuralActive(false)
    if(studentId) void api<{run:NeuralReport|null}>('/v1/students/'+encodeURIComponent(studentId)+'/neural/latest')
      .then(result=>{if(valid)setNeural(result.run)})
      .catch(err=>{if(valid)setNeuralError(err instanceof Error?err.message:'Saved checkpoint unavailable')})
    return ()=>{valid=false}
  },[studentId])
  useEffect(()=>{
    if(!neuralActive||!neural||neural.epoch>=neural.epochs_planned)return
    let valid=true
    const timer=window.setTimeout(()=>{
      void api<NeuralReport>('/v1/students/'+encodeURIComponent(studentId)+'/neural/'+encodeURIComponent(neural.run_id)+'/epoch',
          'POST',{expected_epoch:neural.epoch})
        .then(result=>{if(valid){setNeural(result);if(result.state==='complete'){setNeuralActive(false);setStage(previous=>previous==='running'?'complete':previous)}}})
        .catch(err=>{if(valid){setNeuralActive(false);setNeuralError(err instanceof Error?err.message:'Neural epoch failed')}})
    },420)
    return ()=>{valid=false;window.clearTimeout(timer)}
  },[neuralActive,neural,studentId])
  const allowed = RULES.filter(t=>!chosen || chosen.learning_plan.mode === 'autonomous' || chosen.learning_plan.skills.includes(t))
  const timeline = useMemo(()=>data ? buildTrainingTimeline(data.bars, data.market, allowed) : [],[data,chosen?.id,chosen?.learning_plan.version])
  const current = timeline[Math.min(cursor, timeline.length-1)]
  const visible = timeline.slice(0,cursor+1)
  useEffect(()=>{
    if(stage!=='running' || !timeline.length) return
    const timer=window.setInterval(()=>setCursor(old=>Math.min(old+8, timeline.length-1)),130)
    return ()=>window.clearInterval(timer)
  },[stage,timeline.length])
  useEffect(()=>{
    if(stage==='running' && timeline.length && cursor >= timeline.length-1) setStage('complete')
  },[stage,cursor,timeline.length])
  const train = async () => {
    if(!studentId) return
    setStage('fetching');setData(null);setCursor(0);setError('');setNeuralError('');setNeuralActive(false)
    try{
      const previous = await api<{run:NeuralReport|null}>('/v1/students/'+encodeURIComponent(studentId)+'/neural/latest')
      if(previous.run && previous.run.epoch < previous.run.epochs_planned &&
         previous.run.model_schema === 'research_m15_outcome_mlp8x16x2.v2'){
        setNeural(previous.run);setStage('running');setNeuralActive(true)
        // Resume from durable weights without depending on a fresh feed.
        // If history is accessible, also restore the replay and neural
        // predictions; never make saved training depend on an upload.
        try {
          const history = await api<History>('/v1/students/'+encodeURIComponent(studentId)+'/train-data')
          if(history.student_id===studentId && history.market===previous.run.market &&
             history.bars?.length>=96 && history.paper_trading_enabled===false &&
             history.live_trading_enabled===false) setData(history)
        } catch { /* Saved checkpoint continues training independently of the feed. */ }
        return
      }
      const hist = await api<History>('/v1/students/'+encodeURIComponent(studentId)+'/train-data')
      if(!hist.bars?.length || hist.bars.length<96 || hist.student_id!==studentId || hist.training_kind!=='historical_policy_replay') throw new Error('Insufficient historical research observations')
      // Do not silently train on a market outside the CEO student's plan.
      const scope = chosen?.learning_plan
      if(scope?.mode==='directed' && !scope.markets.includes(hist.market)) throw new Error('Fetched market does not match student learning scope')
      if(hist.neural_training_performed!==false || hist.paper_trading_enabled!==false || hist.live_trading_enabled!==false) throw new Error('Invalid non-research training source')
      setData(hist);setStage('running')
      try{
        const started=await api<NeuralReport>('/v1/students/'+encodeURIComponent(studentId)+'/neural/start','POST',{})
        setNeural(started);setNeuralActive(started.epoch<started.epochs_planned)
      }catch(e){setNeuralError('Neural weights not trained: '+(e instanceof Error?e.message:'No eligible data'))}
    } catch(e){setStage('idle');setError(e instanceof Error?e.message:'Automatic research import failed')}
  }
  return <section className="surface panel tc-panel" aria-label="Student training cockpit">
    <div className="tc-head"><div><p className="eyebrow">AUTOMATIC HISTORICAL RESEARCH</p><h2>Train a student</h2>
      <p>Pick a student. Press Train. Watch their simulated research progress.</p></div>
      <span className="pill pill-blue">NO BROKER ORDERS</span></div>
    <div className="tc-action">
      <label htmlFor="tc-student">Student
        <select id="tc-student" aria-label="Choose student to train" value={studentId}
          disabled={stage==='fetching'||stage==='running'||neuralActive}
          onChange={e=>{setStudentId(e.target.value);setData(null);setNeural(null);setNeuralActive(false);setStage('idle');setError('')}} >
          <option value="">Choose a student…</option>
          {students.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </label>
      {stage==='running'||neuralActive ? <button className="btn btn-secondary tc-button" onClick={()=>{setStage('stopped');setNeuralActive(false)}}><Square size={17}/> Stop</button> :
        <button className="btn btn-primary tc-button" disabled={!studentId||stage==='fetching'||!allowed.length}
          onClick={()=>{if(stage==='stopped'&&(data||(neural&&neural.can_resume))){setStage('running');setNeuralActive(Boolean(neural?.can_resume))}else void train()}}>
          <Play size={17}/> {stage==='fetching'?'Preparing training…':stage==='stopped'?'Resume':'Train'}
        </button>}
    </div>
    {!students.length && <p className="tc-muted">Create your first student under Students, then return here to train.</p>}
    {chosen && <p className="tc-muted">Automatic market: {chosen.learning_plan.mode==='autonomous'?'XAUUSD archive if available; otherwise BTC/USD feed':chosen.learning_plan.markets.join(', ')}. Strategy targets: {allowed.length?allowed.join(', '):'No replay-compatible strategy'}.</p>}
    {stage==='fetching' && <div className="tc-status" role="status"><Activity size={18}/> Importing and verifying historical candles automatically…</div>}
    {error && <div className="message-error" role="alert"><ShieldAlert size={16}/>{error}</div>}
    {neuralError && <div className="message-error" role="alert"><ShieldAlert size={16}/>{neuralError}</div>}
    {neural && <ResearchNeuralStatus run={neural} active={neuralActive}/>}
    {data && neural && <NeuralSignalForecast run={neural} bars={data.bars} cursor={cursor} market={data.market} studentId={studentId}/>}
    {data && current && <>
      <div className="tc-running-head"><span className="online-dot"/><strong>{stage==='running'?'Training replay active':stage==='complete'?'Research replay complete':'Research replay paused'}</strong><span>{data.market} · {data.provider}</span></div>
      <div className="tc-progress"><div className="tc-progress-top"><span>Candles processed</span><strong>{(cursor+1).toLocaleString('en-GB')} / {timeline.length.toLocaleString('en-GB')} · {pct((cursor+1)/timeline.length*100)}</strong></div><progress max={timeline.length} value={cursor+1}/></div>
      <div className="tc-stats">
        <div><span>Hypothetical net P&amp;L</span><strong className={current.pnl<0?'tc-loss':'tc-gain'}>{money(current.pnl)}</strong></div>
        <div><span>Win rate</span><strong>{current.trades?pct(100*current.wins/current.trades):'—'}</strong></div>
        <div><span>Completed example trades</span><strong>{current.trades}</strong></div>
        <div><span>Max drawdown</span><strong>{pct(current.drawdown)}</strong></div>
        <div><span>Research batches</span><strong>{Math.floor((cursor+1)/BATCH)}</strong></div>
        <div><span>Policy updates</span><strong>{current.switchCount}</strong></div>
      </div>
      <EquityChart points={visible}/>
      <div className="tc-explainer"><div><BrainCircuit size={19}/><strong>Current research rule</strong><span>{current.rule}</span></div>
        <p>{current.lastSignal}. Strategy selector reviews the previous five completed 96-candle batches; changes apply only to future observations. The historical selector alone does not update neural weights; the separate neural learner saves real checkpoint versions.</p></div>
      <p className="tc-muted">Source: {data.provider} · {data.bars.length} M15 candles · {data.gap_count} data gaps · unverified research data. Assumed costs: {data.market==='BTCUSD'?'0.001 BTC, 0.20% round-trip notional':'0.10 oz, $1/oz round-trip'}. Every result is hypothetical next-bar open-to-close, not broker fills.</p>
    </>}
    {!data && stage==='idle' && !error && <div className="tc-intro"><BarChart3 size={27}/><strong>Choose a student and press Train</strong><p>No datasets to upload, no manual rules or setup steps.</p></div>}
    <div className="historical-warning"><ShieldAlert size={15}/> Historical policy replay is not a trained neural checkpoint and does not create persistent learning memories. Separately, the CPU neural learner saves real weights and losses for completed training examples, but these remain unqualified and cannot validate profitability or enable paper/live trading. Unavailable source data blocks training rather than inventing statistics.</div>
  </section>
}
