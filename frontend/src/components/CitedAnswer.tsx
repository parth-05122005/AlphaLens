import { useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { formatDate } from '../lib/format'
import type { Citation } from '../types'
import { Badge } from './ui'

/** Turn "[1, 2]" into "[1][2]" and each "[n]" into a markdown link we render as a badge. */
function linkCitations(markdown: string, known: Set<number>) {
  return markdown
    .replace(/\[(\d+(?:\s*,\s*\d+)+)\]/g, (_, group: string) =>
      group
        .split(',')
        .map((n) => `[${n.trim()}]`)
        .join(''),
    )
    .replace(/\[(\d+)\](?!\()/g, (match, n: string) => (known.has(Number(n)) ? `[${n}](#cite-${n})` : match))
}

export default function CitedAnswer({ answer, citations }: { answer: string; citations: Citation[] }) {
  const [active, setActive] = useState<number | null>(null)
  const cards = useRef(new Map<number, HTMLElement>())
  const known = new Set(citations.map((c) => c.n))

  function focus(n: number) {
    setActive(n)
    cards.current.get(n)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  return (
    <div>
      <div className="prose-answer text-sm leading-relaxed text-slate-800">
        <ReactMarkdown
          components={{
            a: ({ href, children }) => {
              const match = href?.match(/^#cite-(\d+)$/)
              if (match) {
                const n = Number(match[1])
                return (
                  <button
                    type="button"
                    onClick={() => focus(n)}
                    aria-label={`Show source ${n}`}
                    className={`mx-0.5 inline-flex h-4 min-w-4 -translate-y-1 items-center justify-center rounded px-1 align-baseline text-[10px] font-semibold ${
                      active === n ? 'bg-brand-600 text-white' : 'bg-brand-100 text-brand-700 hover:bg-brand-600 hover:text-white'
                    }`}
                  >
                    {n}
                  </button>
                )
              }
              return (
                <a href={href} target="_blank" rel="noreferrer" className="text-brand-700 underline">
                  {children}
                </a>
              )
            },
          }}
        >
          {linkCitations(answer, known)}
        </ReactMarkdown>
      </div>

      {citations.length > 0 && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          {citations.map((c) => (
            <div
              key={c.n}
              ref={(el) => {
                if (el) cards.current.set(c.n, el)
                else cards.current.delete(c.n)
              }}
              onClick={() => setActive(c.n)}
              className={`cursor-pointer rounded-xl border p-3 text-xs transition ${
                active === c.n ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-100' : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-start gap-2">
                <span className="flex h-5 min-w-5 shrink-0 items-center justify-center rounded bg-slate-100 px-1 font-semibold text-slate-600">
                  {c.n}
                </span>
                <div className="min-w-0">
                  <p className="line-clamp-2 font-medium text-slate-800">{c.title}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-slate-500">
                    <Badge tone={c.source_type === 'news' ? 'blue' : 'amber'}>{c.source_type === 'news' ? 'News' : 'PDF'}</Badge>
                    {c.published_at && <span>{formatDate(c.published_at)}</span>}
                    {c.url && (
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="font-medium text-brand-700 hover:underline"
                      >
                        Open ↗
                      </a>
                    )}
                  </div>
                  <p className="mt-1.5 line-clamp-3 text-slate-600">{c.snippet}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
