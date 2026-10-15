import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { useAuth } from '../hooks/useAuth'

const inputClass =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100'

export default function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { user, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to={from} replace />

  async function run(action: () => Promise<void>) {
    setBusy(true)
    setError(null)
    try {
      await action()
      navigate(from, { replace: true })
    } catch (err) {
      setError(errorMessage(err, mode === 'login' ? 'Login failed' : 'Registration failed'))
    } finally {
      setBusy(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    run(() => (mode === 'login' ? login(username, password) : register(username, email, password)))
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-lg font-bold text-white">
            α
          </div>
          <h1 className="text-2xl font-semibold tracking-tight">AlphaLens</h1>
          <p className="mt-1 text-sm text-slate-500">AI research copilot for your NSE portfolio</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">{mode === 'login' ? 'Sign in' : 'Create an account'}</h2>
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">Username</span>
            <input className={inputClass} value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
          </label>
          {mode === 'register' && (
            <label className="block space-y-1">
              <span className="text-sm font-medium text-slate-700">Email (optional)</span>
              <input className={inputClass} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
          )}
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">Password</span>
            <input
              className={inputClass}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={mode === 'register' ? 8 : undefined}
              required
            />
          </label>
          {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
          {mode === 'login' && (
            <button
              type="button"
              disabled={busy}
              onClick={() => run(() => login('demo', 'demo12345'))}
              className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              Use demo account
            </button>
          )}
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          {mode === 'login' ? (
            <>
              New here?{' '}
              <Link to="/register" className="font-medium text-brand-600 hover:underline">
                Create an account
              </Link>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <Link to="/login" className="font-medium text-brand-600 hover:underline">
                Sign in
              </Link>
            </>
          )}
        </p>
      </div>
    </div>
  )
}
