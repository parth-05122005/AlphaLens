import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { getTaskStatus } from '../api/portfolio'
import { useToast } from '../components/Toast'

interface Options {
  /** Queries to refetch once the task finishes. */
  invalidate?: QueryKey[]
  successMessage?: string
  failureMessage?: string
  onSettled?: (succeeded: boolean) => void
}

/** Polls /tasks/{id}/ every 2s until the Celery task is ready, then invalidates queries and toasts. */
export function useTaskStatus(taskId: string | null, options: Options = {}) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const optionsRef = useRef(options)
  optionsRef.current = options
  const handled = useRef<string | null>(null)

  const query = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => getTaskStatus(taskId!),
    enabled: Boolean(taskId),
    refetchInterval: (q) => (q.state.data?.ready ? false : 2000),
  })

  const data = query.data
  useEffect(() => {
    if (!taskId || !data?.ready || handled.current === taskId) return
    handled.current = taskId
    const { invalidate = [], successMessage, failureMessage, onSettled } = optionsRef.current
    const ok = data.state === 'SUCCESS'
    invalidate.forEach((key) => queryClient.invalidateQueries({ queryKey: key }))
    if (ok && successMessage) toast(successMessage, 'success')
    if (!ok) toast(failureMessage ?? 'Background job failed', 'error')
    onSettled?.(ok)
  }, [taskId, data, queryClient, toast])

  const running = Boolean(taskId) && !data?.ready
  return { state: data?.state ?? (taskId ? 'PENDING' : null), running }
}
