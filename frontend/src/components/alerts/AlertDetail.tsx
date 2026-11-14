// The alert panel: what is wrong, its story (opened, escalated, acknowledged, resolved), acknowledge / resolve
// actions, whether Telegram was notified, and the anomalies grouped into it.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BellOff, CheckCheck, Eye, Send, X } from 'lucide-react'
import { api, errorMessage } from '../../services/api'
import { alertEvents } from '../../lib/alertEvents'
import {
  SEVERITY_COLOURS, STATUS_COLOURS, formatClock, formatDateTime, formatDuration, formatTime,
} from '../../lib/format'
import { useNow } from '../../hooks/useNow'
import { SeverityBadge } from '../SeverityBadge'
import { AlertTimeline } from './AlertTimeline'
import { StatusPill } from './StatusPill'
import type { Alert, AlertDetail as Detail, AlertStatus } from '../../types/api'

const NAME_KEY = 'observatory.operator'

function savedName(): string {
  try {
    return window.localStorage.getItem(NAME_KEY) ?? ''
  } catch {
    return ''
  }
}

function saveName(name: string) {
  try {
    window.localStorage.setItem(NAME_KEY, name)
  } catch {
    // storage blocked (private window): the name is just not remembered
  }
}

interface Props {
  detail: Detail | null
  loading: boolean
  error: string | null
  onClose: () => void
  onChanged: (alert: Alert) => void
}

function Actions({ detail, onChanged }: { detail: Detail; onChanged: (a: Alert) => void }) {
  const [name, setName] = useState(savedName)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (detail.status === 'RESOLVED') return null

  const change = (status: AlertStatus) => {
    setSaving(true)
    setError(null)
    api.updateAlert(detail.id, status, name.trim() || undefined)
      .then(onChanged)
      .catch((e: unknown) => setError(errorMessage(e)))
      .finally(() => setSaving(false))
  }

  return (
    <section className="detail-section">
      <h3>Respond</h3>
      {detail.status === 'OPEN' && (
        <label className="field operator">
          <span>Your name (saved in this browser)</span>
          <input value={name} maxLength={100} placeholder="e.g. prajwal"
                 onChange={(e) => {
                   setName(e.target.value)
                   saveName(e.target.value)
                 }} />
        </label>
      )}
      <div className="verdict-buttons">
        {detail.status === 'OPEN' && (
          <button type="button" className="action-ack" disabled={saving} onClick={() => change('ACKNOWLEDGED')}>
            <Eye size={15} aria-hidden="true" /> Acknowledge
          </button>
        )}
        <button type="button" className="action-resolve" disabled={saving} onClick={() => change('RESOLVED')}>
          <CheckCheck size={15} aria-hidden="true" /> Resolve
        </button>
      </div>
      <p className="hint">
        {detail.status === 'OPEN'
          ? 'Acknowledge to show the team someone is on it. Alerts also resolve by themselves after 5 minutes without new anomalies.'
          : 'Resolve once the problem is fixed. New anomalies after that open a new alert.'}
      </p>
      {error && <p className="error-note">Could not update the alert: {error}</p>}
    </section>
  )
}

function Telegram({ detail }: { detail: Detail }) {
  if (detail.notification_sent) {
    return <span className="tg tg-sent"><Send size={14} aria-hidden="true" /> Sent to Telegram</span>
  }
  if (detail.severity === 'HIGH' || detail.severity === 'CRITICAL') {
    return <span className="tg"><BellOff size={14} aria-hidden="true" /> Not sent (check the Telegram settings)</span>
  }
  return <span className="tg"><BellOff size={14} aria-hidden="true" /> Not needed (only high and critical)</span>
}

export function AlertDetail({ detail, loading, error, onClose, onChanged }: Props) {
  const now = useNow()

  if (!detail) {
    return (
      <aside className="panel detail detail-empty" aria-live="polite">
        {error ? <p className="error-note">Could not load this alert: {error}</p>
          : <p className="muted">{loading ? 'Loading the alert…' : 'Nothing to show.'}</p>}
      </aside>
    )
  }

  const end = detail.resolved_at ? Date.parse(detail.resolved_at) : now
  const duration = end === null ? null : end - Date.parse(detail.first_seen_at)
  const events = alertEvents(detail)

  return (
    <aside className="panel detail" aria-label="Alert detail">
      <div className="detail-head">
        <div>
          <div className="head-badges">
            <SeverityBadge severity={detail.severity} />
            <StatusPill status={detail.status} />
          </div>
          <h2>{detail.title}</h2>
          <p className="muted">{detail.service}{detail.message ? ` · ${detail.message}` : ''}</p>
        </div>
        <button type="button" className="icon-button" aria-label="Close detail" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      <section className="detail-section">
        <AlertTimeline alert={detail} now={now} />
        <dl className="facts">
          <div>
            <dt>{detail.resolved_at ? 'Lasted' : 'Open for'}</dt>
            <dd className="number">{formatDuration(duration)}</dd>
          </div>
          <div>
            <dt>Anomalous minutes</dt>
            <dd className="number">{detail.occurrence_count}</dd>
          </div>
          <div>
            <dt>Last anomaly</dt>
            <dd className="number">{formatClock(detail.last_seen_at)}</dd>
          </div>
        </dl>
      </section>

      <Actions detail={detail} onChanged={onChanged} />

      <section className="detail-section">
        <h3>What happened</h3>
        <ol className="events">
          {events.map((e) => (
            <li key={`${e.kind}-${e.at}`}
                style={{ ['--dot' as string]: e.severity ? SEVERITY_COLOURS[e.severity]
                  : e.kind === 'acknowledged' ? STATUS_COLOURS.ACKNOWLEDGED : STATUS_COLOURS.RESOLVED }}>
              <span className="number event-time" title={formatDateTime(e.at)}>{formatTime(e.at)}</span>
              <span>{e.text}</span>
            </li>
          ))}
        </ol>
        <p className="tg-line"><Telegram detail={detail} /></p>
      </section>

      <section className="detail-section">
        <h3>Anomalies in this alert ({detail.anomalies.length})</h3>
        {detail.anomalies.length === 0 ? (
          <p className="muted">No anomalies are linked to this alert.</p>
        ) : (
          <ul className="alert-anomalies">
            {detail.anomalies.map((a) => (
              <li key={a.id}>
                <Link to={`/anomalies?service=${encodeURIComponent(a.service)}&id=${a.id}`}>
                  <span className="number">{formatClock(a.window_start)}</span>
                  <SeverityBadge severity={a.severity} />
                  <span className="muted">{(a.summary.reasons ?? []).join('; ') || 'unusual pattern'}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  )
}