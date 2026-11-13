// Typed client for the backend API (api-contracts.md 1.2). Requests go to /api/v1, which the Vite dev server
// forwards to FastAPI on port 8000.
import axios from 'axios'
import type {
  Alert, AlertDetail, AlertStatus, Anomaly, AnomalyDetail, Feedback, Health, Interval, LogEvent, Metric, Model,
  Page, Service, Summary, Timeseries,
} from '../types/api'

export const http = axios.create({ baseURL: '/api/v1', timeout: 15000 })

export interface TimeRange { from?: string; to?: string }
export interface Paging { page?: number; size?: number }
export type AnomalyQuery = TimeRange & Paging & { service?: string; severity?: string; feedback?: string }
export type AlertQuery = TimeRange & Paging & { service?: string; severity?: string; status?: string }
export type LogQuery = TimeRange & Paging & { q?: string; service?: string; level?: string; trace_id?: string }
export type TimeseriesQuery = TimeRange & { metric: Metric; interval?: Interval; service?: string }

const NOT_REACHABLE = 'The backend API is not reachable. Start it on port 8000 (uvicorn) and this page reloads by itself.'

/** Drop empty values so they are not sent as "?service=". */
function clean<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  ) as Partial<T>
}

/** A readable message for any API error (the contract's {"detail": ...} where available). */
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: unknown } | undefined)?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d) => (typeof d === 'object' && d && 'msg' in d ? String(d.msg) : String(d))).join('; ')
    }
    if (!error.response) return NOT_REACHABLE
    // Without an API explanation, these come from the dev-server proxy: the backend is down.
    if ([502, 503, 504].includes(error.response.status)) return NOT_REACHABLE
    return `HTTP ${error.response.status}`
  }
  return error instanceof Error ? error.message : String(error)
}

export const api = {
  // /health answers 503 when degraded; that is still a valid answer, not an error
  health: () => http.get<Health>('/health', { validateStatus: (s) => s === 200 || s === 503 }).then((r) => r.data),
  services: () => http.get<Service[]>('/services').then((r) => r.data),

  logs: (query: LogQuery) => http.get<Page<LogEvent>>('/logs', { params: clean(query) }).then((r) => r.data),
  log: (eventId: string) => http.get<LogEvent>(`/logs/${eventId}`).then((r) => r.data),

  anomalies: (query: AnomalyQuery) =>
    http.get<Page<Anomaly>>('/anomalies', { params: clean(query) }).then((r) => r.data),
  anomaly: (id: string) => http.get<AnomalyDetail>(`/anomalies/${id}`).then((r) => r.data),
  setFeedback: (id: string, feedback: Feedback | null) =>
    http.patch<Anomaly>(`/anomalies/${id}/feedback`, { feedback }).then((r) => r.data),

  alerts: (query: AlertQuery) => http.get<Page<Alert>>('/alerts', { params: clean(query) }).then((r) => r.data),
  alert: (id: string) => http.get<AlertDetail>(`/alerts/${id}`).then((r) => r.data),
  updateAlert: (id: string, status: AlertStatus, acknowledgedBy?: string) =>
    http.patch<Alert>(`/alerts/${id}`, { status, acknowledged_by: acknowledgedBy ?? null }).then((r) => r.data),

  summary: (range: TimeRange) => http.get<Summary>('/stats/summary', { params: clean(range) }).then((r) => r.data),
  timeseries: (query: TimeseriesQuery) =>
    http.get<Timeseries>('/stats/timeseries', { params: clean(query) }).then((r) => r.data),

  models: () => http.get<Model[]>('/models').then((r) => r.data),
  activeModel: () => http.get<Model>('/models/active').then((r) => r.data),
}