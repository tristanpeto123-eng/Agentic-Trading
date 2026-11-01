import { useEffect, useRef, useState } from 'react'
import type { Candle } from './HistoricalResearch'
import { api } from './api'
import './AgentTracePanel.css'

export type TraceObservation = {
  index: number
  observed_at: string
  state: string
  decision: 'NO_TRADE'
  reason: string
  regime: null | {
    market: string; volatility: string; confidence: string; atr: string
    efficiency: string; h1_direction: string; h4_direction: string; reasons: string[]
  }
  candidate: null | {
    direction: 'LONG' | 'SHORT'; tactic: string; entry_reference: string
    stop_price: string; target_price: string; plan_permitted: boolean
    content_sha256: string; policy_sha256: string
  }
  scout_b: string
  guardian: string
  neural?: null | { status: string; recommendation?: string; probability_profit_raw?: number
    expected_net_pct_raw?: number; checkpoint_sha256?: string; epoch?: number
    time_scope?: string; reason?: string; prediction_uncalibrated?: boolean }
  neural_trace_sha256?: string | null
  trace_sha256: string | null
}
type TraceBatch = {
  engine: 'EXISTING_S4_DETERMINISTIC_REFERENCE_PIPELINE'
  source_verified: false; neural_checkpoint_inference_enabled: boolean
  observations: TraceObservation[]; paper_trading_enabled: false
  live_trading_enabled: false
}
function label(reason: string) {
  return reason.replaceAll('_', ' ').toLowerCase().replace(/^./, x => x.toUpperCase())
}
function Stage({ title, status, detail }: { title: string; status: string; detail: string }) {
  return <div className="agent-stage">
    <div className="agent-stage-top"><strong>{title}</strong><span>{status}</span></div>
    <p>{detail}</p>
  </div>
}
export function AgentTracePanel({ bars, cursor, studentId }: {
  bars: Candle[]; cursor: number; studentId: string
}) {
  const [traces, setTraces] = useState<Record<number, TraceObservation>>({})
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const generation = useRef(0)
  const inFlight = useRef(false)
  useEffect(() => {
    generation.current += 1
    inFlight.current = false
    setTraces({})
    setError('')
    setLoading(false)
  }, [bars, studentId])
  useEffect(() => {
    if (!studentId || !bars.length || traces[cursor] || inFlight.current) return
    const requestGeneration = generation.current
    const start = Math.max(0, cursor - 191)
    const end = Math.min(bars.length - 1, cursor + 15)
    const request = {
      student_id: studentId,
      price_basis: 'mid',
      candles: bars.slice(start, end + 1).map(bar => ({
        open_time: bar.open_time, open: bar.open, high: bar.high,
        low: bar.low, close: bar.close,
      })),
      first_index: cursor - start,
      last_index: end - start,
    }
    inFlight.current = true
    setLoading(true)
    setError('')
    void api<TraceBatch>('/v1/research/decision-trace', 'POST', request)
      .then(result => {
        if (requestGeneration !== generation.current) return
        const items: Record<number, TraceObservation> = {}
        for (const item of result.observations) items[start + item.index] = item
        setTraces(previous => ({ ...previous, ...items }))
      }).catch(e => {
        if (requestGeneration === generation.current)
          setError(e instanceof Error ? e.message : 'Trace unavailable')
      }).finally(() => {
        if (requestGeneration === generation.current) {
          inFlight.current = false
          setLoading(false)
        }
      })
  }, [bars, cursor, studentId, traces])
  const current = traces[cursor]
  return <div className="agent-trace-panel" aria-label="Real research agent decision trace">
    <div className="agent-trace-title">
      <div><p className="eyebrow">S4 RESEARCH · SAVED NEURAL INFERENCE WHEN AVAILABLE</p>
        <h4>Scout → Strategist → Scout B → Guardian</h4></div>
      <span className="sim-action sim-wait">NO ORDERS</span>
    </div>
    <p className="agent-trace-hint">Scout and Strategist use the real deterministic research pipeline. When trained, the student’s saved neural checkpoint scores the strategy proposal from completed candles, but predictions remain uncalibrated and do not authorise a trade.</p>
    {loading && !current && <p className="muted" role="status">Evaluating this candle with the research agents…</p>}
    {error && <p className="message-error" role="alert">Trace unavailable: {error}. No decision is authorised.</p>}
    {current && <>
      <p className="agent-trace-time">Observed at {new Date(current.observed_at).toLocaleString('en-GB', { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' })} UTC</p>
      <div className="agent-stage-list">
        <Stage title="1 · Scout A — market regime"
          status={current.regime ? current.regime.market : 'DATA GAP'}
          detail={current.regime
            ? 'Volatility ' + current.regime.volatility + ' · confidence ' +
              (100 * Number(current.regime.confidence)).toFixed(1) + '% · H1 ' +
              current.regime.h1_direction + ' / H4 ' + current.regime.h4_direction +
              (current.regime.reasons.length ? ' · ' + current.regime.reasons.map(label).join(', ') : '')
            : 'Uninterrupted M15 lookback unavailable. Scout abstained.'}/>
        <Stage title="2 · Strategist — candidate only"
          status={current.candidate ? current.candidate.direction + ' PROPOSED' : 'ABSTAIN'}
          detail={current.candidate
            ? current.candidate.tactic + ': reference ' + current.candidate.entry_reference +
              ', stop ' + current.candidate.stop_price + ', target ' + current.candidate.target_price +
              (current.candidate.plan_permitted ? ' · in student learning scope' : ' · outside student learning scope')
            : 'No strategy proposal produced under the current market regime and safety constraints.'}/>
        <Stage title="3 · Neural checkpoint — research candidate score"
          status={current.neural?.status === "INFERENCE_AVAILABLE" ? "MODEL SCORED" : current.neural?.status ?? "NO CHECKPOINT"}
          detail={current.neural?.status === "INFERENCE_AVAILABLE"
            ? "Raw model probability " + (100 * Number(current.neural.probability_profit_raw)).toFixed(1) +
              "% · predicted net " + Number(current.neural.expected_net_pct_raw).toFixed(3) +
              "% · " + current.neural.recommendation + " · " + current.neural.time_scope +
              " · epoch " + current.neural.epoch + " · weights " + current.neural.checkpoint_sha256?.slice(0,12)
            : current.neural?.reason ?? "No valid saved neural model or no proposal to score. This is not an authorised trade."}/>
        <Stage title="4 · Scout B — independent expectancy"
          status={current.scout_b === 'NOT_TRAINED_OR_BOUND' ? 'UNTRAINED' : 'SKIPPED'}
          detail="No independently matured, source-isolated Scout B model is bound to this historical replay. Expected profitability cannot be asserted."/>
        <Stage title="5 · Guardian — independent risk veto"
          status="NOT REACHED"
          detail="Guardian has not approved this candle: without an independently scored proposal, no executable intent exists."/>
      </div>
      <div className="agent-result">
        <div><strong>Final result: NO TRADE</strong><span>{label(current.reason)}</span></div>
        <small>Unqualified neural research is not independent Scout B evidence · paper/live execution OFF</small>
      </div>
      <details className="agent-hash"><summary>Audit fingerprint</summary>
        <code>{current.neural_trace_sha256 ?? current.trace_sha256 ?? 'Not generated: data integrity guard'}</code>
      </details>
    </>}
  </div>
}
