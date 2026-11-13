// Live feed hooks. One WebSocket (LiveFeedProvider) serves the whole app; components subscribe to its events.
import { createContext, useContext, useEffect, useRef } from 'react'
import type { LiveEvent } from '../types/api'

export type LiveStatus = 'connecting' | 'open' | 'reconnecting'
export type LiveListener = (event: LiveEvent) => void

export interface LiveFeedValue {
  status: LiveStatus
  /** Increases on every successful (re)connect: pages reload their data when it changes. */
  connectionCount: number
  subscribe: (listener: LiveListener) => () => void
}

export const LiveFeedContext = createContext<LiveFeedValue | null>(null)

export function useLiveFeed(): LiveFeedValue {
  const value = useContext(LiveFeedContext)
  if (!value) throw new Error('useLiveFeed must be used inside <LiveFeedProvider>')
  return value
}

/** Call `handler` for every live event; the latest handler is always used. */
export function useLiveEvents(handler: LiveListener): void {
  const { subscribe } = useLiveFeed()
  const latest = useRef(handler)
  useEffect(() => {
    latest.current = handler
  })
  useEffect(() => subscribe((event) => latest.current(event)), [subscribe])
}