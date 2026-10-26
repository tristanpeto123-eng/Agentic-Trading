import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import { Activity, BarChart3, Pause, Play, RotateCcw, ShieldAlert } from 'lucide-react'

type PricePoint = { time: string; close: string }
type EquityPoint = { time: string; equity: string }
type Trade = {
  proposal_id: string; direction: 'LONG' | 'SHORT'
  status: 'CLOSED' | 'REJECTED' | 'UNRESOLVED'
  entry_at: string | null; exit_at: string | null
  entry_fill: string | null; exit_fill: string | null
  net_pnl_usd: string | null; exit_reason: string | null
}
type Demo = {
  synthetic: true; student_model_generated: false; qualification_eligible: false
  paper_trading_enabled: false; live_trading_enabled: false
  market: string; timeframe: string; warnings: string[]
  prices: PricePoint[]; equity: EquityPoint[]; trades: Trade[]
  metrics: { starting_equity_usd: string; ending_equity_usd: string; net_pnl_usd: string
    max_drawdown_fraction: string; win_rate_pct: string; closed: number; wins: number
    losses: number; rejected: number; unresolved: number; journal_sha256: string }
}

const cash = (v: number) => Number.isFinite(v)
  ? new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'USD' }).format(v) : '—'
const fmt = (v: number) => Number.isFinite(v) ? v.toFixed(2) : '—'
const asTime = (s: string) => new Date(s).getTime()

function ReplayLine({ values, times, label, color, markers }: {
  values: number[]; times: string[]; label: string; color: string
  markers?: { time: string; label: string; kind: 'entry' | 'exit' }[]
}) {
  if (!values.length) return null
  const lo = Math.min(...values), hi = Math.max(...values)
  const margin = Math.max((hi - lo) * .13, .12)
  const min = lo - margin, max = hi + margin
  const left = 38, top = 27, innerW = 798, innerH = 207
  const x = (i: number) => left + (values.length === 1 ? 0 : i * innerW / (values.length - 1))
  const y = (v: number) => top + (max - v) / (max - min) * innerH
  const path = values.map((v, i) => String(x(i)) + ',' + String(y(v))).join(' ')
  return <svg viewBox="0 0 930 270" className="demo-chart" role="img" aria-label={label} preserveAspectRatio="xMidYMid meet">
    <rect x="0.5" y="0.5" width="929" height="269" rx="13" fill="#091725" stroke="#263b50"/>
    {[0, 1, 2, 3, 4].map(i => {
      const value = max - (max - min) * i / 4
      return <g key={i}>
        <line x1={left} x2={837} y1={y(value)} y2={y(value)} stroke="#2b4254" strokeDasharray="3 7"/>
        <text x="851" y={y(value) + 4} fontSize="13" fill="#a7c2cf">{fmt(value)}</text>
      </g>
    })}
    <polyline points={path} fill="none" stroke={color} strokeWidth="2.7" strokeLinejoin="round"/>
    {(markers ?? []).map((marker, n) => {
      const at = times.findIndex(t => asTime(t) >= asTime(marker.time))
      if (at < 0 || at >= values.length) return null
      return <g key={marker.time + marker.label + n}>
        <circle cx={x(at)} cy={y(values[at])} r="7" fill={marker.kind === 'entry' ? '#61c8a6' : '#e6bb6d'} stroke="#081525" strokeWidth="2"/>
        <title>{marker.label + ' · ' + marker.time}</title>
      </g>
    })}
    <text x="38" y="18" fill="#bad9e5" fontSize="13">{label}</text>
    <text x="38" y="256" fill="#89a9bd" fontSize="12">
      {times[0] ? new Date(times[0]).toLocaleString('en-GB', { timeZone: 'UTC', dateStyle: 'short', timeStyle: 'short' }) + ' UTC' : ''}
    </text>
    <text x="838" y="256" textAnchor="end" fill="#89a9bd" fontSize="12">
      {times.length ? new Date(times[times.length-1]).toLocaleTimeString('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit' }) + ' UTC' : ''}
    </text>
  </svg>
}

