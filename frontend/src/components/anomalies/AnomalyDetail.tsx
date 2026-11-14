// The detail panel: why a window was flagged, what its numbers were, the log lines behind it, and the
// operator's verdict (confirmed / false positive), which is stored for later evaluation and retraining.
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, X, ScrollText } from 'lucide-react'
import { api, errorMessage } from '../../services/api'
import {
  LEVEL_COLOURS, formatDateTime, formatLatency, formatNumber, formatPercent, formatTime,
} from '../../lib/format'
import { SeverityBadge } from '../SeverityBadge'
import { ScoreGauge } from './ScoreGauge'
import type { Anomaly, AnomalyDetail as Detail, Feedback } from '../../types/api'

interface Props {
  detail: Detail | null
  loading: boolean
  error: string | null
  onClose: () => void
  onChanged: (anomaly: Anomaly) => void
}

function Facts({ detail }: { detail: Detail }) {
  const s = detail.summary
  const facts: [string, string][] = [
    ['Log lines', formatNumber(s.log_count)],
    ['Error rate', formatPercent(s.error_rate)],
    ['Warning rate', formatPercent(s.warn_rate)],
    ['Average latency', formatLatency(s.avg_latency_ms)],
    ['p95 latency', formatLatency(s.p95_latency_ms)],
    ['New message types', formatNumber(s.new_templates)],
  ]
  return (
    <dl className="facts">
      {facts.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd className="number">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function FeedbackButtons({ detail, onChanged }: { detail: Detail; onChanged: (a: Anomaly) => void }) {
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const choose = (value: Feedback) => {
    const next = detail.feedback === value ? null : value     // pressing the active choice clears it
    setSaving(true)
    setError(null)
    api.setFeedback(detail.id, next)
      .then(onChanged)
      .catch((e: unknown) => setError(errorMessage(e)))
      .finally(() => setSaving(false))
  }

  return (
    <div className="verdict">
      <div className="verdict-buttons">
        <button type="button" className="verdict-confirm" aria-pressed={detail.feedback === 'CONFIRMED'}
                disabled={saving} onClick={() => choose('CONFIRMED')}>
          <Check size={15} aria-hidden="true" /> Real problem
        </button>
        <button type="button" className="verdict-false" aria-pressed={detail.feedback === 'FALSE_POSITIVE'}
                disabled={saving} onClick={() => choose('FALSE_POSITIVE')}>
          <X size={15} aria-hidden="true" /> False alarm
        </button>
      </div>
      <p className="hint">
        {detail.feedback === null
          ? 'Not reviewed yet. Your verdict is stored with the anomaly and used to measure the model.'
          : 'Saved. Press the same button again to clear it.'}
      </p>
      {error && <p className="error-note">Could not save: {error}</p>}
    </div>
  )
}

function SampleLogs({ detail }: { detail: Detail }) {
  const logsLink = `/logs?service=${encodeURIComponent(detail.service)}`
    + `&from=${encodeURIComponent(detail.window_start)}&to=${encodeURIComponent(detail.window_end)}`
  return (
    <section className="detail-section">
      <div className="section-head">
        <h3>Log lines from this window</h3>
        <Link to={logsLink} className="text-link"><ScrollText size={14} aria-hidden="true" /> All logs of this minute</Link>
      </div>
      {detail.sample_logs_error && (
        <p className="muted">The log lines could not be loaded: {detail.sample_logs_error}</p>
      )}
      {!detail.sample_logs_error && detail.sample_logs.length === 0 && (
        <p className="muted">
          {detail.sample_event_ids.length === 0
            ? 'No log lines were sampled for this window (the service sent no logs).'
            : 'These log lines are no longer stored in Elasticsearch.'}
        </p>
      )}
      <ol className="samples">
        {detail.sample_logs.map((log) => (
          <li key={log.event_id}>
            <div className="sample-meta">
              <span className="number">{formatTime(log.timestamp)}</span>
              <span className="level" style={{ color: LEVEL_COLOURS[log.level] }}>{log.level}</span>
              {log.endpoint && <span>{log.endpoint}</span>}
              {log.status_code != null && <span className="number">{log.status_code}</span>}
              {log.latency_ms != null && <span className="number">{formatLatency(log.latency_ms)}</span>}
            </div>
            <code className="sample-message">{log.message}</code>
            {log.trace_id && <div className="sample-trace">trace {log.trace_id}</div>}
          </li>
        ))}
      </ol>
    </section>
  )
}

export function AnomalyDetail({ detail, loading, error, onClose, onChanged }: Props) {
  if (!detail) {
    return (
      <aside className="panel detail detail-empty" aria-live="polite">
        {error ? <p className="error-note">Could not load this anomaly: {error}</p>
          : loading ? <p className="muted">Loading the anomaly…</p>
            : (
              <>
                <h2>Pick an anomaly</h2>
                <p className="muted">Select a row to see why that minute was flagged, the log lines behind it, and
                  to mark it as a real problem or a false alarm.</p>
              </>
            )}
      </aside>
    )
  }

  const s = detail.summary
  const reasons = s.reasons ?? []
  return (
    <aside className="panel detail" aria-label="Anomaly detail">
      <div className="detail-head">
        <div>
          <SeverityBadge severity={detail.severity} />
          <h2>{detail.service}</h2>
          <p className="muted number">
            Window {formatTime(detail.window_start)}–{formatTime(detail.window_end)} · detected {formatDateTime(detail.detected_at)}
          </p>
        </div>
        <button type="button" className="icon-button" aria-label="Close detail" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      <ScoreGauge score={detail.anomaly_score} raw={s.raw_score} threshold={s.threshold} />

      <section className="detail-section">
        <h3>Why it was flagged</h3>
        {reasons.length > 0 ? (
          <ul className="reasons">{reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        ) : (
          <p className="muted">The overall pattern of this minute was unusual for the model, but no single rule
            (errors, volume, latency, new messages) stood out.</p>
        )}
        {s.rule === 'no_logs' && (
          <p className="muted">Flagged by the no-logs rule: the service went silent while other services still had
            traffic.</p>
        )}
      </section>

      <section className="detail-section">
        <h3>This minute in numbers</h3>
        <Facts detail={detail} />
      </section>

      <section className="detail-section">
        <h3>Your verdict</h3>
        <FeedbackButtons detail={detail} onChanged={onChanged} />
      </section>

      <section className="detail-section detail-context">
        <div>
          <span className="muted">Alert</span>
          {detail.alert_id
            ? <Link to={`/alerts?id=${detail.alert_id}`} className="text-link">Open the alert</Link>
            : <span>{detail.severity === 'LOW' ? 'None (low anomalies do not open alerts)' : 'Not grouped yet'}</span>}
        </div>
        <div>
          <span className="muted">Model</span>
          <span>{detail.model.name} v{detail.model.version}</span>
        </div>
      </section>

      <SampleLogs detail={detail} />
    </aside>
  )
}
