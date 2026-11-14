// Alerts: grouped anomalies that need a person. Active alerts first (open and acknowledged), filterable, with a
// detail panel to acknowledge or resolve. Filters, page and selection live in the URL
// (?status=&service=&severity=&page=&id=); the Anomalies page links here with ?id=.
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Send } from 'lucide-react'
import { AlertDetail } from '../components/alerts/AlertDetail'
import { AlertFilters } from '../components/alerts/AlertFilters'
import { StatusPill } from '../components/alerts/StatusPill'
import '../components/anomalies/anomalies.css'
import '../components/alerts/alerts.css'
import { SeverityBadge } from '../components/SeverityBadge'
import { PAGE_SIZE, useAlertDetail, useAlerts, type StatusGroup } from '../hooks/useAlerts'
import { useServiceNames } from '../hooks/useServiceNames'
import { useLiveEvents } from '../live/context'
import { formatClock, formatShortDateTime, formatTime } from '../lib/format'
import { rangeOption, useTimeRange } from '../lib/timeRange'
import { SEVERITIES, type Alert, type Severity } from '../types/api'

const FRESH_MS = 8_000

function isSeverity(value: string): value is Severity {
  return (SEVERITIES as string[]).includes(value)
}

function isGroup(value: string | null): value is StatusGroup {
  return value === 'active' || value === 'resolved' || value === 'all'
}

export function Alerts() {
  const { range } = useTimeRange()
  const [params, setParams] = useSearchParams()
  const services = useServiceNames()
  const [fresh, setFresh] = useState<Set<string>>(new Set())

  const rawStatus = params.get('status')
  const group: StatusGroup = isGroup(rawStatus) ? rawStatus : 'active'
  const service = params.get('service') ?? ''
  const severities = (params.get('severity') ?? '').split(',').filter(isSeverity)
  const page = Math.max(1, Number(params.get('page')) || 1)
  const selected = params.get('id')

  const list = useAlerts({ group, service, severities, page })
  const detail = useAlertDetail(selected)

  // Alerts that open or change while the page is open glow briefly when the list reloads with them.
  useLiveEvents((event) => {
    if (event.type !== 'alert.created' && event.type !== 'alert.updated') return
    const id = event.data.id
    setFresh((current) => new Set(current).add(id))
    window.setTimeout(() => setFresh((current) => {
      const next = new Set(current)
      next.delete(id)
      return next
    }), FRESH_MS)
  })

  /** Change URL parameters; any filter change goes back to page 1. */
  const update = (changes: Record<string, string | null>, keepPage = false) => {
    setParams((current) => {
      const next = new URLSearchParams(current)
      for (const [key, value] of Object.entries(changes)) {
        if (value) next.set(key, value)
        else next.delete(key)
      }
      if (!keepPage) next.delete('page')
      return next
    }, { replace: true })
  }

  const changed = (alert: Alert) => {
    list.replace(alert)
    detail.replace(alert)
  }

  const total = list.page?.total ?? 0
  const items = list.page?.items ?? []
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const first = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const last = Math.min(total, page * PAGE_SIZE)
  const longRange = range === '24h' || range === '7d'
  const phrase = rangeOption(range).phrase
  const filtered = service !== '' || severities.length > 0

  const emptyText = page > 1 ? 'This page is empty.'
    : filtered ? 'No alerts match these filters.'
      : group === 'active' ? 'No active alerts. Nothing needs attention right now.'
        : `No alerts in the last ${phrase}.`

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Alerts</h1>
          <p className="lead">
            Anomalies of one service close together in time form one alert. Acknowledge an alert when you take it on,
            resolve it when it is fixed. Showing alerts active in the last {phrase}.
          </p>
        </div>
      </div>

      <AlertFilters
        services={services}
        group={group}
        service={service}
        severities={severities}
        counts={list.counts}
        onGroup={(value) => update({ status: value === 'active' ? null : value })}
        onService={(value) => update({ service: value })}
        onSeverities={(value) => update({ severity: value.join(',') })}
      />

      {list.error && <p className="error-note">Could not load alerts: {list.error}</p>}

      <div className={`anomaly-layout${selected ? ' has-detail' : ''}`}>
        <div className={`panel anomaly-list${list.loading ? ' is-loading' : ''}`}>
          {list.page === null ? (
            <p className="muted">{list.error ? 'Nothing to show.' : 'Loading alerts…'}</p>
          ) : items.length === 0 ? (
            <div className="empty">
              <p>{emptyText}</p>
              {page > 1 && <button type="button" className="text-button" onClick={() => update({})}>Back to the first page</button>}
              {page === 1 && filtered && (
                <button type="button" className="text-button" onClick={() => update({ service: null, severity: null })}>
                  Clear the filters
                </button>
              )}
              {page === 1 && !filtered && group === 'active' && (
                <button type="button" className="text-button" onClick={() => update({ status: 'resolved' })}>
                  See resolved alerts
                </button>
              )}
            </div>
          ) : (
            <>
              <table className="anomaly-table alert-table">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th>Service</th>
                    <th>Severity</th>
                    <th>Alert</th>
                    <th><span className="sr-only">Telegram</span></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((a) => (
                    <tr key={a.id}
                        className={[
                          a.id === selected ? 'selected' : '',
                          fresh.has(a.id) ? 'fresh' : '',
                          a.status === 'RESOLVED' ? 'resolved-row' : '',
                        ].join(' ')}
                        tabIndex={0}
                        aria-selected={a.id === selected}
                        onClick={() => update({ id: a.id }, true)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            update({ id: a.id }, true)
                          }
                        }}>
                      <td><StatusPill status={a.status} /></td>
                      <td className="nowrap">{a.service}</td>
                      <td><SeverityBadge severity={a.severity} /></td>
                      <td>
                        <span className="alert-title">{a.title}</span>
                        <span className="alert-meta number"
                              title={`First ${formatTime(a.first_seen_at)}, last ${formatTime(a.last_seen_at)}`}>
                          {a.occurrence_count} anomalous min · {longRange ? formatShortDateTime(a.first_seen_at) : formatClock(a.first_seen_at)}
                          –{formatClock(a.resolved_at ?? a.last_seen_at)}
                          {a.message ? ` · ${a.message}` : ''}
                        </span>
                      </td>
                      <td className="tg-cell">
                        {a.notification_sent && (
                          <span title="Sent to Telegram"><Send size={14} aria-label="Sent to Telegram" /></span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="pager">
                <span className="muted number">{first}–{last} of {total}</span>
                <div className="pager-buttons">
                  <button type="button" className="icon-button" aria-label="Previous page" disabled={page <= 1}
                          onClick={() => update({ page: page > 2 ? String(page - 1) : null }, true)}>
                    <ChevronLeft size={18} aria-hidden="true" />
                  </button>
                  <span className="number">Page {page} of {pages}</span>
                  <button type="button" className="icon-button" aria-label="Next page" disabled={page >= pages}
                          onClick={() => update({ page: String(page + 1) }, true)}>
                    <ChevronRight size={18} aria-hidden="true" />
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {selected && (
          <AlertDetail
            detail={detail.detail}
            loading={detail.loading}
            error={detail.error}
            onClose={() => update({ id: null }, true)}
            onChanged={changed}
          />
        )}
      </div>
    </section>
  )
}