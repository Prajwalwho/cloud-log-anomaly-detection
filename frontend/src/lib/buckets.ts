// Time buckets for charts. The API groups windows with PostgreSQL date_bin (UTC, aligned to whole minutes /
// 5 minutes / hours), so the dashboard builds the same list of buckets to show gaps as gaps.
import type { Interval } from '../types/api'

const STEP_MS: Record<Interval, number> = { '1m': 60_000, '5m': 300_000, '1h': 3_600_000 }

/** Bucket start times (epoch ms) covering [from, to). */
export function buckets(from: string, to: string, interval: Interval): number[] {
  const step = STEP_MS[interval]
  const end = Date.parse(to)
  const result: number[] = []
  for (let t = Math.floor(Date.parse(from) / step) * step; t < end; t += step) result.push(t)
  return result
}

const timeOnly = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })
const dayAndTime = new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })

/** Label for a bucket in local time: "20:07" for minute buckets, "13 Nov, 20:00" for hourly ones. */
export function formatBucket(ms: number, interval: Interval): string {
  return (interval === '1h' ? dayAndTime : timeOnly).format(new Date(ms))
}

/** service -> (bucket ms -> value) */
export function lookupBySeries(series: { service: string; points: { t: string; v: number | null }[] }[]) {
  return new Map(series.map((s) => [s.service, new Map(s.points.map((p) => [Date.parse(p.t), p.v]))]))
}