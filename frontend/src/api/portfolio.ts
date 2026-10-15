import type { Holding, HoldingInput, Paginated, Period, PortfolioSummary, PriceHistory, TaskAccepted, TaskStatus } from '../types'
import { api } from './client'

export async function listHoldings() {
  // Portfolios are small; one page of 100 covers the prototype.
  const { data } = await api.get<Paginated<Holding>>('/holdings/', { params: { page_size: 100 } })
  return data.results
}

export async function getHolding(id: number) {
  return (await api.get<Holding>(`/holdings/${id}/`)).data
}

export async function createHolding(input: HoldingInput) {
  return (await api.post<Holding>('/holdings/', input)).data
}

export async function updateHolding(id: number, input: Partial<HoldingInput>) {
  return (await api.patch<Holding>(`/holdings/${id}/`, input)).data
}

export async function deleteHolding(id: number) {
  await api.delete(`/holdings/${id}/`)
}

export async function refreshPrices() {
  return (await api.post<TaskAccepted>('/holdings/refresh-prices/')).data
}

export async function getPriceHistory(id: number, period: Period) {
  return (await api.get<PriceHistory>(`/holdings/${id}/history/`, { params: { period } })).data
}

export async function getSummary() {
  return (await api.get<PortfolioSummary>('/portfolio/summary/')).data
}

export async function getTaskStatus(taskId: string) {
  return (await api.get<TaskStatus>(`/tasks/${taskId}/`)).data
}
