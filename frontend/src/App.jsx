import { useCallback } from 'react'
import GasCards from './components/GasCards'
import DiagnosticsPanel from './components/DiagnosticsPanel'
import HistoryChart from './components/HistoryChart'
import AlertsPanel from './components/AlertsPanel'
import usePolling from './hooks/usePolling'
import { getDiagnostics } from './lib/api'

export default function App() {
  const fetchDiag = useCallback(() => getDiagnostics(), [])
  const { data: diagData } = usePolling(fetchDiag, 5000)

  const statusColor = !diagData?.latest
    ? 'bg-gray-500'
    : diagData.latest.condition === 'normal'
      ? 'bg-green-500'
      : diagData.latest.condition === 'corrosion' || diagData.latest.condition === 'fouling'
        ? 'bg-amber-500'
        : 'bg-red-500'

  return (
    <div className="min-h-screen bg-gray-950 p-4 md:p-6">
      {/* Header */}
      <header className="flex items-center justify-between mb-6">
        <h1 className="text-xl md:text-2xl font-bold text-gray-100 tracking-tight">
          Corrosion Gas Monitor
        </h1>
        <div className="flex items-center gap-2">
          <span className={`inline-block w-3 h-3 rounded-full ${statusColor} animate-pulse`} />
          <span className="text-sm text-gray-400">
            {diagData?.latest?.condition?.toUpperCase() ?? 'CONNECTING'}
          </span>
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <GasCards />
        <DiagnosticsPanel data={diagData} />
      </div>

      {/* History Chart */}
      <div className="mb-4">
        <HistoryChart />
      </div>

      {/* Alerts */}
      <AlertsPanel />
    </div>
  )
}
