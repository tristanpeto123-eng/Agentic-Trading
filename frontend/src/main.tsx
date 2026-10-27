import React, { useCallback, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Activity, ArrowLeft, ArrowRight, BarChart3, BookOpen, Bot, Check, ChevronRight, ClipboardList, Database, GraduationCap, Home, Layers3, LockKeyhole, LogOut, Plus, RefreshCw, ShieldCheck, ShieldOff, Sparkles, UserPlus, Users, X, AlertCircle, Settings2, BookMarked, Search, Target, Clock3, FileUp, FileCheck2, GitBranch, ShieldAlert } from 'lucide-react'
import { api, APIError, MARKETS, SKILLS, setCsrf } from './api'
import type { CEO, Dashboard, HistoricalDataset, LearningPlan, Market, Mode, PlanInput, Skill, Student, StudentInput, StudentSkillProgress, StudentMemory, StudentTrainingHistory, StudentExamHistory, AcademyState, EvolutionState, SentinelState, PaperReadiness, Tab, TradingMode } from './api'
import { HistoricalResearch } from './HistoricalResearch'
import { HistoricalDemoLab } from './HistoricalDemoLab'
import { BrowserCsvReplay } from './BrowserCsvReplay'
import './styles.css'

const NUM_FORMAT = new Intl.NumberFormat('en-GB')
function friendlyDate(date: string): string {
  const value = new Date(date)
  return Number.isNaN(value.getTime()) ? '—' : value.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}
const shortId = (student: Student) => student.id.split('-')[0].toUpperCase()
const titleCase = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())
function ModePill({ mode }: { mode: Mode }) {
  return <span className={`pill ${mode === 'autonomous' ? 'pill-blue' : 'pill-amber'}`}>
    {mode === 'autonomous' ? <Sparkles size={12} /> : <Target size={12} />} {mode === 'autonomous' ? 'Autonomous' : 'CEO-directed'}
  </span>
}
function EmptyIcon({ icon: Icon }: { icon: typeof Users }) {
  return <div className="empty-icon"><Icon size={22} strokeWidth={1.65} /></div>
}
function Login({ onLogin }: { onLogin: (ceo: CEO) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setBusy(true); setError('')
    try {
      const user = await api<CEO>('/v1/auth/login', 'POST', { email, password })
      setCsrf(user.csrf_token)
      onLogin(user)
    } catch (err) { setError(err instanceof Error ? err.message : 'Login failed') }
    finally { setBusy(false) }
  }
  return <main className="login-layout">
    <div className="login-art" aria-hidden="true">
      <div className="visual-grid" />
      <div className="login-art-body">
        <div className="brand brand-large"><span className="brand-symbol"><Layers3 size={21}/></span> AGENTIC<span>TRADING</span></div>
        <p className="eyebrow">INTELLIGENCE, UNDER YOUR CONTROL</p>
        <h1>Train the system.<br/><em>Keep the authority.</em></h1>
        <p className="login-description">Your command centre for developing, evaluating and overseeing independent AI trading students.</p>
        <div className="login-steps"><span>01 &nbsp; LEARN</span><span>02 &nbsp; VALIDATE</span><span>03 &nbsp; DECIDE</span></div>
      </div>
    </div>
    <div className="login-panel">
      <div className="login-card">
        <span className="login-lock"><LockKeyhole size={19}/></span>
        <p className="eyebrow">CEO ACCESS ONLY</p>
        <h2>Welcome back.</h2>
        <p className="muted">Sign in to your private operating console.</p>
        <form onSubmit={submit} className="login-form">
          <label>Email address<input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required placeholder="ceo@example.com" /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required placeholder="Enter your password" /></label>
          {error && <p className="message-error" role="alert"><AlertCircle size={15} /> {error}</p>}
          <button className="btn btn-primary btn-wide" disabled={busy}>{busy ? 'Signing in…' : 'Access console'} <ArrowRight size={16}/></button>
        </form>
        <div className="login-footer"><ShieldCheck size={15}/> Research only. No broker or trading is connected.</div>
      </div>
      <div className="login-bottom">Agentic Trading <span>·</span> Research environment v0.1</div>
    </div>
  </main>
}

