// The app's single WebSocket to /api/v1/ws/live, with automatic reconnect (1 s, 2 s, 4 s ... max 30 s).
// Events sent while disconnected are not replayed (api-contracts.md §4), so connectionCount tells pages to reload.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { LiveEvent } from '../types/api'
import { LiveFeedContext, type LiveListener, type LiveStatus } from './context'

const MAX_DELAY_MS = 30_000

function liveUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${protocol}://${window.location.host}/api/v1/ws/live`
}

export function LiveFeedProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<LiveStatus>('connecting')
  const [connectionCount, setConnectionCount] = useState(0)
  const listeners = useRef(new Set<LiveListener>())

  useEffect(() => {
    let socket: WebSocket | null = null
    let attempt = 0
    let timer: number | undefined
    let stopped = false

    const connect = () => {
      socket = new WebSocket(liveUrl())
      socket.onopen = () => {
        attempt = 0
        setStatus('open')
        setConnectionCount((n) => n + 1)
      }
      socket.onmessage = (message) => {
        let event: LiveEvent
        try {
          event = JSON.parse(message.data) as LiveEvent
        } catch {
          return
        }
        listeners.current.forEach((listener) => listener(event))
      }
      socket.onclose = () => {
        if (stopped) return
        setStatus('reconnecting')
        const delay = Math.min(MAX_DELAY_MS, 1000 * 2 ** attempt)
        attempt += 1
        timer = window.setTimeout(connect, delay)
      }
      socket.onerror = () => socket?.close()
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(timer)
      socket?.close()
    }
  }, [])

  const subscribe = useCallback((listener: LiveListener) => {
    listeners.current.add(listener)
    return () => {
      listeners.current.delete(listener)
    }
  }, [])

  const value = useMemo(() => ({ status, connectionCount, subscribe }), [status, connectionCount, subscribe])
  return <LiveFeedContext.Provider value={value}>{children}</LiveFeedContext.Provider>
}