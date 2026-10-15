import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listAgents, runAgent } from '../api/agents'
import { errorMessage } from '../api/client'
import { listHoldings } from '../api/portfolio'
import AgentForm from '../components/AgentForm'
import { RunProgress, RunStatusBadge } from '../components/RunStatus'
import { useToast } from '../components/Toast'
import { Badge, Button, Card, EmptyState, Skeleton } from '../components/ui'
import { useAgentRun } from '../hooks/useAgentRun'
import { timeAgo } from '../lib/format'
import type { Agent } from '../types'

function AgentCard({ agent, symbols }: { agent: Agent; symbols: Map<number, string> }) {
  const toast = useToast()
  const [runId, setRunId] = useState<number | null>(null)
  const run = useAgentRun(runId)

  const start = useMutation({
    mutationFn: () => runAgent(agent.id),
    onSuccess: (r) => setRunId(r.id),
    onError: (err) => toast(errorMessage(err, 'Could not start the run'), 'error'),
  })

  const inFlight = start.isPending || (run !== undefined && (run.status === 'queued' || run.status === 'running'))
  const last = run ?? agent.last_run

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link to={`/agents/${agent.id}`} className="font-semibold text-slate-900 hover:text-brand-700 hover:underline">
            {agent.name}
          </Link>
          <div className="mt-1 flex flex-wrap gap-1.5">
            <Badge tone={agent.schedule === 'daily' ? 'blue' : 'gray'}>{agent.schedule === 'daily' ? 'Daily 8 AM' : 'Manual'}</Badge>
            {!agent.is_active && <Badge tone="amber">Paused</Badge>}
            <Badge>
              {agent.holdings.length ? agent.holdings.map((id) => symbols.get(id) ?? `#${id}`).join(', ') : 'All holdings'}
            </Badge>
          </div>
        </div>
        <Button variant="secondary" onClick={() => start.mutate()} loading={inFlight} className="shrink-0">
          {inFlight ? 'Running…' : 'Run now'}
        </Button>
      </div>
      <p className="line-clamp-2 text-sm text-slate-600">{agent.instruction}</p>
      <div className="mt-auto flex items-center justify-between gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
        {run && inFlight ? (
          <RunProgress status={run.status} />
        ) : last ? (
          <span className="flex items-center gap-2">
            Last run <RunStatusBadge status={last.status} /> {timeAgo(last.finished_at ?? last.created_at)}
          </span>
        ) : (
          <span>Never run</span>
        )}
        <Link to={`/agents/${agent.id}`} className="font-medium text-brand-700 hover:underline">
          {run?.status === 'success' ? 'View report →' : 'History →'}
        </Link>
      </div>
    </Card>
  )
}

export default function Agents() {
  const [creating, setCreating] = useState(false)
  const agents = useQuery({ queryKey: ['agents'], queryFn: listAgents })
  const holdings = useQuery({ queryKey: ['holdings'], queryFn: listHoldings })
  const symbols = new Map((holdings.data ?? []).map((h) => [h.id, h.symbol.replace('.NS', '')]))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
          <p className="text-sm text-slate-500">
            Saved research tasks that run in the background, on demand or every morning at 8 AM.
          </p>
        </div>
        <Button onClick={() => setCreating(true)}>New agent</Button>
      </div>

      {agents.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }, (_, i) => (
            <Skeleton key={i} className="h-40" />
          ))}
        </div>
      ) : !agents.data?.length ? (
        <EmptyState title="No agents yet">
          Create one with a plain-English instruction, e.g. “Flag any news about layoffs in my IT stocks”.
        </EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {agents.data.map((a) => (
            <AgentCard key={a.id} agent={a} symbols={symbols} />
          ))}
        </div>
      )}

      {creating && <AgentForm onClose={() => setCreating(false)} />}
    </div>
  )
}
