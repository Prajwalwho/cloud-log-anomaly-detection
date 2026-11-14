// The path of one request through the services: every line with the same trace_id, oldest first, with the time
// since the request started. Shows where a request slowed down or failed (gateway -> order -> payment ...).
import { X } from 'lucide-react'
import { LEVEL_COLOURS, formatLatency } from '../../lib/format'
import { formatLogTime, formatOffset } from '../../lib/logFormat'
import { serviceColour } from '../charts/theme'
import type { LogEvent } from '../../types/api'

interface Props {
  trace: string
  logs: LogEvent[]
  loading: boolean
  error: string | null
  onClose: () => void
}

export function TracePath({ trace, logs, loading, error, onClose }: Props) {
  const start = logs.length ? Date.parse(logs[0].timestamp) : 0
  const end = logs.length ? Date.parse(logs[logs.length - 1].timestamp) : 0
  const services = [...new Set(logs.map((l) => l.service))]
  const failed = logs.some((l) => l.level === 'ERROR' || l.level === 'FATAL')

  return (
    <section className="panel trace-panel" aria-label={`Request ${trace}`}>
      <div className="section-head">
        <div>
          <h2>Request path</h2>
          <p className="muted trace-summary">
            Trace <code>{trace}</code>
            {logs.length > 0 && (
              <> · {logs.length} lines · {services.length} {services.length === 1 ? 'service' : 'services'}
                {' '}· {formatOffset(end - start).slice(1)} from first to last line
                {' '}· <span className={failed ? 'trace-failed' : 'trace-ok'}>{failed ? 'failed' : 'succeeded'}</span></>
            )}
          </p>
        </div>
        <button type="button" className="icon-button" aria-label="Close request path" onClick={onClose}>
          <X size={18} aria-hidden="true" />
        </button>
      </div>

      {error && <p className="error-note">Could not load this request: {error}</p>}
      {loading && <p className="muted">Loading the request…</p>}
      {!loading && !error && logs.length === 0 && (
        <p className="muted">No lines with this trace ID in the last 7 days.</p>
      )}

      <ol className="trace-steps">
        {logs.map((log) => (
          <li key={log.event_id} style={{ ['--svc' as string]: serviceColour(log.service) }}>
            <span className="trace-offset number" title={formatLogTime(log.timestamp)}>
              {formatOffset(Date.parse(log.timestamp) - start)}
            </span>
            <span className="trace-node" aria-hidden="true" />
            <div className="trace-body">
              <div className="trace-head">
                <span className="trace-service">{log.service}</span>
                <span className="log-level" style={{ color: LEVEL_COLOURS[log.level] }}>{log.level}</span>
                {log.endpoint && <span className="muted">{log.endpoint}</span>}
                {log.status_code != null && <span className="number muted">{log.status_code}</span>}
                {log.latency_ms != null && <span className="number muted">{formatLatency(log.latency_ms)}</span>}
              </div>
              <code className="trace-message">{log.message}</code>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}