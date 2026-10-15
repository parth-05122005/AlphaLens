import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { deleteHolding, getHolding, getPriceHistory } from '../api/portfolio'
import PriceChart from '../components/PriceChart'
import { useToast } from '../components/Toast'
import { Button, Card, CardTitle, EmptyState, Skeleton } from '../components/ui'
import { formatINR, formatNumber, formatPct, formatSignedINR, pnlClass, timeAgo } from '../lib/format'
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

  const holding = useQuery({ queryKey: ['holdings', id], queryFn: () => getHolding(id) })
  const history = useQuery({
    queryKey: ['history', id, period],
    queryFn: () => getPriceHistory(id, period),
    enabled: holding.isSuccess,
  })

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
    </div>
  )
}
