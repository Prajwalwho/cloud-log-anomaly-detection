// Time series for the overview charts, at the bucket size that suits the chosen range.
import { useEffect, useState } from 'react'
import { api, errorMessage } from '../services/api'
import { rangeBounds, rangeOption, useTimeRange } from '../lib/timeRange'
import { useReloadKey } from './useReloadKey'
import type { Interval, Timeseries } from '../types/api'

export interface SeriesData {
  from: string
  to: string
  interval: Interval
  score: Timeseries        // max anomaly score per bucket (heatmap)
  errorRate: Timeseries
  anomalies: Timeseries    // number of anomalous windows per bucket
}

export function useOverviewSeries(): { series: SeriesData | null; error: string | null } {
  const { range } = useTimeRange()
  const reload = useReloadKey()
  const [series, setSeries] = useState<SeriesData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const { from, to } = rangeBounds(range)
    const interval = rangeOption(range).interval
    Promise.all([
      api.timeseries({ metric: 'anomaly_score', interval, from, to }),
      api.timeseries({ metric: 'error_rate', interval, from, to }),
      api.timeseries({ metric: 'anomaly_count', interval, from, to }),
    ])
      .then(([score, errorRate, anomalies]) => {
        if (!active) return
        setSeries({ from, to, interval, score, errorRate, anomalies })
        setError(null)
      })
      .catch((e: unknown) => {
        if (active) setError(errorMessage(e))
      })
    return () => {
      active = false
    }
  }, [range, reload])

  return { series, error }
}