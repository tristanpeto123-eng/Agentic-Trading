import { useEffect, useState } from 'react'
import { api } from './api'
import type { Candle } from './HistoricalResearch'
import type { NeuralReport } from './ResearchNeuralStatus'

type RawModelSignal = {
  status: string
  recommendation?: string
  probability_profit_raw?: number
  expected_net_pct_raw?: number
  candidate_direction?: string
  epoch?: number
  checkpoint_sha256?: string
  time_scope?: string
  reason?: string
}
type ModelResponse = {
  model: RawModelSignal
  decision: 'NO_TRADE'
  guardian: 'NOT_EVALUATED'
  research_only: true
}
const titleCase = (s: string) => s.replaceAll('_', ' ').toLowerCase().replace(/^./, c => c.toUpperCase())

type SignalSample = { index: number; candles: Pick<Candle, 'open_time'|'open'|'high'|'low'|'close'>[] }

// A strategy cannot be scored at arbitrary, gapped, sideways or incomplete bars.
// Find the latest actual *signal* among already observed bars, never a future bar.
export function latestClosedStrategySignal(bars: Candle[], cursor: number, tactic: string): SignalSample | null {
  const end = Math.min(cursor, bars.length - 1)
  for (let at = end; at >= Math.max(5, end - 95); at--) {
    const window = bars.slice(at - 4, at + 1)
    if (window.length !== 5) continue
    const times = window.map(c => Date.parse(c.open_time))
    if (times.some((t, i) => !Number.isFinite(t) || (i > 0 && t - times[i-1] !== 900000))) continue
    const close = Number(window[4].close)
    const previous = Number(window[3].close)
    const older = Number(window[0].close)
    if (!Number.isFinite(close) || !Number.isFinite(previous) || !Number.isFinite(older) ||
        previous <= 0 || older <= 0 || Math.abs(close / previous - 1) > .04) continue
    let direction = 0
    if (tactic === 'trend') direction = Math.sign(close - previous)
    else if (tactic === 'range') direction = -Math.sign(close - previous)
    else if (tactic === 'breakout') {
      const high = Math.max(...window.slice(0, 4).map(c => Number(c.high)))
      const low = Math.min(...window.slice(0, 4).map(c => Number(c.low)))
      direction = Number(close > high) - Number(close < low)
    }
    if (!direction) continue
    return { index: at, candles: window.map(({open_time, open, high, low, close}) =>
      ({open_time, open, high, low, close})) }
  }
  return null
}

export function NeuralSignalForecast({ run, bars, cursor, market, studentId }: {
  run: NeuralReport | null; bars: Candle[]; cursor: number
  market: string; studentId: string
}) {
  const [signal, setSignal] = useState<RawModelSignal | null>(null)
  const [error, setError] = useState('')
  const [observedAt, setObservedAt] = useState('')
  const compatible = run?.model_schema === 'research_m15_outcome_mlp8x16x2.v2'
  const ready = Boolean(compatible && run && run.epoch >= 1 && market === run.market)
  const sample = ready ? latestClosedStrategySignal(bars, cursor, run!.tactic) : null
  // Request once per 96 processed candles, and when a checkpoint first appears
  // or reaches another five-epoch milestone—not on every animation frame.
  const interval = Math.floor(cursor / 96)
  const epochMilestone = Math.floor((run?.epoch ?? 0) / 5)
  const hasSample = Boolean(sample)
  useEffect(() => {
    let valid = true
    setSignal(null)
    setError('')
    setObservedAt('')
    if (!ready || !sample) return () => { valid = false }
    const latest = sample.candles[4]
    void api<ModelResponse>(
      '/v1/students/' + encodeURIComponent(studentId) + '/neural/predict',
      'POST', {
        student_id: studentId, market, tactic: run!.tactic,
        candles: sample.candles,
      },
    ).then(reply => {
      if (valid) {
        setSignal(reply.model)
        setObservedAt(latest.open_time)
      }
    }).catch(err => {
      if (valid) setError(err instanceof Error ? err.message : 'Neural prediction unavailable')
    })
    return () => { valid = false }
  // Candidate selection is updated on the next 96-bar boundary; an initial
  // signal appearing earlier triggers via hasSample. Not every frame.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.run_id, ready, interval, epochMilestone, hasSample, run?.tactic, market, studentId, bars])

  if (!run) return null
  return <section className="neural-status" aria-label="Neural model signal">
    <div className="neural-header">
      <div><p className="eyebrow">SAVED STUDENT MODEL · HISTORICAL RESEARCH</p>
        <h3>What does the student predict?</h3></div>
      <span className="neural-label">NOT QUALIFIED</span>
    </div>
    {!compatible ? <p className="neural-note" role="status">
      This student has a saved legacy {run.model_schema} model. Its older features cannot be
      used safely for new predictions. Press <strong>Train</strong> to start a compatible v2
      experiment. Previous checkpoints are preserved.
    </p> : run.epoch < 1 ? <p className="neural-note" role="status">
      Training has started. A first saved neural checkpoint is required before it can predict.
    </p> : market !== run.market ? <p className="neural-note" role="status">
      Saved model market {run.market} does not match the selected historical market {market}.
    </p> : !sample ? <p className="neural-note" role="status">
      Saved neural weights are ready, but no eligible {run.tactic} signal has occurred in the
      last 96 completed M15 candles. No prediction is fabricated.
    </p> : signal?.status === 'INFERENCE_AVAILABLE' ? <>
      <div className="neural-metrics">
        <div className="neural-metric"><span>Strategy signal</span><strong>{signal.candidate_direction}</strong></div>
        <div className="neural-metric"><span>Raw profitable probability</span><strong>{(100 * Number(signal.probability_profit_raw)).toFixed(1)}%</strong></div>
        <div className="neural-metric"><span>Raw predicted net return</span><strong>{Number(signal.expected_net_pct_raw).toFixed(3)}%</strong></div>
        <div className="neural-metric"><span>Model preference</span><strong>{titleCase(signal.recommendation ?? 'ABSTAIN')}</strong></div>
      </div>
      <p className="neural-note">
        Signal at {new Date(observedAt).toLocaleString('en-GB', { timeZone:'UTC' })} UTC
        · evidence: {titleCase(signal.time_scope ?? 'UNKNOWN')}
        · model epoch {signal.epoch}, {signal.checkpoint_sha256?.slice(0, 12)}.
        This is an uncalibrated historical prediction, not independent profitability proof.
      </p>
    </> : signal ? <p className="neural-note" role="status">
      Research abstained: {titleCase(signal.reason ?? signal.status)}. No trade was authorised.
    </p> : error ? <p className="neural-note" role="alert">
      Neural prediction could not be calculated: {error}. Saved training weights remain intact.
    </p> : <p className="neural-note" role="status">Reading the latest completed strategy signal…</p>}
    <p className="neural-note">Guardian: NOT EVALUATED. Final decision: <strong>NO TRADE</strong>.
      Independent verification and approval are required before any broker orders.</p>
  </section>
}
