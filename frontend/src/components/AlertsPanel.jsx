import { useCallback } from 'react'
import usePolling from '../hooks/usePolling'
import { getAlerts } from '../lib/api'

const SEVERITY_STYLES = {
  warning: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
  critical: 'bg-red-500/10 border-red-500/30 text-red-400',
}

export default function AlertsPanel() {
  const fetchAlerts = useCallback(() => getAlerts({ limit: 10 }), [])
  const { data: alerts, loading } = usePolling(fetchAlerts, 5000)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
        Recent Alerts
      </h2>

      {loading && !alerts ? (
        <div className="text-gray-500 text-sm">Loading...</div>
      ) : !alerts || alerts.length === 0 ? (
        <div className="text-gray-500 text-sm">No alerts</div>
      ) : (
        <div className="space-y-2 max-h-60 overflow-y-auto">
          {alerts.map(alert => {
            const style = SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.warning
            return (
              <div
                key={alert.id}
                className={`flex items-start gap-3 p-3 rounded-lg border ${style}`}
              >
                <span className="text-xs font-bold uppercase mt-0.5 shrink-0">
                  {alert.severity}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 truncate">{alert.message}</p>
                  <p className="text-xs text-gray-500 mt-1 font-mono">
                    {new Date(alert.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
