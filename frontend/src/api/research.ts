import type { Document, DocumentFilters, Paginated, TaskAccepted } from '../types'
import { api } from './client'

export async function listDocuments(filters: DocumentFilters = {}, page = 1) {
  const { data } = await api.get<Paginated<Document>>('/documents/', { params: { ...filters, page } })
  return data
}

export async function deleteDocument(id: number) {
  await api.delete(`/documents/${id}/`)
}

export async function uploadDocument(file: File, holding?: number) {
  const form = new FormData()
  form.append('file', file)
  if (holding) form.append('holding', String(holding))
  const { data } = await api.post<Document & TaskAccepted>('/documents/upload/', form)
  return data
}

export async function refreshNews(holdingId: number) {
  return (await api.post<TaskAccepted>(`/holdings/${holdingId}/refresh-news/`)).data
}
