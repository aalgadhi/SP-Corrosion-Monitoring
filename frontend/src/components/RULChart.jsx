import { useCallback } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import usePolling from '../hooks/usePolling'
import { getRULHistory } from '../lib/api'

export default function RULChart() {
  const fetchRUL = useCallback(() => getRULHistory({ limit: 200 }), [])
  const { data: history, loading } = usePolling(fetchRUL, 10000)

  const chartData = history ? [...history].reverse() : []

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
            Remaining Useful Life Trend
          </h2>
          <p className="text-xs text-gray-600 mt-0.5">Pipeline RUL over time (days)</p>
        </div>
        {chartData.length > 0 && (
          <div className="text-right">
            <span className="text-2xl font-bold font-mono text-gray-100">
              {chartData[chartData.length - 1]?.rul_days?.toFixed(0) ?? '--'}
            </span>
            <span className="text-sm text-gray-400 ml-1">days</span>
          </div>
        )}
      </div>

      <div className="h-56">
        {loading && !history ? (
          <div className="h-full flex items-center justify-center text-gray-500">Loading...</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="rulGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="timestamp"
                tick={{ fontSize: 10, fill: '#6b7280' }}
                tickFormatter={ts => {
                  const d = new Date(ts)
                  return d.toLocaleDateString([], { month: 'short', day: 'numeric' })
                }}
              />
              <YAxis
                tick={{ fontSize: 10, fill: '#6b7280' }}
                label={{ value: 'RUL (days)', angle: -90, position: 'insideLeft', style: { fontSize: 10, fill: '#6b7280' } }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px' }}
                labelStyle={{ color: '#9ca3af' }}
                formatter={(value) => [`${value?.toFixed(1)} days`, 'RUL']}
              />
              <ReferenceLine y={365} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: 'Warning (1yr)', fill: '#f59e0b', fontSize: 10 }} />
              <ReferenceLine y={90} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Critical (90d)', fill: '#ef4444', fontSize: 10 }} />
              <Area
                type="monotone"
                dataKey="rul_days"
                stroke="#22c55e"
                strokeWidth={2}
                fill="url(#rulGradient)"
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
