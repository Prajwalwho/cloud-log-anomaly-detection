// Log search for the Logs page (GET /logs, Elasticsearch). Unlike the other pages, logs arrive thousands per
// minute, so the list does not reload by itself while someone is reading it: it loads when the filters change or
// when "Refresh" is pressed (refresh counter). A request's full path (all lines of one trace_id) is loaded
// separately over the last 7 days, so it is complete even when it falls outside the chosen time range.
import { useEffect, useState } from 'react'
import { api, errorMessage } from '../services/api'
import { rangeBounds, useTimeRange } from '../lib/timeRange'
import type { LogEvent, LogLevel, Page } from '../types/api'

export const PAGE_SIZE = 100
export const MAX_RESULTS = 10_000          // Elasticsearch from/size limit (api-contracts.md §3.3)
const TRACE_LOOKBACK_MS = 7 * 24 * 3600 * 1000

export interface LogSearchFilters {
  q: string
  service: string
  levels: LogLevel[]
  trace: string
  from: string          // '' = use the chosen time range
  to: string
  page: number
  refresh: number
}

interface SearchState {
  key: string
  page: Page<LogEvent> | null
  until: string | null   // end of the searched period, shown as "as of"
  error: string | null
}

export function useLogSearch(filters: LogSearchFilters) {
  const { range } = useTimeRange()
  const { q, service, trace, from, to, page, refresh } = filters
  const level = filters.levels.join(',')
  const key = [range, q, service, level, trace, from, to, page, refresh].join('|')
  const [state, setState] = useState<SearchState>({ key: '', page: null, until: null, error: null })

  useEffect(() => {
    let active = true
    const bounds = from && to ? { from, to } : rangeBounds(range)
    const requestKey = [range, q, service, level, trace, from, to, page, refresh].join('|')
    api.logs({ ...bounds, q, service, level, trace_id: trace, page, size: PAGE_SIZE })
      .then((result) => {
        if (active) setState({ key: requestKey, page: result, until: bounds.to, error: null })
      })
      .catch((e: unknown) => {
        if (active) setState((s) => ({ ...s, key: requestKey, error: errorMessage(e) }))
      })
    return () => {
      active = false
    }
  }, [range, q, service, level, trace, from, to, page, refresh])

  return { page: state.page, until: state.until, error: state.error, loading: state.key !== key }
}

interface TraceState {
  trace: string
  logs: LogEvent[]
  error: string | null
}

/** Every line of one request, oldest first. */
export function useTrace(trace: string) {
  const [state, setState] = useState<TraceState>({ trace: '', logs: [], error: null })

  useEffect(() => {
    if (!trace) return
    let active = true
    const to = new Date()
    const from = new Date(to.getTime() - TRACE_LOOKBACK_MS)
    api.logs({ trace_id: trace, from: from.toISOString(), to: to.toISOString(), size: 200 })
      .then((result) => {
        if (!active) return
        const logs = [...result.items].sort((a, b) => a.timestamp.localeCompare(b.timestamp))
        setState({ trace, logs, error: null })
      })
      .catch((e: unknown) => {
        if (active) setState({ trace, logs: [], error: errorMessage(e) })
      })
    return () => {
      active = false
    }
  }, [trace])

  const current = trace !== '' && state.trace === trace
  return { logs: current ? state.logs : [], error: current ? state.error : null, loading: trace !== '' && !current }
}