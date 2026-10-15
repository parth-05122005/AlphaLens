import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { errorMessage } from '../api/client'
import { listHoldings } from '../api/portfolio'
import { deleteDocument } from '../api/research'
import { SentimentBadge, StatusBadge } from '../components/badges'
import PdfUpload from '../components/PdfUpload'
import { useToast } from '../components/Toast'
import { Button, Card, EmptyState, Skeleton } from '../components/ui'
import { useDocuments } from '../hooks/useDocuments'
import { formatDate } from '../lib/format'
import type { DocumentFilters, DocumentStatus, SourceType } from '../types'

const selectClass =
  'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100'

export default function Documents() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [filters, setFilters] = useState<DocumentFilters>({})
  const [page, setPage] = useState(1)

  const holdings = useQuery({ queryKey: ['holdings'], queryFn: listHoldings })
  const docs = useDocuments(filters, page)

  const remove = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      toast('Document deleted', 'success')
    },
    onError: (err) => toast(errorMessage(err), 'error'),
  })

  function update(next: DocumentFilters) {
    setFilters(next)
    setPage(1)
  }

  const total = docs.data?.count ?? 0
  const pages = Math.max(1, Math.ceil(total / 20))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <p className="text-sm text-slate-500">Everything Ask AlphaLens can cite: auto-fetched headlines and the PDFs you upload.</p>
      </div>

      <Card>
        <PdfUpload />
        <p className="mt-2 text-xs text-slate-500">
          Uploads here are general documents. To attach a report to a stock, upload it from that holding’s page.
        </p>
      </Card>

      <Card flush className="overflow-hidden">
        <div className="flex flex-wrap gap-2 p-4">
          <select
            className={selectClass}
            value={filters.holding ?? ''}
            onChange={(e) => update({ ...filters, holding: e.target.value ? Number(e.target.value) : undefined })}
            aria-label="Filter by holding"
          >
            <option value="">All holdings</option>
            {holdings.data?.map((h) => (
              <option key={h.id} value={h.id}>
                {h.symbol}
              </option>
            ))}
          </select>
          <select
            className={selectClass}
            value={filters.source_type ?? ''}
            onChange={(e) => update({ ...filters, source_type: (e.target.value || undefined) as SourceType | undefined })}
            aria-label="Filter by type"
          >
            <option value="">All types</option>
            <option value="news">News</option>
            <option value="pdf">PDF</option>
          </select>
          <select
            className={selectClass}
            value={filters.status ?? ''}
            onChange={(e) => update({ ...filters, status: (e.target.value || undefined) as DocumentStatus | undefined })}
            aria-label="Filter by status"
          >
            <option value="">Any status</option>
            <option value="ready">Ready</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="failed">Failed</option>
          </select>
          <span className="ml-auto self-center text-sm text-slate-500">{total} documents</span>
        </div>

        {docs.isLoading ? (
          <div className="space-y-2 p-4">
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : !docs.data?.results.length ? (
          <div className="p-4">
            <EmptyState title="No documents match">
              News arrives automatically for each holding; you can also upload PDFs above.
            </EmptyState>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-y border-slate-100 bg-slate-50 text-left text-xs font-medium text-slate-500 uppercase">
                  <th className="px-4 py-2.5">Title</th>
                  <th className="px-3 py-2.5">Holding</th>
                  <th className="px-3 py-2.5">Type</th>
                  <th className="px-3 py-2.5">Date</th>
                  <th className="px-3 py-2.5">Status</th>
                  <th className="px-3 py-2.5">Sentiment</th>
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {docs.data.results.map((d) => (
                  <tr key={d.id} className="border-b border-slate-100 last:border-0">
                    <td className="max-w-[340px] px-4 py-3">
                      {d.url ? (
                        <a href={d.url} target="_blank" rel="noreferrer" className="line-clamp-2 font-medium text-slate-800 hover:underline">
                          {d.title}
                        </a>
                      ) : (
                        <span className="line-clamp-2 font-medium text-slate-800">{d.title}</span>
                      )}
                    </td>
                    <td className="px-3 py-3">
                      {d.holding ? (
                        <Link to={`/holdings/${d.holding}`} className="text-brand-700 hover:underline">
                          {d.holding_symbol?.replace('.NS', '')}
                        </Link>
                      ) : (
                        <span className="text-slate-400">General</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-slate-600 uppercase">{d.source_type}</td>
                    <td className="px-3 py-3 whitespace-nowrap text-slate-600">{formatDate(d.published_at ?? d.created_at)}</td>
                    <td className="px-3 py-3">
                      <StatusBadge status={d.status} error={d.error} />
                    </td>
                    <td className="px-3 py-3">
                      {d.source_type === 'news' ? <SentimentBadge label={d.sentiment_label} /> : <span className="text-xs text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => window.confirm(`Delete “${d.title}”?`) && remove.mutate(d.id)}
                        className="rounded px-2 py-1 text-xs text-slate-500 hover:bg-rose-50 hover:text-rose-600"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {pages > 1 && (
          <div className="flex items-center justify-end gap-2 border-t border-slate-100 p-3">
            <Button variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <span className="text-sm text-slate-500">
              Page {page} of {pages}
            </span>
            <Button variant="secondary" disabled={page >= pages} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}
