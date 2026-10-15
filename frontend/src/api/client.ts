import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

const ACCESS_KEY = 'alphalens.access'
const REFRESH_KEY = 'alphalens.refresh'

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY)
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY)
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

/** Fired when the session can't be recovered; AuthProvider listens and logs out. */
export const LOGOUT_EVENT = 'alphalens:logout'

export const api = axios.create({ baseURL: API_URL })

api.interceptors.request.use((config) => {
  const access = tokens.access
  if (access) config.headers.Authorization = `Bearer ${access}`
  return config
})

/**
 * Render's free tier sleeps when idle, so the first request can take 30s+.
 * If the first request is still pending after 5s we announce it so the UI can say so.
 */
export const WAKING_EVENT = 'alphalens:waking'
let firstRequestSettled = false
let wakingTimer: ReturnType<typeof setTimeout> | null = null

function settleFirstRequest() {
  if (firstRequestSettled) return
  firstRequestSettled = true
  if (wakingTimer) clearTimeout(wakingTimer)
  window.dispatchEvent(new CustomEvent(WAKING_EVENT, { detail: false }))
}

api.interceptors.request.use((config) => {
  if (!firstRequestSettled && !wakingTimer) {
    wakingTimer = setTimeout(() => {
      if (!firstRequestSettled) window.dispatchEvent(new CustomEvent(WAKING_EVENT, { detail: true }))
    }, 5000)
  }
  return config
})

api.interceptors.response.use(
  (response) => {
    settleFirstRequest()
    return response
  },
  (error: AxiosError) => {
    if (error.response) settleFirstRequest()
    throw error
  },
)

// Share one refresh call between all requests that hit a 401 at the same time.
let refreshing: Promise<string> | null = null

async function refreshAccessToken(): Promise<string> {
  const refresh = tokens.refresh
  if (!refresh) throw new Error('No refresh token')
  const { data } = await axios.post<{ access: string; refresh?: string }>(`${API_URL}/auth/refresh/`, { refresh })
  tokens.set(data.access, data.refresh)
  return data.access
}

type RetryConfig = InternalAxiosRequestConfig & { _retried?: boolean }

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetryConfig | undefined
    const isAuthCall = config?.url?.startsWith('/auth/login') || config?.url?.startsWith('/auth/register')
    if (error.response?.status !== 401 || !config || config._retried || isAuthCall) {
      throw error
    }
    config._retried = true
    try {
      refreshing ??= refreshAccessToken().finally(() => {
        refreshing = null
      })
      const access = await refreshing
      config.headers.Authorization = `Bearer ${access}`
      return api(config)
    } catch {
      tokens.clear()
      window.dispatchEvent(new Event(LOGOUT_EVENT))
      throw error
    }
  },
)

/** Pull a readable message out of a DRF error response. */
export function errorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return 'Cannot reach the server. Is the backend running?'
    const data = err.response.data as Record<string, unknown> | undefined
    if (data && typeof data === 'object') {
      if (typeof data.detail === 'string') return data.detail
      const first = Object.entries(data)[0]
      if (first) {
        const [field, value] = first
        const msg = Array.isArray(value) ? value[0] : value
        if (typeof msg === 'string') return field === 'non_field_errors' ? msg : `${field}: ${msg}`
      }
    }
  }
  return fallback
}
