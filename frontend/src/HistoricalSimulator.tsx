import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, ChevronRight, FileUp, Pause, Play, RotateCcw, ShieldAlert, SkipForward, StepForward } from 'lucide-react'
import { api } from './api'
import type { HistoricalDataset, Student } from './api'
import { parseLocalHistoricalCsv } from './BrowserCsvReplay'
import type { Candle } from './HistoricalResearch'
import './HistoricalSimulator.css'

type Rule = 'trend' | 'range' | 'breakout'
type Action = 'BUY' | 'SELL' | 'WAIT'
type Decision = { action: Action; reason: string; guard: string; time: string; index: number; pnl: number | null }
type Page = { bars: Candle[]; has_more: boolean; total_rows: number }
const BARS_PER_PAGE = 360
const MAX_SAVED_PAGES = 12
const LOOKBACK = 4
const COST_USD = 0.10 // Illustrative XAUUSD 0.10oz * USD1.00/oz round-trip
const POSITION_OZ = 0.10
const money = (value: number) => new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'USD' }).format(value)
const stamp = (s: string) => new Date(s).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC'

function decisionAt(bars: Candle[], index: number, rule: Rule): Decision {
  const now = bars[index]
  const time = now?.available_at ?? ''
  const base = { index, time, action: 'WAIT' as Action, pnl: null, reason: '', guard: '' }
  if (index < LOOKBACK) return { ...base, guard: 'WAITING', reason: 'Collecting four completed candles before evaluating signals.' }
  const last = bars[index]
  const previous = bars[index - 1]
  // Only observations available at the close of this candle are used.
  for (let j = index - LOOKBACK + 1; j <= index; j++) {
    if (Date.parse(bars[j].open_time) - Date.parse(bars[j - 1].open_time) !== 900000)
      return { ...base, guard: 'DATA GAP', reason: 'A 15-minute candle is missing from the lookback. Abstain; do not fill missing prices.' }
  }
  const close = Number(last.close)
  const prev = Number(previous.close)
  if (!Number.isFinite(close) || !Number.isFinite(prev) || prev <= 0)
    return { ...base, guard: 'INVALID PRICE', reason: 'Price guard rejected this observation.' }
  if (Math.abs(close / prev - 1) > .04)
    return { ...base, guard: 'VOLATILITY', reason: 'Price moved more than 4% in one candle. Protective abstention.' }
  let sign = 0
  let reason = ''
  if (rule === 'trend') {
    sign = Math.sign(close - prev)
    reason = sign > 0 ? 'Trend baseline: latest close rose versus previous completed close.' :
      sign < 0 ? 'Trend baseline: latest close fell versus previous completed close.' : 'No change in the latest close.'
  } else if (rule === 'range') {
    sign = -Math.sign(close - prev)
    reason = sign > 0 ? 'Range baseline: fading the latest downward close.' :
      sign < 0 ? 'Range baseline: fading the latest upward close.' : 'No change to fade.'
  } else {
    const prior = bars.slice(index - LOOKBACK, index)
    const ceiling = Math.max(...prior.map(bar => Number(bar.high)))
    const floor = Math.min(...prior.map(bar => Number(bar.low)))
    sign = Number(close > ceiling) - Number(close < floor)
    reason = sign > 0 ? 'Breakout baseline: close exceeded the highs of the previous four completed candles.' :
      sign < 0 ? 'Breakout baseline: close fell below the lows of the previous four completed candles.' :
      'No break of the previous four-candle range. Remain flat.'
  }
  return { ...base, action: sign > 0 ? 'BUY' : sign < 0 ? 'SELL' : 'WAIT', guard: 'CLEAR', reason }
}

