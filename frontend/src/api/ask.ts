import type { AiStats, AskResponse, Paginated, QueryLogEntry } from '../types'
import { api } from './client'

export async function ask(question: string, holdingIds: number[] = []) {
  return (await api.post<AskResponse>('/ask/', { question, holding_ids: holdingIds })).data
}

export async function askHistory() {
  return (await api.get<Paginated<QueryLogEntry>>('/ask/history/')).data.results
}

export async function getStats() {
  return (await api.get<AiStats>('/stats/')).data
}
