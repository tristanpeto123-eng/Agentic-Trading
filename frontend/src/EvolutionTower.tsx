import { useEffect, useMemo, useState } from 'react'
import { Bot, ChevronDown, ChevronUp, CirclePause, Dna, GitBranch, Layers3, Play, RotateCw, ShieldAlert, ShieldCheck, Skull, Trophy } from 'lucide-react'
import { api } from './api'
import { EvolutionTowerScene } from './EvolutionTowerScene'
import type { TowerAgent, TowerEvent } from './EvolutionTowerScene'
import './EvolutionTower.css'

type TowerState = {
  initialized:boolean;research_only:true;generation?:number;total_born?:number;total_culled?:number
  agents?:TowerAgent[];last_events?:TowerEvent[];state_sha256?:string
  penthouse_locked:true;population_size?:number;mode?:string
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
  const [showArchive,setShowArchive]=useState(false)
  const [expanded,setExpanded]=useState(true)
  const agents=state?.agents??[]
  const events=state?.last_events??[]
  const sorted=useMemo(()=>[...agents].sort((a,b)=>b.floor-a.floor||
    (b.metrics?.selection.fitness??-999)-(a.metrics?.selection.fitness??-999)),[agents])
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
      if(kind==='advance')setSelectedId(result.agents?.[0]?.id??null)
    }catch(e){setAuto(false);setError(e instanceof Error?e.message:'Evolution step failed')}
    finally{setBusy(false)}
  }
  useEffect(()=>{
    if(!auto||busy||!state?.initialized||state.generation===undefined||state.generation>=100)return
    const timer=window.setTimeout(()=>void action('advance'),2800)
    return()=>window.clearTimeout(timer)
  // Auto-evolve intentionally only runs while this browser tab is mounted.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[auto,busy,state?.generation,state?.initialized])
  const culls=events.length?events[0].removed.length:0
  return <section className="surface evo-shell" aria-label="Evolution Tower research arena">
    <div className="evo-heading">
      <div><p className="eyebrow">ATL · EVOLUTIONARY RESEARCH ARENA</p>
        <h2><Layers3 size={23}/> Evolution Tower <span>v1</span></h2>
        <p>100-floor 3D command centre · a population of real saved neural chromosomes</p>
      </div>
      <div className="evo-head-right">
        <span className="evo-experiment"><span/> SYNTHETIC RESEARCH</span>
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
            <EvolutionTowerScene agents={agents} events={events} selectedId={selected?.id??null} onSelect={setSelectedId}/>
            <div className="evo-view-top"><span>CAM 01 · ORBIT VIEW</span><span>FLOOR {selected?.floor??1}</span></div>
            <div className="evo-view-legend">
              <span><i className="evo-dot nursery"/> Nursery</span>
              <span><i className="evo-dot survivor"/> Survivors</span>
              <span><i className="evo-dot leader"/> Research leader</span>
            </div>
            <div className="evo-zoom-help">Drag to orbit · pinch to zoom · tap a robot</div>
          </>:<div className="evo-empty">
            <Layers3 size={42}/>
            <strong>YOUR EVOLUTION TOWER</strong>
            <p>Generate 16 simulated neural agents and see them occupy the building. Each generation evaluates costs, archives failures and breeds successors.</p>
          </div>}
        </div>
        <aside className="evo-sidebar">
          <div className="evo-sidebar-title"><div><p className="eyebrow">LIVE RANKINGS</p>
            <h3>Research population</h3></div><span>{agents.length} robots</span></div>
          <div className="evo-agent-list">
            {sorted.length?sorted.map((a,index)=><button key={a.id}
              className={'evo-agent-row'+(selected?.id===a.id?' active':'')}
              onClick={()=>setSelectedId(a.id)}>
                <span className={'evo-mini-bot '+(a.status==='research_leader'?'winner':'')}><Bot size={18}/></span>
                <span className="evo-agent-copy"><strong>{a.id}</strong><small>Gen {a.generation} · {level(a.floor)}</small></span>
                <span className="evo-agent-score">F{a.floor.toString().padStart(2,'0')}<small>{index===0?'TOP':fmt(a.metrics?.selection.fitness,2)}</small></span>
              </button>):<div className="evo-no-agents">No research population created yet.</div>}
          </div>
          {selected&&<div className="evo-inspect">
            <div className="evo-inspect-title"><span>INSPECTING AGENT</span><strong>{selected.id}</strong></div>
            <div className="evo-inspect-grid">
              <div><span>FLOOR</span><strong>{selected.floor}</strong></div>
              <div><span>GENERATION</span><strong>{selected.generation}</strong></div>
              <div><span>NET RETURN · TOY C</span><strong>{fmt(selected.metrics?.selection.return_pct,2)}%</strong></div>
              <div><span>MAX DRAWDOWN · TOY C</span><strong>{fmt(selected.metrics?.selection.drawdown_pct,2)}%</strong></div>
              <div><span>SIMULATED ENTRIES</span><strong>{selected.metrics?.selection.trades??'—'}</strong></div>
              <div><span>EXECUTION COSTS</span><strong>{'$'}{fmt(selected.metrics?.selection.cost_usd,2)}</strong></div>
            </div>
            <p><Dna size={13}/> Genome {selected.genome_sha256.slice(0,15)}…</p>
            <p><GitBranch size={13}/> Parent {selected.parent_id??'New random initialisation'}</p>
          </div>}
        </aside>
      </div>
      <div className="evo-floor-index">
        <div><Trophy size={16}/><strong>ROOF / PENTHOUSE</strong><span>Locked · independent slice D never used</span></div>
        <div><ShieldCheck size={16}/><strong>51–99 / ELITE</strong><span>Inaccessible until real-data evidence gates</span></div>
        <div><Bot size={16}/><strong>21–49 / SURVIVORS</strong><span>Relative positive toy-selection score</span></div>
        <div><Dna size={16}/><strong>G / NURSERY</strong><span>Neural children start here</span></div>
      </div>
      <div className="evo-toolbar">
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
        <span>Each generation is saved to PostgreSQL</span>
      </div>
      {culls>0&&<div className="evo-event"><Skull size={17}/> Generation {state?.generation}: {culls} eliminated · descendants spawned in the nursery. Failure reasons are preserved.</div>}
      {showArchive&&<div className="evo-archive" aria-label="Evolution failure archive">
        <h3>Archived research failures</h3>
        {events.length?events.flatMap(e=>e.removed.map(a=>({gen:e.generation,...a}))).map((a,i)=>
          <div key={a.id+'-'+i}><span>{a.id}</span><span>Gen {a.gen} · from Floor {a.from_floor}</span><strong>{label(a.reason)}</strong></div>)
          :<p>No eliminated agents yet.</p>}
      </div>}
      {error&&<p className="message-error" role="alert"><ShieldAlert size={15}/>{error}</p>}
      <p className="evo-disclaimer"><ShieldAlert size={15}/> This engineering prototype uses deterministic random-walk data, assumed friction and bounded browser-driven generations. The building and rankings reflect saved simulation events, but <strong>none establishes a market edge, trading qualification or permission.</strong> No 24/7 worker is deployed; auto evolution runs only while this page remains open.</p>
    </>}
  </section>
}
