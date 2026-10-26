import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from './api'
import type { HistoricalDataset } from './api'
import { Activity, ArrowLeft, Database, Pause, Play, RefreshCw, ShieldAlert } from 'lucide-react'

type Candle = {
  open_time: string
  available_at: string
  open: string
  high: string
  low: string
  close: string
  volume: string | null
}
type CandlePage = {
  dataset_id: string
  bars: Candle[]
  has_more: boolean
  total_rows: number
  source_verified: false
  research_eligible: false
  historical_execution_enabled: false
  note: string
}
const LAST = 62
const fmt = (value: number) => Number.isFinite(value) ? value.toFixed(2) : '—'
const when = (s: string) => s ? new Date(s).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC' : '—'

function CandleChart({ candles }: { candles: Candle[] }) {
  const plotted = useMemo(() => {
    return candles.map((c) => ({ ...c, o: Number(c.open), h: Number(c.high), l: Number(c.low), cl: Number(c.close) }))
      .filter(c => [c.o, c.h, c.l, c.cl].every(Number.isFinite))
  }, [candles])
  if (!plotted.length) return <div className="dataset-empty">No valid candle values to draw.</div>
  const hi = Math.max(...plotted.map(c => c.h))
  const lo = Math.min(...plotted.map(c => c.l))
  const padding = Math.max((hi - lo) * 0.12, 0.15)
  const minY = lo - padding
  const maxY = hi + padding
  const y = (price: number) => 28 + (maxY - price) / (maxY - minY) * 269
  const step = 749 / plotted.length
  return <svg className="historical-candle-chart" viewBox="0 0 860 348" role="img"
    aria-label="Historical XAUUSD M15 candlestick price chart, research only">
    <rect x="1" y="1" width="858" height="346" rx="12" fill="#081525" stroke="#233b4e"/>
    {[0, 1, 2, 3, 4].map(i => {
      const price = minY + (maxY - minY) * (4 - i) / 4
      const lineY = y(price)
      return <g key={i}><line x1="22" x2="768" y1={lineY} y2={lineY} stroke="#244056" strokeDasharray="4 8"/>
        <text x="780" y={lineY + 4} fontSize="12" fill="#91aabb">{fmt(price)}</text></g>
    })}
    {plotted.map((c, i) => {
      const x = 24 + i * step + step / 2
      const up = c.cl >= c.o
      const color = up ? '#61c8a6' : '#f08c91'
      const highY = y(c.h), lowY = y(c.l), openY = y(c.o), closeY = y(c.cl)
      return <g key={c.open_time}>
        <line x1={x} y1={highY} x2={x} y2={lowY} stroke={color} strokeWidth="1.6"/>
        <rect x={x - Math.max(1, Math.min(5, step * .36))} y={Math.min(openY, closeY)}
          width={Math.max(2, Math.min(10, step * .72))} height={Math.max(1.7, Math.abs(openY - closeY))}
          rx=".6" fill={color}/>
        <title>{when(c.open_time)} | O {fmt(c.o)} H {fmt(c.h)} L {fmt(c.l)} C {fmt(c.cl)}</title>
      </g>
    })}
    <text x="22" y="328" fontSize="12" fill="#94a9ba">{when(plotted[0].open_time)}</text>
    <text x="768" y="328" fontSize="12" fill="#94a9ba" textAnchor="end">{when(plotted[plotted.length-1].open_time)}</text>
    <text x="28" y="19" fontSize="12" fill="#9acedd">XAUUSD / M15 · Historical candles · Not a P&amp;L chart</text>
  </svg>
}

