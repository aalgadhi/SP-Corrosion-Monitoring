import { useCallback } from 'react'
import GasCards from './components/GasCards'
import EnvironmentCards from './components/EnvironmentCards'
import DiagnosticsPanel from './components/DiagnosticsPanel'
import RULChart from './components/RULChart'
import HistoryChart from './components/HistoryChart'
import AlertsPanel from './components/AlertsPanel'
import DevicesPanel from './components/DevicesPanel'
import SystemStats from './components/SystemStats'
import usePolling from './hooks/usePolling'
import { getDiagnostics, getStats } from './lib/api'

export default function App() {
  const fetchDiag = useCallback(() => getDiagnostics(), [])
  const fetchStats = useCallback(() => getStats(), [])
  const { data: diagData } = usePolling(fetchDiag, 5000)
  const { data: statsData } = usePolling(fetchStats, 10000)

  const condition = diagData?.latest?.condition
  const statusColor = !condition
    ? 'bg-gray-500'
    : condition === 'normal'
      ? 'bg-green-500'
      : 'bg-red-500'

  return (
    <div className="min-h-screen bg-gray-950 p-4 md:p-6">
      {/* Header */}
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl md:text-2xl font-bold text-gray-100 tracking-tight">
            Corrosion Gas Monitor
          </h1>
          <p className="text-xs text-gray-500 mt-0.5">Real-Time Pipeline Monitoring Dashboard</p>
        </div>
        <div className="flex items-center gap-4">
          <DevicesPanel stats={statsData} />
          <div className="flex items-center gap-2">
            <span className={`inline-block w-3 h-3 rounded-full ${statusColor} animate-pulse`} />
            <span className="text-sm text-gray-400">
              {condition?.toUpperCase() ?? 'CONNECTING'}
            </span>
          </div>
        </div>
      </header>

      {/* Top Row: Gas Cards + Diagnostics */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-2">
          <GasCards />
        </div>
        <DiagnosticsPanel data={diagData} />
      </div>

      {/* Environment Cards Row */}
      <div className="mb-4">
        <EnvironmentCards />
      </div>

      {/* RUL Trend Chart */}
      <div className="mb-4">
        <RULChart />
      </div>

      {/* Gas History Chart */}
      <div className="mb-4">
        <HistoryChart />
      </div>

      {/* Bottom Row: Alerts + System Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2">
          <AlertsPanel />
        </div>
        <SystemStats data={statsData} />
      </div>
    </div>
  )
}
