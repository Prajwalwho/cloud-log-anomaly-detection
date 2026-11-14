// One log line. Collapsed: time, level, service, message and the request fields. Expanded: every field of the
// event, its metadata, and ways to follow it (the whole request, or this service around this moment).
import { useState } from 'react'
import { ChevronDown, ChevronRight, Copy, Route, Timer } from 'lucide-react'
import { LEVEL_COLOURS, formatDateTime, formatLatency } from '../../lib/format'
import { formatLogDay, formatLogTime } from '../../lib/logFormat'
import { serviceColour } from '../charts/theme'
import type { LogEvent } from '../../types/api'

interface Props {
  log: LogEvent
  showDay: boolean
  expanded: boolean
  onToggle: () => void
  onTrace: (trace: string) => void
  onAround: (log: LogEvent) => void
}

export function LogRow({ log, showDay, expanded, onToggle, onTrace, onAround }: Props) {
  const [copied, setCopied] = useState(false)

  const copyId = () => {
    navigator.clipboard?.writeText(log.event_id)
      .then(() => {
        setCopied(true)
        window.setTimeout(() => setCopied(false), 1500)
      })
      .catch(() => {
        // clipboard not allowed (e.g. plain http on another host): the id is visible to copy by hand
      })
  }

  const metadata = log.metadata && Object.keys(log.metadata).length > 0 ? log.metadata : null

  return (
    <li className={`log-row level-${log.level.toLowerCase()}${expanded ? ' expanded' : ''}`}
        style={{ ['--level' as string]: LEVEL_COLOURS[log.level] }}>
      <button type="button" className="log-line" aria-expanded={expanded} onClick={onToggle}>
        {expanded ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
        <span className="log-time number" title={formatDateTime(log.timestamp)}>
          {showDay && <span className="log-day">{formatLogDay(log.timestamp)} </span>}
          {formatLogTime(log.timestamp)}
        </span>
        <span className="log-level">{log.level}</span>
        <span className="log-service" style={{ ['--svc' as string]: serviceColour(log.service) }}>{log.service}</span>
        <span className="log-message">{log.message}</span>
        <span className="log-request number">
          {log.endpoint && <span>{log.endpoint}</span>}
          {log.status_code != null && (
            <span className={log.status_code >= 500 ? 'code-5xx' : log.status_code >= 400 ? 'code-4xx' : ''}>
              {log.status_code}
            </span>
          )}
          {log.latency_ms != null && <span>{formatLatency(log.latency_ms)}</span>}
        </span>
      </button>

      {expanded && (
        <div className="log-detail">
          <dl>
            <div><dt>Time</dt><dd className="number">{formatDateTime(log.timestamp)} ({log.timestamp})</dd></div>
            <div><dt>Service · host</dt><dd>{log.service} · {log.host}</dd></div>
            <div><dt>Message</dt><dd><code>{log.message}</code></dd></div>
            {log.endpoint && <div><dt>Endpoint</dt><dd>{log.endpoint}</dd></div>}
            {log.status_code != null && <div><dt>Status</dt><dd className="number">{log.status_code}</dd></div>}
            {log.latency_ms != null && <div><dt>Latency</dt><dd className="number">{formatLatency(log.latency_ms)}</dd></div>}
            {log.trace_id && <div><dt>Trace ID</dt><dd><code>{log.trace_id}</code></dd></div>}
            <div><dt>Event ID</dt><dd><code>{log.event_id}</code></dd></div>
            {metadata && <div><dt>Metadata</dt><dd><pre>{JSON.stringify(metadata, null, 2)}</pre></dd></div>}
          </dl>
          <div className="log-actions">
            {log.trace_id && (
              <button type="button" onClick={() => onTrace(log.trace_id as string)}>
                <Route size={14} aria-hidden="true" /> Follow this request
              </button>
            )}
            <button type="button" onClick={() => onAround(log)}>
              <Timer size={14} aria-hidden="true" /> {log.service} around this moment
            </button>
            <button type="button" onClick={copyId}>
              <Copy size={14} aria-hidden="true" /> {copied ? 'Copied' : 'Copy event ID'}
            </button>
          </div>
        </div>
      )}
    </li>
  )
}