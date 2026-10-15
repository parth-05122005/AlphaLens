import type { DocumentStatus, SentimentLabel } from '../types'
import { Badge, Spinner } from './ui'

const sentimentText: Record<SentimentLabel, { tone: 'green' | 'red' | 'gray'; icon: string; label: string }> = {
  positive: { tone: 'green', icon: '▲', label: 'Positive' },
  neutral: { tone: 'gray', icon: '●', label: 'Neutral' },
  negative: { tone: 'red', icon: '▼', label: 'Negative' },
}

export function SentimentBadge({ label, score }: { label: SentimentLabel | null; score?: number | null }) {
  if (!label) return <span className="text-xs text-slate-400">—</span>
  const s = sentimentText[label]
  return (
    <Badge tone={s.tone}>
      <span aria-hidden className="text-[9px]">
        {s.icon}
      </span>
      {s.label}
      {score !== undefined && score !== null && <span className="tabular-nums opacity-70">{score.toFixed(2)}</span>}
    </Badge>
  )
}

export function StatusBadge({ status, error }: { status: DocumentStatus; error?: string | null }) {
  if (status === 'pending' || status === 'processing') {
    return (
      <Badge tone="blue">
        <Spinner className="h-3 w-3" />
        Processing…
      </Badge>
    )
  }
  if (status === 'failed') {
    return (
      <span title={error ?? undefined}>
        <Badge tone="red">Failed</Badge>
      </span>
    )
  }
  return <Badge tone="green">Ready</Badge>
}