export function calculateResearchDecisions(bars: Candle[], rule: Rule): Decision[] {
  return bars.map((bar, index) => {
    const decision = decisionAt(bars, index, rule)
    if (decision.action === 'WAIT' || index + 1 >= bars.length) return decision
    const next = bars[index + 1]
    if (Date.parse(next.open_time) !== Date.parse(bar.available_at))
      return { ...decision, pnl: null, guard: 'NEXT BAR GAP', reason: decision.reason + ' Next-bar outcome unavailable across a gap.' }
    const movement = Number(next.close) - Number(next.open)
    const sign = decision.action === 'BUY' ? 1 : -1
    return { ...decision, pnl: sign * movement * POSITION_OZ - COST_USD }
  })
}

function DecisionChart({ bars, decisions, cursor }: { bars: Candle[]; decisions: Decision[]; cursor: number }) {
  const first = Math.max(0, cursor - 65)
  const shown = bars.slice(first, cursor + 1)
  if (!shown.length) return null
  const prices = shown.flatMap(b => [Number(b.high), Number(b.low)])
  const highest = Math.max(...prices), lowest = Math.min(...prices)
  const pad = Math.max((highest - lowest) * .16, .01)
  const min = lowest - pad, max = highest + pad
  const y = (value: number) => 24 + (max - value) / (max - min) * 218
  const x = (index: number) => 24 + (index + .5) * 744 / shown.length
  const bodyWidth = Math.max(2.4, Math.min(10, 744 / shown.length * .64))
  return <svg className="simulation-chart" viewBox="0 0 840 285" role="img"
    aria-label="Historical price chart with research BUY and SELL decisions" preserveAspectRatio="xMidYMid meet">
    <rect x=".5" y=".5" width="839" height="284" rx="12" fill="#081525" stroke="#284458"/>
    {[0, 1, 2, 3, 4].map(n => {
      const level = max - (max - min) * n / 4
      return <g key={n}><line x1="18" x2="771" y1={y(level)} y2={y(level)} stroke="#263a50" strokeDasharray="3 7"/>
        <text x="781" y={y(level) + 4} fill="#96aebe" fontSize="12">{level.toFixed(2)}</text></g>
    })}
    {shown.map((bar, i) => {
      const idx = first + i, dec = decisions[idx]
      const up = Number(bar.close) >= Number(bar.open)
      const color = up ? '#65cab5' : '#ed8897'
      const xx = x(i)
      return <g key={bar.open_time}>
        <line x1={xx} x2={xx} y1={y(Number(bar.high))} y2={y(Number(bar.low))} stroke={color} strokeWidth="1.6"/>
        <rect x={xx - bodyWidth / 2} y={Math.min(y(Number(bar.open)), y(Number(bar.close)))}
          width={bodyWidth} height={Math.max(1.9, Math.abs(y(Number(bar.open)) - y(Number(bar.close))))} rx="1" fill={color}/>
        {dec.action !== 'WAIT' && <g>
          <circle cx={xx} cy={dec.action === 'BUY' ? y(Number(bar.low)) + 11 : y(Number(bar.high)) - 11}
            r="6" fill={dec.action === 'BUY' ? '#70e3af' : '#e7b56a'} stroke="#071421" strokeWidth="2"/>
          <title>{dec.action + ': ' + dec.reason + ' at ' + stamp(dec.time)}</title>
        </g>}
      </g>
    })}
    <text x="19" y="269" fill="#91acbd" fontSize="11">{stamp(shown[0].open_time)}</text>
    <text x="766" y="269" fill="#91acbd" fontSize="11" textAnchor="end">{stamp(shown[shown.length - 1].open_time)}</text>
    <text x="22" y="16" fill="#badce5" fontSize="11">M15 · completed candles only · green BUY / amber SELL</text>
  </svg>
}

