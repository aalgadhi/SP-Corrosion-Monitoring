import { useCallback } from 'react'
import { LineChart, Line, ResponsiveContainer } from 'recharts'
import usePolling from '../hooks/usePolling'
import { getReadings } from '../lib/api'

const GASES = [
  { key: 'h2s', label: 'H\u2082S', unit: 'ppm', warn: 20, crit: 40, color: '#f59e0b' },
  { key: 'co', label: 'CO', unit: 'ppm', warn: 50, crit: 150, color: '#3b82f6' },
  { key: 'ch4', label: 'CH\u2084', unit: '% LEL', warn: 10, crit: 20, color: '#8b5cf6' },
  { key: 'o2', label: 'O\u2082', unit: '% v/v', warn: 19.5, crit: 18, color: '#06b6d4', invert: true },
]

function getStatusColor(value, gas) {
  if (gas.invert) {
    if (value < gas.crit) return 'text-red-400'
    if (value < gas.warn) return 'text-amber-400'
    return 'text-green-400'
  }
  if (value >= gas.crit) return 'text-red-400'
  if (value >= gas.warn) return 'text-amber-400'
  return 'text-green-400'
}

export default function GasCards() {
  const fetchReadings = useCallback(() => getReadings({ limit: 60 }), [])
  const { data: readings, loading } = usePolling(fetchReadings, 2000)

  if (loading || !readings) {
    return (
      <div className="grid grid-cols-2 gap-3">
        {GASES.map(g => (
          <div key={g.key} className="bg-gray-900 border border-gray-800 rounded-lg p-4 animate-pulse h-32" />
        ))}
      </div>
    )
  }

  const sorted = [...readings].reverse()

  return (
    <div className="grid grid-cols-2 gap-3">
      {GASES.map(gas => {
        const current = readings[0]?.[gas.key] ?? 0
        const color = getStatusColor(current, gas)
        return (
          <div key={gas.key} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm text-gray-400">{gas.label}</span>
              <span className="text-xs text-gray-500">{gas.unit}</span>
            </div>
            <div className={`text-2xl font-bold font-mono ${color}`}>
              {current.toFixed(1)}
            </div>
            <div className="h-10 mt-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sorted}>
                  <Line
                    type="monotone"
                    dataKey={gas.key}
                    stroke={gas.color}
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )
      })}
    </div>
  )
}
