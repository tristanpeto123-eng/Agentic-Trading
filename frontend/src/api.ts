export type Mode = 'autonomous' | 'directed'
export type Tab = 'home' | 'students' | 'trading'
export type TradingMode = 'historical' | 'paper' | 'live'
export type Market = 'XAUUSD' | 'EURUSD' | 'GBPUSD' | 'US500' | 'NAS100' | 'BTCUSD'
export type Skill = 'trend' | 'breakout' | 'range' | 'scalping' | 'swing' | 'risk_management'
export type StudentInput = { name: string; mode: Mode; markets: Market[]; skills: Skill[] }
export type PlanInput = { mode: Mode; markets: Market[]; skills: Skill[]; reason?: string }
export type LearningPlan = PlanInput & { version: number; reason: string; created_at: string }
export type Student = {
  id: string; name: string; status: 'research_pending'; created_at: string; updated_at: string
  learning_plan: LearningPlan; plan_history?: LearningPlan[] | null
  training_active: boolean; qualification: 'unqualified'
}
export type HistoricalDataset = {
  id: string; instrument: 'XAUUSD'; timeframe: 'M15'; provider: string
  state: 'quarantined'; research_eligible: false; source_hash: string; canonical_hash: string
  quality_report: { rows: number; gap_count: number; calendar_days: number; warnings: string[]; first_open: string; last_close: string }
  ingested_at: string
}
export type SkillProgress = {
  skill_id: string; title: string; version: number; target: boolean
  experience_count: number; good: number; bad: number; flat: number
  net_pnl_usd: string; net_r: string; mastery_status: 'unassessed'; research_qualified: false
  evidence_warning: string
}
export type StudentSkillProgress = {
  student_id: string; catalog_sha256: string; qualification: 'unqualified'; skills: SkillProgress[]
}
export type MemoryEpisode = {
  event_id: string; instrument: string; strategy_version: string; skill_ids: string[]
  partition: 'train' | 'validation' | 'holdout'; origin: string; available_at: string
  outcome: 'good' | 'bad' | 'flat'; net_pnl_usd: string; net_r: string
  gross_pnl_usd: string; fees_usd: string; spread_cost_usd: string
  slippage_cost_usd: string; close_reason: string; research_qualified: false
  content_sha256: string
}
export type StudentMemory = { student_id: string; episodes: MemoryEpisode[]; qualification: 'unqualified'; note: string }
export type TrainingMetrics = { epoch: number; train_loss: number; development_loss: number }
export type StudentTrainingRun = {
  run_id: string; student_id: string; state: 'research_only'; qualification: 'unqualified'
  config: { market: Market; tactic: string; plan_version: number; epochs: number; as_of: string }
  epoch: number; metrics: TrainingMetrics[]; research_eligible: false; snapshot_sha256: string
}
export type StudentTrainingHistory = {
  student_id: string; runs: StudentTrainingRun[]; qualification: 'unqualified'
  automatic_training_enabled: false; note: string
}
export type ExamMetrics = {
  closed_trades: number; rejected_trades: number; unresolved_trades: number
  wins: number; losses: number; flat: number
  net_pnl_usd: string; profit_factor: string | null
  max_drawdown_fraction: string; final_equity_usd: string; journal_sha256: string
}
export type StudentExam = {
  exam_id: string; student_id: string; market: string; tactic: string
  challenger_model_sha256: string; incumbent_model_sha256: string | null
  report_sha256: string; challenger: ExamMetrics; incumbent: ExamMetrics
  challenger_outperformed: boolean; numerical_thresholds_passed: boolean
  verdict: 'PROVISIONAL_NUMERIC_PASS' | 'PROVISIONAL_NUMERIC_FAIL'
  qualification: 'unqualified'; research_promotion_allowed: false
  paper_trading_allowed: false; live_trading_allowed: false; blockers: string[]
}
export type StudentExamHistory = {
  student_id: string; exams: StudentExam[]; qualification: 'unqualified'
  automatic_promotion_enabled: false; note: string
}
export type CEO = { email: string; role: 'ceo'; csrf_token: string }
export type Dashboard = {
  students_total: number; students_training: number; research_qualified: number; historical_datasets_total: number
  market_data_status: string; research_status: string
  historical_research: 'available'; historical_trading: string; paper_trading: string; live_trading: string
  system_health: string; net_pnl: number | null; open_positions: number | null
  attention: string[]
}

