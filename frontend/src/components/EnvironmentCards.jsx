import { useCallback } from 'react'
import usePolling from '../hooks/usePolling'
import { getReadings } from '../lib/api'

const ENV_METRICS = [
  { key: 'temperature', label: 'Temperature', unit: '\u00B0C', icon: '\u{1F321}', min: 40, max: 95, color: 'text-orange-400' },
  { key: 'humidity', label: 'Humidity', unit: '%', icon: '\u{1F4A7}', min: 20, max: 90, color: 'text-cyan-400' },
  { key: 'pressure', label: 'Pressure', unit: 'bar', icon: '\u{2B07}', min: 1, max: 7, color: 'text-violet-400' },
  { key: 'flow_rate', label: 'Flow Rate', unit: 'm\u00B3/hr', icon: '\u{1F30A}', min: 0, max: 1.5, color: 'text-blue-400' },
]

export default function EnvironmentCards() {
  const fetchReadings = useCallback(() => getReadings({ limit: 1 }), [])
  const { data: readings, loading } = usePolling(fetchReadings, 2000)

  const current = readings?.[0] ?? {}

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {ENV_METRICS.map(metric => {
        const value = current[metric.key]
        const pct = value != null
          ? Math.min(100, Math.max(0, ((value - metric.min) / (metric.max - metric.min)) * 100))
          : 0

        return (
          <div key={metric.key} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-400">{metric.label}</span>
              <span className="text-xs text-gray-500">{metric.unit}</span>
            </div>
            <div className={`text-xl font-bold font-mono ${metric.color}`}>
              {loading || value == null ? '--' : value.toFixed(1)}
            </div>
            <div className="w-full h-1.5 bg-gray-800 rounded-full mt-2 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${pct}%`,
                  backgroundColor: pct > 80 ? '#ef4444' : pct > 60 ? '#f59e0b' : '#22c55e',
                }}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}
