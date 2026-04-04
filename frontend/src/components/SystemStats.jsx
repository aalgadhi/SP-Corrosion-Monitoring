export default function SystemStats({ data }) {
  if (!data) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 animate-pulse h-48" />
    )
  }

  const items = [
    { label: 'Total Readings', value: data.total_readings?.toLocaleString() ?? '0' },
    { label: 'Diagnostics Run', value: data.total_diagnostics?.toLocaleString() ?? '0' },
    { label: 'Alerts Generated', value: data.total_alerts?.toLocaleString() ?? '0' },
    { label: 'Days of Data', value: `${data.days_of_data ?? 0}` },
    { label: 'DB Size', value: `${data.db_size_mb ?? 0} MB` },
    {
      label: 'S8 Compliance',
      value: data.spec_s8_met ? 'PASSED' : 'NOT MET',
      color: data.spec_s8_met ? 'text-green-400' : 'text-red-400',
    },
  ]

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
        System Stats
      </h2>
      <div className="space-y-3">
        {items.map(item => (
          <div key={item.label} className="flex items-center justify-between">
            <span className="text-sm text-gray-500">{item.label}</span>
            <span className={`text-sm font-mono font-semibold ${item.color ?? 'text-gray-200'}`}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
      {data.oldest_reading && (
        <div className="mt-4 pt-3 border-t border-gray-800">
          <div className="text-xs text-gray-600">
            Data range: {new Date(data.oldest_reading).toLocaleDateString()} — {new Date(data.newest_reading).toLocaleDateString()}
          </div>
        </div>
      )}
    </div>
  )
}
