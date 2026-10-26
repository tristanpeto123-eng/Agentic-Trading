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
export type CEO = { email: string; role: 'ceo'; csrf_token: string }
export type Dashboard = {
  students_total: number; students_training: number; research_qualified: number; historical_datasets_total: number
  market_data_status: string; research_status: string
  historical_trading: string; paper_trading: string; live_trading: string
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
