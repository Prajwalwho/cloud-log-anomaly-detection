// Data for the Anomalies page: one page of the filtered list, the count per severity, and one anomaly's detail.
// Both reload with useReloadKey (every 30 s, after live events, after a reconnect) and keep showing the previous
// result while a new one loads, so the page does not flicker.
import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage } from '../services/api'
import { rangeBounds, useTimeRange } from '../lib/timeRange'
import { useReloadKey } from './useReloadKey'
import { SEVERITIES, type Anomaly, type AnomalyDetail, type Page, type Severity } from '../types/api'

export const PAGE_SIZE = 50

export interface AnomalyFilters {
  service: string          // '' = all services
  severities: Severity[]   // [] = all severities
  feedback: string         // '' = all, or NONE / CONFIRMED / FALSE_POSITIVE
  page: number
}

interface ListState {
  key: string
  page: Page<Anomaly> | null
  counts: Record<Severity, number> | null
  error: string | null
}

export function useAnomalies(filters: AnomalyFilters) {
  const { range } = useTimeRange()
  const reload = useReloadKey()
  const { service, feedback, page } = filters
  const severity = filters.severities.join(',')
  const key = [range, service, severity, feedback, page].join('|')
  const [state, setState] = useState<ListState>({ key: '', page: null, counts: null, error: null })

  useEffect(() => {
    let active = true
    const { from, to } = rangeBounds(range)
    const base = { from, to, service, feedback }
    const requestKey = [range, service, severity, feedback, page].join('|')
    Promise.all([
      api.anomalies({ ...base, severity, page, size: PAGE_SIZE }),
      // counts per severity ignore the severity filter, so every chip shows how many it would add
      ...SEVERITIES.map((s) => api.anomalies({ ...base, severity: s, size: 1 })),
    ])
      .then(([list, ...bySeverity]) => {
        if (!active) return
        const counts = Object.fromEntries(SEVERITIES.map((s, i) => [s, bySeverity[i].total])) as Record<Severity, number>
        setState({ key: requestKey, page: list, counts, error: null })
      })
      .catch((e: unknown) => {
        if (active) setState((s) => ({ ...s, key: requestKey, error: errorMessage(e) }))
      })
    return () => {
      active = false
    }
  }, [range, service, severity, feedback, page, reload])

  /** Replace one item after a change (feedback) without waiting for the next reload. */
  const replace = useCallback((updated: Anomaly) => {
    setState((s) => (s.page
      ? { ...s, page: { ...s.page, items: s.page.items.map((a) => (a.id === updated.id ? updated : a)) } }
      : s))
  }, [])

  return { page: state.page, counts: state.counts, error: state.error, loading: state.key !== key, replace }
}

interface DetailState {
  id: string | null
  detail: AnomalyDetail | null
  error: string | null
}

export function useAnomalyDetail(id: string | null) {
  const reload = useReloadKey()
  const [state, setState] = useState<DetailState>({ id: null, detail: null, error: null })

  useEffect(() => {
    if (!id) return
    let active = true
    api.anomaly(id)
      .then((detail) => {
        if (active) setState({ id, detail, error: null })
      })
      .catch((e: unknown) => {
        if (active) setState((s) => ({ id, detail: s.id === id ? s.detail : null, error: errorMessage(e) }))
      })
    return () => {
      active = false
    }
  }, [id, reload])

  const replace = useCallback((updated: Anomaly) => {
    setState((s) => (s.detail && s.detail.id === updated.id ? { ...s, detail: { ...s.detail, ...updated } } : s))
  }, [])

  const current = id !== null && state.id === id
  return {
    detail: current ? state.detail : null,
    error: current ? state.error : null,
    loading: id !== null && (!current || (state.detail === null && state.error === null)),
    replace,
  }
}
