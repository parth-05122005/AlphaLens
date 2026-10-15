import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { useSearchParams } from 'react-router-dom'
import { ask, askHistory } from '../api/ask'
import { errorMessage } from '../api/client'
import { listHoldings } from '../api/portfolio'
import CitedAnswer from '../components/CitedAnswer'
import { Badge, Button, Card, Spinner, inputClass } from '../components/ui'
import type { AskResponse } from '../types'

interface Turn {
  id: number
  question: string
  holdingIds: number[]
  result?: AskResponse
  error?: string
}

const STARTERS = [
  'Which of my holdings had negative news this week?',
  'Summarize the latest news across my portfolio.',
  'Are there any risks or regulatory issues I should know about?',
  'What did the uploaded reports say about guidance?',
]

let nextId = 1

function friendlyError(err: unknown) {
  if (axios.isAxiosError(err) && err.response?.status === 429) {
    return "You've asked a lot of questions in a short time. Take a breather and try again in a few minutes."
  }
  return errorMessage(err, 'Something went wrong answering that.')
}

export default function Ask() {
  const queryClient = useQueryClient()
  const [params, setParams] = useSearchParams()
  const [question, setQuestion] = useState(params.get('q') ?? '')
  const [selected, setSelected] = useState<number[]>(() => {
    const h = params.get('holding')
    return h ? [Number(h)] : []
  })
  const [turns, setTurns] = useState<Turn[]>([])
  const bottom = useRef<HTMLDivElement>(null)

  const holdings = useQuery({ queryKey: ['holdings'], queryFn: listHoldings })
  const history = useQuery({ queryKey: ['ask-history'], queryFn: askHistory })

  const mutation = useMutation({
    mutationFn: ({ q, ids }: { q: string; ids: number[]; turnId: number }) => ask(q, ids),
    onSuccess: (result, { turnId }) => {
      setTurns((t) => t.map((x) => (x.id === turnId ? { ...x, result } : x)))
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      queryClient.invalidateQueries({ queryKey: ['ask-history'] })
    },
    onError: (err, { turnId }) => setTurns((t) => t.map((x) => (x.id === turnId ? { ...x, error: friendlyError(err) } : x))),
  })

  function submit(q: string) {
    const text = q.trim()
    if (text.length < 3 || mutation.isPending) return
    const turnId = nextId++
    setTurns((t) => [...t, { id: turnId, question: text, holdingIds: selected }])
    setQuestion('')
    mutation.mutate({ q: text, ids: selected, turnId })
  }

  // Arriving from a holding page with ?q=... asks straight away.
  const autoAsked = useRef(false)
  useEffect(() => {
    const q = params.get('q')
    if (q && !autoAsked.current) {
      autoAsked.current = true
      submit(q)
      setParams({}, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns])

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    submit(question)
  }

  function toggle(id: number) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  }

  const symbol = (id: number) => holdings.data?.find((h) => h.id === id)?.symbol.replace('.NS', '') ?? `#${id}`

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Ask AlphaLens</h1>
        <p className="text-sm text-slate-500">Answers come only from your stored news and documents, with numbered sources.</p>
      </div>

      {holdings.data && holdings.data.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-slate-500">Focus on:</span>
          {holdings.data.map((h) => {
            const on = selected.includes(h.id)
            return (
              <button
                key={h.id}
                onClick={() => toggle(h.id)}
                aria-pressed={on}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                  on ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300 bg-white text-slate-600 hover:border-slate-400'
                }`}
              >
                {h.symbol.replace('.NS', '')}
              </button>
            )
          })}
          {selected.length > 0 && (
            <button onClick={() => setSelected([])} className="text-xs text-slate-500 hover:underline">
              Clear
            </button>
          )}
        </div>
      )}

      {turns.length === 0 ? (
        <Card>
          <p className="text-sm font-medium text-slate-700">Try asking</p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2">
            {STARTERS.map((s) => (
              <button
                key={s}
                onClick={() => submit(s)}
                className="rounded-xl border border-slate-200 px-3 py-2.5 text-left text-sm text-slate-700 hover:border-brand-500 hover:bg-brand-50"
              >
                {s}
              </button>
            ))}
          </div>
          {history.data && history.data.length > 0 && (
            <div className="mt-5">
              <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">Recent questions</p>
              <ul className="mt-2 space-y-1">
                {history.data.slice(0, 5).map((h) => (
                  <li key={h.id}>
                    <button onClick={() => setQuestion(h.question)} className="text-left text-sm text-brand-700 hover:underline">
                      {h.question}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      ) : (
        <div className="space-y-4">
          {turns.map((t) => (
            <div key={t.id} className="space-y-2">
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2.5 text-sm text-white">
                  {t.question}
                  {t.holdingIds.length > 0 && (
                    <div className="mt-1 text-xs text-brand-100">About {t.holdingIds.map(symbol).join(', ')}</div>
                  )}
                </div>
              </div>
              <Card>
                {t.result ? (
                  <>
                    <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                      {t.result.cache_hit && <Badge tone="amber">⚡ cached</Badge>}
                      <span className="tabular-nums">{(t.result.latency_ms / 1000).toFixed(2)}s</span>
                    </div>
                    <CitedAnswer answer={t.result.answer} citations={t.result.citations} />
                  </>
                ) : t.error ? (
                  <p className="text-sm text-rose-700">{t.error}</p>
                ) : (
                  <p className="flex items-center gap-2 text-sm text-slate-500">
                    <Spinner /> Searching your documents…
                  </p>
                )}
              </Card>
            </div>
          ))}
          <div ref={bottom} />
        </div>
      )}

      <form onSubmit={onSubmit} className="sticky bottom-4 flex gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-lg">
        <input
          className={`${inputClass} border-0 focus:ring-0`}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={selected.length ? `Ask about ${selected.map(symbol).join(', ')}…` : 'Ask about your portfolio…'}
          maxLength={500}
          aria-label="Question"
        />
        <Button type="submit" loading={mutation.isPending} disabled={question.trim().length < 3}>
          Ask
        </Button>
      </form>
    </div>
  )
}
