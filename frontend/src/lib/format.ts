// Display helpers. All API times are UTC; the dashboard is the only place they become local time
// (contracts.md §1).
import type { AlertStatus, LogLevel, Severity } from '../types/api'

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
})
const shortDateTimeFormat = new Intl.DateTimeFormat(undefined, {
  month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit',
})
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const clockFormat = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })
const compactFormat = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTimeFormat.format(new Date(iso)) : '—'
}

/** "Nov 14, 10:15" */
export function formatShortDateTime(iso: string | null | undefined): string {
  return iso ? shortDateTimeFormat.format(new Date(iso)) : '—'
}

export function formatTime(iso: string | null | undefined): string {
  return iso ? timeFormat.format(new Date(iso)) : '—'
}

/** Local clock time without seconds: "10:15". */
export function formatClock(iso: string | null | undefined): string {
  return iso ? clockFormat.format(new Date(iso)) : '—'
}

/** A window as local clock times: "10:15–10:16". */
export function formatWindow(start: string, end: string): string {
  return `${clockFormat.format(new Date(start))}–${clockFormat.format(new Date(end))}`
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(digits)}%`
}

export function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : value.toLocaleString()
}

/** 1240 -> "1.2K", 64440 -> "64.4K" */
export function formatCompact(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : compactFormat.format(value)
}

/** 137.4 -> "137 ms", 5790 -> "5.79 s" */
export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—'
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`
}

/** 35_000 -> "35 s", 240_000 -> "4 min", 4_320_000 -> "1 h 12 min" */
export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || ms < 0) return '—'
  const seconds = Math.round(ms / 1000)
  if (seconds < 60) return `${seconds} s`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours < 24) return rest ? `${hours} h ${rest} min` : `${hours} h`
  const days = Math.floor(hours / 24)
  return hours % 24 ? `${days} d ${hours % 24} h` : `${days} d`
}

export const SEVERITY_COLOURS: Record<Severity, string> = {
  LOW: 'var(--sev-low)',
  MEDIUM: 'var(--sev-medium)',
  HIGH: 'var(--sev-high)',
  CRITICAL: 'var(--sev-critical)',
}

export const LEVEL_COLOURS: Record<LogLevel, string> = {
  DEBUG: 'var(--faint)',
  INFO: 'var(--muted)',
  WARN: 'var(--sev-medium)',
  ERROR: 'var(--sev-high)',
  FATAL: 'var(--sev-critical)',
}

export const STATUS_COLOURS: Record<AlertStatus, string> = {
  OPEN: 'var(--sev-high)',
  ACKNOWLEDGED: 'var(--nebula)',
  RESOLVED: 'var(--healthy)',
}

export const STATUS_NAMES: Record<AlertStatus, string> = {
  OPEN: 'Open',
  ACKNOWLEDGED: 'Acknowledged',
  RESOLVED: 'Resolved',
}