const newForm = (): StudentInput => ({ name: '', mode: 'autonomous', markets: [], skills: [] })
function Selector({ form, onChange }: { form: StudentInput | PlanInput; onChange: (v: StudentInput | PlanInput) => void }) {
  const toggleMarket = (market: Market) => onChange({ ...form, markets: form.markets.includes(market) ? form.markets.filter(x => x !== market) : [...form.markets, market] })
  const toggleSkill = (skill: Skill) => onChange({ ...form, skills: form.skills.includes(skill) ? form.skills.filter(x => x !== skill) : [...form.skills, skill] })
  return <>
    <div className="field-set">
      <label className="form-label">Learning direction</label>
      <div className="mode-options" role="group" aria-label="Learning direction">
        <button type="button" className={`mode-option ${form.mode === 'autonomous' ? 'selected' : ''}`} onClick={() => onChange({ ...form, mode: 'autonomous', markets: [], skills: [] })}>
          <Sparkles size={19}/><strong>Autonomous</strong><span>Academy decides what to research.</span>
        </button>
        <button type="button" className={`mode-option ${form.mode === 'directed' ? 'selected' : ''}`} onClick={() => onChange({ ...form, mode: 'directed' })}>
          <Target size={19}/><strong>CEO-directed</strong><span>You choose markets and skills.</span>
        </button>
      </div>
    </div>
    {form.mode === 'directed' && <>
      <div className="field-set">
        <label className="form-label">Target markets <span className="required">· choose at least one</span></label>
        <div className="chip-grid">{MARKETS.map(m => <button type="button" key={m.id} className={`pick-chip ${form.markets.includes(m.id) ? 'picked' : ''}`} onClick={() => toggleMarket(m.id)} aria-pressed={form.markets.includes(m.id)}>
          <span>{m.label}<small>{m.family}</small></span>{form.markets.includes(m.id) ? <Check size={15}/> : <Plus size={14}/>}</button>)}</div>
      </div>
      <div className="field-set">
        <label className="form-label">Target skills <span className="required">· choose at least one</span></label>
        <div className="skill-chips">{SKILLS.map(s => <button type="button" key={s.id} className={`skill-chip ${form.skills.includes(s.id) ? 'picked' : ''}`} onClick={() => toggleSkill(s.id)} aria-pressed={form.skills.includes(s.id)}>{form.skills.includes(s.id) ? <Check size={13}/> : <Plus size={13}/>} {s.label}</button>)}</div>
      </div>
    </>}
  </>
}
function CreateStudent({ onClose, onCreate }: { onClose: () => void; onCreate: (s: StudentInput) => Promise<void> }) {
  const [form, setForm] = useState<StudentInput>(newForm)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])
  const generate = () => {
    const names = ['Orion', 'Nova', 'Atlas', 'Kairo', 'Vortex', 'Lyra', 'Axiom', 'Solace']
    const rand = new Uint32Array(1)
    crypto.getRandomValues(rand)
    setForm(f => ({ ...f, name: `${names[rand[0] % names.length]} ${String(rand[0] % 10000).padStart(4, '0')}` }))
  }
  const valid = form.name.trim().length >= 2 && (form.mode === 'autonomous' || (form.markets.length > 0 && form.skills.length > 0))
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setSaving(true)
    try { await onCreate(form) }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not create student') }
    finally { setSaving(false) }
  }
  return <div className="dialog-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
    <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="create-title">
      <div className="dialog-head"><div><p className="eyebrow">ACADEMY / ENROLMENT</p><h2 id="create-title">Create new student</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><X size={19}/></button></div>
      <form onSubmit={submit}>
        <div className="dialog-scroll">
          <div className="field-set"><label className="form-label" htmlFor="student-name">Student name</label>
            <div className="name-input"><input id="student-name" placeholder="e.g. Orion" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} maxLength={40} autoFocus required /><button type="button" className="btn btn-secondary" onClick={generate}><Sparkles size={15}/> Generate</button></div>
            <p className="field-help">Every student has its own permanent identity and separate history.</p>
          </div>
          <Selector form={form} onChange={v => setForm(v as StudentInput)}/>
          <div className="research-notice"><ShieldCheck size={18}/><p><strong>Research only</strong><br/>Creating a student does not start trading or grant skill mastery. Training becomes available in a later sprint.</p></div>
          {error && <p className="message-error" role="alert"><AlertCircle size={16}/> {error}</p>}
        </div>
        <div className="dialog-actions"><button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button><button type="submit" disabled={!valid || saving} className="btn btn-primary"><UserPlus size={16}/> {saving ? 'Creating…' : 'Create student'}</button></div>
      </form>
    </section>
  </div>
}
function ChangePlan({ student, onClose, onSave }: { student: Student; onClose: () => void; onSave: (p: PlanInput) => Promise<void> }) {
  const [form, setForm] = useState<PlanInput>({ mode: student.learning_plan.mode, markets: student.learning_plan.markets, skills: student.learning_plan.skills, reason: 'CEO updated learning direction' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const valid = form.mode === 'autonomous' || (form.markets.length > 0 && form.skills.length > 0)
  const submit = async (e: React.FormEvent) => { e.preventDefault(); setSaving(true); setError(''); try { await onSave(form) } catch (err) { setError(err instanceof Error ? err.message : 'Could not save plan') } finally { setSaving(false) } }
  return <div className="dialog-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}><section className="dialog" role="dialog" aria-modal="true" aria-labelledby="direction-title">
    <div className="dialog-head"><div><p className="eyebrow">{student.name} · PLAN V{student.learning_plan.version}</p><h2 id="direction-title">Change learning direction</h2></div><button onClick={onClose} className="icon-button" aria-label="Close"><X size={19}/></button></div>
    <form onSubmit={submit}><div className="dialog-scroll"><Selector form={form} onChange={v => setForm(v)}/>
      <div className="field-set"><label className="form-label" htmlFor="reason">Reason for change</label><textarea id="reason" rows={2} value={form.reason} onChange={e => setForm(p => ({ ...p, reason: e.target.value }))} maxLength={200}/></div>
      <div className="research-notice"><BookMarked size={18}/><p>A new version of the plan will be recorded. Previous plans, student identity and history are preserved. No trading permissions change.</p></div>
      {error && <p className="message-error" role="alert"><AlertCircle size={16}/> {error}</p>}</div>
      <div className="dialog-actions"><button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button><button className="btn btn-primary" disabled={!valid || saving || !form.reason?.trim()}>{saving ? 'Saving…' : 'Save new plan'} <ArrowRight size={16}/></button></div>
    </form>
  </section></div>
}
function ProfileSkillsPane({ student }: { student: Student }) {
  const [data, setData] = useState<StudentSkillProgress | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setData(null); setError('')
    void api<StudentSkillProgress>(`/v1/students/${student.id}/skills`).then(value => {
      if (active) setData(value)
    }).catch(err => { if (active) setError(err instanceof Error ? err.message : 'Could not load skills') })
    return () => { active = false }
  }, [student.id, student.learning_plan.version])
  if (error) return <div className="surface empty-panel"><p role="alert" className="message-error">{error}</p></div>
  if (!data) return <div className="surface empty-panel"><p>Loading skill catalogue…</p></div>
  return <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">ACADEMY / SKILLS</p><h3>Skill Library</h3></div><GraduationCap size={19}/></div>
    <div className="panel-content">
      <p className="skills-disclaimer">Experience is not mastery. Only independently examined evidence can qualify a skill. Current observations are research-only.</p>
      {data.skills.length === 0 ? <div className="dataset-empty"><BookOpen size={19}/><span>No skill targets or experiences recorded yet. Autonomous assignment starts with future training workers.</span></div>
        : <div className="skill-progress-list">{data.skills.map(skill => <div className="skill-progress-row" key={skill.skill_id}>
          <div className="skill-progress-head"><strong>{skill.title}</strong><span className="pill pill-muted">{skill.mastery_status === 'unassessed' ? 'Unassessed' : skill.mastery_status}</span></div>
          <div className="skill-progress-meta"><span>{skill.target ? 'Learning target' : 'Observed skill'} · v{skill.version}</span><span>{skill.experience_count} archived experiences</span></div>
          {skill.experience_count > 0 && <div className="skill-progress-meta"><span>Good {skill.good} · Bad {skill.bad} · Flat {skill.flat}</span><span>Net {skill.net_r}R (research)</span></div>}
        </div>)}</div>}
    </div>
  </section>
}
function ProfileMemoryPane({ student }: { student: Student }) {
  const [data, setData] = useState<StudentMemory | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setData(null); setError('')
    void api<StudentMemory>(`/v1/students/${student.id}/memory`).then(value => {
      if (active) setData(value)
    }).catch(err => { if (active) setError(err instanceof Error ? err.message : 'Could not load memories') })
    return () => { active = false }
  }, [student.id])
  if (error) return <div className="surface empty-panel"><p role="alert" className="message-error">{error}</p></div>
  if (!data) return <div className="surface empty-panel"><p>Loading memory archive…</p></div>
  const good = data.episodes.filter(e => e.outcome === 'good').length
  const bad = data.episodes.filter(e => e.outcome === 'bad').length
  const flat = data.episodes.filter(e => e.outcome === 'flat').length
  return <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">ACADEMY / EPISODIC MEMORY</p><h3>Good / Bad archive</h3></div><BookOpen size={19}/></div>
    <div className="panel-content"><p className="skills-disclaimer">Closed-trade research memories, net of costs. Training recall excludes validation and holdout episodes. None of this establishes profitability or qualification.</p>
      <div className="memory-totals"><span><strong>{good}</strong> Good</span><span><strong>{bad}</strong> Bad</span><span><strong>{flat}</strong> Flat</span></div>
      {data.episodes.length === 0 ? <div className="dataset-empty"><BookOpen size={19}/><span>No closed research experiences yet. The Learning Academy has not started training.</span></div>
        : <div className="memory-list">{data.episodes.map(item => <div className="memory-row" key={item.event_id}>
          <div className="skill-progress-head"><strong>{item.instrument} · {item.strategy_version}</strong><span className={`memory-outcome ${item.outcome}`}>{titleCase(item.outcome)}</span></div>
          <div className="skill-progress-meta"><span>Net {item.net_r}R · ${item.net_pnl_usd}</span><span>{friendlyDate(item.available_at)}</span></div>
          <div className="skill-progress-meta"><span>{item.origin.replaceAll('_', ' ')} · {item.partition}</span><span>Research only</span></div>
        </div>)}</div>}
    </div>
  </section>
}
function TrainingCurve({ metrics }: { metrics: { epoch: number; train_loss: number; development_loss: number }[] }) {
  if (!metrics.length) return null
  const width = 620, height = 160, pad = 16
  const all = metrics.flatMap(m => [m.train_loss, m.development_loss]).filter(Number.isFinite)
  const lo = Math.min(...all), hi = Math.max(...all)
  const range = Math.max(0.01, hi - lo)
  const point = (m: { epoch: number; train_loss: number; development_loss: number }, i: number, field: 'train_loss' | 'development_loss') => {
    const x = pad + (metrics.length === 1 ? 0 : i * (width - 2 * pad) / (metrics.length - 1))
    const y = height - pad - (m[field] - lo) * (height - 2 * pad) / range
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }
  return <div className="training-graph"><svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Training and development loss by epoch" preserveAspectRatio="none">
    <polyline points={metrics.map((m,i) => point(m,i,'train_loss')).join(' ')} fill="none" stroke="#58bfd3" strokeWidth="3"/>
    <polyline points={metrics.map((m,i) => point(m,i,'development_loss')).join(' ')} fill="none" stroke="#e0b270" strokeWidth="3"/>
  </svg><div className="training-legend"><span>● Training loss</span><span>● Development loss</span></div></div>
}
function ProfileTrainingPane({ student }: { student: Student }) {
  const [data, setData] = useState<StudentTrainingHistory | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setData(null); setError('')
    void api<StudentTrainingHistory>(`/v1/students/${student.id}/training`)
      .then(value => { if (active) setData(value) })
      .catch(err => { if (active) setError(err instanceof Error ? err.message : 'Unable to load training history') })
    return () => { active = false }
  }, [student.id])
  if (error) return <div className="surface empty-panel"><p role="alert" className="message-error">{error}</p></div>
  if (!data) return <div className="surface empty-panel">Loading training history…</div>
  return <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">ACADEMY / NEURAL RESEARCH</p><h3>Training history</h3></div><Activity size={19}/></div><div className="panel-content">
    <p className="skills-disclaimer">Model losses are research diagnostics, not profitability, skill mastery or independent examination. Automatic training remains disabled.</p>
    {data.runs.length === 0 ? <div className="dataset-empty"><BookOpen size={19}/><span>No neural training runs recorded yet. Offline research training requires closed, eligible training memories.</span></div>
      : <div className="skill-progress-list">{data.runs.map(run => <div className="skill-progress-row" key={run.run_id}>
          <div className="skill-progress-head"><strong>{run.config.market} · {titleCase(run.config.tactic)}</strong><span className="pill pill-muted">Research only</span></div>
          <div className="skill-progress-meta"><span>Epoch {run.epoch} / {run.config.epochs}</span><span>Plan v{run.config.plan_version} · Unqualified</span></div>
          <TrainingCurve metrics={run.metrics}/>
          <div className="skill-progress-meta"><span>Snapshot {run.snapshot_sha256.slice(0,12)}…</span><span>Not examined</span></div>
        </div>)}</div>}
  </div></section>
}
function ProfileExamsPane({ student }: { student: Student }) {
  const [data, setData] = useState<StudentExamHistory | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let mounted = true
    setData(null); setError('')
    void api<StudentExamHistory>(`/v1/students/${student.id}/exams`)
      .then(value => { if (mounted) setData(value) })
      .catch(err => { if (mounted) setError(err instanceof Error ? err.message : 'Unable to load examinations') })
    return () => { mounted = false }
  }, [student.id])
  if (error) return <div className="surface empty-panel"><p className="message-error" role="alert">{error}</p></div>
  if (!data) return <div className="surface empty-panel">Loading examination records…</div>
  return <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">ACADEMY / INDEPENDENT EXAMINER</p><h3>Examination reports</h3></div><ClipboardList size={19}/></div>
    <div className="panel-content"><p className="skills-disclaimer">These are <strong>provisional historical-research comparisons</strong>, not independently qualified profitability. No model promotion, paper or live trading is authorised.</p>
      {data.exams.length === 0 ? <div className="dataset-empty"><ClipboardList size={19}/><span>No independent historical research examinations recorded yet. Verified market data is still required for qualification.</span></div>
      : <div className="skill-progress-list">{data.exams.map(exam => <div className="skill-progress-row" key={exam.exam_id}>
        <div className="skill-progress-head"><strong>{exam.market} · {titleCase(exam.tactic)}</strong><span className="pill pill-amber">{exam.verdict === 'PROVISIONAL_NUMERIC_PASS' ? 'Provisional numeric pass' : 'Numeric fail'}</span></div>
        <div className="skill-progress-meta"><span>Closed trades: {exam.challenger.closed_trades}</span><span>Net P&amp;L: ${exam.challenger.net_pnl_usd}</span></div>
        <div className="skill-progress-meta"><span>Profit factor: {exam.challenger.profit_factor ?? 'Undefined'}</span><span>Max drawdown: {(Number(exam.challenger.max_drawdown_fraction) * 100).toFixed(1)}%</span></div>
        <div className="skill-progress-meta"><span>Compared with {exam.incumbent_model_sha256 ? 'incumbent strategy' : 'cash baseline'}</span><span>Qualification: unqualified</span></div>
        <small className="muted">Report SHA {exam.report_sha256.slice(0,12)}… · {exam.blockers.length} outstanding safeguards</small>
      </div>)}</div>}
    </div></section>
}
function ProfileAcademyPane({ student }: { student: Student }) {
  const [value,setValue] = useState<AcademyState|null>(null)
  const [error,setError] = useState('')
  useEffect(() => { let active=true; void api<AcademyState>(`/v1/students/${student.id}/academy`).then(r=>{if(active)setValue(r)}).catch(e=>{if(active)setError(String(e))}); return ()=>{active=false} },[student.id])
  return <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">RESEARCH SCHEDULER</p><h3>Academy lessons</h3></div><GraduationCap size={18}/></div><div className="panel-content">
    {error && <p role="alert">{error}</p>}{!value && !error && <p>Loading Academy…</p>}
    {value && <><p className="skills-disclaimer">{value.note}</p><div className="plan-row"><span>Next lesson</span><strong>{value.curriculum.next_lesson}</strong></div><div className="plan-row"><span>Learning plan</span><strong>v{value.curriculum.plan_version}</strong></div>
      {!value.jobs.length ? <div className="dataset-empty">No scheduled research jobs yet.</div> : value.jobs.map(job=><div key={job.id} className="memory-row"><strong>{job.market} · {job.tactic}</strong><span className="pill pill-muted">{titleCase(job.state)}</span><p>Attempt {job.attempts} · Unqualified research</p></div>)}</>}
  </div></section>
}
function ProfileEvolutionPane({ student }: { student: Student }) {
  const [value,setValue] = useState<EvolutionState|null>(null)
  const [error,setError] = useState('')
  useEffect(() => { let active=true; void api<EvolutionState>(`/v1/students/${student.id}/evolution`).then(r=>{if(active)setValue(r)}).catch(e=>{if(active)setError(String(e))});return ()=>{active=false} },[student.id])
  return <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">STRATEGY DNA</p><h3>Evolution tree</h3></div><GitBranch size={18}/></div><div className="panel-content">
  {error && <p role="alert">{error}</p>}{!value && !error && <p>Loading strategy evolution…</p>}
  {value && <><p className="skills-disclaimer">Research candidates only. Inheritance does not confer proficiency or trading rights.</p>
    {!value.tree.strategies.length && <div className="dataset-empty">No strategy versions recorded yet.</div>}
    {value.tree.strategies.map(revision=><div key={revision.id} className="memory-row"><div className="skill-progress-head"><strong>{revision.family} v{revision.version}</strong><span className="pill pill-muted">Candidate</span></div><p>{revision.market} · {revision.tactic} · {revision.parent_ids.length} parent(s)</p><small>DNA {revision.dna_sha256.slice(0,12)}…</small></div>)}
    <h3>Peer lessons</h3>{!value.lessons.length ? <p className="muted">No lessons shared with this student.</p> : value.lessons.map(l=><p key={l.id}>{l.skill_id} · Research material</p>)}
    <p className="skills-disclaimer">Mentorship: {value.mentor_status.blocker}</p></>}
  </div></section>
}
function StudentProfile({ student, onBack, onEdit }: { student: Student; onBack: () => void; onEdit: () => void }) {
  const [section, setSection] = useState<'overview' | 'skills' | 'memory' | 'training' | 'exams' | 'academy' | 'evolution'>('overview')
  const history = student.plan_history ?? [student.learning_plan]
  return <div className="page-enter">
    <button className="back-link" onClick={onBack}><ArrowLeft size={16}/> All students</button>
    <div className="profile-head"><div className="student-avatar student-avatar-lg">{student.name[0]?.toUpperCase()}</div><div className="profile-name"><p className="eyebrow">STUDENT / {shortId(student)}</p><h1>{student.name}</h1><div className="profile-meta"><ModePill mode={student.learning_plan.mode}/><span className="pill pill-muted">Awaiting research</span><span className="muted">Enrolled {friendlyDate(student.created_at)}</span></div></div><button className="btn btn-secondary" onClick={onEdit}><Settings2 size={17}/> Change direction</button></div>
    <div className="profile-summary"><Sparkles size={20}/><div><strong>Academy briefing</strong><p>{student.name} has been enrolled with {student.learning_plan.mode === 'autonomous' ? 'an autonomous research plan. Academy will select learning targets when training is available.' : `a CEO-directed plan covering ${student.learning_plan.markets.join(', ')} and ${student.learning_plan.skills.map(titleCase).join(', ')}.`} Automatic training has not started. Neural research runs are currently offline-only and require archived closed training examples.</p></div></div>
    <div className="section-tabs" role="tablist" aria-label="Student profile sections">{(['overview','skills','memory','training','exams','academy','evolution'] as const).map(tab => <button key={tab} role="tab" aria-selected={section === tab} className={section === tab ? 'active' : ''} onClick={() => setSection(tab)}>{titleCase(tab)}</button>)}</div>
    {section === 'overview' && <div className="two-columns"><section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">CURRENT DIRECTION</p><h3>Learning plan <span className="version">v{student.learning_plan.version}</span></h3></div><Target size={18}/></div><div className="panel-content"><div className="plan-row"><span>Mode</span><ModePill mode={student.learning_plan.mode}/></div><div className="plan-row"><span>Target markets</span><strong>{student.learning_plan.markets.length ? student.learning_plan.markets.join(', ') : 'Academy selected (future)'}</strong></div><div className="plan-row"><span>Target skills</span><strong>{student.learning_plan.skills.length ? student.learning_plan.skills.map(titleCase).join(', ') : 'Academy selected (future)'}</strong></div><div className="plan-row"><span>Qualification</span><strong>Not yet assessed</strong></div><button className="text-action" onClick={onEdit}>Adjust learning plan <ArrowRight size={15}/></button></div></section>
      <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">VERSION HISTORY</p><h3>Development record</h3></div><Clock3 size={18}/></div><div className="panel-content"><div className="timeline">{[...history].reverse().map((plan: LearningPlan) => <div key={plan.version} className="timeline-item"><div className="timeline-mark"/><div><strong>Learning plan v{plan.version}</strong><p>{plan.reason}</p><small>{friendlyDate(plan.created_at)} · {plan.mode === 'autonomous' ? 'Autonomous' : 'CEO-directed'}</small></div></div>)}</div></div></section></div>}
    {section === 'skills' && <ProfileSkillsPane student={student}/>}
    {section === 'memory' && <ProfileMemoryPane student={student}/>}
    {section === 'training' && <ProfileTrainingPane student={student}/>}
    {section === 'exams' && <ProfileExamsPane student={student}/>}
    {section === 'academy' && <ProfileAcademyPane student={student}/>}
    {section === 'evolution' && <ProfileEvolutionPane student={student}/>}
  </div>
}
function Header({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="page-header"><div><p className="eyebrow">CEO CONSOLE / {title.toUpperCase()}</p><h1>{title}</h1><p className="page-subtitle">{description}</p></div>{action && <div className="header-action">{action}</div>}</div>
}
function DataEnginePanel() {
  const [datasets, setDatasets] = useState<HistoricalDataset[]>([])
  const [showImport, setShowImport] = useState(false)
  const [importAvailable, setImportAvailable] = useState<boolean | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [ownerUnverified, setOwnerUnverified] = useState(true)
  const [provider, setProvider] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [rights, setRights] = useState('')
  const [extractRef, setExtractRef] = useState('')
  const [basis, setBasis] = useState<'bid'|'ask'|'mid'|'trade'|'unknown'>('unknown')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const load = useCallback(async () => {
    try { setDatasets(await api<HistoricalDataset[]>('/v1/datasets')) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load dataset records') }
  }, [])
  useEffect(() => { void load() }, [load])
  useEffect(() => { void api<{ historical_data_import_enabled: boolean }>('/v1/capabilities')
    .then(c => setImportAvailable(c.historical_data_import_enabled)).catch(() => setImportAvailable(false)) }, [])
  const importData = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!selectedFile) { setError('Select an M15 CSV file'); return }
    if (selectedFile.size > 12 * 1024 * 1024) { setError('File exceeds 12 MiB import limit'); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const content = await selectedFile.text()
      const dataset = await api<HistoricalDataset>('/v1/datasets/import', 'POST', {
        source: { provider: ownerUnverified ? 'USER_SUPPLIED_UNVERIFIED' : provider,
          source_url: ownerUnverified ? null : sourceUrl,
          rights_reference: ownerUnverified ? 'UNVERIFIED_OWNER_ARCHIVE' : rights,
          extraction_reference: ownerUnverified ? 'Owner-provided ' + selectedFile.name : extractRef,
          acquired_at: new Date().toISOString(),
          instrument: 'XAUUSD', timeframe: 'M15', price_basis: basis,
          timezone: 'UTC', evidence_kind: 'historical' }, csv_content: content
      })
      setNotice(`Import recorded: ${dataset.quality_report.rows.toLocaleString('en-GB')} bars. Quarantined until provenance verification.`)
      setShowImport(false); setSelectedFile(null); await load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Import rejected') }
    finally { setBusy(false) }
  }
  return <section className="surface panel data-engine-panel" aria-label="Historical data engine">
    <div className="panel-heading"><div><p className="eyebrow">HISTORICAL DATA · SPRINT 02</p><h3>Data Engine</h3></div><button className="btn btn-secondary" disabled={importAvailable === false} onClick={() => setShowImport(!showImport)}><FileUp size={16}/>{showImport ? 'Close' : 'Import CSV'}</button></div>
    <div className="data-engine-content">
      {importAvailable === false && <p className="message-error">Import requires your persistent PostgreSQL connection. Check the Render DATABASE_URL environment variable; your existing students are not affected.</p>}
      <p className="data-explainer">Import XAUUSD M15 history, including private owner archives without a known provider URL. Every imported dataset remains <strong>quarantined</strong> until its origin and usage rights can be independently established. No automatic training, qualification or trading is enabled.</p>
      {notice && <p className="data-notice" role="status"><FileCheck2 size={15}/>{notice}</p>}
      {error && <p className="message-error" role="alert"><AlertCircle size={16}/>{error}</p>}
      {showImport && <form className="data-import-form" onSubmit={importData}>
        <label>CSV file — UTC M15, time/open/high/low/close or timestamp_open/open/high/low/close<input type="file" accept=".csv,text/csv" required onChange={e => setSelectedFile(e.target.files?.[0] ?? null)}/></label>
        <label className="owner-source-option"><input type="checkbox" checked={ownerUnverified} onChange={e=>setOwnerUnverified(e.target.checked)} /> Owner-supplied private file — source/licence not yet verified</label>
        {!ownerUnverified && <>
          <label>Source provider<input value={provider} onChange={e=>setProvider(e.target.value)} required minLength={3} maxLength={120} placeholder="Provider name"/></label>
          <label>Export or source URL (HTTPS)<input type="url" value={sourceUrl} onChange={e=>setSourceUrl(e.target.value)} required placeholder="https://provider.example/..."/></label>
          <label>Export reference<input value={extractRef} onChange={e=>setExtractRef(e.target.value)} required minLength={3} placeholder="Broker download ID / export command"/></label>
          <label>Usage rights reference<input value={rights} onChange={e=>setRights(e.target.value)} required minLength={8} placeholder="Provider licence or agreement reference"/></label>
        </>}
        <label>OHLC price convention<select value={basis} onChange={e=>setBasis(e.target.value as typeof basis)}><option value="unknown">Unknown / not verified</option><option value="mid">Mid</option><option value="bid">Bid</option><option value="ask">Ask</option><option value="trade">Trades</option></select></label>
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Validating…' : 'Validate & freeze dataset'}</button>
        <small>Maximum 12 MiB. UTC bars only. Potential bad ticks, price jumps and gaps remain flagged. A source label never certifies authenticity or legality.</small>
      </form>}
      <div className="dataset-list">{!datasets.length && <div className="dataset-empty"><Database size={18}/><span>No historical datasets imported yet.</span></div>}
        {datasets.map(d=><div className="dataset-row" key={d.id}><div className="dataset-summary"><strong>{d.instrument} · {d.timeframe}</strong><span>{d.provider} · {d.quality_report.rows.toLocaleString('en-GB')} bars · {d.quality_report.calendar_days.toFixed(1)} days</span><small>{d.quality_report.gap_count} detected gaps · SHA {d.source_hash.slice(0,12)}…</small></div><span className="pill pill-amber">Quarantined</span></div>)}
      </div>
    </div>
  </section>
}
function SentinelPanel() {
  const [state,setState]=useState<SentinelState|null>(null)
  const [error,setError]=useState('')
  const [busy,setBusy]=useState(false)
  const refresh=useCallback(()=>{void api<SentinelState>('/v1/sentinel/report').then(setState).catch(e=>setError(String(e)))},[])
  useEffect(()=>{refresh()},[refresh])
  const stop=async()=>{setBusy(true);setError('');try { await api('/v1/safety/emergency-stop','POST');refresh() } catch(e){setError(String(e))} finally{setBusy(false)}}
  return <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">SAFETY / SENTINEL</p><h3>Research integrity</h3></div><ShieldAlert size={19}/></div><div className="panel-content">
  <div className="plan-row"><span>Scanner</span><strong>{state ? titleCase(state.status) : 'Checking…'}</strong></div>
  <div className="plan-row"><span>Trading safety latch</span><strong>Locked</strong></div>
  <div className="plan-row"><span>Source verification</span><strong>Outstanding</strong></div>
  {state?.findings.map((f,i)=><p key={i} className="skills-disclaimer">{f.area}: {f.reason}</p>)}
  {error && <p role="alert" className="message-error">{error}</p>}
  <button className="btn btn-secondary" type="button" onClick={()=>void stop()} disabled={busy}><ShieldOff size={16}/> Engage emergency stop</button>
  <p className="muted">Stop is latched and has no in-app unlock. Paper/live trading are not available.</p>
  </div></section>
}
function HomePage({ dashboard, onNew, onStudents }: { dashboard: Dashboard | null; onNew: () => void; onStudents: () => void }) {
  const rows = [{ label: 'Enrolled students', value: dashboard ? NUM_FORMAT.format(dashboard.students_total) : '—', icon: Users, detail: 'Created AI identities' },
    { label: 'Students training', value: dashboard ? NUM_FORMAT.format(dashboard.students_training) : '—', icon: GraduationCap, detail: 'Workers not enabled' },
    { label: 'Qualified strategies', value: dashboard ? NUM_FORMAT.format(dashboard.research_qualified) : '—', icon: ShieldCheck, detail: 'Requires independent exams' },
    { label: 'System status', value: dashboard ? 'Online' : '—', icon: Activity, detail: 'API connection status' }]
  return <div className="page-enter"><Header title="Overview" description="Your research command centre. A clear view of what exists, what is learning and what needs your decision." action={<button className="btn btn-primary" onClick={onNew}><Plus size={17}/> New student</button>}/>
    <div className="scope-banner"><span className="scope-dot"/><span><strong>Research environment</strong> · No market feed, broker account or trading permission is active.</span><span className="scope-stage">RESEARCH · S10</span></div>
    <div className="metrics-grid">{rows.map(row => <div className="surface metric-card" key={row.label}><div className="metric-top"><span>{row.label}</span><row.icon size={19}/></div><strong>{row.value}</strong><small>{row.detail}</small></div>)}</div>
    <div className="dashboard-grid"><section className="surface panel overview-main"><div className="panel-heading"><div><p className="eyebrow">FINANCIAL PERFORMANCE</p><h3>Trading overview</h3></div><span className="pill pill-muted"><ShieldOff size={13}/> Disabled</span></div><div className="scope-selector"><span>Historical</span><span>Paper</span><span>Live</span></div><div className="blank-chart"><BarChart3 size={30} strokeWidth={1.2}/><strong>No performance data yet</strong><p>Equity curves, realised net P&amp;L and trade journals require verified market data and a validated simulator.</p><small>Not zero profit. No financial results exist.</small></div></section>
      <div className="dashboard-aside"><section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">ACTION CENTRE</p><h3>Needs attention</h3></div><span className="count-badge">{dashboard?.attention.length ?? 0}</span></div><div className="notice-list"><div className="notice-item"><div className="notice-icon"><Database size={17}/></div><div><strong>Historical data onboarding</strong><p>Import XAUUSD data and review quality; source verification is still required.</p><span>Research prerequisites</span></div><ChevronRight size={16}/></div></div></section><section className="surface panel quick-panel"><div className="panel-heading"><div><p className="eyebrow">ACADEMY</p><h3>Start building your cohort</h3></div><Users size={19}/></div><div className="panel-content"><p className="muted">Give your students identities and choose their learning direction before data and training come online.</p><button className="btn btn-secondary btn-wide" onClick={onStudents}>Open student academy <ArrowRight size={16}/></button></div></section></div></div>
    <SentinelPanel/>
    <DataEnginePanel/>
    <div className="footer-note"><LockKeyhole size={14}/> No orders, positions, broker balances or live deployment controls are available in this sprint.</div>
  </div>
}
function StudentsPage({ students, onNew, onOpen }: { students: Student[]; onNew: () => void; onOpen: (id: string) => void }) {
  const [search, setSearch] = useState('')
  const filtered = students.filter(s => s.name.toLowerCase().includes(search.toLowerCase()))
  return <div className="page-enter"><Header title="Students" description="Independent identities. Individual histories. One academy." action={<button onClick={onNew} className="btn btn-primary"><UserPlus size={17}/> Create student</button>}/>
    <div className="students-tools"><div className="search-wrap"><Search size={18}/><input placeholder="Search students…" value={search} onChange={e => setSearch(e.target.value)} aria-label="Search students"/></div><span className="results-count">{students.length} enrolled</span></div>
    {!students.length && <div className="surface empty-panel student-empty"><EmptyIcon icon={Bot}/><p className="eyebrow">YOUR ACADEMY STARTS HERE</p><h2>No students yet.</h2><p>Create your first named AI student. Choose its learning direction now; verified training comes later.</p><button className="btn btn-primary" onClick={onNew}><Plus size={17}/> Create first student</button></div>}
    {students.length > 0 && <div className="student-grid">{filtered.map(student => <button key={student.id} className="surface student-card" onClick={() => onOpen(student.id)}><div className="student-card-head"><div className="student-avatar">{student.name[0]?.toUpperCase()}</div><span className="pill pill-muted">Research pending</span></div><h3>{student.name}</h3><p className="student-serial">STUDENT {shortId(student)}</p><div className="student-card-divider"/><div className="student-card-detail"><span>Learning</span><ModePill mode={student.learning_plan.mode}/></div><div className="student-card-detail"><span>Plan version</span><strong>v{student.learning_plan.version}</strong></div><div className="student-card-detail"><span>Training</span><span className="muted">Not started</span></div><div className="student-card-footer">Open profile <ArrowRight size={16}/></div></button>)}{filtered.length === 0 && <div className="surface empty-panel"><p>No student matches “{search}”.</p></div>}</div>}
    <section className="academy-bottom"><div className="academy-icon"><GraduationCap size={20}/></div><div><strong>A growing academy, not identical bots.</strong><p>Each student will gain independent memories, Strategy DNA, specialist skills and research qualifications. Collaborations and examinations are scheduled for later sprints.</p></div></section>
  </div>
}
function PaperReadinessPanel() {
  const [state,setState]=useState<PaperReadiness|null>(null)
  const [error,setError]=useState('')
  useEffect(()=>{let active=true; void api<PaperReadiness>('/v1/paper/readiness').then(data=>{if(active)setState(data)}).catch(e=>{if(active)setError(String(e))});return()=>{active=false}},[])
  return <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">SPRINT 11 / PRE-FLIGHT</p><h3>Paper pilot readiness</h3></div><ShieldOff size={18}/></div><div className="panel-content">
    <p className="skills-disclaimer">Research is not permission to trade. Paper activation remains locked until verified data, independent exams, operational checks and your exact authorisation.</p>
    {error && <p role="alert" className="message-error">{error}</p>}
    {!state && !error && <p className="muted">Checking readiness…</p>}
    {state && <><div className="plan-row"><span>Paper pilot</span><strong>Not authorised</strong></div>
      <div className="plan-row"><span>Live operations</span><strong>Disabled</strong></div>
      <div className="skill-progress-list">{state.blockers.map((blocker,i)=><div className="memory-row" key={i}><ShieldAlert size={15}/> {blocker}</div>)}</div>
      <small className="muted">{state.next_action}</small></>}
  </div></section>
}
function TradingPage() {
  const [scope, setScope] = useState<TradingMode>('historical')
  const details = {
    paper: { heading: 'Paper trading is disabled', intro: 'Pilot readiness has been evaluated, but independent data verification and CEO activation are still required.', next: 'Review the pre-flight blockers below' },
    live: { heading: 'Live trading is disabled', intro: 'Real-money trading remains outside this programme until separate readiness checks and exact CEO approval.', next: 'Not scheduled in current sprints' },
  }
  return <div className="page-enter">
    <Header title="Trading" description="Try the synthetic simulator or replay your own M15 candles locally. Paper and live remain locked."/>
    <div className="trading-switch" role="tablist" aria-label="Trading environment">
      {(['historical','paper','live'] as const).map(m => <button key={m} role="tab"
        aria-selected={scope === m} className={scope === m ? 'active' : ''} onClick={() => setScope(m)}>
        {titleCase(m)} <span className="mode-disabled">{m === 'historical' ? 'REPLAY' : 'LOCKED'}</span>
      </button>)}
    </div>
    {scope === 'historical' ? <>
      <HistoricalDemoLab/>
      <BrowserCsvReplay/>
      <HistoricalResearch/>
      <DataEnginePanel/>
    </> : <>
      <div className="surface trading-placeholder">
        <div className="trading-disabled-icon"><ShieldOff size={29}/></div>
        <span className="pill pill-muted">{scope.toUpperCase()} · NOT ENABLED</span>
        <h2>{details[scope].heading}</h2>
        <p>{details[scope].intro}</p>
        <div className="coming-next"><Clock3 size={16}/>{details[scope].next}</div>
      </div>
      <div className="trading-bottom">
        <div className="surface small-status"><div className="small-status-top"><BarChart3 size={18}/><span>Equity &amp; net P&amp;L</span></div><strong>Not available</strong><small>No qualified financial results</small></div>
        <div className="surface small-status"><div className="small-status-top"><ClipboardList size={18}/><span>Trade journal</span></div><strong>Empty</strong><small>No operational trading activity</small></div>
        <div className="surface small-status"><div className="small-status-top"><ShieldCheck size={18}/><span>CEO permissions</span></div><strong>None granted</strong><small>No trading model deployed</small></div>
      </div>
      {scope === 'paper' && <PaperReadinessPanel/>}
    </>}
  </div>
}

function App() {
  const [ceo, setCeo] = useState<CEO | null>(null)
  const [initialising, setInitialising] = useState(true)
  const [tab, setTab] = useState<Tab>('home')
  const [dashboard, setDashboard] = useState<Dashboard | null>(null)
  const [students, setStudents] = useState<Student[]>([])
  const [activeStudent, setActiveStudent] = useState<Student | null>(null)
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState(false)
  const [banner, setBanner] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const refresh = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [d, s] = await Promise.all([api<Dashboard>('/v1/dashboard'), api<Student[]>('/v1/students')])
      setDashboard(d); setStudents(s)
    } catch (err) {
      if (err instanceof APIError && err.status === 401) { setCeo(null); setCsrf(null) }
      else setError(err instanceof Error ? err.message : 'Connection failed')
    } finally { setLoading(false) }
  }, [])
  useEffect(() => {
    api<CEO>('/v1/auth/me').then(user => { setCeo(user); setCsrf(user.csrf_token) }).catch(() => { setCeo(null); setCsrf(null) }).finally(() => setInitialising(false))
  }, [])
  useEffect(() => { if (ceo) void refresh() }, [ceo, refresh])
  const navigate = (next: Tab) => { setTab(next); setActiveStudent(null); setBanner('') }
  const openStudent = async (id: string) => {
    try { setActiveStudent(await api<Student>(`/v1/students/${id}`)); setBanner('') }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not load student') }
  }
  const createStudent = async (input: StudentInput) => {
    const student = await api<Student>('/v1/students', 'POST', input)
    setCreating(false); setTab('students'); await refresh(); await openStudent(student.id)
    setBanner(`${student.name} enrolled successfully. Research will begin once market data and training are available.`)
  }
  const savePlan = async (plan: PlanInput) => {
    if (!activeStudent) return
    const updated = await api<Student>(`/v1/students/${activeStudent.id}/direction`, 'PATCH', plan)
    setActiveStudent(updated); setEditing(false); await refresh(); setBanner(`Learning plan v${updated.learning_plan.version} saved. No trading permissions changed.`)
  }
  const logout = async () => {
    try { await api('/v1/auth/logout', 'POST') } catch { /* local session cleared regardless */ }
    setCsrf(null); setCeo(null); setStudents([]); setDashboard(null); setActiveStudent(null)
  }
  if (initialising) return <div className="boot"><span className="brand-symbol"><Layers3/></span><p>Loading your console…</p></div>
  if (!ceo) return <Login onLogin={user => { setCeo(user); setTab('home'); setActiveStudent(null) }}/>
  const nav: { id: Tab; label: string; icon: typeof Home }[] = [ { id: 'home', label: 'Home', icon: Home }, { id: 'students', label: 'Students', icon: Users }, { id: 'trading', label: 'Trading', icon: BarChart3 } ]
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-symbol"><Layers3 size={19}/></span><span>AGENTIC<strong>TRADING</strong></span></div><div className="sidebar-section"><p className="eyebrow">WORKSPACE</p><nav aria-label="Main navigation">{nav.map(n => <button key={n.id} className={`sidebar-link ${tab === n.id ? 'active' : ''}`} onClick={() => navigate(n.id)}><n.icon size={18}/>{n.label}{tab === n.id && <span className="nav-indicator"/>}</button>)}</nav></div><div className="sidebar-spacer"/><div className="side-system"><span className="online-dot"/><span>Research workspace</span><small>Development / S5</small></div><button className="sidebar-user" onClick={logout} title="Sign out"><span className="user-avatar">CEO</span><span><strong>Chief Executive</strong><small>{ceo.email}</small></span><LogOut size={17}/></button></aside>
    <div className="workspace"><header className="topbar"><div className="topbar-left"><span className="breadcrumb-brand">Agentic Trading</span><ChevronRight size={14}/><span>{tab === 'students' && activeStudent ? activeStudent.name : titleCase(tab)}</span></div><div className="topbar-right"><span className="environment-tag"><span className="online-dot"/> RESEARCH</span><button className="icon-button top-refresh" onClick={() => void refresh()} disabled={loading} title="Refresh data" aria-label="Refresh"><RefreshCw size={17} className={loading ? 'spin' : ''}/></button><span className="top-avatar">CEO</span></div></header>
      <main className="main-content">
        {error && <div className="message-error page-error" role="alert"><AlertCircle size={17}/>{error}<button onClick={() => setError('')} aria-label="Dismiss"><X size={16}/></button></div>}
        {banner && <div className="message-success" role="status"><Check size={17}/>{banner}<button onClick={() => setBanner('')} aria-label="Dismiss"><X size={16}/></button></div>}
        {tab === 'home' && <HomePage dashboard={dashboard} onNew={() => setCreating(true)} onStudents={() => navigate('students')}/>}
        {tab === 'students' && (activeStudent ? <StudentProfile student={activeStudent} onBack={() => setActiveStudent(null)} onEdit={() => setEditing(true)}/> : <StudentsPage students={students} onNew={() => setCreating(true)} onOpen={id => void openStudent(id)}/>)}
        {tab === 'trading' && <TradingPage/>}
      </main>
      <nav className="bottom-nav" aria-label="Mobile navigation">{nav.map(n => <button key={n.id} className={tab === n.id ? 'active' : ''} onClick={() => navigate(n.id)}><n.icon size={21} strokeWidth={tab === n.id ? 2.2 : 1.7}/><span>{n.label}</span></button>)}</nav>
    </div>
    {creating && <CreateStudent onClose={() => setCreating(false)} onCreate={createStudent}/>}
    {editing && activeStudent && <ChangePlan student={activeStudent} onClose={() => setEditing(false)} onSave={savePlan}/>}
  </div>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
