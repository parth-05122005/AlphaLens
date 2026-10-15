import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createAgent, updateAgent } from '../api/agents'
import { errorMessage } from '../api/client'
import { listHoldings } from '../api/portfolio'
import type { Agent, AgentSchedule } from '../types'
import { useToast } from './Toast'
import { Button, inputClass } from './ui'

const TEMPLATES = [
  {
    label: 'IT risk watch',
    text: 'Summarize news for my IT stocks and flag anything about layoffs, guidance cuts or large deal losses.',
  },
  {
    label: 'Morning brief',
    text: 'Give me a morning brief: the 3 most important developments across my holdings and why they matter.',
  },
  {
    label: 'Bank health check',
    text: 'For my banking holdings, highlight anything about asset quality, NPAs, RBI actions or management changes.',
  },
]

export default function AgentForm({ agent, onClose }: { agent?: Agent; onClose: () => void }) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const holdings = useQuery({ queryKey: ['holdings'], queryFn: listHoldings })

  const [name, setName] = useState(agent?.name ?? '')
  const [instruction, setInstruction] = useState(agent?.instruction ?? '')
  const [selected, setSelected] = useState<number[]>(agent?.holdings ?? [])
  const [schedule, setSchedule] = useState<AgentSchedule>(agent?.schedule ?? 'manual')
  const [active, setActive] = useState(agent?.is_active ?? true)
  const [error, setError] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () => {
      const input = { name, instruction, holdings: selected, schedule, is_active: active }
      return agent ? updateAgent(agent.id, input) : createAgent(input)
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      queryClient.setQueryData(['agents', saved.id], saved)
      toast(agent ? 'Agent updated' : `Created “${saved.name}”`, 'success')
      onClose()
    },
    onError: (err) => setError(errorMessage(err, 'Could not save the agent')),
  })

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    save.mutate()
  }

  const toggle = (id: number) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center" onClick={onClose}>
      <form
        onSubmit={onSubmit}
        onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full max-w-lg space-y-4 overflow-y-auto rounded-2xl bg-white p-6 shadow-xl"
      >
        <h2 className="text-lg font-semibold">{agent ? 'Edit agent' : 'New agent'}</h2>

        <label className="block space-y-1">
          <span className="text-sm font-medium text-slate-700">Name</span>
          <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="IT risk watch" required maxLength={120} />
        </label>

        <div className="space-y-1">
          <label htmlFor="instruction" className="text-sm font-medium text-slate-700">
            Instruction
          </label>
          <div className="flex flex-wrap gap-1.5">
            {TEMPLATES.map((t) => (
              <button
                key={t.label}
                type="button"
                onClick={() => {
                  setInstruction(t.text)
                  if (!name) setName(t.label)
                }}
                className="rounded-full border border-slate-300 px-2.5 py-0.5 text-xs text-slate-600 hover:border-brand-500 hover:text-brand-700"
              >
                {t.label}
              </button>
            ))}
          </div>
          <textarea
            id="instruction"
            className={`${inputClass} min-h-28`}
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="What should this agent look for and report on?"
            required
            maxLength={2000}
          />
        </div>

        <div className="space-y-1.5">
          <span className="text-sm font-medium text-slate-700">Holdings</span>
          <p className="text-xs text-slate-500">Leave empty to cover all of your holdings.</p>
          <div className="flex flex-wrap gap-1.5">
            {holdings.data?.map((h) => {
              const on = selected.includes(h.id)
              return (
                <button
                  key={h.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(h.id)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium ${
                    on ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300 text-slate-600 hover:border-slate-400'
                  }`}
                >
                  {h.symbol.replace('.NS', '')}
                </button>
              )
            })}
            {holdings.data?.length === 0 && <span className="text-xs text-slate-500">Add holdings on the dashboard first.</span>}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <label className="block space-y-1">
            <span className="text-sm font-medium text-slate-700">Schedule</span>
            <select className={inputClass} value={schedule} onChange={(e) => setSchedule(e.target.value as AgentSchedule)}>
              <option value="manual">Manual (Run now only)</option>
              <option value="daily">Daily at 8:00 AM IST</option>
            </select>
          </label>
          <label className="flex items-end gap-2 pb-2 text-sm text-slate-700">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} className="h-4 w-4 accent-brand-600" />
            Active
          </label>
        </div>

        {error && <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={save.isPending}>
            {agent ? 'Save changes' : 'Create agent'}
          </Button>
        </div>
      </form>
    </div>
  )
}
