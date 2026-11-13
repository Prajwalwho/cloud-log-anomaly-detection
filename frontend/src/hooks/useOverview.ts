// Data for the overview: summary, log volume per service, open alerts and the service list.
// Reloads when the range changes, every 30 s, shortly after live events, and after a live-feed reconnect.
import { useEffect, useRef, useState } from 'react'
import { api, errorMessage } from '../services/api'
import { useLiveEvents, useLiveFeed } from '../live/context'
import { rangeBounds, useTimeRange } from '../lib/timeRange'
import type { Alert, Summary } from '../types/api'

export interface OverviewData {
  summary: Summary
  services: string[]
  logCounts: Record<string, number>
  openAlerts: Alert[]
}

const REFRESH_MS = 30_000
const AFTER_EVENT_MS = 1_500
const ALERT_LOOKBACK_MS = 7 * 24 * 3600 * 1000

export function useOverview(): { data: OverviewData | null; error: string | null } {
  const { range } = useTimeRange()
  const { connectionCount } = useLiveFeed()
  const [data, setData] = useState<OverviewData | null>(null)
  const [error, setError] = useState<string | null>(null)
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

  useEffect(() => {
    let active = true
    const { from, to } = rangeBounds(range)
    const alertsFrom = new Date(Date.now() - ALERT_LOOKBACK_MS).toISOString()
    Promise.all([
      api.summary({ from, to }),
      api.timeseries({ metric: 'log_count', interval: '1h', from, to }),
      api.alerts({ status: 'OPEN,ACKNOWLEDGED', from: alertsFrom, to, size: 200 }),
      api.services(),
    ])
      .then(([summary, volume, alerts, services]) => {
        if (!active) return
        const logCounts = Object.fromEntries(
          volume.series.map((s) => [s.service, s.points.reduce((sum, p) => sum + (p.v ?? 0), 0)]),
        )
        setData({ summary, services: services.map((s) => s.name), logCounts, openAlerts: alerts.items })
        setError(null)
      })
      .catch((e: unknown) => {
        if (active) setError(errorMessage(e))
      })
    return () => {
      active = false
    }
  }, [range, connectionCount, tick])

  return { data, error }
}