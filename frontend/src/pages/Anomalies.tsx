// Anomalies: every flagged minute in the chosen time range, filterable, with a detail panel.
// Filters, page and selection live in the URL (?service=&severity=&feedback=&page=&id=), so a view can be
// bookmarked and the Overview constellation can link straight to one service.
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { AnomalyDetail } from '../components/anomalies/AnomalyDetail'
import { AnomalyFilters } from '../components/anomalies/AnomalyFilters'
import { ScoreMeter } from '../components/anomalies/ScoreGauge'
import '../components/anomalies/anomalies.css'
import { SeverityBadge } from '../components/SeverityBadge'
import { SeverityBar } from '../components/SeverityBar'
import { PAGE_SIZE, useAnomalies, useAnomalyDetail } from '../hooks/useAnomalies'
import { useServiceNames } from '../hooks/useServiceNames'
import { useLiveEvents } from '../live/context'
import { formatClock, formatShortDateTime, formatTime, formatWindow } from '../lib/format'
import { rangeOption, useTimeRange } from '../lib/timeRange'
import { SEVERITIES, type Anomaly, type Feedback, type Severity } from '../types/api'

const FRESH_MS = 8_000
const FEEDBACK_LABEL: Record<Feedback, string> = { CONFIRMED: 'Real problem', FALSE_POSITIVE: 'False alarm' }

function isSeverity(value: string): value is Severity {
  return (SEVERITIES as string[]).includes(value)
}

function whatHappened(anomaly: Anomaly): string {
  const reasons = anomaly.summary.reasons ?? []
  if (reasons.length) return reasons.join('; ')
  return anomaly.summary.rule === 'no_logs' ? 'no logs' : 'unusual pattern'
}

export function Anomalies() {
  const { range } = useTimeRange()
  const [params, setParams] = useSearchParams()
  const services = useServiceNames()
  const [fresh, setFresh] = useState<Set<string>>(new Set())

  const service = params.get('service') ?? ''
  const severities = (params.get('severity') ?? '').split(',').filter(isSeverity)
  const feedback = params.get('feedback') ?? ''
  const page = Math.max(1, Number(params.get('page')) || 1)
  const selected = params.get('id')

  const list = useAnomalies({ service, severities, feedback, page })
  const detail = useAnomalyDetail(selected)

  // New anomalies glow briefly when the list reloads with them (the reload itself comes from useReloadKey).
  useLiveEvents((event) => {
    if (event.type !== 'anomaly.created') return
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

  const changed = (anomaly: Anomaly) => {
    list.replace(anomaly)
    detail.replace(anomaly)
  }

  const total = list.page?.total ?? 0
  const items = list.page?.items ?? []
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const first = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const last = Math.min(total, page * PAGE_SIZE)
  const longRange = range === '24h' || range === '7d'
  const filtered = service !== '' || severities.length > 0 || feedback !== ''

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Anomalies</h1>
          <p className="lead">
            Every minute in the last {rangeOption(range).phrase} that the model found unusual
            {service ? <> for <strong>{service}</strong></> : ''}. Select one to see why.
          </p>
        </div>
        {list.counts && (
          <div className="head-spectrum">
            <SeverityBar counts={list.counts} />
          </div>
        )}
      </div>

      <AnomalyFilters
        services={services}
        service={service}
        severities={severities}
        feedback={feedback}
        counts={list.counts}
        onService={(value) => update({ service: value })}
        onSeverities={(value) => update({ severity: value.join(',') })}
        onFeedback={(value) => update({ feedback: value })}
      />

      {list.error && <p className="error-note">Could not load anomalies: {list.error}</p>}

      <div className={`anomaly-layout${selected ? ' has-detail' : ''}`}>
        <div className={`panel anomaly-list${list.loading ? ' is-loading' : ''}`}>
          {list.page === null ? (
            <p className="muted">{list.error ? 'Nothing to show.' : 'Loading anomalies…'}</p>
          ) : items.length === 0 ? (
            <div className="empty">
              <p>{page > 1 ? 'This page is empty.' : filtered
                ? 'No anomalies match these filters.'
                : `No anomalies in the last ${rangeOption(range).phrase}. All quiet.`}</p>
              {page > 1 && <button type="button" className="text-button" onClick={() => update({})}>Back to the first page</button>}
              {page === 1 && filtered && (
                <button type="button" className="text-button"
                        onClick={() => update({ service: null, severity: null, feedback: null })}>
                  Clear the filters
                </button>
              )}
            </div>
          ) : (
            <>
              <table className="anomaly-table">
                <thead>
                  <tr>
                    <th>Minute</th>
                    <th>Service</th>
                    <th>Severity</th>
                    <th>Score</th>
                    <th>What happened</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((a) => (
                    <tr key={a.id}
                        className={[a.id === selected ? 'selected' : '', fresh.has(a.id) ? 'fresh' : ''].join(' ')}
                        tabIndex={0}
                        aria-selected={a.id === selected}
                        onClick={() => update({ id: a.id }, true)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            update({ id: a.id }, true)
                          }
                        }}>
                      <td className="number nowrap"
                          title={`Window ${formatWindow(a.window_start, a.window_end)}, detected ${formatTime(a.detected_at)}`}>
                        {longRange ? formatShortDateTime(a.window_start) : formatClock(a.window_start)}
                      </td>
                      <td className="nowrap">{a.service}</td>
                      <td><SeverityBadge severity={a.severity} /></td>
                      <td><ScoreMeter score={a.anomaly_score} /></td>
                      <td className="reason-cell">
                        {whatHappened(a)}
                        {a.feedback && (
                          <span className={`review review-${a.feedback.toLowerCase()}`}>{FEEDBACK_LABEL[a.feedback]}</span>
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
          <AnomalyDetail
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