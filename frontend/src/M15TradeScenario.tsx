import { useEffect, useState } from 'react'
import { Activity, Play, ShieldAlert, Wallet } from 'lucide-react'
import { api } from './api'
import type { HistoricalDataset } from './api'

type Totals = {
  closed: number
  good: number
  bad: number
  flat: number
  gross_usd: string
  cost_usd: string
  net_usd: string
  win_rate_pct: number | null
  expectancy_usd: string | null
  profit_factor: string | null
}

type ScenarioBatch = {
  batch: number
  end_at: string
  selected_rule: string
  selector_version: number
  closed: number
  good: number
  bad: number
  net_usd: string
  cumulative_net_usd: string
  hypothetical_equity_usd: string
  skipped: number
  selector_updated_after: boolean
}

type HypotheticalEpisode = {
  signal_at: string
  entry_at: string
  exit_at: string
  direction: string
  rule: string
  net_usd: string
  cost_usd: string
  outcome: 'good' | 'bad' | 'flat'
}

type ScenarioReport = {
  schema_version: string
  dataset_id: string
  source_verified: false
  fill_assumptions_independently_validated: false
  trade_execution_performed: false
  durable_trade_memory_written: false
  holdout_evaluated: false
  sealed_holdout_bars: number
  selector_version: number
  selected_rule: string
  training: Totals
  development_validation: Totals & { selector_frozen: true }
  training_max_drawdown_fraction: string
  assumed_starting_equity_usd: string
  round_trip_cost_usd_per_oz: string
  assumed_costs: {
    full_spread_usd_per_oz: string
    slippage_usd_per_oz_per_side: string
    commission_usd_per_oz_per_side: string
    quantity_oz: string
  }
  batches: ScenarioBatch[]
  hypothetical_outcome_preview: HypotheticalEpisode[]
  warning: string
}

