// Reads a model's stored evaluation (model_registry.metrics, written by backend/detection/train.py) into typed
// values. The API returns it as free-form JSON, so every field is checked; anything missing becomes null.

export interface IncidentResult {
  scenario: string
  service: string
  flagged: number
  windows: number
  timeToFlagS: number | null
}

export interface FaultRun {
  file: string | null
  precision: number | null
  recall: number | null
  f1: number | null
  incidentsDetected: number | null
  incidents: number | null
  quietFalseAlarms: number | null
  quietWindows: number | null
  severities: Record<string, number>
  perRecord: IncidentResult[]
}

export interface NormalRun {
  file: string | null
  windows: number | null
  falseAlarms: number | null
  falseAlarmRate: number | null
  severities: Record<string, number>
}

type Json = Record<string, unknown>

const obj = (v: unknown): Json | null => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Json) : null)
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const str = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const counts = (v: unknown): Record<string, number> => Object.fromEntries(
  Object.entries(obj(v) ?? {}).filter(([, n]) => typeof n === 'number') as [string, number][],
)

export function readMetrics(metrics: Record<string, unknown>): { faultRun: FaultRun | null; normalRun: NormalRun | null } {
  const f = obj(metrics.fault_run)
  const n = obj(metrics.normal_run)
  const faultRun: FaultRun | null = f && {
    file: str(f.file),
    precision: num(f.precision),
    recall: num(f.recall),
    f1: num(f.f1),
    incidentsDetected: num(f.incidents_detected),
    incidents: num(f.incidents),
    quietFalseAlarms: num(f.quiet_false_alarms),
    quietWindows: num(f.quiet_windows),
    severities: counts(f.severities_of_faulty_windows),
    perRecord: (Array.isArray(f.per_record) ? f.per_record : []).map(obj).filter((r): r is Json => r !== null).map((r) => ({
      scenario: str(r.scenario) ?? '?',
      service: str(r.service) ?? '?',
      flagged: num(r.flagged) ?? 0,
      windows: num(r.windows) ?? 0,
      timeToFlagS: num(r.time_to_detect_s),
    })),
  }
  const normalRun: NormalRun | null = n && {
    file: str(n.file),
    windows: num(n.windows),
    falseAlarms: num(n.false_alarms),
    falseAlarmRate: num(n.false_alarm_rate),
    severities: counts(n.false_alarm_severities),
  }
  return { faultRun, normalRun }
}

const SCENARIO_NAMES: Record<string, string> = {
  error_burst: 'Error burst',
  latency_spike: 'Latency spike',
  new_error: 'New error type',
  silent_service: 'Silent service',
  cascading_failure: 'Cascading failure',
}

export function scenarioName(key: string): string {
  return SCENARIO_NAMES[key] ?? key.replace(/_/g, ' ')
}

/** Model parameters in words: ("log_counts", true) -> ["Log-scaled counts", "on"]. */
const PARAMETER_NAMES: Record<string, string> = {
  algorithm: 'Algorithm',
  log_counts: 'Log-scaled counts',
  per_service: 'One model per service',
  percentile: 'Threshold percentile',
  min_std: 'Minimum spread',
  normalisation: 'Score normalisation',
  window_s: 'Window',
  grace_s: 'Grace period',
}

export function describeParameter(key: string, value: unknown): [string, string] {
  const name = PARAMETER_NAMES[key] ?? key.replace(/_/g, ' ')
  if (typeof value === 'boolean') return [name, value ? 'yes' : 'no']
  if (key === 'window_s' || key === 'grace_s') return [name, `${value} s`]
  if (key === 'percentile') return [name, `${value}th`]
  if (key === 'algorithm' && typeof value === 'string') return [name, value.toUpperCase()]
  return [name, typeof value === 'object' ? JSON.stringify(value) : String(value)]
}