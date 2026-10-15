import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { errorMessage } from '../api/client'
import { createHolding } from '../api/portfolio'
import { useToast } from './Toast'
import { Button, inputClass } from './ui'

export default function AddHoldingModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [symbol, setSymbol] = useState('')
  const [quantity, setQuantity] = useState('')
  const [avgPrice, setAvgPrice] = useState('')
  const [name, setName] = useState('')
  const [sector, setSector] = useState('')
  const [error, setError] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: createHolding,
    onSuccess: (holding) => {
      queryClient.invalidateQueries({ queryKey: ['summary'] })
      queryClient.invalidateQueries({ queryKey: ['holdings'] })
      toast(`Added ${holding.symbol}. Fetching news in the background…`, 'success')
      onClose()
    },
    onError: (err) => setError(errorMessage(err, 'Could not add holding')),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    mutation.mutate({
      symbol,
      quantity,
      avg_buy_price: avgPrice,
      ...(name && { name }),
      ...(sector && { sector }),
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center" onClick={onClose}>
      <form
        onSubmit={onSubmit}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 shadow-xl"
      >
        <div>
          <h2 className="text-lg font-semibold">Add holding</h2>
          <p className="text-sm text-slate-500">NSE symbols get “.NS” added automatically (e.g. INFY → INFY.NS).</p>
        </div>
        <label className="block space-y-1">
          <span className="text-sm font-medium text-slate-700">Symbol</span>
          <input className={inputClass} value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="INFY" required autoFocus />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">Quantity</span>
            <input className={inputClass} type="number" step="any" min="0" value={quantity} onChange={(e) => setQuantity(e.target.value)} required />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">Avg buy price (₹)</span>
            <input className={inputClass} type="number" step="0.01" min="0" value={avgPrice} onChange={(e) => setAvgPrice(e.target.value)} required />
          </label>
        </div>
        <details className="text-sm">
          <summary className="cursor-pointer text-slate-500">Name and sector (auto-filled if left blank)</summary>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <input className={inputClass} placeholder="Company name" value={name} onChange={(e) => setName(e.target.value)} />
            <input className={inputClass} placeholder="Sector" value={sector} onChange={(e) => setSector(e.target.value)} />
          </div>
        </details>
        {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            Add holding
          </Button>
        </div>
      </form>
    </div>
  )
}
