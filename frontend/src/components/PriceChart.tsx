import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { AXIS, GRID, SERIES } from '../lib/chartColors'
import { formatDate, formatINR } from '../lib/format'

export default function PriceChart({ points }: { points: { date: string; close: number }[] }) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: AXIS, fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: GRID }}
            minTickGap={40}
            tickFormatter={(d: string) => new Date(d).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fill: AXIS, fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={72}
            tickFormatter={(v: number) => formatINR(v, true)}
          />
          <Tooltip
            cursor={{ stroke: AXIS, strokeDasharray: '3 3' }}
            labelFormatter={(d) => formatDate(String(d))}
            formatter={(v) => [formatINR(Number(v)), 'Close']}
            contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 12 }}
          />
          <Line
            type="monotone"
            dataKey="close"
            stroke={SERIES[0]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: '#fff' }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
