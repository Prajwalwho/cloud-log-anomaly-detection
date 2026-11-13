// Types of the backend API (docs/design/api-contracts.md 1.2). Times are ISO 8601 UTC strings.

export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export const SEVERITIES: Severity[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
export type AlertStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'
export type Feedback = 'CONFIRMED' | 'FALSE_POSITIVE'
export type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'FATAL'

export interface Page<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface Health {
  status: 'ok' | 'degraded'
  components: Record<string, 'ok' | 'down'>
}

export interface Service {
  id: number
  name: string
  description: string | null
  created_at: string
}

export interface LogEvent {
  schema_version: string
  event_id: string
  timestamp: string
  service: string
  host: string
  level: LogLevel
  message: string
  trace_id?: string | null
  endpoint?: string | null
  status_code?: number | null
  latency_ms?: number | null
  metadata?: Record<string, unknown>
}

export interface AnomalySummary {
  log_count: number
  error_rate: number
  warn_rate?: number
  avg_latency_ms: number | null
  p95_latency_ms?: number | null
  new_templates: number
  raw_score?: number
  threshold?: number
  rule?: string | null
  reasons?: string[]
}

export interface ModelRef {
  id: number | null
  name: string
  version: string
}

export interface Anomaly {
  id: string
  service: string
  detected_at: string
  window_start: string
  window_end: string
  anomaly_score: number
  severity: Severity
  model: ModelRef
  summary: AnomalySummary
  alert_id: string | null
  feedback: Feedback | null
}

export interface AnomalyDetail extends Anomaly {
  sample_event_ids: string[]
  sample_logs: LogEvent[]
  sample_logs_error: string | null
}

export interface Alert {
  id: string
  service: string
  severity: Severity
  title: string
  message: string | null
  status: AlertStatus
  occurrence_count: number
  first_seen_at: string
  last_seen_at: string
  acknowledged_at: string | null
  acknowledged_by: string | null
  resolved_at: string | null
  notification_sent: boolean
}

export interface AlertDetail extends Alert {
  anomalies: Anomaly[]
}

export interface Summary {
  total_logs: number
  total_windows: number
  total_anomalies: number
  open_alerts: number
  error_rate: number
  by_severity: Record<Severity, number>
  by_service: { service: string; anomalies: number; error_rate: number }[]
}

export type Metric = 'log_count' | 'error_rate' | 'avg_latency_ms' | 'anomaly_score' | 'anomaly_count'
export type Interval = '1m' | '5m' | '1h'

export interface Timeseries {
  metric: Metric
  interval: Interval
  series: { service: string; points: { t: string; v: number | null }[] }[]
}

export interface Model {
  id: number
  name: string
  version: string
  algorithm: string
  threshold: number | null
  training_data: string | null
  training_samples: number | null
  is_active: boolean
  trained_at: string
  parameters: Record<string, unknown>
  metrics: Record<string, unknown>
}

// Messages on /ws/live (api-contracts.md §4)
export type LiveEvent =
  | { type: 'anomaly.created'; data: Anomaly }
  | { type: 'alert.created' | 'alert.updated'; data: Alert }
  | { type: 'ping'; data: Record<string, never> }