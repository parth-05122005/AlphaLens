import { useQuery } from '@tanstack/react-query'
import { getStats } from '../api/ask'
import { Card, CardTitle, Skeleton } from './ui'

function ms(value: number | null) {
  if (value === null) return '—'
  return value >= 1000 ? `${(value / 1000).toFixed(2)}s` : `${value}ms`
}

export default function AiStatsCard() {
  const stats = useQuery({ queryKey: ['stats'], queryFn: getStats })
  const s = stats.data

  return (
    <Card>
      <CardTitle>AI stats</CardTitle>
      {!s ? (
        <Skeleton className="h-32" />
      ) : (
        <div className="space-y-4">
          <div>
            <div className="flex items-baseline justify-between">
              <span className="text-sm text-slate-500">Semantic cache hit rate</span>
              <span className="text-xl font-semibold tabular-nums">{Math.round(s.cache_hit_rate * 100)}%</span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-brand-500" style={{ width: `${s.cache_hit_rate * 100}%` }} />
            </div>
            <p className="mt-1 text-xs text-slate-500">{s.total_queries} questions asked</p>
          </div>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-xs text-slate-500">⚡ Cached answer</dt>
              <dd className="mt-0.5 font-semibold tabular-nums">{ms(s.avg_latency_ms_cached)}</dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-xs text-slate-500">Fresh LLM answer</dt>
              <dd className="mt-0.5 font-semibold tabular-nums">{ms(s.avg_latency_ms_uncached)}</dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-xs text-slate-500">Documents</dt>
              <dd className="mt-0.5 font-semibold tabular-nums">{s.documents_count}</dd>
            </div>
            <div className="rounded-lg bg-slate-50 p-3">
              <dt className="text-xs text-slate-500">Indexed chunks</dt>
              <dd className="mt-0.5 font-semibold tabular-nums">{s.chunks_count}</dd>
            </div>
          </dl>
        </div>
      )}
    </Card>
  )
}
