export interface User {
  id: number
  username: string
  email: string
}

export interface AuthResponse {
  user: User
  access: string
  refresh: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface TaskAccepted {
  task_id: string
}

export type TaskState = 'PENDING' | 'STARTED' | 'RETRY' | 'SUCCESS' | 'FAILURE' | 'REVOKED'

export interface TaskStatus {
  task_id: string
  state: TaskState
  ready: boolean
}

export interface Holding {
  id: number
  symbol: string
  name: string
  sector: string | null
  quantity: string
  avg_buy_price: string
  last_price: string | null
  last_price_at: string | null
  news_refreshed_at: string | null
  created_at: string
  invested: number
  value: number
  pnl: number
  pnl_pct: number
}

export interface HoldingInput {
  symbol: string
  name?: string
  sector?: string
  quantity: string
  avg_buy_price: string
}

export interface SummaryHolding {
  id: number
  symbol: string
  name: string
  sector: string | null
  quantity: number
  avg_buy_price: number
  last_price: number | null
  last_price_at: string | null
  invested: number
  value: number
  pnl: number
  pnl_pct: number
}

export interface PortfolioSummary {
  total_invested: number
  current_value: number
  pnl: number
  pnl_pct: number
  allocation_by_sector: { sector: string; value: number }[]
  holdings: SummaryHolding[]
  prices_updated_at: string | null
}

export type Period = '1mo' | '6mo' | '1y'

export interface PriceHistory {
  symbol: string
  period: Period
  points: { date: string; close: number }[]
}
