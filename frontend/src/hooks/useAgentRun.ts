import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getRun } from '../api/agents'
import { useToast } from '../components/Toast'

const done = (status?: string) => status === 'success' || status === 'failed'

/** Polls /agent-runs/{id}/ every 2s until the run succeeds or fails. */
export function useAgentRun(runId: number | null, onDone?: () => void) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const notified = useRef<number | null>(null)
  const onDoneRef = useRef(onDone)
  onDoneRef.current = onDone

  const query = useQuery({
    queryKey: ['agent-run', runId],
    queryFn: () => getRun(runId!),
    enabled: runId !== null,
    refetchInterval: (q) => (done(q.state.data?.status) ? false : 2000),
  })

  const run = query.data
  useEffect(() => {
    if (!run || !done(run.status) || notified.current === run.id) return
    notified.current = run.id
    queryClient.invalidateQueries({ queryKey: ['agents'] })
    queryClient.invalidateQueries({ queryKey: ['agent-runs', run.agent] })
    if (run.status === 'success') toast(`${run.agent_name}: report ready`, 'success')
    else toast(`${run.agent_name}: run failed`, 'error')
    onDoneRef.current?.()
  }, [run, queryClient, toast])

  return run
}
