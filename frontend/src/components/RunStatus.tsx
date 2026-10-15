import type { RunStatus as Status } from '../types'
import { Badge, Spinner } from './ui'

const STEPS: { key: Status; label: string }[] = [
  { key: 'queued', label: 'Queued' },
  { key: 'running', label: 'Running' },
  { key: 'success', label: 'Done' },
]

export function RunStatusBadge({ status }: { status: Status }) {
  switch (status) {
    case 'queued':
      return <Badge tone="gray">Queued</Badge>
    case 'running':
      return (
        <Badge tone="blue">
          <Spinner className="h-3 w-3" /> Running
        </Badge>
      )
    case 'success':
      return <Badge tone="green">Done</Badge>
    case 'failed':
      return <Badge tone="red">Failed</Badge>
  }
}

/** Queued → Running → Done stepper shown while a run is in flight. */
export function RunProgress({ status }: { status: Status }) {
  const current = status === 'failed' ? 2 : STEPS.findIndex((s) => s.key === status)
  return (
    <ol className="flex items-center gap-2 text-xs" aria-label="Run progress">
      {STEPS.map((step, i) => {
        const reached = i <= current
        const failedHere = status === 'failed' && i === 2
        return (
          <li key={step.key} className="flex items-center gap-2">
            <span
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${
                failedHere
                  ? 'bg-rose-100 text-rose-700'
                  : reached
                    ? 'bg-brand-600 text-white'
                    : 'bg-slate-100 text-slate-500'
              }`}
            >
              {i === current && status === 'running' && <Spinner className="h-3 w-3" />}
              {failedHere ? 'Failed' : step.label}
            </span>
            {i < STEPS.length - 1 && <span className={`h-px w-6 ${i < current ? 'bg-brand-600' : 'bg-slate-200'}`} />}
          </li>
        )
      })}
    </ol>
  )
}
