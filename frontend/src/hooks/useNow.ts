// The current time, refreshed every `everyMs`. Null until the first tick, so render stays pure
// (no Date.now() during render); callers fall back to a known timestamp until then.
import { useEffect, useState } from 'react'

export function useNow(everyMs = 15_000): number | null {
  const [now, setNow] = useState<number | null>(null)

  useEffect(() => {
    const tick = () => setNow(Date.now())
    const first = window.setTimeout(tick, 0)
    const timer = window.setInterval(tick, everyMs)
    return () => {
      window.clearTimeout(first)
      window.clearInterval(timer)
    }
  }, [everyMs])

  return now
}