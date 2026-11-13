// Display helpers. All API times are UTC; the dashboard is the only place they become local time
// (contracts.md §1).
import type { Severity } from '../types/api'

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit',
})
const timeFormat = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })
const compactFormat = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTimeFormat.format(new Date(iso)) : '—'
}

export function formatTime(iso: string | null | undefined): string {
  return iso ? timeFormat.format(new Date(iso)) : '—'
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

export const SEVERITY_COLOURS: Record<Severity, string> = {
  LOW: 'var(--sev-low)',
  MEDIUM: 'var(--sev-medium)',
  HIGH: 'var(--sev-high)',
  CRITICAL: 'var(--sev-critical)',
}