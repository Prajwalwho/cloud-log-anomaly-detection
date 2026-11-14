// A value that changes whenever data should be reloaded: every 30 s, 1.5 s after a live event (several events in a
// row cause one reload), and after the live feed reconnects (missed events are not replayed).
import { useEffect, useRef, useState } from 'react'
import { useLiveEvents, useLiveFeed } from '../live/context'

const REFRESH_MS = 30_000
const AFTER_EVENT_MS = 1_500

export function useReloadKey(): string {
  const { connectionCount } = useLiveFeed()
  const [tick, setTick] = useState(0)
  const pending = useRef<number | undefined>(undefined)

  useEffect(() => {
    const timer = window.setInterval(() => setTick((n) => n + 1), REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [])

  useLiveEvents((event) => {
    if (event.type === 'ping') return
    window.clearTimeout(pending.current)
    pending.current = window.setTimeout(() => setTick((n) => n + 1), AFTER_EVENT_MS)
  })

  return `${connectionCount}-${tick}`
}