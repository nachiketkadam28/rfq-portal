import { useCallback, useEffect, useState, type DependencyList } from 'react'

/** Fetch on mount / when deps change. `reload` re-runs; `set` replaces data after a mutation. */
export function useLoad<T>(fn: () => Promise<T>, deps: DependencyList) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  useEffect(() => {
    let live = true
    setError(null)
    fn().then(d => { if (live) setData(d) }).catch(e => { if (live) setError(e.message) })
    return () => { live = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick(t => t + 1), [])
  return { data, error, reload, set: setData }
}
