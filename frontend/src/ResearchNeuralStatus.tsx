import type { ReactNode } from 'react'
import './ResearchNeuralStatus.css'

export type NeuralReport = {
  run_id: string; student_id: string; market: string; tactic: string
  model_schema: string; epoch: number; epochs_planned: number
  train_examples: number; development_examples: number
  state: string; metrics: {epoch:number; train_loss:number; development_loss:number}[]
  snapshot_sha256: string; latest_weights_sha256: string | null
  weights_persisted: boolean; can_resume: boolean; trained_neural_model: boolean
  qualification: 'unqualified'; independent_holdout_evaluated: false
  paper_trading_enabled: false; live_trading_enabled: false
}
function Metric({label, children}:{label:string;children:ReactNode}){
  return <div className="neural-metric"><span>{label}</span><strong>{children}</strong></div>
}
export function ResearchNeuralStatus({run, active}:{run:NeuralReport; active:boolean}){
  const last = run.metrics.at(-1)
  const progress = run.epochs_planned ? 100*run.epoch/run.epochs_planned : 0
  const points = run.metrics
  const chart = (metric:'train_loss'|'development_loss')=>{
    if(points.length<2)return ''
    const values=points.flatMap(x=>[x.train_loss,x.development_loss])
    const lower=Math.min(...values),upper=Math.max(...values)
    return points.map((x,i)=>{
      const y=154-125*(x[metric]-lower)/Math.max(1e-8,upper-lower)
      const px=20+i*640/Math.max(points.length-1,1)
      return px.toFixed(1)+','+y.toFixed(1)
    }).join(' ')
  }
  return <section className="neural-status" aria-label="Persistent neural model training">
    <div className="neural-header"><div><p className="eyebrow">GENUINE CPU NEURAL TRAINING · SAVED TO DATABASE</p><h3>Student neural weights</h3></div>
      <span className="neural-label">{active?'TRAINING':run.state==='complete'?'CHECKPOINT COMPLETE':'SAVED · READY TO RESUME'}</span>
    </div>
    <div className="neural-progress-head"><span>Epoch {run.epoch} / {run.epochs_planned}</span><span>{progress.toFixed(0)}%</span></div>
    <progress value={run.epoch} max={run.epochs_planned}/>
    <div className="neural-metrics">
      <Metric label="Training loss">{last?last.train_loss.toFixed(5):'—'}</Metric>
      <Metric label="Development loss">{last?last.development_loss.toFixed(5):'—'}</Metric>
      <Metric label="Training examples">{run.train_examples}</Metric>
      <Metric label="Development examples">{run.development_examples}</Metric>
    </div>
    {points.length>1&&<svg viewBox="0 0 700 185" role="img" aria-label="Saved neural training and development loss curves" className="neural-plot">
      <rect x="1" y="1" width="698" height="183" rx="10" fill="#071524" stroke="#29475b"/>
      <polyline points={chart('train_loss')} fill="none" stroke="#7fd4dd" strokeWidth="2.7"/>
      <polyline points={chart('development_loss')} fill="none" stroke="#f6b97c" strokeWidth="2.7"/>
      <text x="22" y="177" fill="#b5cdda" fontSize="12">Blue: training loss</text>
      <text x="230" y="177" fill="#efc5a0" fontSize="12">Amber: development loss</text>
    </svg>}
    <div className="neural-artifact">
      <span>Saved model version</span>
      <strong>{run.latest_weights_sha256?'epoch '+run.epoch+' · '+run.latest_weights_sha256.slice(0,12):'Initialising'}</strong>
      <span>Frozen snapshot</span><code>{run.snapshot_sha256.slice(0,16)}…</code>
    </div>
    <p className="neural-note">These are actual trained weights, persisted after each epoch. Closing or refreshing the page does not erase them. The model has <strong>not</strong> passed an independent holdout exam and does not direct trades.</p>
  </section>
}
