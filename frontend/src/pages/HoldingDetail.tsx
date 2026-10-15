import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { deleteHolding, getHolding, getPriceHistory } from '../api/portfolio'
import { deleteDocument, refreshNews } from '../api/research'
import { SentimentBadge, StatusBadge } from '../components/badges'
import PdfUpload from '../components/PdfUpload'
import PriceChart from '../components/PriceChart'
import { useToast } from '../components/Toast'
import { Button, Card, CardTitle, EmptyState, Skeleton, inputClass } from '../components/ui'
import { useDocuments } from '../hooks/useDocuments'
import { useTaskStatus } from '../hooks/useTaskStatus'
import { formatDate, formatINR, formatNumber, formatPct, formatSignedINR, pnlClass, timeAgo } from '../lib/format'
import type { Period } from '../types'

const PERIODS: { value: Period; label: string }[] = [
  { value: '1mo', label: '1M' },
  { value: '6mo', label: '6M' },
  { value: '1y', label: '1Y' },
]

export default function HoldingDetail() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [period, setPeriod] = useState<Period>('1mo')
  const [newsTask, setNewsTask] = useState<string | null>(null)
  const [question, setQuestion] = useState('')

  const holding = useQuery({ queryKey: ['holdings', id], queryFn: () => getHolding(id) })
  const history = useQuery({
    queryKey: ['history', id, period],
    queryFn: () => getPriceHistory(id, period),
    enabled: holding.isSuccess,
  })

  const news = useDocuments({ holding: id, source_type: 'news' })
  const pdfs = useDocuments({ holding: id, source_type: 'pdf' })

  const startNewsRefresh = useMutation({
    mutationFn: () => refreshNews(id),
    onSuccess: ({ task_id }) => setNewsTask(task_id),
    onError: (err) => {
      toast(errorMessage(err, 'News refresh failed'), 'error')
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
  const newsStatus = useTaskStatus(newsTask, {
    invalidate: [['documents'], ['holdings', id], ['summary'], ['alerts']],
    successMessage: 'News refreshed',
    failureMessage: 'News refresh failed',
    onSettled: () => setNewsTask(null),
  })

  const removeDoc = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      toast('Document deleted', 'success')
    },
    onError: (err) => toast(errorMessage(err), 'error'),
  })

  function ask(e: FormEvent) {
    e.preventDefault()
    const params = new URLSearchParams({ holding: String(id) })
    if (question.trim()) params.set('q', question.trim())
    navigate(`/ask?${params}`)
  }

  const remove = useMutation({
    mutationFn: () => deleteHolding(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      queryClient.invalidateQueries({ queryKey: ['holdings'] })
      toast('Holding removed', 'success')
      navigate('/')
    },
    onError: (err) => toast(errorMessage(err), 'error'),
  })

  if (holding.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-80" />
      </div>
    )
  }
  if (holding.isError || !holding.data) {
    return (
      <EmptyState title="Holding not found">
        <Link to="/" className="text-brand-600 hover:underline">
          Back to dashboard
        </Link>
      </EmptyState>
    )
  }

  const h = holding.data
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link to="/" className="text-sm text-slate-500 hover:text-slate-700">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            {h.symbol.replace('.NS', '')} <span className="text-base font-normal text-slate-500">{h.name}</span>
          </h1>
          <p className="text-sm text-slate-500">
            {h.sector ?? 'Sector unknown'} · price updated {timeAgo(h.last_price_at)}
          </p>
        </div>
        <Button
          variant="danger"
          loading={remove.isPending}
          onClick={() => window.confirm(`Remove ${h.symbol} from your portfolio?`) && remove.mutate()}
        >
          Remove
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Card>
          <p className="text-sm text-slate-500">Last price</p>
          <p className="mt-1 text-xl font-semibold tabular-nums">{formatINR(h.last_price)}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500">Quantity · Avg</p>
          <p className="mt-1 text-xl font-semibold tabular-nums">
            {formatNumber(h.quantity)} <span className="text-sm font-normal text-slate-500">@ {formatINR(h.avg_buy_price)}</span>
          </p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500">Value</p>
          <p className="mt-1 text-xl font-semibold tabular-nums">{formatINR(h.value)}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-500">P&L</p>
          <p className={`mt-1 text-xl font-semibold tabular-nums ${pnlClass(h.pnl)}`}>
            {formatSignedINR(h.pnl)} <span className="text-sm">{formatPct(h.pnl_pct)}</span>
          </p>
        </Card>
      </div>

      <Card>
        <CardTitle
          action={
            <div className="flex rounded-lg border border-slate-200 p-0.5" role="group" aria-label="Chart period">
              {PERIODS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setPeriod(p.value)}
                  className={`rounded-md px-3 py-1 text-xs font-medium ${
                    period === p.value ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          }
        >
          Price
        </CardTitle>
        {history.isLoading ? (
          <Skeleton className="h-72" />
        ) : history.isError ? (
          <EmptyState title="Price history unavailable">{errorMessage(history.error)}</EmptyState>
        ) : history.data?.points.length ? (
          <PriceChart points={history.data.points} />
        ) : (
          <EmptyState title="No price data for this period" />
        )}
      </Card>

      <Card>
        <form onSubmit={ask} className="flex flex-col gap-2 sm:flex-row">
          <input
            className={inputClass}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={`Ask about ${h.symbol.replace('.NS', '')}, e.g. "What did management say about guidance?"`}
          />
          <Button type="submit" className="shrink-0">
            Ask AlphaLens
          </Button>
        </form>
      </Card>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardTitle
            action={
              <Button
                variant="secondary"
                onClick={() => startNewsRefresh.mutate()}
                loading={startNewsRefresh.isPending || newsStatus.running}
              >
                {newsStatus.running ? 'Fetching…' : 'Refresh news'}
              </Button>
            }
          >
            News
          </CardTitle>
          <p className="-mt-2 mb-3 text-xs text-slate-500">
            Last refreshed {timeAgo(h.news_refreshed_at)} · auto-refreshes every 3 hours
          </p>
          {news.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : news.data?.results.length ? (
            <ul className="divide-y divide-slate-100">
              {news.data.results.map((d) => (
                <li key={d.id} className="flex items-start justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <a
                      href={d.url ?? undefined}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-slate-800 hover:text-brand-700 hover:underline"
                    >
                      {d.title}
                    </a>
                    <p className="mt-0.5 text-xs text-slate-500">{formatDate(d.published_at ?? d.created_at)}</p>
                  </div>
                  <div className="shrink-0">
                    {d.status === 'ready' ? (
                      <SentimentBadge label={d.sentiment_label} />
                    ) : (
                      <StatusBadge status={d.status} error={d.error} />
                    )}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title="No news yet">
              {newsStatus.running ? 'Fetching headlines…' : 'Click "Refresh news" to pull the latest headlines.'}
            </EmptyState>
          )}
        </Card>

        <Card className="xl:col-span-2">
          <CardTitle>Documents</CardTitle>
          <PdfUpload holdingId={id} />
          {pdfs.data?.results.length ? (
            <ul className="mt-4 divide-y divide-slate-100">
              {pdfs.data.results.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800">{d.title}</p>
                    <p className="text-xs text-slate-500">Uploaded {timeAgo(d.created_at)}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <StatusBadge status={d.status} error={d.error} />
                    <button
                      onClick={() => window.confirm(`Delete "${d.title}"?`) && removeDoc.mutate(d.id)}
                      className="rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                      aria-label={`Delete ${d.title}`}
                    >
                      ✕
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            !pdfs.isLoading && <p className="mt-3 text-center text-xs text-slate-500">No reports uploaded for this stock yet.</p>
          )}
        </Card>
      </div>
    </div>
  )
}
