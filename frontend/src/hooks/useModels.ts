// Data for the Models page: every registered model (newest first) and the operators' verdicts on anomalies in the
// chosen time range (feedback from the Anomalies page). Reloads with useReloadKey, so new verdicts show up.
import { useEffect, useState } from 'react'
import { api, errorMessage } from '../services/api'
import { rangeBounds, useTimeRange } from '../lib/timeRange'
import { useReloadKey } from './useReloadKey'
import type { Model } from '../types/api'

export interface Verdicts {
  confirmed: number
  falseAlarms: number
  notReviewed: number
}

export function useModels() {
  const { range } = useTimeRange()
  const reload = useReloadKey()
  const [models, setModels] = useState<Model[] | null>(null)
  const [verdicts, setVerdicts] = useState<Verdicts | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    const { from, to } = rangeBounds(range)
    Promise.all([
      api.models(),
      api.anomalies({ from, to, feedback: 'CONFIRMED', size: 1 }),
      api.anomalies({ from, to, feedback: 'FALSE_POSITIVE', size: 1 }),
      api.anomalies({ from, to, feedback: 'NONE', size: 1 }),
    ])
      .then(([list, confirmed, falseAlarms, notReviewed]) => {
        if (!active) return
        setModels(list)
        setVerdicts({ confirmed: confirmed.total, falseAlarms: falseAlarms.total, notReviewed: notReviewed.total })
        setError(null)
      })
      .catch((e: unknown) => {
        if (active) setError(errorMessage(e))
      })
    return () => {
      active = false
    }
  }, [range, reload])

  return { models, verdicts, error }
}