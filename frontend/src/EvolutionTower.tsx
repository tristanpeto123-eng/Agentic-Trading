import { useEffect, useMemo, useState } from 'react'
import { Bot, ChevronDown, ChevronUp, CirclePause, Dna, GitBranch, Layers3, Play, RotateCw, ShieldAlert, ShieldCheck, Skull, Trophy } from 'lucide-react'
import { api } from './api'
import { EvolutionTowerScene } from './EvolutionTowerScene'
import type { TowerAgent, TowerEvent } from './EvolutionTowerScene'
import './EvolutionTower.css'

type TowerState = {
  initialized:boolean;research_only:true;generation?:number;total_born?:number;total_culled?:number
  agents?:TowerAgent[];last_events?:TowerEvent[];state_sha256?:string
  penthouse_locked:true;population_size?:number;mode?:string;performance_kind?:string
  real_generation?:number;research_data?:{
    provider:string;source_sha256:string;observations_received:number
    d_bars_withheld:number;gap_count:number;first_open_time:string;last_research_open_time:string
  }
}
const fmt=(v:number|undefined,digits=1)=>v===undefined?'—':v.toFixed(digits)
const level=(floor:number)=>floor>=50?'ELITE':floor>=21?'SURVIVOR':floor>1?'APPRENTICE':'NURSERY'
const label=(s:string)=>s.replaceAll('_',' ').toLowerCase().replace(/^./,x=>x.toUpperCase())

