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
  prediction_uncalibrated?: boolean
}
type ModelResponse = {
  model: RawModelSignal
  decision: 'NO_TRADE'
  guardian: 'NOT_EVALUATED'
  research_only: true
}
const titleCase = (s:string) => s.replaceAll('_',' ').toLowerCase().replace(/^./,c=>c.toUpperCase())
export function NeuralSignalForecast({ run, bars, cursor, market, studentId }: {
  run: NeuralReport | null; bars: Candle[]; cursor: number
  market: string; studentId: string
}) {
  const [signal,setSignal]=useState<RawModelSignal|null>(null)
  const [status,setStatus]=useState('')
  // Bounded inspection; update every historical batch or checkpoint milestone.
  const interval=Math.floor(cursor/96)
  const epochMilestone=Math.floor((run?.epoch??0)/5)
  useEffect(()=>{
    let valid=true
    setSignal(null);setStatus('')
    if(!run || run.epoch<1 || bars.length<6 || cursor<5 || market!==run.market) return ()=>{valid=false}
    const at=Math.min(cursor,bars.length-1)
    const barsIn=bars.slice(at-4,at+1).map(bar=>({
      open_time:bar.open_time,open:bar.open,high:bar.high,low:bar.low,close:bar.close,
    }))
    if(barsIn.length!==5)return ()=>{valid=false}
    void api<ModelResponse>(
      '/v1/students/'+encodeURIComponent(studentId)+'/neural/predict',
      'POST',{student_id:studentId,market,tactic:run.tactic,candles:barsIn},
    ).then(reply=>{
      if(valid)setSignal(reply.model)
    }).catch(err=>{
      if(valid)setStatus(err instanceof Error?err.message:'Neural forecast unavailable')
    })
    return ()=>{valid=false}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[run?.run_id,epochMilestone,interval,market,studentId,bars])
  if(!run || run.epoch<1)return null
  return <section className="neural-status" aria-label="Neural model signal">
    <div className="neural-header"><div><p className="eyebrow">SAVED NEURAL MODEL · LIVE RESEARCH PREDICTION</p>
      <h3>What does the student predict?</h3></div>
      <span className="neural-label">NOT QUALIFIED</span></div>
    {signal?.status==='INFERENCE_AVAILABLE'?<>
      <div className="neural-metrics">
        <div className="neural-metric"><span>Strategy signal</span><strong>{signal.candidate_direction}</strong></div>
        <div className="neural-metric"><span>Raw profitable probability</span><strong>{(100*Number(signal.probability_profit_raw)).toFixed(1)}%</strong></div>
        <div className="neural-metric"><span>Raw predicted net return</span><strong>{Number(signal.expected_net_pct_raw).toFixed(3)}%</strong></div>
        <div className="neural-metric"><span>Model preference</span><strong>{titleCase(signal.recommendation??'ABSTAIN')}</strong></div>
      </div>
      <p className="neural-note">Evidence window: {titleCase(signal.time_scope??'UNKNOWN')} · model checkpoint epoch {signal.epoch}, {signal.checkpoint_sha256?.slice(0,12)}. Scores are uncalibrated. They are never broker instructions or independent validation.</p>
    </>:<p className="neural-note">{signal?titleCase(signal.status):status?('No model signal: '+status):'Preparing completed-candle neural forecast…'}</p>}
    <p className="neural-note">Guardian: NOT EVALUATED. Final decision: <strong>NO TRADE</strong>. Independent Scout B evidence, model evaluation and release approval are still required.</p>
  </section>
}
