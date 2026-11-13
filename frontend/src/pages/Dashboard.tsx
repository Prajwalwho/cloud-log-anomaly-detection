// Overview. Day 33: the constellation, the readout and the live signal list. Day 34: heatmap and charts.
import { useState } from 'react'
import { Constellation, type Star } from '../components/Constellation'
import { SeverityBar } from '../components/SeverityBar'
import { SeverityBadge } from '../components/SeverityBadge'
import { useOverview } from '../hooks/useOverview'
import { useLiveEvents } from '../live/context'
import { formatCompact, formatPercent, formatTime } from '../lib/format'
import { rangeOption, useTimeRange } from '../lib/timeRange'
import { SEVERITIES, type Alert, type LiveEvent } from '../types/api'

type Shown = Exclude<LiveEvent, { type: 'ping' }> & { receivedAt: string }

function worstAlert(alerts: Alert[], service: string): Alert | null {
  const own = alerts.filter((a) => a.service === service)
  own.sort((a, b) => SEVERITIES.indexOf(b.severity) - SEVERITIES.indexOf(a.severity))
  return own[0] ?? null
}

export function Dashboard() {
  const { range } = useTimeRange()
  const { data, error } = useOverview()
  const [flares, setFlares] = useState<Record<string, number>>({})
  const [events, setEvents] = useState<Shown[]>([])

  useLiveEvents((event) => {
    if (event.type === 'ping') return
    if (event.type === 'anomaly.created') {
      const now = Date.now()
      setFlares((current) => ({ ...current, [event.data.service]: now }))
    }
    setEvents((current) => [{ ...event, receivedAt: new Date().toISOString() }, ...current].slice(0, 12))
  })

  const phrase = rangeOption(range).phrase
  const byService = Object.fromEntries((data?.summary.by_service ?? []).map((s) => [s.service, s]))
  const stars: Star[] = (data?.services ?? []).map((service) => ({
    service,
    logs: data?.logCounts[service] ?? 0,
    errorRate: byService[service]?.error_rate ?? null,
    alert: data ? worstAlert(data.openAlerts, service) : null,
    flare: flares[service],
  }))

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Overview</h1>
          <p className="lead">Your services over the last {phrase}. Bigger stars log more; warmer colours need attention.</p>
        </div>
      </div>

      {error && <p className="error-note">Could not load the overview: {error}</p>}

      <div className="overview-hero">
        <div className="sky">
          {data ? <Constellation stars={stars} /> : <p className="muted">Loading the sky…</p>}
          <p className="sky-caption">Select a star to see that service's anomalies.</p>
        </div>

        {data && (
          <dl className="readout">
            <div>
              <dt>Open alerts</dt>
              <dd>{data.summary.open_alerts}</dd>
            </div>
            <div>
              <dt>Anomalies in the last {phrase}</dt>
              <dd>{data.summary.total_anomalies}</dd>
              <SeverityBar counts={data.summary.by_severity} />
            </div>
            <div>
              <dt>Error rate</dt>
              <dd>{formatPercent(data.summary.error_rate)}</dd>
            </div>
            <div>
              <dt>Log lines analysed</dt>
              <dd>{formatCompact(data.summary.total_logs)}<small>in {data.summary.total_windows} windows</small></dd>
            </div>
          </dl>
        )}
      </div>

      <div className="panel signals-panel">
        <h2>Live signals</h2>
        {events.length === 0 ? (
          <p className="muted">Quiet so far. New anomalies and alerts appear here the moment they are detected.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Time</th><th>Signal</th><th>Service</th><th>Severity</th><th>What happened</th></tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={`${e.type}-${e.data.id}-${e.receivedAt}`}>
                  <td className="number">{formatTime(e.receivedAt)}</td>
                  <td>{e.type === 'anomaly.created' ? 'Anomaly' : e.type === 'alert.created' ? 'Alert opened' : 'Alert updated'}</td>
                  <td>{e.data.service}</td>
                  <td><SeverityBadge severity={e.data.severity} /></td>
                  <td>
                    {e.type === 'anomaly.created'
                      ? (e.data.summary.reasons ?? []).join('; ')
                      : `${e.data.title} (${e.data.status.toLowerCase()}, ${e.data.occurrence_count} min)`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}