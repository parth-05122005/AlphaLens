import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { OTHER, SERIES, SURFACE } from '../lib/chartColors'
import { formatINR } from '../lib/format'

interface Slice {
  sector: string
  value: number
}

/** Keep the top 8 sectors in fixed color order and fold the rest into "Other". */
function foldSlices(data: Slice[]): (Slice & { color: string })[] {
  const named = data.filter((s) => s.sector !== 'Other').sort((a, b) => b.value - a.value)
  const slices = named.slice(0, SERIES.length).map((s, i) => ({ ...s, color: SERIES[i] }))
  const otherValue =
    data.filter((s) => s.sector === 'Other').reduce((sum, s) => sum + s.value, 0) +
    named.slice(SERIES.length).reduce((sum, s) => sum + s.value, 0)
  if (otherValue > 0) slices.push({ sector: 'Other', value: otherValue, color: OTHER })
  return slices
}

export default function SectorPie({ data }: { data: Slice[] }) {
  const slices = foldSlices(data)
  const total = slices.reduce((sum, s) => sum + s.value, 0)

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row xl:flex-col">
      <div className="h-48 w-48 shrink-0">
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="sector"
              innerRadius="58%"
              outerRadius="100%"
              stroke={SURFACE}
              strokeWidth={2}
              isAnimationActive={false}
            >
              {slices.map((s) => (
                <Cell key={s.sector} fill={s.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value) => [`${formatINR(Number(value))} (${((Number(value) / total) * 100).toFixed(1)}%)`, 'Value']}
              contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 12 }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="w-full space-y-1.5 text-sm">
        {slices.map((s) => (
          <li key={s.sector} className="flex items-center justify-between gap-3">
            <span className="flex min-w-0 items-center gap-2 text-slate-700">
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: s.color }} />
              <span className="truncate">{s.sector}</span>
            </span>
            <span className="text-slate-500 tabular-nums">{((s.value / total) * 100).toFixed(1)}%</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