export function EvolutionTower(){
  const [state,setState]=useState<TowerState|null>(null)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const [selectedId,setSelectedId]=useState<string|null>(null)
  const [auto,setAuto]=useState(false)
  const [source,setSource]=useState<'oanda'|'dukascopy'>('oanda')
  const [showArchive,setShowArchive]=useState(false)
  const [expanded,setExpanded]=useState(true)
  const agents=state?.agents??[]
  const real=state?.mode==='REAL_XAUUSD_BID_ASK_RESEARCH'
  const events=state?.last_events??[]
  const probation=agents.filter(a=>a.status==='probation').length
  const sorted=useMemo(()=>[...agents].sort((a,b)=>b.floor-a.floor||
    ((real?b.metrics?.training.fitness:b.metrics?.selection.fitness)??-999)-
    ((real?a.metrics?.training.fitness:a.metrics?.selection.fitness)??-999)),[agents,real])
  const selected=agents.find(a=>a.id===selectedId)??sorted[0]??null
  useEffect(()=>{
    let alive=true
    void api<TowerState>('/v1/evolution-tower').then(s=>{if(alive)setState(s)})
      .catch(e=>{if(alive)setError(e instanceof Error?e.message:'Tower unavailable')})
    return()=>{alive=false}
  },[])
  const action=async (kind:'start'|'advance')=>{
    if(busy)return
    setBusy(true);setError('')
    try{
      const endpoint=kind==='start'?'/v1/evolution-tower/start':'/v1/evolution-tower/advance'
      const result=await api<TowerState>(endpoint,'POST',
        kind==='advance'?{expected_generation:state?.generation??0}:{})
      setState(result)
      // Keep the exterior camera stable as agents ascend. Only explicit
      // agent selection changes camera focus.
    }catch(e){setAuto(false);setError(e instanceof Error?e.message:'Evolution step failed')}
    finally{setBusy(false)}
  }
  useEffect(()=>{
    if(!auto||busy||!state?.initialized||state.generation===undefined||state.generation>=100)return
    const timer=window.setTimeout(()=>void action('advance'),10000)
    return()=>window.clearTimeout(timer)
  // Auto-evolve intentionally only runs while this browser tab is mounted.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[auto,busy,state?.generation,state?.initialized])
  const activateReal=async()=>{
    if(busy||!state?.initialized||real)return
    setAuto(false);setBusy(true);setError('')
    try{
      const result=await api<TowerState>('/v1/evolution-tower/use-real-history','POST',{
        expected_generation:state.generation??0,source
      })
      setState(result);setSelectedId(null)
    }catch(e){setError(e instanceof Error?e.message:'Historical XAU/USD import failed')}
    finally{setBusy(false)}
  }
  const culls=events.length?events[0].removed.length:0
  const latestEvaluation=events.find(e=>e.type==='GENERATION_EVALUATED')
  const entryStatus=latestEvaluation?.entry_diagnostics
  const entries=selected?.metrics?.training.entry_samples??[]
  return <section className="surface evo-shell" aria-label="Evolution Tower research arena">
    <div className="evo-heading">
      <div><p className="eyebrow">ATL · EVOLUTIONARY RESEARCH ARENA</p>
        <h2><Layers3 size={23}/> Evolution Tower <span>v1</span></h2>
        <p>100-floor 3D command centre · a population of real saved neural chromosomes</p>
      </div>
      <div className="evo-head-right">
        <span className="evo-experiment"><span/> {real?'REAL PRICE RESEARCH':'SYNTHETIC RESEARCH'}</span>
        <button className="evo-collapse" aria-label={expanded?'Collapse tower':'Expand tower'}
          onClick={()=>setExpanded(!expanded)}>{expanded?<ChevronUp size={19}/>:<ChevronDown size={19}/>}</button>
      </div>
    </div>
    {expanded&&<>
      <div className="evo-stats">
        <div><span>GENERATION</span><strong>{state?.generation??'—'} <small>/ 100</small></strong></div>
        <div><span>ACTIVE BOTS</span><strong>{state?.initialized?agents.length:'—'}</strong></div>
        <div><span>BORN</span><strong>{state?.total_born??'—'}</strong></div>
        <div><span>ELIMINATED</span><strong>{state?.total_culled??'—'}</strong></div>
        <div><span>VALIDATED CHAMPIONS</span><strong>0 <small>locked</small></strong></div>
      </div>
      <div className="evo-workspace">
        <div className="evo-stage">
          {state?.initialized ? <>
            <EvolutionTowerScene agents={agents} events={events} selectedId={selectedId} onSelect={setSelectedId}/>
            <div className="evo-view-top"><span>CAM 01 · ORBIT VIEW</span><button type="button" className="evo-full-view" onClick={()=>setSelectedId(null)}>Full tower</button></div>
            <div className="evo-view-legend">
              <span><i className="evo-dot nursery"/> Nursery</span>
              <span><i className="evo-dot survivor"/> Survivors</span>
              <span><i className="evo-dot leader"/> Research leader</span>
              <span><i className="evo-dot probation"/> Probation</span>
            </div>
            <div className="evo-zoom-help">Drag to orbit · pinch to zoom · tap a robot</div>
          </>:<div className="evo-empty">
            <Layers3 size={42}/>
            <strong>YOUR EVOLUTION TOWER</strong>
            <p>Generate 16 simulated neural agents. Survival is earned through performance, weak agents receive probation, and only actual retirements create new nursery spaces.</p>
          </div>}
        </div>
        <aside className="evo-sidebar">
          <div className="evo-sidebar-title"><div><p className="eyebrow">LIVE RANKINGS</p>
            <h3>Research population</h3></div><span>{agents.length} robots</span></div>
          <div className="evo-agent-list">
            {sorted.length?sorted.map((a,index)=><button key={a.id}
              className={'evo-agent-row'+(selected?.id===a.id?' active':'')}
              onClick={()=>setSelectedId(a.id)}>
                <span className={'evo-mini-bot '+(a.status==='research_leader'?'winner':a.status==='probation'?'probation':'')}><Bot size={18}/></span>
                <span className="evo-agent-copy"><strong>{a.id}</strong><small>Gen {a.generation} · {a.status==='probation'?'PROBATION':level(a.floor)}</small></span>
                <span className="evo-agent-score">F{a.floor.toString().padStart(2,'0')}<small>{index===0?'TOP':fmt(real?a.metrics?.training.fitness:a.metrics?.selection.fitness,2)}</small></span>
              </button>):<div className="evo-no-agents">No research population created yet.</div>}
          </div>
          {selected&&<div className="evo-inspect">
            <div className="evo-inspect-title"><span>INSPECTING AGENT</span><strong>{selected.id}</strong></div>
            <div className="evo-inspect-grid">
              <div><span>FLOOR</span><strong>{selected.floor}</strong></div>
              <div><span>GENERATION</span><strong>{selected.generation}</strong></div>
              <div><span>ASSESSMENTS</span><strong>{selected.assessments??0}</strong></div>
              <div><span>PROBATION STREAK</span><strong>{selected.probation_streak??0} / 3</strong></div>
              <div><span>NET RETURN · {real?'HISTORICAL B':'TOY B'} (SELECTION)</span><strong>{fmt(selected.metrics?.training.return_pct,2)}%</strong></div>
              <div><span>ENTRIES · {real?'HISTORICAL B':'TOY B'} (SELECTION)</span><strong>{selected.metrics?.training.trades??'—'}</strong></div>
              <div><span>NET RETURN · {real?'HISTORICAL C':'TOY C'} (DIAGNOSTIC)</span><strong>{fmt(selected.metrics?.selection.return_pct,2)}%</strong></div>
              <div><span>MAX DRAWDOWN · {real?'HISTORICAL C':'TOY C'}</span><strong>{fmt(selected.metrics?.selection.drawdown_pct,2)}%</strong></div>
              <div><span>ENTRIES · DIAGNOSTIC C</span><strong>{selected.metrics?.selection.trades??'—'}</strong></div>
              <div><span>ESTIMATED EXECUTION COSTS</span><strong>{'$'}{fmt(selected.metrics?.selection.cost_usd,2)}</strong></div>
            </div>
            {entries.length>0&&<div className="evo-entries">
              <strong>Research B · first {entries.length} hypothetical entries</strong>
              {entries.map((entry,i)=><div key={i}>
                <span>{entry.open_time??`Step ${entry.step??'—'}`}</span>
                <b>{entry.side}</b><span>{fmt(entry.price,3)}</span>
              </div>)}
            </div>}
            {selected.metrics?.training.trades===0&&
              <p className="evo-flat-note">No entry decisions in research B. This agent is inactive, not profitable; probation applies.</p>}
            <p><Dna size={13}/> Genome {selected.genome_sha256.slice(0,15)}…</p>
            <p><GitBranch size={13}/> Parent {selected.parent_id??'New random initialisation'}</p>
          </div>}
        </aside>
      </div>
      {entryStatus&&<div className="evo-entry-diagnostics">
        <strong>Historical replay entry audit · generation {latestEvaluation?.generation}</strong>
        <div><span>Training B: {entryStatus.training_entries_total} hypothetical entries
          ({entryStatus.training_inactive_agents}/{entryStatus.evaluated_agents} agents inactive)</span>
        <span>Diagnostic C: {entryStatus.diagnostic_entries_total} hypothetical entries
          ({entryStatus.diagnostic_inactive_agents}/{entryStatus.evaluated_agents} agents inactive)</span></div>
        <small>Training B controls ranking. Diagnostic C may show zero even when B entered. These are historical replay simulations, not live or paper broker orders.</small>
      </div>}
      <div className="evo-floor-index">
        <div><Trophy size={16}/><strong>ROOF / PENTHOUSE</strong><span>Locked · independent slice D never used</span></div>
        <div><ShieldCheck size={16}/><strong>51–99 / ELITE</strong><span>Inaccessible until real-data evidence gates</span></div>
        <div><Bot size={16}/><strong>21–49 / SURVIVORS</strong><span>Positive research results; rank alone never triggers elimination</span></div>
        <div><Dna size={16}/><strong>G / NURSERY</strong><span>Neural children start here</span></div>
      </div>
      <div className="evo-toolbar">
        {state?.initialized&&!real&&<div className="evo-source-switch">
          <label htmlFor="evo-real-provider">Historical XAU/USD source</label>
          <select id="evo-real-provider" value={source} onChange={e=>setSource(e.target.value as 'oanda'|'dukascopy')} disabled={busy||auto}>
            <option value="oanda">OANDA practice bid/ask</option>
            <option value="dukascopy">Dukascopy bid/ask</option>
          </select>
          <button className="btn btn-secondary" onClick={()=>void activateReal()} disabled={busy||auto}>
            {busy?'Importing real quotes…':'Switch tower to real data'}
          </button>
        </div>}
        {real&&state?.research_data&&<p className="evo-real-provenance">
          Observed XAU/USD M15 BID/ASK · {state.research_data.provider} · {state.research_data.observations_received} bars
          · {state.research_data.d_bars_withheld} final bars withheld · B ranks · C diagnostic only · Research generation {state.real_generation??0}
        </p>}
        {!state?.initialized?<button className="btn btn-primary" onClick={()=>void action('start')} disabled={busy}>
          <Dna size={17}/>{busy?'Creating research population…':'Generate 16 agents'}</button>:<>
          <button className="btn btn-primary" onClick={()=>void action('advance')} disabled={busy||auto||(state.generation??0)>=100}>
            <Play size={16}/>{busy?'Evaluating…':'Run next generation'}</button>
          <button className={'btn '+(auto?'btn-primary':'btn-secondary')} disabled={busy||(state.generation??0)>=100}
            onClick={()=>setAuto(x=>!x)}>
            {auto?<CirclePause size={16}/>:<RotateCw size={16}/>}
            {auto?'Pause auto evolution':'Auto-evolve in this tab'}
          </button>
          <button className="btn btn-secondary" onClick={()=>setShowArchive(x=>!x)}>
            <Skull size={16}/>{showArchive?'Hide':'View'} failure archive
          </button>
        </>}
        <span>Each generation is saved to PostgreSQL · auto-evolve every 10 seconds</span>
      </div>
      {state?.initialized&&events.length>0&&events[0].type==='GENERATION_EVALUATED'&&
        <div className={'evo-event'+(culls===0?' safe':'')}>
          {culls>0?<Skull size={17}/>:<ShieldCheck size={17}/>}
          Generation {state?.generation}: {culls>0
            ? `${culls} retired for risk or persistent underperformance · ${culls} replacements spawned.`
            : 'No bots retired; the full population survived this assessment.'}
          {' '}{probation} on probation. No compulsory bottom-half purge.
        </div>}
      {showArchive&&<div className="evo-archive" aria-label="Evolution failure archive">
        <h3>Archived research failures</h3>
        {events.length?events.flatMap(e=>e.removed.map(a=>({gen:e.generation,...a}))).map((a,i)=>
          <div key={a.id+'-'+i}><span>{a.id}</span><span>Gen {a.gen} · from Floor {a.from_floor}</span><strong>{label(a.reason)}</strong></div>)
          :<p>No eliminated agents yet.</p>}
      </div>}
      {error&&<p className="message-error" role="alert"><ShieldAlert size={15}/>{error}</p>}
      <p className="evo-disclaimer"><ShieldAlert size={15}/><span>{real
        ? 'Real XAU/USD BID/ASK historical quotes are used in a costed hypothetical replay. Observed spreads are real; slippage, commissions and financing remain estimates. Entries shown here are replayed historical decisions, NOT broker orders. B drives evolutionary selection, repeatedly viewed C is diagnostic only, and the final D bars remain withheld. Three assessments of the same bars are not independent validation.'
        : 'This engineering prototype currently uses synthetic random-walk data. Connect an approved real BID/ASK feed above to begin historical research.'}
        {' '}The building rankings do not independently establish a market edge, trading qualification or permission. No 24/7 worker is deployed; auto evolution runs only while this page remains open.</span></p>
    </>}
  </section>
}
