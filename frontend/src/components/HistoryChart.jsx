import { useState, useCallback } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import usePolling from '../hooks/usePolling'
import { getReadings } from '../lib/api'

const TIME_RANGES = [
  { label: '1h', hours: 1, limit: 60 },
  { label: '6h', hours: 6, limit: 360 },
  { label: '24h', hours: 24, limit: 1440 },
  { label: '7d', hours: 168, limit: 5000 },
  { label: '30d', hours: 720, limit: 10000 },
]

const SERIES = [
  { key: 'h2s', color: '#f59e0b', label: 'H\u2082S (ppm)' },
  { key: 'co', color: '#3b82f6', label: 'CO (ppm)' },
  { key: 'ch4', color: '#8b5cf6', label: 'CH\u2084 (% LEL)' },
  { key: 'o2', color: '#06b6d4', label: 'O\u2082 (% v/v)' },
]

export default function HistoryChart() {
  const [rangeIdx, setRangeIdx] = useState(0)
  const [visible, setVisible] = useState({ h2s: true, co: true, ch4: true, o2: true })
  const range = TIME_RANGES[rangeIdx]

  const since = new Date(Date.now() - range.hours * 3600 * 1000).toISOString()
  const fetchData = useCallback(
    () => getReadings({ since, limit: range.limit }),
    [since, range.limit],
  )
  const { data: readings, loading } = usePolling(fetchData, 5000)

  const chartData = readings ? [...readings].reverse() : []

  const toggleSeries = (key) => {
    setVisible(prev => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
          History
        </h2>
        <div className="flex gap-1">
          {TIME_RANGES.map((tr, i) => (
            <button
              key={tr.label}
              onClick={() => setRangeIdx(i)}
              className={`px-3 py-1 text-xs rounded font-mono transition-colors ${
                i === rangeIdx
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {tr.label}
            </button>
          ))}
        </div>
      </div>

      {/* Series toggles */}
      <div className="flex gap-3 mb-3">
        {SERIES.map(s => (
          <button
            key={s.key}
            onClick={() => toggleSeries(s.key)}
            className={`flex items-center gap-1 text-xs transition-opacity ${
              visible[s.key] ? 'opacity-100' : 'opacity-40'
            }`}
          >
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
            {s.label}
          </button>
        ))}
      </div>

      <div className="h-64">
        {loading && !readings ? (
          <div className="h-full flex items-center justify-center text-gray-500">Loading...</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis
                dataKey="timestamp"
                tick={{ fontSize: 10, fill: '#6b7280' }}
                tickFormatter={ts => {
                  const d = new Date(ts)
                  return range.hours <= 24
                    ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : d.toLocaleDateString([], { month: 'short', day: 'numeric' })
                }}
              />
              <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px' }}
                labelStyle={{ color: '#9ca3af' }}
              />
              {SERIES.map(s =>
                visible[s.key] ? (
                  <Line
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    stroke={s.color}
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                ) : null,
              )}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}
