import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import * as authApi from '../api/auth'
import { LOGOUT_EVENT, tokens } from '../api/client'
import type { User } from '../types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: (username: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(() => Boolean(tokens.access))

  const logout = useCallback(() => {
    tokens.clear()
    setUser(null)
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    if (!tokens.access) return
    let cancelled = false
    // Only a rejected token ends the session; a sleeping or restarting server is retried.
    async function restore(attempt = 1): Promise<void> {
      try {
        const me = await authApi.fetchMe()
        if (!cancelled) setUser(me)
      } catch (err) {
        const status = axios.isAxiosError(err) ? err.response?.status : undefined
        if (status === undefined && attempt < 4 && !cancelled) {
          await new Promise((r) => setTimeout(r, 2000 * attempt))
          return restore(attempt + 1)
        }
        if (status === 401) tokens.clear()
      }
    }
    restore().finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    window.addEventListener(LOGOUT_EVENT, logout)
    return () => window.removeEventListener(LOGOUT_EVENT, logout)
  }, [logout])

  const login = useCallback(async (username: string, password: string) => {
    const { access, refresh } = await authApi.login(username, password)
    tokens.set(access, refresh)
    setUser(await authApi.fetchMe())
  }, [])

  const register = useCallback(async (username: string, email: string, password: string) => {
    const data = await authApi.register(username, email, password)
    tokens.set(data.access, data.refresh)
    setUser(data.user)
  }, [])

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
