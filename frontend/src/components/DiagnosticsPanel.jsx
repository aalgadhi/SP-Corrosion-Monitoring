const CONDITION_STYLES = {
  normal: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/30', label: 'Normal' },
  corrosion: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30', label: 'Corrosion Detected' },
}

function HealthGauge({ score }) {
  const radius = 40
  const circumference = 2 * Math.PI * radius
  const pct = (score ?? 0) / 100
  const offset = circumference * (1 - pct)
  const color = score >= 70 ? '#22c55e' : score >= 40 ? '#f59e0b' : '#ef4444'

  return (
    <div className="flex flex-col items-center">
      <svg width="100" height="56" viewBox="0 0 100 56">
        <path
          d="M 10 50 A 40 40 0 0 1 90 50"
          fill="none"
          stroke="#1f2937"
          strokeWidth="8"
          strokeLinecap="round"
        />
        <path
          d="M 10 50 A 40 40 0 0 1 90 50"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference / 2}
          strokeDashoffset={(circumference / 2) * (1 - pct)}
          className="transition-all duration-700"
        />
        <text x="50" y="48" textAnchor="middle" fill={color} fontSize="18" fontWeight="bold" fontFamily="monospace">
          {score != null ? Math.round(score) : '--'}
        </text>
      </svg>
      <span className="text-xs text-gray-500 -mt-1">Health Score</span>
    </div>
  )
}

export default function DiagnosticsPanel({ data }) {
  if (!data?.latest) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 flex items-center justify-center">
        <span className="text-gray-500">Waiting for diagnostics...</span>
      </div>
    )
  }

  const { condition, rul_days, confidence, corrosion_rate, health_score } = data.latest
  const style = CONDITION_STYLES[condition] ?? CONDITION_STYLES.normal
  const confidencePct = Math.round((confidence ?? 0) * 100)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 flex flex-col gap-4">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
        AI Diagnostics
      </h2>

      {/* Status Badge + Health Gauge */}
      <div className="flex items-start justify-between">
        <div className={`inline-flex self-start px-4 py-2 rounded-full border ${style.bg} ${style.border}`}>
          <span className={`text-sm font-bold uppercase ${style.text}`}>
            {style.label}
          </span>
        </div>
        <HealthGauge score={health_score} />
      </div>

      {/* RUL */}
      <div>
        <span className="text-xs text-gray-500 uppercase tracking-wider">Remaining Useful Life</span>
        <div className="text-3xl font-bold font-mono text-gray-100 mt-1">
          {rul_days != null ? (
            <>
              {rul_days.toFixed(0)} <span className="text-base text-gray-400">days</span>
            </>
          ) : 'N/A'}
        </div>
      </div>

      {/* Corrosion Rate */}
      <div>
        <span className="text-xs text-gray-500 uppercase tracking-wider">Corrosion Rate</span>
        <div className="text-xl font-bold font-mono text-gray-100 mt-1">
          {corrosion_rate != null ? (
            <>
              {corrosion_rate.toFixed(3)} <span className="text-sm text-gray-400">mm/yr</span>
            </>
          ) : 'N/A'}
        </div>
      </div>

      {/* Confidence */}
      <div>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Confidence</span>
          <span className="text-gray-300 font-mono text-sm">{confidencePct}%</span>
        </div>
        <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-500 rounded-full transition-all duration-500"
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>
    </div>
  )
}
