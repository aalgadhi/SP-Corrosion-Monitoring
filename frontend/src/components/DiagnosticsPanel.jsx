const CONDITION_STYLES = {
  normal: { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/30' },
  corrosion: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30' },
  fouling: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/30' },
  leak: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' },
}

export default function DiagnosticsPanel({ data }) {
  if (!data?.latest) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 flex items-center justify-center">
        <span className="text-gray-500">Waiting for diagnostics...</span>
      </div>
    )
  }

  const { condition, rul_days, confidence } = data.latest
  const style = CONDITION_STYLES[condition] ?? CONDITION_STYLES.normal
  const confidencePct = Math.round((confidence ?? 0) * 100)

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 flex flex-col gap-4">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
        AI Diagnostics
      </h2>

      {/* Status Badge */}
      <div className={`inline-flex self-start px-4 py-2 rounded-full border ${style.bg} ${style.border}`}>
        <span className={`text-lg font-bold uppercase ${style.text}`}>
          {condition}
        </span>
      </div>

      {/* RUL */}
      <div>
        <span className="text-sm text-gray-400">Estimated Remaining Life</span>
        <div className="text-3xl font-bold font-mono text-gray-100 mt-1">
          {rul_days != null ? `${rul_days.toFixed(0)} days` : 'N/A'}
        </div>
      </div>

      {/* Confidence */}
      <div>
        <div className="flex justify-between text-sm mb-1">
          <span className="text-gray-400">Confidence</span>
          <span className="text-gray-300 font-mono">{confidencePct}%</span>
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
