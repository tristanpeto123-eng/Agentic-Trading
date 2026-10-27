import { useEffect, useMemo, useState } from 'react'
import { api } from './api'
import type { HistoricalDataset } from './api'
import { Activity, Database, Pause, Play, ShieldAlert } from 'lucide-react'

type StudyBatch = {
  batch: number
  start_at: string
  end_at: string
  close: string
  bars: number
  selected_rule: string
  selector_version: number
  observations: number
  correct: number
  accuracy_pct: number | null
  cumulative_accuracy_pct: number | null
  skipped: number
  updated_after: boolean
  next_selected_rule?: string
  next_selector_version?: number
}
type StudyResult = {
  schema_version: string
  dataset_id: string
  source_sha256: string
  market: 'XAUUSD'
  mode: string
  source_verified: false
  research_eligible: false
  trade_execution_performed: false
  neural_training_performed: false
  net_pnl_usd: null
  paper_trading_enabled: false
  live_trading_enabled: false
  update_every_batches: number
  training_bars: number
  validation_bars: number
  sealed_holdout_bars: number
  holdout_evaluated: false
  selector_version: number
  selected_rule: string
  training: { observations: number; correct: number; accuracy_pct: number | null }
  development_validation: { observations: number; correct: number; accuracy_pct: number | null; selector_frozen: true }
  batches: StudyBatch[]
  warnings: string[]
}

