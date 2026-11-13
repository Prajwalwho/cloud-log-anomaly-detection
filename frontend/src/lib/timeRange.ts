// The time range shown on every page, chosen once in the top bar.
import { createContext, useContext } from 'react'
import type { Interval } from '../types/api'

export type RangeKey = '15m' | '1h' | '6h' | '24h' | '7d'

export interface RangeOption {
  key: RangeKey
  label: string        // picker label
  phrase: string       // used in sentences: "over the last 1 hour"
  minutes: number
  interval: Interval   // chart / heatmap bucket size for this range
}

export const RANGES: RangeOption[] = [
  { key: '15m', label: '15 min', phrase: '15 minutes', minutes: 15, interval: '1m' },
  { key: '1h', label: '1 hour', phrase: '1 hour', minutes: 60, interval: '1m' },
  { key: '6h', label: '6 hours', phrase: '6 hours', minutes: 360, interval: '5m' },
  { key: '24h', label: '24 hours', phrase: '24 hours', minutes: 1440, interval: '1h' },
  { key: '7d', label: '7 days', phrase: '7 days', minutes: 10080, interval: '1h' },
]

export function rangeOption(key: RangeKey): RangeOption {
  return RANGES.find((r) => r.key === key) ?? RANGES[1]
}

/** ISO bounds ending now. Call this in effects or handlers, not during render. */
export function rangeBounds(key: RangeKey): { from: string; to: string } {
  const to = new Date()
  const from = new Date(to.getTime() - rangeOption(key).minutes * 60_000)
  return { from: from.toISOString(), to: to.toISOString() }
}

export interface TimeRangeValue {
  range: RangeKey
  setRange: (range: RangeKey) => void
}

export const TimeRangeContext = createContext<TimeRangeValue | null>(null)

export function useTimeRange(): TimeRangeValue {
  const value = useContext(TimeRangeContext)
  if (!value) throw new Error('useTimeRange must be used inside <TimeRangeProvider>')
  return value
}