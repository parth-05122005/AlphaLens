import type { AuthResponse, User } from '../types'
import { api } from './client'

export async function login(username: string, password: string) {
  const { data } = await api.post<{ access: string; refresh: string }>('/auth/login/', { username, password })
  return data
}

export async function register(username: string, email: string, password: string) {
  const { data } = await api.post<AuthResponse>('/auth/register/', { username, email, password })
  return data
}

export async function fetchMe() {
  const { data } = await api.get<User>('/auth/me/')
  return data
}