export function HistoricalResearch() {
  const [datasets, setDatasets] = useState<HistoricalDataset[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [page, setPage] = useState<CandlePage | null>(null)
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const reloadDatasets = useCallback(() => {
    void api<HistoricalDataset[]>('/v1/datasets').then(items => {
      setDatasets(items)
      setSelectedId(prev => items.some(x => x.id === prev) ? prev : items[0]?.id ?? '')
    }).catch(e => setError(e instanceof Error ? e.message : String(e)))
  }, [])
  useEffect(() => { reloadDatasets() }, [reloadDatasets])
  const loadPage = useCallback(async (id: string, before?: string) => {
    if (!id) { setPage(null); return }
    setBusy(true); setPlaying(false); setError('')
    try {
      const route = '/v1/datasets/' + encodeURIComponent(id) + '/candles?limit=240' +
        (before ? '&before=' + encodeURIComponent(before) : '')
      const data = await api<CandlePage>(route)
      setPage(data)
      setCursor(Math.max(0, data.bars.length - 1))
    } catch (err) {
      setPage(null)
      setError(err instanceof Error ? err.message : String(err))
    } finally { setBusy(false) }
  }, [])
  useEffect(() => { void loadPage(selectedId) }, [selectedId, loadPage])
  useEffect(() => {
    if (!playing || !page?.bars.length) return
    const id = window.setInterval(() => setCursor(i => Math.min(i + 1, page.bars.length - 1)), 200)
    return () => window.clearInterval(id)
  }, [playing, page])
  useEffect(() => { if (playing && page && cursor >= page.bars.length - 1) setPlaying(false) }, [cursor, playing, page])
  const bars = page?.bars ?? []
  const candle = bars[cursor]
  const selected = datasets.find(d => d.id === selectedId)
  const visible = bars.slice(Math.max(0, cursor - LAST + 1), cursor + 1)

  return <section className="surface panel historical-replay" aria-label="Historical candle replay">
    <div className="panel-heading">
      <div><p className="eyebrow">HISTORICAL · INTERACTIVE RESEARCH</p><h3>Candle Replay</h3></div>
      <span className="pill pill-amber"><Activity size={13}/> OFFLINE M15</span>
    </div>
    <div className="historical-body">
      <p className="skills-disclaimer">Study the chronological XAUUSD price action from your imported data. Playback reveals <strong>only completed candles</strong>, never future bars. This is <strong>not</strong> a trading strategy, execution simulator, independently verified dataset, or profit claim.</p>
      <div className="historical-toolbar">
        <label>Historical dataset
          <select value={selectedId} onChange={e => setSelectedId(e.target.value)}>
            {!datasets.length && <option value="">No imported datasets</option>}
            {datasets.map(d => <option key={d.id} value={d.id}>{d.instrument} · {d.provider} · {d.quality_report.rows.toLocaleString('en-GB')} candles</option>)}
          </select>
        </label>
        <button type="button" className="btn btn-secondary" onClick={reloadDatasets}><RefreshCw size={15}/> Refresh datasets</button>
      </div>
      {error && <p className="message-error" role="alert">{error}</p>}
      {!datasets.length && <div className="dataset-empty"><Database size={18}/> No datasets yet. Import an XAUUSD M15 CSV in the Data Engine below, then refresh this panel.</div>}
      {selected && <div className="historical-meta">
        <span>Source: <strong>{selected.provider}</strong></span>
        <span>Rows: <strong>{selected.quality_report.rows.toLocaleString('en-GB')}</strong></span>
        <span><ShieldAlert size={13}/> QUARANTINED — NOT VERIFIED</span>
      </div>}
      {selected && busy && <p className="muted">Checking candle hashes and loading your data…</p>}
      {selected && !busy && page && <>{bars.length > 0 ? <>
        <CandleChart candles={visible}/>
        <div className="historical-figures">
          <div><span>Current candle</span><strong>{cursor + 1} / {bars.length}</strong></div>
          <div><span>Open</span><strong>{fmt(Number(candle?.open))}</strong></div>
          <div><span>High</span><strong>{fmt(Number(candle?.high))}</strong></div>
          <div><span>Low</span><strong>{fmt(Number(candle?.low))}</strong></div>
          <div><span>Close</span><strong>{fmt(Number(candle?.close))}</strong></div>
        </div>
        <div className="historical-scrubber">
          <label htmlFor="historical-progress">Timeline — {when(candle?.open_time || '')}</label>
          <input id="historical-progress" type="range" min="0" max={Math.max(0, bars.length - 1)}
            value={cursor} onChange={e => { setPlaying(false); setCursor(Number(e.target.value)) }}/>
        </div>
        <div className="historical-actions">
          <button type="button" className="btn btn-primary" onClick={() => {
            if (cursor >= bars.length - 1) setCursor(0)
            setPlaying(p => !p)
          }}>{playing ? <Pause size={15}/> : <Play size={15}/>} {playing ? 'Pause replay' : 'Play candles'}</button>
          <button type="button" className="btn btn-secondary" disabled={!page.has_more || busy}
            onClick={() => { if (bars.length) void loadPage(selectedId, bars[0].open_time) }}>
            <ArrowLeft size={15}/> Earlier candles
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => void loadPage(selectedId)}>
            Latest candles
          </button>
        </div>
      </> : <div className="dataset-empty">No completed candles are available for this dataset.</div>}</>}
      <p className="historical-warning">No simulated orders, trades, win rate or equity curves are generated here. The independent M1 bid/ask replay engine remains separate and offline; paper/live execution stays locked.</p>
    </div>
  </section>
}
