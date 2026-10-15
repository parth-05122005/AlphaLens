import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { deleteAgent, getAgent, listRuns, runAgent } from '../api/agents'
import { errorMessage } from '../api/client'
import AgentForm from '../components/AgentForm'
import CitedAnswer from '../components/CitedAnswer'
import { RunProgress, RunStatusBadge } from '../components/RunStatus'
import { useToast } from '../components/Toast'
import { Badge, Button, Card, CardTitle, EmptyState, Skeleton } from '../components/ui'
import { useAgentRun } from '../hooks/useAgentRun'
import { formatDate } from '../lib/format'

function formatDateTime(iso: string) {
  return `${formatDate(iso)}, ${new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}`
}

export default function AgentDetail() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const toast = useToast()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [runId, setRunId] = useState<number | null>(null)
  const [openRun, setOpenRun] = useState<number | null>(null)

  const agent = useQuery({ queryKey: ['agents', id], queryFn: () => getAgent(id) })
  const runs = useQuery({ queryKey: ['agent-runs', id], queryFn: () => listRuns(id) })
  const live = useAgentRun(runId, () => setOpenRun(runId))

  const start = useMutation({
    mutationFn: () => runAgent(id),
    onSuccess: (r) => {
      setRunId(r.id)
      queryClient.invalidateQueries({ queryKey: ['agent-runs', id] })
    },
    onError: (err) => toast(errorMessage(err, 'Could not start the run'), 'error'),
  })

  const remove = useMutation({
    mutationFn: () => deleteAgent(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      toast('Agent deleted', 'success')
      navigate('/agents')
    },
    onError: (err) => toast(errorMessage(err), 'error'),
  })

  if (agent.isLoading) return <Skeleton className="h-64" />
  if (!agent.data) {
    return (
      <EmptyState title="Agent not found">
        <Link to="/agents" className="text-brand-700 hover:underline">
          Back to agents
        </Link>
      </EmptyState>
    )
  }

  const a = agent.data
  const inFlight = start.isPending || (live !== undefined && (live.status === 'queued' || live.status === 'running'))
  // Show the newest run expanded by default.
  const expanded = openRun ?? runs.data?.[0]?.id ?? null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to="/agents" className="text-sm text-slate-500 hover:text-slate-700">
            ← Agents
          </Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{a.name}</h1>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <Badge tone={a.schedule === 'daily' ? 'blue' : 'gray'}>{a.schedule === 'daily' ? 'Daily 8 AM' : 'Manual'}</Badge>
            {!a.is_active && <Badge tone="amber">Paused</Badge>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setEditing(true)}>
            Edit
          </Button>
          <Button variant="danger" loading={remove.isPending} onClick={() => window.confirm(`Delete “${a.name}” and its run history?`) && remove.mutate()}>
            Delete
          </Button>
          <Button onClick={() => start.mutate()} loading={inFlight}>
            {inFlight ? 'Running…' : 'Run now'}
          </Button>
        </div>
      </div>

      <Card>
        <p className="text-xs font-medium tracking-wide text-slate-500 uppercase">Instruction</p>
        <p className="mt-1 text-sm whitespace-pre-wrap text-slate-700">{a.instruction}</p>
        {live && inFlight && (
          <div className="mt-4 border-t border-slate-100 pt-4">
            <RunProgress status={live.status} />
            <p className="mt-2 text-xs text-slate-500">Refreshing news and writing the report in a background worker…</p>
          </div>
        )}
      </Card>

      <Card flush>
        <div className="px-5 pt-5">
          <CardTitle>Run history</CardTitle>
        </div>
        {runs.isLoading ? (
          <div className="p-5">
            <Skeleton className="h-24" />
          </div>
        ) : !runs.data?.length ? (
          <div className="px-5 pb-5">
            <EmptyState title="No runs yet">Click “Run now” to generate the first report.</EmptyState>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100 border-t border-slate-100">
            {runs.data.map((r) => {
              const isOpen = expanded === r.id
              const current = live && live.id === r.id ? live : r
              return (
                <li key={r.id}>
                  <button
                    onClick={() => setOpenRun(isOpen ? -1 : r.id)}
                    aria-expanded={isOpen}
                    className="flex w-full items-center justify-between gap-3 px-5 py-3 text-left hover:bg-slate-50"
                  >
                    <span className="flex items-center gap-3 text-sm">
                      <RunStatusBadge status={current.status} />
                      <span className="text-slate-700">{formatDateTime(r.created_at)}</span>
                      <span className="text-xs text-slate-500">{r.trigger === 'scheduled' ? 'Scheduled' : 'Manual'}</span>
                    </span>
                    <span className="text-slate-400">{isOpen ? '−' : '+'}</span>
                  </button>
                  {isOpen && (
                    <div className="px-5 pb-5">
                      {current.status === 'success' ? (
                        <CitedAnswer answer={current.output} citations={current.citations} />
                      ) : current.status === 'failed' ? (
                        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{current.error ?? 'The run failed.'}</p>
                      ) : (
                        <RunProgress status={current.status} />
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </Card>

      {editing && <AgentForm agent={a} onClose={() => setEditing(false)} />}
    </div>
  )
}
