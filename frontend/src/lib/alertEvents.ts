// The story of an alert, built from what the API returns: when it opened, when it escalated (an anomaly of a higher
// severity joined), when it was acknowledged and when it was resolved. Escalations are not stored separately; they
// follow from the severities of the alert's anomalies in time order.
import { SEVERITIES, type AlertDetail, type Severity } from '../types/api'

export type AlertEventKind = 'opened' | 'escalated' | 'acknowledged' | 'resolved'

export interface AlertEvent {
  at: string
  kind: AlertEventKind
  text: string
  severity?: Severity
}

const rank = (s: Severity) => SEVERITIES.indexOf(s)

export function alertEvents(alert: AlertDetail): AlertEvent[] {
  const events: AlertEvent[] = []
  const anomalies = [...alert.anomalies].sort((a, b) => a.detected_at.localeCompare(b.detected_at))

  let worst: Severity | null = null
  for (const a of anomalies) {
    if (worst === null) {
      worst = a.severity
      const why = a.summary.reasons?.[0]
      events.push({ at: alert.first_seen_at, kind: 'opened', severity: a.severity,
                    text: `Opened as ${a.severity.toLowerCase()}${why ? `: ${why}` : ''}` })
    } else if (rank(a.severity) > rank(worst)) {
      worst = a.severity
      const why = a.summary.reasons?.[0]
      events.push({ at: a.detected_at, kind: 'escalated', severity: a.severity,
                    text: `Escalated to ${a.severity.toLowerCase()}${why ? `: ${why}` : ''}` })
    }
  }
  if (worst === null) {
    events.push({ at: alert.first_seen_at, kind: 'opened', severity: alert.severity,
                  text: `Opened as ${alert.severity.toLowerCase()}` })
  }
  if (alert.acknowledged_at) {
    events.push({ at: alert.acknowledged_at, kind: 'acknowledged',
                  text: `Acknowledged${alert.acknowledged_by ? ` by ${alert.acknowledged_by}` : ''}` })
  }
  if (alert.resolved_at) {
    const quietMin = Math.round((Date.parse(alert.resolved_at) - Date.parse(alert.last_seen_at)) / 60_000)
    events.push({ at: alert.resolved_at, kind: 'resolved',
                  text: quietMin >= 1 ? `Resolved after ${quietMin} min without new anomalies` : 'Resolved' })
  }
  return events.sort((a, b) => a.at.localeCompare(b.at))
}