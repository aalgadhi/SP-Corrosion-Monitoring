export default function DevicesPanel({ stats }) {
  const online = stats?.devices_online ?? 0
  const total = stats?.devices_total ?? 0
  const allOnline = total > 0 && online === total
  const color = total === 0 ? 'text-gray-500' : allOnline ? 'text-green-400' : 'text-amber-400'
  const dot = total === 0 ? 'bg-gray-500' : allOnline ? 'bg-green-500' : 'bg-amber-500'

  return (
    <div className="flex items-center gap-2 bg-gray-900 border border-gray-800 rounded-full px-3 py-1.5">
      <span className={`w-2 h-2 rounded-full ${dot}`} />
      <span className={`text-xs font-mono ${color}`}>
        {total === 0 ? 'No devices' : `${online}/${total} online`}
      </span>
    </div>
  )
}
