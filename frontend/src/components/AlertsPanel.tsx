import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { getAlerts } from '../api/agents'
import { formatDate } from '../lib/format'
import { Card, CardTitle, Skeleton } from './ui'

export default function AlertsPanel() {
  const alerts = useQuery({ queryKey: ['alerts'], queryFn: getAlerts })

  return (
    <Card>
      <CardTitle>Risk alerts</CardTitle>
      {alerts.isLoading ? (
        <Skeleton className="h-24" />
      ) : !alerts.data?.length ? (
        <div className="flex items-center gap-3 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span aria-hidden>✓</span>
          No holdings with clearly negative news in the last 7 days.
        </div>
      ) : (
        <ul className="space-y-3">
          {alerts.data.map((a) => (
            <li key={a.holding_id} className="rounded-xl border border-rose-200 bg-rose-50/60 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Link to={`/holdings/${a.holding_id}`} className="flex items-center gap-2 font-semibold text-rose-800 hover:underline">
                  <span aria-hidden>⚠</span>
                  {a.symbol.replace('.NS', '')}
                  <span className="text-sm font-normal text-rose-700">{a.name}</span>
                </Link>
                <span className="text-xs text-rose-700 tabular-nums">avg sentiment {a.average_sentiment.toFixed(2)}</span>
              </div>
              <p className="mt-1 text-sm text-rose-800">{a.reason}</p>
              {a.headlines.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {a.headlines.map((h) => (
                    <li key={h.document_id} className="text-xs text-slate-700">
                      <a href={h.url ?? undefined} target="_blank" rel="noreferrer" className="hover:underline">
                        {h.title}
                      </a>
                      {h.published_at && <span className="text-slate-500"> · {formatDate(h.published_at)}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
