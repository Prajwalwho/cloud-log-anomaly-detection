// Data for the Alerts page: one page of the filtered list, counts per status group, and one alert's detail with
// its anomalies. Both reload with useReloadKey (every 30 s, after live events, after a reconnect) and keep showing
// the previous result while a new one loads.
import { useCallback, useEffect, useState } from 'react'
import { api, errorMessage } from '../services/api'
import { rangeBounds, useTimeRange } from '../lib/timeRange'
import { useReloadKey } from './useReloadKey'
import type { Alert, AlertDetail, Page, Severity } from '../types/api'

export const PAGE_SIZE = 50

/** Status groups shown as tabs; each maps to the API's comma-separated status filter. */
export type StatusGroup = 'active' | 'resolved' | 'all'
export const STATUS_FILTER: Record<StatusGroup, string> = {
  active: 'OPEN,ACKNOWLEDGED',
  resolved: 'RESOLVED',
  all: '',
}

export interface AlertFilters {
  group: StatusGroup
  service: string          // '' = all services
  severities: Severity[]   // [] = all severities
  page: number
}

interface ListState {
  key: string
  page: Page<Alert> | null
  counts: Record<StatusGroup, number> | null
  error: string | null
}

export function useAlerts(filters: AlertFilters) {
  const { range } = useTimeRange()
  const reload = useReloadKey()
  const { group, service, page } = filters
  const severity = filters.severities.join(',')
  const key = [range, group, service, severity, page].join('|')
  const [state, setState] = useState<ListState>({ key: '', page: null, counts: null, error: null })

  useEffect(() => {
    let active = true
    const { from, to } = rangeBounds(range)
    const base = { from, to, service, severity }
    const requestKey = [range, group, service, severity, page].join('|')
    Promise.all([
      api.alerts({ ...base, status: STATUS_FILTER[group], page, size: PAGE_SIZE }),
      api.alerts({ ...base, status: STATUS_FILTER.active, size: 1 }),
      api.alerts({ ...base, status: STATUS_FILTER.resolved, size: 1 }),
    ])
      .then(([list, activeCount, resolvedCount]) => {
        if (!active) return
        const counts = {
          active: activeCount.total,
          resolved: resolvedCount.total,
          all: activeCount.total + resolvedCount.total,
        }
        setState({ key: requestKey, page: list, counts, error: null })
      })
      .catch((e: unknown) => {
        if (active) setState((s) => ({ ...s, key: requestKey, error: errorMessage(e) }))
      })
    return () => {
      active = false
    }
  }, [range, group, service, severity, page, reload])

  /** Replace one item after a change (acknowledge / resolve) without waiting for the next reload. */
  const replace = useCallback((updated: Alert) => {
    setState((s) => (s.page
      ? { ...s, page: { ...s.page, items: s.page.items.map((a) => (a.id === updated.id ? updated : a)) } }
      : s))
  }, [])

  return { page: state.page, counts: state.counts, error: state.error, loading: state.key !== key, replace }
}

interface DetailState {
  id: string | null
  detail: AlertDetail | null
  error: string | null
}

export function useAlertDetail(id: string | null) {
  const reload = useReloadKey()
  const [state, setState] = useState<DetailState>({ id: null, detail: null, error: null })

  useEffect(() => {
    if (!id) return
    let active = true
    api.alert(id)
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

  const replace = useCallback((updated: Alert) => {
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