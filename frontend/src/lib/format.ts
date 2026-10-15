const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 })
const inrCompact = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
const num = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 4 })

export function formatINR(value: number | string | null | undefined, compact = false) {
  if (value === null || value === undefined || value === '') return '—'
  return (compact ? inrCompact : inr).format(Number(value))
}

export function formatNumber(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === '') return '—'
  return num.format(Number(value))
}

export function formatPct(value: number) {
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

export function formatSignedINR(value: number) {
  return `${value > 0 ? '+' : ''}${formatINR(value)}`
}

export function pnlClass(value: number) {
  if (value > 0) return 'text-emerald-600'
  if (value < 0) return 'text-rose-600'
  return 'text-slate-600'
}

export function timeAgo(iso: string | null | undefined) {
  if (!iso) return 'never'
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  return `${Math.round(hours / 24)} d ago`
}

export function formatDate(iso: string | null | undefined) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}
