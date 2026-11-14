// Data for the overview header: summary, log volume per service, open alerts and the service list.
import { useEffect, useState } from 'react'
import { api, errorMessage } from '../services/api'
import { rangeBounds, useTimeRange } from '../lib/timeRange'
import { useReloadKey } from './useReloadKey'
import type { Alert, Summary } from '../types/api'

export interface OverviewData {
  summary: Summary
  services: string[]
  logCounts: Record<string, number>
  openAlerts: Alert[]
}

const ALERT_LOOKBACK_MS = 7 * 24 * 3600 * 1000

export function useOverview(): { data: OverviewData | null; error: string | null } {
  const { range } = useTimeRange()
  const reload = useReloadKey()
  const [data, setData] = useState<OverviewData | null>(null)
  const [error, setError] = useState<string | null>(null)

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
  }, [range, reload])

  return { data, error }
}