function StudyLine({
  values, total, title, percent = false,
}: {
  values: (number | null)[]; total: number; title: string; percent?: boolean
}) {
  const width = 620, height = 208
  const usable = values.map((value, index) => ({ value, index }))
    .filter((point): point is { value: number; index: number } => point.value !== null && Number.isFinite(point.value))
  const numbers = usable.map(point => point.value)
  const lo = percent ? 0 : (numbers.length ? Math.min(...numbers) : 0)
  const hi = percent ? 100 : (numbers.length ? Math.max(...numbers) : 1)
  const range = Math.max(hi - lo, 1)
  const path = usable.map((point, i) => {
    const x = 40 + point.index * 550 / Math.max(1, total - 1)
    const y = 180 - (point.value - lo) / range * 152
    return `${i ? 'L' : 'M'}${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
  const last = usable.at(-1)?.value
  return <div style={{ minWidth: 0 }}>
    <p className="muted" style={{ marginBottom: 6 }}>{title}</p>
    <svg viewBox={`0 0 ${width} ${height}`} className="historical-candle-chart"
      role="img" aria-label={title + ' across completed historical training batches'}>
      <rect width={width} height={height} rx={10} fill="#081525"/>
      {[0, 1, 2, 3, 4].map(i => {
        const val = lo + range * (4 - i) / 4
        const y = 28 + i * 38
        return <g key={i}>
          <line x1={40} x2={590} y1={y} y2={y} stroke="#234257" strokeDasharray="4 7"/>
          <text x={4} y={y + 4} fontSize={11} fill="#8fa9b8">{percent ? val.toFixed(0) : val.toFixed(0)}</text>
        </g>
      })}
      <path d={path} fill="none" stroke="#61c8a6" strokeWidth={2.7}
        strokeLinejoin="round" strokeLinecap="round"/>
      <text x={40} y={198} fill="#8fa9b8" fontSize={11}>Batch 1</text>
      <text x={590} y={198} fill="#8fa9b8" fontSize={11} textAnchor="end">Batch {total}</text>
      {last !== undefined && <text x={580} y={18} fill="#b3e9db" fontSize={12}
        textAnchor="end">{last.toFixed(2)}{percent ? '%' : ''}</text>}
    </svg>
  </div>
}

export function MarketStudy({ studentId }: { studentId: string }) {
  const [datasets, setDatasets] = useState<HistoricalDataset[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [report, setReport] = useState<StudyResult | null>(null)
  const [cursor, setCursor] = useState(0)
  const [running, setRunning] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    void api<HistoricalDataset[]>('/v1/datasets').then(items => {
      if (!active) return
      const xau = items.filter(item => item.instrument === 'XAUUSD' && item.timeframe === 'M15')
      setDatasets(xau)
      setDatasetId(xau[0]?.id ?? '')
    }).catch(err => { if (active) setError(err instanceof Error ? err.message : 'Could not list archives') })
    return () => { active = false }
  }, [studentId])

  useEffect(() => {
    if (!running || !report) return
    const interval = window.setInterval(() => {
      setCursor(previous => Math.min(previous + 1, report.batches.length))
    }, 160)
    return () => window.clearInterval(interval)
  }, [running, report])

  useEffect(() => {
    if (report && cursor >= report.batches.length) setRunning(false)
  }, [report, cursor])

  const start = async () => {
    if (!datasetId || busy) return
    setError(''); setBusy(true); setReport(null); setRunning(false); setCursor(0)
    try {
      const result = await api<StudyResult>(
        `/v1/students/${encodeURIComponent(studentId)}/candle-study?dataset_id=${encodeURIComponent(datasetId)}`
      )
      setReport(result)
      setCursor(1)
      setRunning(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to open research study')
    } finally {
      setBusy(false)
    }
  }

  const shown = useMemo(() => report?.batches.slice(0, cursor) ?? [], [report, cursor])
  const latest = shown.at(-1)
  const complete = !!report && cursor >= report.batches.length
  const currentTactic = latest?.updated_after ? latest.next_selected_rule : latest?.selected_rule
  const currentRevision = latest?.updated_after ? latest.next_selector_version : latest?.selector_version

  return <section className="surface panel" aria-label="Market-specific imported candle research">
    <div className="panel-heading">
      <div><p className="eyebrow">ACADEMY / IMPORTED XAUUSD</p><h3>Student Candle Study</h3></div>
      <Activity size={19}/>
    </div>
    <div className="panel-content">
      <p className="skills-disclaimer">
        This study uses <strong>your stored M15 candles</strong>, not a synthetic chart.
        It compares fixed directional rules using completed historical bars and updates only
        the student's exploratory rule selector every five training batches.
        It does <strong>not</strong> train a neural model, place trades or calculate investable profit.
        The rule selector is recalculated on demand, not saved as an approved student model.
      </p>
      <div className="historical-toolbar">
        <label>Saved gold dataset
          <select value={datasetId} onChange={e => {
            setDatasetId(e.target.value); setReport(null); setRunning(false); setCursor(0)
          }}>
            {!datasets.length && <option value="">No imported XAUUSD datasets</option>}
            {datasets.map(d => <option key={d.id} value={d.id}>
              {d.quality_report.rows.toLocaleString('en-GB')} candles · {d.provider}
            </option>)}
          </select>
        </label>
        <button type="button" className="btn btn-primary" disabled={!datasetId || busy}
          onClick={() => void start()}><Play size={15}/>{busy ? 'Reading verified archive…' : report ? 'Restart study' : 'Start study'}</button>
        {report && <button type="button" className="btn btn-secondary"
          onClick={() => setRunning(previous => !previous)} disabled={complete}>
          {running ? <Pause size={15}/> : <Play size={15}/>}
          {running ? 'Pause' : 'Continue'}
        </button>}
      </div>
      {error && <p className="message-error" role="alert">{error}</p>}
      {!datasets.length && !error && <div className="dataset-empty"><Database size={18}/>
        Import an XAUUSD M15 CSV in Data Engine to enable research observation.
      </div>}
      {report && <div>
        <div className="historical-meta">
          <span><ShieldAlert size={13}/> DATA UNVERIFIED</span>
          <span>Training batches: <strong>{cursor} / {report.batches.length}</strong></span>
          <span>Selector: <strong>{currentTactic ?? '—'} v{currentRevision ?? 1}</strong></span>
        </div>
        <div className="historical-figures">
          <div><span>Bars reviewed</span><strong>{shown.reduce((sum, batch) => sum + batch.bars, 0).toLocaleString('en-GB')}</strong></div>
          <div><span>Directional observations</span><strong>{shown.reduce((sum, batch) => sum + batch.observations, 0).toLocaleString('en-GB')}</strong></div>
          <div><span>Direction accuracy</span><strong>{latest?.cumulative_accuracy_pct == null ? '—' : latest.cumulative_accuracy_pct.toFixed(1) + '%'}</strong></div>
          <div><span>Paper / live</span><strong>Locked</strong></div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 16, marginTop: 16 }}>
          <StudyLine title="M15 price checkpoints · USD/oz" total={report.batches.length}
            values={shown.map(batch => Number(batch.close))}/>
          <StudyLine title="Cumulative directional accuracy · NOT win rate" total={report.batches.length} percent
            values={shown.map(batch => batch.cumulative_accuracy_pct)}/>
        </div>
        <div className="historical-scrubber">
          <label htmlFor="academy-study-progress">Research progress — batch {cursor} of {report.batches.length}</label>
          <input id="academy-study-progress" type="range" min={0} max={report.batches.length}
            value={cursor} onChange={e => { setRunning(false); setCursor(Number(e.target.value)) }}/>
        </div>
        <div className="historical-meta">
          <span>Selector revisions: <strong>{shown.filter(batch => batch.updated_after).length}</strong></span>
          <span>Validation: <strong>{complete ? 'Reviewed without selector updates' : 'Sealed during replay'}</strong></span>
          <span>Final holdout: <strong>Sealed ({report.sealed_holdout_bars.toLocaleString('en-GB')} bars)</strong></span>
        </div>
        {complete && <div className="memory-row" role="status">
          <strong>Historical observation completed · Not qualified</strong>
          <p>Development validation: {report.development_validation.observations.toLocaleString('en-GB')} directional observations;
            accuracy {report.development_validation.accuracy_pct === null ? '—' : report.development_validation.accuracy_pct.toFixed(1) + '%'}.
            No trades, net P&amp;L or neural checkpoints were produced.</p>
        </div>}
        <p className="historical-warning">
          Results describe an exploratory directional classifier, not a profitable strategy.
          Imported source rights and execution bid/ask quotes remain unverified.
          Neural training, Registrar qualification, paper trading and live trading remain disabled.
        </p>
      </div>}
    </div>
  </section>
}