export function HistoricalDemoLab() {
  const [data, setData] = useState<Demo | null>(null)
  const [error, setError] = useState('')
  const [index, setIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(3)
  useEffect(() => {
    let active = true
    void api<Demo>('/v1/historical/demo').then(r => {
      if (active) { setData(r); setIndex(0) }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : 'Historical demo unavailable') })
    return () => { active = false }
  }, [])
  useEffect(() => {
    if (!playing || !data) return
    const timer = window.setInterval(() => {
      setIndex(i => Math.min(i + speed, data.prices.length - 1))
    }, 150)
    return () => window.clearInterval(timer)
  }, [playing, data, speed])
  useEffect(() => {
    if (data && index >= data.prices.length - 1) setPlaying(false)
  }, [index, data])
  const view = useMemo(() => {
    if (!data) return null
    const last = Math.min(index, data.prices.length - 1)
    const windowStart = Math.max(0, last - 89)
    const pts = data.prices.slice(windowStart, last + 1)
    const eq = data.equity.slice(windowStart, last + 1)
    const at = asTime(data.equity[last].time)
    const completed = data.trades.filter(t => t.status === 'CLOSED' && t.exit_at && asTime(t.exit_at) <= at)
    const wins = completed.filter(t => Number(t.net_pnl_usd) > 0).length
    const currentEquity = Number(data.equity[last].equity)
    const start = Number(data.metrics.starting_equity_usd)
    const equityHistory = data.equity.slice(0, last + 1).map(t => Number(t.equity))
    let peak = start, dd = 0
    for (const value of equityHistory) {
      peak = Math.max(value, peak)
      if (peak > 0) dd = Math.max(dd, (peak - value) / peak)
    }
    const markers = data.trades.flatMap(t => {
      const list: { time: string; label: string; kind: 'entry' | 'exit' }[] = []
      if (t.entry_at && asTime(t.entry_at) <= at) list.push({ time: t.entry_at, label: t.direction + ' entry', kind: 'entry' })
      if (t.exit_at && asTime(t.exit_at) <= at) list.push({ time: t.exit_at, label: 'Exit · ' + cash(Number(t.net_pnl_usd)), kind: 'exit' })
      return list
    })
    return { pts, eq, at, completed, wins, currentEquity, start, dd, markers }
  }, [data, index])
  return <section className="surface panel historical-replay historical-demo-lab" aria-label="Synthetic historical trading simulation demonstration">
    <div className="panel-heading">
      <div><p className="eyebrow">HISTORICAL SIMULATOR · ENGINE DEMO</p><h3>Trade and P&amp;L replay</h3></div>
      <span className="pill pill-amber"><Activity size={13}/> SYNTHETIC ONLY</span>
    </div>
    <div className="historical-body">
      <p className="skills-disclaimer"><strong>This is a functional demo of the conservative M1 bid/ask replay engine.</strong> The candles and fixed trade signals are entirely invented. The trades are <strong>not</strong> generated by a trained student, and the P&amp;L is not evidence of market profitability.</p>
      {error && <p role="alert" className="message-error">{error}</p>}
      {!data && !error && <p className="muted">Loading historical engine fixture…</p>}
      {data && view && <>
        <div className="historical-figures demo-figures">
          <div><span>Simulated equity</span><strong>{cash(view.currentEquity)}</strong></div>
          <div><span>Net P&amp;L after costs</span><strong>{cash(view.currentEquity - view.start)}</strong></div>
          <div><span>Closed trades</span><strong>{view.completed.length} / {data.trades.length}</strong></div>
          <div><span>Win rate</span><strong>{view.completed.length ? fmt(view.wins * 100 / view.completed.length) + '%' : '—'}</strong></div>
          <div><span>Max drawdown</span><strong>{fmt(view.dd * 100)}%</strong></div>
        </div>
        <div className="demo-chart-stack">
          <ReplayLine values={view.pts.map(p => Number(p.close))} times={view.pts.map(p => p.time)}
            label="XAUUSD synthetic M1 bid price · green: entry, amber: exit" color="#6dbdda" markers={view.markers}/>
          <ReplayLine values={view.eq.map(p => Number(p.equity))} times={view.eq.map(p => p.time)}
            label="Simulated account equity (USD), realised net after costs" color="#82cba4"/>
        </div>
        <div className="historical-scrubber">
          <label htmlFor="demo-historical-timeline">Replay candle {index + 1} / {data.prices.length} · {new Date(view.at).toLocaleString('en-GB', {timeZone: 'UTC'})} UTC</label>
          <input id="demo-historical-timeline" type="range" min={0} max={data.prices.length - 1}
            value={index} onChange={e => { setPlaying(false); setIndex(Number(e.target.value)) }}/>
        </div>
        <div className="historical-actions">
          <button className="btn btn-primary" type="button" onClick={() => {
            if (index >= data.prices.length - 1) setIndex(0)
            setPlaying(p => !p)
          }}>{playing ? <Pause size={15}/> : <Play size={15}/>} {playing ? 'Pause' : 'Run historical demo'}</button>
          <button className="btn btn-secondary" type="button" onClick={() => { setPlaying(false); setIndex(0) }}><RotateCcw size={15}/> Reset</button>
          <label className="demo-speed">Speed
            <select value={speed} onChange={e => setSpeed(Number(e.target.value))}>
              <option value={1}>1×</option><option value={3}>3×</option><option value={10}>10×</option>
            </select>
          </label>
        </div>
        <div className="demo-trade-list">
          <h4><BarChart3 size={15}/> Closed trade journal (revealed chronologically)</h4>
          {view.completed.length === 0 ? <p className="muted">No closed trades yet. Press Run to begin.</p>
            : view.completed.map(trade => <div className="demo-trade-row" key={trade.proposal_id}>
                <span>{trade.direction} · {trade.exit_reason || 'Closed'}</span>
                <strong>{cash(Number(trade.net_pnl_usd))}</strong>
              </div>)}
        </div>
      </>}
      <p className="historical-warning"><ShieldAlert size={14}/> This demonstration runs on fabricated test data. Importing M15 candles does not provide the bid/ask M1 tape required for defendable historical trade P&amp;L. Model training, real market simulation, paper and live trading remain disabled.</p>
    </div>
  </section>
}
