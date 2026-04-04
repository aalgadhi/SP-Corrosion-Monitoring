import { useState, useEffect, useRef, useCallback } from 'react'

export default function usePolling(fetchFn, intervalMs = 2000) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const timerRef = useRef(null)
  const mountedRef = useRef(true)

  const poll = useCallback(async () => {
    try {
      const result = await fetchFn()
      if (mountedRef.current) {
        setData(result)
        setError(null)
        setLoading(false)
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err)
        setLoading(false)
      }
    }
  }, [fetchFn])

  useEffect(() => {
    mountedRef.current = true
    poll()
    timerRef.current = setInterval(poll, intervalMs)
    return () => {
      mountedRef.current = false
      clearInterval(timerRef.current)
    }
  }, [poll, intervalMs])

  return { data, loading, error }
}