export function HistoricalSimulator({ students }: { students: Student[] }) {
  const [bars, setBars] = useState<Candle[]>([])
  const [source, setSource] = useState('')
  const [gaps, setGaps] = useState(0)
  const [saved, setSaved] = useState<HistoricalDataset[]>([])
  const [selectedSaved, setSelectedSaved] = useState('')
  const [studentId, setStudentId] = useState('')
  const [rule, setRule] = useState<Rule>('breakout')
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [truncated, setTruncated] = useState(false)
  const chosen = students.find(s => s.id === studentId)
  const permitted = (['trend', 'range', 'breakout'] as Rule[]).filter(r =>
    !chosen || chosen.learning_plan.mode === 'autonomous' ||
    (chosen.learning_plan.markets.includes('XAUUSD') && chosen.learning_plan.skills.includes(r)))
  const selectedRule = permitted.includes(rule) ? rule : permitted[0] ?? null
  const decisions = useMemo(() => selectedRule ? calculateResearchDecisions(bars, selectedRule) : [], [bars, selectedRule])
  const current = decisions[cursor]
  const visibleTrades = useMemo(() => decisions.slice(0, cursor).filter(d => d.pnl !== null), [decisions, cursor])
  const net = visibleTrades.reduce((sum, d) => sum + (d.pnl ?? 0), 0)
  const wins = visibleTrades.filter(d => (d.pnl ?? 0) > 0).length
  const upcoming = decisions.find(d => d.index > cursor && d.action !== 'WAIT')
  const lastDecisions = decisions.slice(Math.max(0, cursor - 19), cursor + 1).filter(d => d.action !== 'WAIT').slice(-8).reverse()

  useEffect(() => {
    let active = true
    void api<HistoricalDataset[]>('/v1/datasets').then(items => { if (active) setSaved(items) })
      .catch(() => { if (active) setSaved([]) })
    return () => { active = false }
  }, [])
  useEffect(() => {
    if (!playing || !bars.length) return
    const timer = window.setInterval(() => setCursor(index => Math.min(bars.length - 1, index + speed)), 190)
    return () => window.clearInterval(timer)
  }, [playing, bars.length, speed])
  useEffect(() => {
    if (playing && cursor >= bars.length - 1) setPlaying(false)
  }, [cursor, playing, bars.length])

  const loadFile = async (file: File | undefined) => {
    setPlaying(false); setError(''); setBusy(true)
    try {
      if (!file) return
      if (file.size > 12 * 1024 * 1024) throw new Error('CSV exceeds the 12 MiB local safety limit.')
      const result = parseLocalHistoricalCsv(await file.text(), Date.now())
      setBars(result.bars); setSource(file.name); setGaps(result.gaps); setTruncated(false)
      setCursor(Math.min(39, result.bars.length - 1))
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load CSV') }
    finally { setBusy(false) }
  }
  const loadSaved = async () => {
    if (!selectedSaved) { setError('Choose a saved dataset.'); return }
    setPlaying(false); setError(''); setBusy(true)
    try {
      let before = ''
      let pages: Candle[][] = []
      let more = true
      let total = 0
      for (let p = 0; p < MAX_SAVED_PAGES && more; p++) {
        const url = '/v1/datasets/' + encodeURIComponent(selectedSaved) + '/candles?limit=' + BARS_PER_PAGE +
          (before ? '&before=' + encodeURIComponent(before) : '')
        const result = await api<Page>(url)
        if (!result.bars.length) break
        pages = [result.bars, ...pages]
        total += result.bars.length
        more = result.has_more
        before = result.bars[0].open_time
      }
      const data = pages.flat()
      if (!data.length) throw new Error('This dataset has no available candles.')
      const boundaries = data.reduce((sum, item, index) =>
        index && Date.parse(item.open_time) - Date.parse(data[index - 1].open_time) !== 900000 ? sum + 1 : sum, 0)
      setBars(data); setGaps(boundaries)
      setSource('Saved XAUUSD archive · ' + (saved.find(d => d.id === selectedSaved)?.provider ?? 'historical'))
      setTruncated(more); setCursor(Math.min(39, data.length - 1))
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load saved archive') }
    finally { setBusy(false) }
  }
  return <section className="surface panel sim-panel" aria-label="Historical Simulation">
    <div className="panel-heading"><div><p className="eyebrow">RESEARCH COCKPIT · XAUUSD M15</p>
      <h3>Historical Simulation</h3></div><span className="pill pill-blue">LOCAL DECISIONS · NO ORDERS</span></div>
    <div className="sim-body">
      <p className="sim-lead">Load historical candles, select a student profile and research rule, then watch every BUY, SELL or WAIT decision as it happens. This is a transparent <strong>rule baseline</strong>, not a trained neural student.</p>
      <div className="sim-steps">
        <div className="sim-step"><span className="sim-step-number">1</span><div className="sim-step-main">
          <h4>Load historical data</h4>
          <label className="sim-upload"><FileUp size={18}/> Choose M15 CSV from Files
            <input aria-label="Load M15 historical CSV" type="file" accept=".csv,text/csv" disabled={busy}
              onChange={e => { void loadFile(e.target.files?.[0]); e.target.value = '' }}/>
          </label>
          {!!saved.length && <div className="sim-saved">
            <label htmlFor="sim-saved-select">Or load a saved dataset</label>
            <select id="sim-saved-select" value={selectedSaved} onChange={e => setSelectedSaved(e.target.value)}>
              <option value="">Choose imported archive…</option>
              {saved.map(d => <option key={d.id} value={d.id}>{d.provider} · {d.quality_report.rows.toLocaleString('en-GB')} bars</option>)}
            </select>
            <button className="btn btn-secondary" disabled={!selectedSaved || busy} onClick={() => void loadSaved()}>Load saved <ArrowRight size={14}/></button>
          </div>}
          <small className="muted">CSV columns: timestamp_open (or time), open, high, low, close [,volume]. UTC, 15-minute candles. Device files stay in this browser session.</small>
        </div></div>
        <div className="sim-step"><span className="sim-step-number">2</span><div className="sim-step-main">
          <h4>Choose who and how to evaluate</h4>
          <div className="sim-options">
            <label>Student context
              <select aria-label="Simulation student" value={studentId} onChange={e => { setPlaying(false); setStudentId(e.target.value) }}>
                <option value="">Research baseline · no student</option>
                {students.map(student => <option key={student.id} value={student.id}>{student.name} · profile only</option>)}
              </select>
            </label>
            <label>Decision rule
              <select aria-label="Simulation rule" value={selectedRule ?? ''} disabled={!permitted.length}
                onChange={e => { setPlaying(false); setRule(e.target.value as Rule) }}>
                {!permitted.length && <option value="">No XAUUSD rule in plan</option>}
                {permitted.map(r => <option key={r} value={r}>{r === 'trend' ? 'Trend following' : r === 'range' ? 'Range reversal' : '4-candle breakout'}</option>)}
              </select>
            </label>
          </div>
          {chosen && <small className="muted">{chosen.name} is used only to scope permitted research rules. No stored neural checkpoint is running and the student is not learning from this replay.</small>}
          {!permitted.length && <p className="message-error" role="alert">This student's plan has no XAUUSD trend, range or breakout target. Choose another student or the standalone baseline.</p>}
        </div></div>
      </div>

      {error && <p className="message-error" role="alert">{error}</p>}
      {busy && <p className="muted" role="status">Verifying historical candles and preparing timeline…</p>}
      {!bars.length && !busy && <div className="sim-empty"><FileUp size={23}/><strong>Ready for your historical dataset</strong>
        <span>Load an XAUUSD M15 CSV above to start replaying actual archived candles, rather than the invented engine demo.</span></div>}
      {!!bars.length && selectedRule && <>
        <div className="sim-loaded"><strong>{source}</strong><span>{bars.length.toLocaleString('en-GB')} completed candles · {gaps} gaps · unverified archive</span></div>
        {truncated && <p className="sim-note">Displaying the latest {bars.length.toLocaleString('en-GB')} saved candles. For the full historical archive, select its original CSV from Files.</p>}
        <div className="sim-dashboard">
          <div><span>Candle</span><strong>{(cursor + 1).toLocaleString('en-GB')} / {bars.length.toLocaleString('en-GB')}</strong></div>
          <div><span>Decisions to trade</span><strong>{decisions.slice(0, cursor + 1).filter(d => d.action !== 'WAIT').length}</strong></div>
          <div><span>Closed hypothetical outcomes</span><strong>{visibleTrades.length}</strong></div>
          <div><span>Net assumed P&amp;L</span><strong className={net < 0 ? 'sim-negative' : 'sim-positive'}>{money(net)}</strong></div>
          <div><span>Win rate</span><strong>{visibleTrades.length ? (wins * 100 / visibleTrades.length).toFixed(1) + '%' : '—'}</strong></div>
        </div>
        <DecisionChart bars={bars} decisions={decisions} cursor={cursor}/>
        <div className="sim-control-panel">
          <label htmlFor="simulation-timeline">3 · Replay timeline — {stamp(bars[cursor].available_at)}</label>
          <input id="simulation-timeline" type="range" min={0} max={bars.length - 1} value={cursor}
            onChange={e => { setPlaying(false); setCursor(Number(e.target.value)) }}/>
          <div className="sim-controls">
            <button type="button" className="btn btn-primary" onClick={() => {
              if (cursor >= bars.length - 1) setCursor(0)
              setPlaying(state => !state)
            }}>{playing ? <Pause size={15}/> : <Play size={15}/>} {playing ? 'Pause replay' : 'Start replay'}</button>
            <button type="button" className="btn btn-secondary" disabled={cursor >= bars.length - 1}
              onClick={() => { setPlaying(false); setCursor(i => Math.min(i + 1, bars.length - 1)) }}><StepForward size={15}/> Step</button>
            <button type="button" className="btn btn-secondary" disabled={!upcoming}
              onClick={() => { setPlaying(false); if (upcoming) setCursor(upcoming.index) }}><SkipForward size={15}/> Next decision</button>
            <button type="button" className="btn btn-secondary" onClick={() => { setPlaying(false); setCursor(0) }}><RotateCcw size={15}/> Reset</button>
            <label>Speed
              <select aria-label="Simulation speed" value={speed} onChange={e => setSpeed(Number(e.target.value))}>
                <option value={1}>1×</option><option value={5}>5×</option><option value={20}>20×</option>
              </select>
            </label>
          </div>
        </div>
        {current && <div className="sim-decision" role="status" aria-live="off">
          <div className="sim-decision-head"><div><p className="eyebrow">DECISION · CANDLE CLOSE</p><h4>Why did the rule choose this?</h4></div>
            <span className={'sim-action sim-' + current.action.toLowerCase()}>{current.action}</span></div>
          <p>{current.reason}</p>
          <div className="sim-detail-grid">
            <span>Policy: <strong>{selectedRule}</strong></span>
            <span>Guardian data check: <strong>{current.guard}</strong></span>
            <span>Time: <strong>{stamp(current.time)}</strong></span>
          </div>
          {current.action !== 'WAIT' && <p className="sim-note">Signal observed at this completed candle close. Illustrative entry is the NEXT candle's recorded open, and exit its close. It cannot know that next-bar result yet.</p>}
        </div>}
        <div className="sim-journal"><h4>Decision journal <ChevronRight size={15}/></h4>
          {lastDecisions.length ? lastDecisions.map(d => <div className="sim-journal-row" key={d.index}>
            <span className={'sim-action sim-' + d.action.toLowerCase()}>{d.action}</span>
            <div><strong>{stamp(d.time)}</strong><small>{d.reason}</small></div>
            <span>{d.index < cursor && d.pnl !== null ? money(d.pnl) : 'Pending'}</span>
          </div>) : <p className="muted">No BUY or SELL signal yet. Step forward or select Next decision.</p>}
        </div>
      </>}
      <div className="historical-warning"><ShieldAlert size={15}/> This is a **rule-based replay**, not a trained neural model or approved trading bot. P&amp;L uses unverified M15 open/close prices and assumed fixed costs, with no real quotes, broker fills, stops, latency, margin or funding. It sends NO orders and writes NO student training memories.</div>
    </div>
  </section>
}
