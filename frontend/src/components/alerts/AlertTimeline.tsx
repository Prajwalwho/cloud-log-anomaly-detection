// An alert's life on one line: each anomaly is a dot (colour = severity) at the time it was detected, with marks for
// acknowledged and resolved. An alert that is still active runs on (dashed) to now.
import { SEVERITY_COLOURS, STATUS_COLOURS, formatClock } from '../../lib/format'
import type { AlertDetail } from '../../types/api'

const W = 340
const H = 58
const PAD = 10
const LINE_Y = 24
const RADIUS = { LOW: 3, MEDIUM: 4, HIGH: 5, CRITICAL: 6 } as const

export function AlertTimeline({ alert, now }: { alert: AlertDetail; now: number | null }) {
  const starts = [Date.parse(alert.first_seen_at), ...alert.anomalies.map((a) => Date.parse(a.detected_at))]
  const t0 = Math.min(...starts)
  const lastSeen = Date.parse(alert.last_seen_at)
  const active = alert.resolved_at === null
  const t1 = alert.resolved_at ? Date.parse(alert.resolved_at) : Math.max(lastSeen, now ?? lastSeen)
  const span = Math.max(t1 - t0, 60_000)
  const x = (t: number) => PAD + ((t - t0) / span) * (W - 2 * PAD)

  const label = `Alert timeline from ${formatClock(alert.first_seen_at)} to ${active ? 'now' : formatClock(alert.resolved_at)}, `
    + `${alert.anomalies.length} anomalies`

  return (
    <svg className="alert-timeline" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
      <line x1={x(t0)} x2={x(lastSeen)} y1={LINE_Y} y2={LINE_Y} className="tl-line" />
      <line x1={x(lastSeen)} x2={x(t1)} y1={LINE_Y} y2={LINE_Y} className={active ? 'tl-line tl-open' : 'tl-line'} />

      {alert.acknowledged_at && (
        <line x1={x(Date.parse(alert.acknowledged_at))} x2={x(Date.parse(alert.acknowledged_at))}
              y1={LINE_Y - 11} y2={LINE_Y + 11} stroke={STATUS_COLOURS.ACKNOWLEDGED} strokeWidth={2}>
          <title>Acknowledged {formatClock(alert.acknowledged_at)}</title>
        </line>
      )}

      {alert.anomalies.map((a) => (
        <circle key={a.id} cx={x(Date.parse(a.detected_at))} cy={LINE_Y} r={RADIUS[a.severity]}
                fill={SEVERITY_COLOURS[a.severity]} className="tl-dot">
          <title>{formatClock(a.window_start)} {a.severity.toLowerCase()}: {(a.summary.reasons ?? []).join('; ') || 'unusual pattern'}</title>
        </circle>
      ))}

      {alert.resolved_at && (
        <circle cx={x(t1)} cy={LINE_Y} r={7} fill="none" stroke={STATUS_COLOURS.RESOLVED} strokeWidth={1.5}>
          <title>Resolved {formatClock(alert.resolved_at)}</title>
        </circle>
      )}

      <text x={PAD} y={H - 4} className="tl-tick">{formatClock(alert.first_seen_at)}</text>
      <text x={W - PAD} y={H - 4} className="tl-tick" textAnchor="end">
        {active ? 'now' : formatClock(alert.resolved_at)}
      </text>
    </svg>
  )
}