let csrfToken: string | null = null
export function setCsrf(value: string | null) { csrfToken = value }

export class APIError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

export async function api<T>(endpoint: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(endpoint, {
    method,
    credentials: 'same-origin',
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(method !== 'GET' && csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  })
  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const json = await response.json()
      if (typeof json.detail === 'string') message = json.detail
      else if (Array.isArray(json.detail)) message = json.detail.map((x: { msg?: string }) => x.msg ?? 'Invalid input').join('; ')
    } catch { /* API unavailable or non-JSON error */ }
    throw new APIError(response.status, message)
  }
  return response.json() as Promise<T>
}

export const MARKETS: { id: Market; label: string; family: string }[] = [
  { id: 'XAUUSD', label: 'Gold', family: 'Commodities' },
  { id: 'EURUSD', label: 'EUR / USD', family: 'Forex' },
  { id: 'GBPUSD', label: 'GBP / USD', family: 'Forex' },
  { id: 'US500', label: 'S&P 500', family: 'Indices' },
  { id: 'NAS100', label: 'Nasdaq 100', family: 'Indices' },
  { id: 'BTCUSD', label: 'Bitcoin', family: 'Crypto' },
]
export const SKILLS: { id: Skill; label: string }[] = [
  { id: 'trend', label: 'Trend trading' }, { id: 'breakout', label: 'Breakouts' },
  { id: 'range', label: 'Range trading' }, { id: 'scalping', label: 'Scalping' },
  { id: 'swing', label: 'Swing trading' }, { id: 'risk_management', label: 'Risk management' },
]

export type AcademyState = { curriculum: { mode: Mode; plan_version: number; market_targets: string[]; tactic_targets: string[]; next_lesson: string }; jobs: { id: string; state: string; market: string; tactic: string; attempts: number; qualification: 'unqualified' }[]; autonomous_training_enabled: false; note: string }
export type EvolutionState = { tree: { strategies: {id:string; family:string; version:number; market:string; tactic:string; parent_ids:string[]; dna_sha256:string; qualified:false}[] }; lessons: {id:string;source_student_id:string;skill_id:string;mentor_qualified:false}[]; mentor_status:{eligible:false;blocker:string}; qualification:'unqualified' }
export type SentinelState = { status: 'research_safe'|'attention'|'blocked'; findings: {area:string;severity:string;reason:string}[]; safety: {locked:true;reason:string;paper_enabled:false;live_enabled:false}; research_data_verified:false }

export type PaperAccountPosition = {
  symbol: string; side: string; qty: string | null
  market_value: string | null; unrealized_pl: string | null
  avg_entry_price: string | null; current_price: string | null
}
export type PaperAccountSnapshot = {
  configured: boolean; paper_api_readable: boolean; reason?: string
  account_bound?: boolean; account_suffix?: string; account_status?: string
  currency?: string; cash?: string | null; equity?: string | null
  buying_power?: string | null; positions_count?: number
  positions?: PaperAccountPosition[]; positions_truncated?: boolean
  open_orders_count?: number; open_orders_count_capped?: boolean
  as_of_utc?: string; paper_trading_enabled: false; live_trading_enabled: false
  broker_order_execution_enabled?: false; student_order_execution_enabled?: false
  note?: string
}

export type PaperReadiness = { ready:false; activation_allowed:false; paper_trading_enabled:false; live_trading_enabled:false; blockers:string[]; next_action:string }