function ScenarioEquity({ report }: { report: ScenarioReport }) {
  const values = [Number(report.assumed_starting_equity_usd), ...report.batches.map(
    b => Number(b.hypothetical_equity_usd)
  )]
  const numbers = values.filter(Number.isFinite)
  const min = Math.min(...numbers), max = Math.max(...numbers)
  const pad = Math.max(1, (max - min) * 0.05)
  const low = min - pad, high = max + pad
  const path = values.map((v, i) => {
    const x = 44 + (i * 550) / Math.max(1, values.length - 1)
    const y = 183 - (v - low) * 151 / (high - low)
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
  return <div>
    <p className="muted">Assumed-cost equity · USD · NOT BROKER P&amp;L</p>
    <svg role="img" aria-label="Hypothetical training equity after assumed costs"
      viewBox="0 0 620 220" style={{ width: '100%', height: 'auto', display: 'block', marginTop: 8 }}>
      <rect width="620" height="220" fill="#081525" rx="10"/>
      {[0, 1, 2, 3, 4].map(i => {
        const y = 32 + 38 * i
        const v = high - (high - low) * i / 4
        return <g key={i}>
          <line x1="44" y1={y} x2="596" y2={y} stroke="#234257" strokeDasharray="4 7"/>
          <text x="4" y={y + 4} fill="#8fa9b8" fontSize="11">{v.toFixed(0)}</text>
        </g>
      })}
      <path d={path} fill="none" stroke="#68c7bd" strokeWidth="3" strokeLinejoin="round"/>
      <text x="44" y="209" fill="#92adbd" fontSize="11">Batch 0</text>
      <text x="595" y="209" fill="#92adbd" fontSize="11" textAnchor="end">
        Batch {report.batches.length}
      </text>
    </svg>
  </div>
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="memory-row">
    <div className="skill-progress-head">
      <span>{label}</span><strong>{value}</strong>
    </div>
  </div>
}

export function M15TradeScenario({ studentId }: { studentId: string }) {
  const [datasets, setDatasets] = useState<HistoricalDataset[]>([])
  const [datasetId, setDatasetId] = useState('')
  const [result, setResult] = useState<ScenarioReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setResult(null); setError('')
    void api<HistoricalDataset[]>('/v1/datasets').then(all => {
      if (!active) return
      const gold = all.filter(d => d.instrument === 'XAUUSD' && d.timeframe === 'M15')
      setDatasets(gold); setDatasetId(gold[0]?.id ?? '')
    }).catch(err => {
      if (active) setError(err instanceof Error ? err.message : 'Unable to list archives')
    })
    return () => { active = false }
  }, [studentId])

  const inspect = async () => {
    if (!datasetId || loading) return
    setLoading(true); setResult(null); setError('')
    try {
      const r = await api<ScenarioReport>(
        `/v1/students/${encodeURIComponent(studentId)}/m15-trade-scenario?dataset_id=${encodeURIComponent(datasetId)}`
      )
      setResult(r)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Research cost scenario unavailable')
    } finally {
      setLoading(false)
    }
  }

  const money = (v: string) => {
    const parsed = Number(v)
    if (!Number.isFinite(parsed)) return '—'
    return new Intl.NumberFormat('en-GB', {
      style: 'currency', currency: 'USD',
      minimumFractionDigits: 2, maximumFractionDigits: 2,
    }).format(parsed)
  }
  return <section className="surface panel" aria-label="Hypothetical M15 trade scenario">
    <div className="panel-heading">
      <div>
        <p className="eyebrow">ACADEMY / COSTED RESEARCH SCENARIO</p>
        <h3>Good / Bad Trade Outcomes</h3>
      </div>
      <Wallet size={19}/>
    </div>
    <div className="panel-content">
      <p className="skills-disclaimer">
        Next-step experiment: compare hypothetical next-candle trades after
        <strong> assumed</strong> spread, slippage and commission.
        This is NOT observed bid/ask execution, real trading P&amp;L, neural training or agent qualification.
      </p>
      <div className="historical-toolbar">
        <label>Historical archive
          <select value={datasetId} onChange={e => {
            setDatasetId(e.target.value); setResult(null); setError('')
          }}>
            {!datasets.length && <option value="">No saved XAUUSD M15 archive</option>}
            {datasets.map(d => <option key={d.id} value={d.id}>
              {d.quality_report.rows.toLocaleString('en-GB')} bars · {d.provider}
            </option>)}
          </select>
        </label>
        <button className="btn btn-primary" type="button"
          disabled={!datasetId || loading} onClick={() => void inspect()}>
          {loading ? <Activity size={16}/> : <Play size={16}/>}
          {loading ? 'Calculating scenario…' : 'Evaluate hypothetical trades'}
        </button>
      </div>
      {error && <p role="alert" className="message-error">{error}</p>}
      {result && <>
        <div className="historical-meta">
          <span><ShieldAlert size={14}/> UNVERIFIED SOURCE</span>
          <span>Cost model: ASSUMED / NOT MEASURED</span>
          <span>Selector v{result.selector_version} · {result.selected_rule}</span>
        </div>
        <div className="historical-figures">
          <div>
            <span>Good scenarios</span>
            <strong>{result.training.good.toLocaleString('en-GB')}</strong>
          </div>
          <div>
            <span>Bad scenarios</span>
            <strong>{result.training.bad.toLocaleString('en-GB')}</strong>
          </div>
          <div>
            <span>Hypothetical net · training</span>
            <strong>{money(result.training.net_usd)}</strong>
          </div>
          <div>
            <span>Assumed cost · per oz round trip</span>
            <strong>{money(result.round_trip_cost_usd_per_oz)}</strong>
          </div>
        </div>
        <ScenarioEquity report={result}/>
        <div style={{ marginTop: 14 }}>
          <Metric label="Hypothetical training wins / completed"
            value={`${result.training.win_rate_pct?.toFixed(2) ?? '—'}% · ${result.training.closed.toLocaleString('en-GB')}`}/>
          <Metric label="Hypothetical development validation"
            value={money(result.development_validation.net_usd)}/>
          <Metric label="Validation wins / completed"
            value={`${result.development_validation.win_rate_pct?.toFixed(2) ?? '—'}% · ${result.development_validation.closed.toLocaleString('en-GB')}`}/>
          <Metric label="Training max drawdown (cost scenario)"
            value={`${(Number(result.training_max_drawdown_fraction) * 100).toFixed(2)}%`}/>
          <Metric label="Final test set"
            value={`Sealed · ${result.sealed_holdout_bars.toLocaleString('en-GB')} M15 bars`}/>
          <Metric label="Hypothetical position size"
            value={`${result.assumed_costs.quantity_oz} oz · starting equity ${money(result.assumed_starting_equity_usd)}`}/>
        </div>
        <h3 style={{ marginTop: 18, marginBottom: 8 }}>Recent hypothetical outcomes</h3>
        <div className="skill-progress-list">
          {result.hypothetical_outcome_preview.slice(-8).reverse().map((trade, i) =>
            <div key={trade.entry_at + trade.rule + i} className="memory-row">
              <div className="skill-progress-head">
                <strong>{trade.rule} · {trade.direction}</strong>
                <span className={`memory-outcome ${trade.outcome}`}>
                  {trade.outcome.toUpperCase()}
                </span>
              </div>
              <div className="skill-progress-meta">
                <span>Scenario net {money(trade.net_usd)}</span>
                <span>{new Date(trade.entry_at).toLocaleDateString('en-GB')}</span>
              </div>
            </div>
          )}
        </div>
        <p className="historical-warning">
          {result.warning} Good/bad observations are held in this report only.
          They are not imported into the trusted student-memory system.
        </p>
      </>}
      {!result && !error && <div className="dataset-empty">
        This is a separate, explicitly cost-assumed experiment. Run it to test whether
        directional decisions survive transaction friction before developing neural training.
      </div>}
    </div>
  </section>
}
