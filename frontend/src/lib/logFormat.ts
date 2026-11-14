// Formatting for log lines, which need millisecond precision (requests through several services take a few ms).
const msTimeFormat = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3,
})
const dayFormat = new Intl.DateTimeFormat(undefined, { month: 'short', day: '2-digit' })

/** "14:50:12.345" in local time. */
export function formatLogTime(iso: string): string {
  return msTimeFormat.format(new Date(iso))
}

/** "Nov 14" in local time. */
export function formatLogDay(iso: string): string {
  return dayFormat.format(new Date(iso))
}

/** +0 ms, +12 ms, +1.24 s: the offset of a step from the first line of a request. */
export function formatOffset(ms: number): string {
  return ms < 1000 ? `+${Math.round(ms)} ms` : `+${(ms / 1000).toFixed(2)} s`
}