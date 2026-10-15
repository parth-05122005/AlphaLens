import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { listDocuments } from '../api/research'
import { useToast } from '../components/Toast'
import type { DocumentFilters } from '../types'

const inFlight = (status: string) => status === 'pending' || status === 'processing'

/** Document list that polls every 3s while anything is still being processed in the background. */
export function useDocuments(filters: DocumentFilters, page = 1) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const watching = useRef(new Set<number>())

  const query = useQuery({
    queryKey: ['documents', filters, page],
    queryFn: () => listDocuments(filters, page),
    refetchInterval: (q) => (q.state.data?.results.some((d) => inFlight(d.status)) ? 3000 : false),
  })

  // Toast when a document we saw processing finishes.
  useEffect(() => {
    for (const doc of query.data?.results ?? []) {
      if (inFlight(doc.status)) {
        watching.current.add(doc.id)
      } else if (watching.current.delete(doc.id)) {
        if (doc.status === 'ready') toast(`“${doc.title}” is ready to ask about`, 'success')
        else toast(`Processing “${doc.title}” failed`, 'error')
        queryClient.invalidateQueries({ queryKey: ['stats'] })
      }
    }
  }, [query.data, toast, queryClient])

  return query
}
