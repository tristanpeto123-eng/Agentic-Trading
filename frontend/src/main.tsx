import React, { useCallback, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Activity, ArrowLeft, ArrowRight, BarChart3, BookOpen, Bot, Check, ChevronRight, ClipboardList, Database, GraduationCap, Home, Layers3, LockKeyhole, LogOut, Plus, RefreshCw, ShieldCheck, ShieldOff, Sparkles, UserPlus, Users, X, AlertCircle, Settings2, BookMarked, Search, Target, Clock3, FileUp, FileCheck2 } from 'lucide-react'
import { api, APIError, MARKETS, SKILLS, setCsrf } from './api'
import type { CEO, Dashboard, HistoricalDataset, LearningPlan, Market, Mode, PlanInput, Skill, Student, StudentInput, StudentSkillProgress, StudentMemory, Tab, TradingMode } from './api'
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
function StudentProfile({ student, onBack, onEdit }: { student: Student; onBack: () => void; onEdit: () => void }) {
  const [section, setSection] = useState<'overview' | 'skills' | 'memory' | 'exams'>('overview')
  const history = student.plan_history ?? [student.learning_plan]
  return <div className="page-enter">
    <button className="back-link" onClick={onBack}><ArrowLeft size={16}/> All students</button>
    <div className="profile-head"><div className="student-avatar student-avatar-lg">{student.name[0]?.toUpperCase()}</div><div className="profile-name"><p className="eyebrow">STUDENT / {shortId(student)}</p><h1>{student.name}</h1><div className="profile-meta"><ModePill mode={student.learning_plan.mode}/><span className="pill pill-muted">Awaiting research</span><span className="muted">Enrolled {friendlyDate(student.created_at)}</span></div></div><button className="btn btn-secondary" onClick={onEdit}><Settings2 size={17}/> Change direction</button></div>
    <div className="profile-summary"><Sparkles size={20}/><div><strong>Academy briefing</strong><p>{student.name} has been enrolled with {student.learning_plan.mode === 'autonomous' ? 'an autonomous research plan. Academy will select learning targets when training is available.' : `a CEO-directed plan covering ${student.learning_plan.markets.join(', ')} and ${student.learning_plan.skills.map(titleCase).join(', ')}.`} Training has not started. Historical data and learning workers arrive in later sprints.</p></div></div>
    <div className="section-tabs" role="tablist" aria-label="Student profile sections">{(['overview','skills','memory','exams'] as const).map(tab => <button key={tab} role="tab" aria-selected={section === tab} className={section === tab ? 'active' : ''} onClick={() => setSection(tab)}>{titleCase(tab)}</button>)}</div>
    {section === 'overview' && <div className="two-columns"><section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">CURRENT DIRECTION</p><h3>Learning plan <span className="version">v{student.learning_plan.version}</span></h3></div><Target size={18}/></div><div className="panel-content"><div className="plan-row"><span>Mode</span><ModePill mode={student.learning_plan.mode}/></div><div className="plan-row"><span>Target markets</span><strong>{student.learning_plan.markets.length ? student.learning_plan.markets.join(', ') : 'Academy selected (future)'}</strong></div><div className="plan-row"><span>Target skills</span><strong>{student.learning_plan.skills.length ? student.learning_plan.skills.map(titleCase).join(', ') : 'Academy selected (future)'}</strong></div><div className="plan-row"><span>Qualification</span><strong>Not yet assessed</strong></div><button className="text-action" onClick={onEdit}>Adjust learning plan <ArrowRight size={15}/></button></div></section>
      <section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">VERSION HISTORY</p><h3>Development record</h3></div><Clock3 size={18}/></div><div className="panel-content"><div className="timeline">{[...history].reverse().map((plan: LearningPlan) => <div key={plan.version} className="timeline-item"><div className="timeline-mark"/><div><strong>Learning plan v{plan.version}</strong><p>{plan.reason}</p><small>{friendlyDate(plan.created_at)} · {plan.mode === 'autonomous' ? 'Autonomous' : 'CEO-directed'}</small></div></div>)}</div></div></section></div>}
    {section === 'skills' && <ProfileSkillsPane student={student}/>}
    {section === 'memory' && <ProfileMemoryPane student={student}/>}
    {section === 'exams' && <div className="surface empty-panel"><EmptyIcon icon={ClipboardList}/><h3>No examinations taken</h3><p>Students must earn qualifications from independent, leakage-checked evidence. No qualifications are granted at enrolment.</p></div>}
  </div>
}
function Header({ title, description, action }: { title: string; description: string; action?: React.ReactNode }) {
  return <div className="page-header"><div><p className="eyebrow">CEO CONSOLE / {title.toUpperCase()}</p><h1>{title}</h1><p className="page-subtitle">{description}</p></div>{action && <div className="header-action">{action}</div>}</div>
}
function DataEnginePanel() {
  const [datasets, setDatasets] = useState<HistoricalDataset[]>([])
  const [showImport, setShowImport] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [provider, setProvider] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [rights, setRights] = useState('')
  const [extractRef, setExtractRef] = useState('')
  const [basis, setBasis] = useState<'bid'|'ask'|'mid'|'trade'>('mid')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const load = useCallback(async () => {
    try { setDatasets(await api<HistoricalDataset[]>('/v1/datasets')) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to load dataset records') }
  }, [])
  useEffect(() => { void load() }, [load])
  const importData = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!selectedFile) { setError('Select an M15 CSV file'); return }
    if (selectedFile.size > 12 * 1024 * 1024) { setError('File exceeds 12 MiB import limit'); return }
    setBusy(true); setError(''); setNotice('')
    try {
      const content = await selectedFile.text()
      const dataset = await api<HistoricalDataset>('/v1/datasets/import', 'POST', {
        source: { provider, source_url: sourceUrl, rights_reference: rights,
          extraction_reference: extractRef, acquired_at: new Date().toISOString(),
          instrument: 'XAUUSD', timeframe: 'M15', price_basis: basis,
          timezone: 'UTC', evidence_kind: 'historical' }, csv_content: content
      })
      setNotice(`Import recorded: ${dataset.quality_report.rows.toLocaleString('en-GB')} bars. Quarantined until provenance verification.`)
      setShowImport(false); setSelectedFile(null); await load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Import rejected') }
    finally { setBusy(false) }
  }
  return <section className="surface panel data-engine-panel" aria-label="Historical data engine">
    <div className="panel-heading"><div><p className="eyebrow">HISTORICAL DATA · SPRINT 02</p><h3>Data Engine</h3></div><button className="btn btn-secondary" onClick={() => setShowImport(!showImport)}><FileUp size={16}/>{showImport ? 'Close' : 'Import CSV'}</button></div>
    <div className="data-engine-content">
      <p className="data-explainer">Import genuine XAUUSD M15 exports with source details. Every imported dataset is frozen, checked and <strong>quarantined</strong> until its provenance and usage rights are independently verified. No training or trading is enabled.</p>
      {notice && <p className="data-notice" role="status"><FileCheck2 size={15}/>{notice}</p>}
      {error && <p className="message-error" role="alert"><AlertCircle size={16}/>{error}</p>}
      {showImport && <form className="data-import-form" onSubmit={importData}>
        <label>CSV file — UTC M15, timestamp_open/open/high/low/close[/volume]<input type="file" accept=".csv,text/csv" required onChange={e => setSelectedFile(e.target.files?.[0] ?? null)}/></label>
        <label>Source provider<input value={provider} onChange={e=>setProvider(e.target.value)} required minLength={3} maxLength={120} placeholder="Provider name"/></label>
        <label>Export or source URL (HTTPS)<input type="url" value={sourceUrl} onChange={e=>setSourceUrl(e.target.value)} required placeholder="https://provider.example/..."/></label>
        <label>Export reference<input value={extractRef} onChange={e=>setExtractRef(e.target.value)} required minLength={3} placeholder="Broker download ID / export command"/></label>
        <label>Usage rights reference<input value={rights} onChange={e=>setRights(e.target.value)} required minLength={8} placeholder="Provider licence or agreement reference"/></label>
        <label>OHLC price convention<select value={basis} onChange={e=>setBasis(e.target.value as typeof basis)}><option value="mid">Mid</option><option value="bid">Bid</option><option value="ask">Ask</option><option value="trade">Trades</option></select></label>
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Validating…' : 'Validate & freeze dataset'}</button>
        <small>Maximum 12 MiB. Timestamps must be explicit UTC and bars must be closed. No missing prices are invented.</small>
      </form>}
      <div className="dataset-list">{!datasets.length && <div className="dataset-empty"><Database size={18}/><span>No historical datasets imported yet.</span></div>}
        {datasets.map(d=><div className="dataset-row" key={d.id}><div className="dataset-summary"><strong>{d.instrument} · {d.timeframe}</strong><span>{d.provider} · {d.quality_report.rows.toLocaleString('en-GB')} bars · {d.quality_report.calendar_days.toFixed(1)} days</span><small>{d.quality_report.gap_count} detected gaps · SHA {d.source_hash.slice(0,12)}…</small></div><span className="pill pill-amber">Quarantined</span></div>)}
      </div>
    </div>
  </section>
}
function HomePage({ dashboard, onNew, onStudents }: { dashboard: Dashboard | null; onNew: () => void; onStudents: () => void }) {
  const rows = [{ label: 'Enrolled students', value: dashboard ? NUM_FORMAT.format(dashboard.students_total) : '—', icon: Users, detail: 'Created AI identities' },
    { label: 'Students training', value: dashboard ? NUM_FORMAT.format(dashboard.students_training) : '—', icon: GraduationCap, detail: 'Workers not enabled' },
    { label: 'Qualified strategies', value: dashboard ? NUM_FORMAT.format(dashboard.research_qualified) : '—', icon: ShieldCheck, detail: 'Requires independent exams' },
    { label: 'System status', value: dashboard ? 'Online' : '—', icon: Activity, detail: 'API connection status' }]
  return <div className="page-enter"><Header title="Overview" description="Your research command centre. A clear view of what exists, what is learning and what needs your decision." action={<button className="btn btn-primary" onClick={onNew}><Plus size={17}/> New student</button>}/>
    <div className="scope-banner"><span className="scope-dot"/><span><strong>Research environment</strong> · No market feed, broker account or trading permission is active.</span><span className="scope-stage">SPRINT 02</span></div>
    <div className="metrics-grid">{rows.map(row => <div className="surface metric-card" key={row.label}><div className="metric-top"><span>{row.label}</span><row.icon size={19}/></div><strong>{row.value}</strong><small>{row.detail}</small></div>)}</div>
    <div className="dashboard-grid"><section className="surface panel overview-main"><div className="panel-heading"><div><p className="eyebrow">FINANCIAL PERFORMANCE</p><h3>Trading overview</h3></div><span className="pill pill-muted"><ShieldOff size={13}/> Disabled</span></div><div className="scope-selector"><span>Historical</span><span>Paper</span><span>Live</span></div><div className="blank-chart"><BarChart3 size={30} strokeWidth={1.2}/><strong>No performance data yet</strong><p>Equity curves, realised net P&amp;L and trade journals require verified market data and a validated simulator.</p><small>Not zero profit. No financial results exist.</small></div></section>
      <div className="dashboard-aside"><section className="surface panel"><div className="panel-heading"><div><p className="eyebrow">ACTION CENTRE</p><h3>Needs attention</h3></div><span className="count-badge">{dashboard?.attention.length ?? 0}</span></div><div className="notice-list"><div className="notice-item"><div className="notice-icon"><Database size={17}/></div><div><strong>Historical data onboarding</strong><p>Import XAUUSD data and review quality; source verification is still required.</p><span>Research prerequisites</span></div><ChevronRight size={16}/></div></div></section><section className="surface panel quick-panel"><div className="panel-heading"><div><p className="eyebrow">ACADEMY</p><h3>Start building your cohort</h3></div><Users size={19}/></div><div className="panel-content"><p className="muted">Give your students identities and choose their learning direction before data and training come online.</p><button className="btn btn-secondary btn-wide" onClick={onStudents}>Open student academy <ArrowRight size={16}/></button></div></section></div></div>
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
function TradingPage() {
  const [scope, setScope] = useState<TradingMode>('historical')
  const details: Record<TradingMode, { heading: string; intro: string; next: string }> = {
    historical: { heading: 'Historical testing not yet available', intro: 'Historical execution will replay verified data with cost-aware fills and immutable journals.', next: 'Planned: Data Engine (S2) and Simulator (S3)' },
    paper: { heading: 'Paper trading is disabled', intro: 'Paper operations require independently qualified models and explicit CEO authorisation.', next: 'Planned: Paper pilot (S11)' },
    live: { heading: 'Live trading is disabled', intro: 'Real-money trading remains completely outside this programme until separate readiness checks and exact CEO approval.', next: 'Not scheduled in current sprints' },
  }
  return <div className="page-enter"><Header title="Trading" description="Historical, paper and live are completely separate. No artificial balances or trading activity."/>
    <div className="trading-switch" role="tablist" aria-label="Trading environment">{(['historical','paper','live'] as const).map(m => <button key={m} role="tab" aria-selected={scope === m} className={scope === m ? 'active' : ''} onClick={() => setScope(m)}>{titleCase(m)} <span className="mode-disabled">OFFLINE</span></button>)}</div>
    <div className="surface trading-placeholder"><div className="trading-disabled-icon"><ShieldOff size={29}/></div><span className="pill pill-muted">{scope.toUpperCase()} · NOT ENABLED</span><h2>{details[scope].heading}</h2><p>{details[scope].intro}</p><div className="coming-next"><Clock3 size={16}/>{details[scope].next}</div></div>
    <div className="trading-bottom"><div className="surface small-status"><div className="small-status-top"><BarChart3 size={18}/><span>Equity &amp; net P&amp;L</span></div><strong>Not available</strong><small>No results have been generated</small></div><div className="surface small-status"><div className="small-status-top"><ClipboardList size={18}/><span>Trade journal</span></div><strong>Empty</strong><small>Independent journal comes with the simulator</small></div><div className="surface small-status"><div className="small-status-top"><ShieldCheck size={18}/><span>CEO permissions</span></div><strong>None granted</strong><small>No trading model deployed</small></div></div>
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
