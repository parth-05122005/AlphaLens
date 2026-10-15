import type { Agent, AgentInput, AgentRun, Paginated, RiskAlert } from '../types'
import { api } from './client'

export async function listAgents() {
  return (await api.get<Paginated<Agent>>('/agents/', { params: { page_size: 100 } })).data.results
}

export async function getAgent(id: number) {
  return (await api.get<Agent>(`/agents/${id}/`)).data
}

export async function createAgent(input: AgentInput) {
  return (await api.post<Agent>('/agents/', input)).data
}

export async function updateAgent(id: number, input: Partial<AgentInput>) {
  return (await api.patch<Agent>(`/agents/${id}/`, input)).data
}

export async function deleteAgent(id: number) {
  await api.delete(`/agents/${id}/`)
}

export async function runAgent(id: number) {
  return (await api.post<AgentRun>(`/agents/${id}/run/`)).data
}

export async function listRuns(agentId: number) {
  return (await api.get<Paginated<AgentRun>>(`/agents/${agentId}/runs/`)).data.results
}

export async function getRun(id: number) {
  return (await api.get<AgentRun>(`/agent-runs/${id}/`)).data
}

export async function getAlerts() {
  return (await api.get<RiskAlert[]>('/alerts/')).data
}
