import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { getSummary, refreshPrices } from '../api/portfolio'
import AddHoldingModal from '../components/AddHoldingModal'
import AiStatsCard from '../components/AiStatsCard'
import AlertsPanel from '../components/AlertsPanel'
import { SentimentBadge } from '../components/badges'
import SectorPie from '../components/SectorPie'
import { useToast } from '../components/Toast'
import { Button, Card, CardTitle, EmptyState, Skeleton } from '../components/ui'
import { useTaskStatus } from '../hooks/useTaskStatus'
import { formatINR, formatNumber, formatPct, formatSignedINR, pnlClass, timeAgo } from '../lib/format'

function StatCard({ label, value, sub, valueClass = '' }: { label: string; value: string; sub?: string; valueClass?: string }) {
  return (
    <Card>
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`mt-1 text-xl font-semibold tracking-tight whitespace-nowrap tabular-nums sm:text-2xl ${valueClass}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </Card>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const toast = useToast()
  const [adding, setAdding] = useState(false)
  const [priceTask, setPriceTask] = useState<string | null>(null)

  const summary = useQuery({ queryKey: ['summary'], queryFn: getSummary, refetchInterval: 60_000 })

  const refresh = useMutation({
    mutationFn: refreshPrices,
    onSuccess: ({ task_id }) => setPriceTask(task_id),
    onError: (err) => toast(errorMessage(err), 'error'),
  })
  const priceStatus = useTaskStatus(priceTask, {
    invalidate: [['summary'], ['holdings']],
    successMessage: 'Prices refreshed',
    failureMessage: 'Price refresh failed',
    onSettled: () => setPriceTask(null),
  })

  const data = summary.data
  const hasHoldings = Boolean(data?.holdings.length)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-slate-500">
            Prices updated {timeAgo(data?.prices_updated_at)} · auto-refreshes during market hours
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => refresh.mutate()}
            loading={refresh.isPending || priceStatus.running}
            disabled={!hasHoldings}
          >
            {priceStatus.running ? 'Refreshing…' : 'Refresh prices'}
          </Button>
          <Button onClick={() => setAdding(true)}>Add holding</Button>
        </div>
      </div>

      {summary.isLoading ? (
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : summary.isError ? (
        <Card>
          <p className="text-sm text-rose-700">{errorMessage(summary.error, 'Could not load your portfolio.')}</p>
        </Card>
      ) : (
        data && (
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <StatCard label="Invested" value={formatINR(data.total_invested)} />
            <StatCard label="Current value" value={formatINR(data.current_value)} />
            <StatCard label="P&L" value={formatSignedINR(data.pnl)} valueClass={pnlClass(data.pnl)} />
            <StatCard label="P&L %" value={formatPct(data.pnl_pct)} valueClass={pnlClass(data.pnl)} />
          </div>
        )
      )}

      <div className="grid gap-6 xl:grid-cols-3">
        <Card flush className="overflow-hidden xl:col-span-2">
          <div className="px-5 pt-5">
            <CardTitle>Holdings</CardTitle>
          </div>
          {summary.isLoading ? (
            <div className="space-y-2 px-5 pb-5">
              {Array.from({ length: 4 }, (_, i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          ) : !hasHoldings ? (
            <div className="px-5 pb-5">
              <EmptyState title="No holdings yet">Add the NSE stocks you own to see value, P&L and news.</EmptyState>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="border-y border-slate-100 bg-slate-50 text-left text-xs font-medium text-slate-500 uppercase">
                    <th className="px-5 py-2.5">Symbol</th>
                    <th className="px-3 py-2.5 text-right">Qty</th>
                    <th className="px-3 py-2.5 text-right">Avg price</th>
                    <th className="px-3 py-2.5 text-right">Last price</th>
                    <th className="px-3 py-2.5 text-right">Value</th>
                    <th className="px-3 py-2.5 text-right">P&L</th>
                    <th className="px-5 py-2.5">News</th>
                  </tr>
                </thead>
                <tbody>
                  {data!.holdings.map((h) => (
                    <tr
                      key={h.id}
                      onClick={() => navigate(`/holdings/${h.id}`)}
                      className="cursor-pointer border-b border-slate-100 last:border-0 hover:bg-slate-50"
                    >
                      <td className="px-5 py-3">
                        <div className="font-medium text-slate-900">{h.symbol.replace('.NS', '')}</div>
                        <div className="max-w-[200px] truncate text-xs text-slate-500">{h.name}</div>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums">{formatNumber(h.quantity)}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{formatINR(h.avg_buy_price)}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{formatINR(h.last_price)}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{formatINR(h.value)}</td>
                      <td className={`px-3 py-3 text-right tabular-nums ${pnlClass(h.pnl)}`}>
                        <div>{formatSignedINR(h.pnl)}</div>
                        <div className="text-xs">{formatPct(h.pnl_pct)}</div>
                      </td>
                      <td className="px-5 py-3">
                        <SentimentBadge label={h.sentiment_label} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card>
          <CardTitle>Sector allocation</CardTitle>
          {summary.isLoading ? (
            <Skeleton className="h-48" />
          ) : hasHoldings ? (
            <SectorPie data={data!.allocation_by_sector} />
          ) : (
            <EmptyState title="Nothing to show yet" />
          )}
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <AlertsPanel />
        </div>
        <AiStatsCard />
      </div>

      {adding && <AddHoldingModal onClose={() => setAdding(false)} />}
    </div>
  )
}
