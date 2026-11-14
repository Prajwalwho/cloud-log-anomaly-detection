// Logs: search the stored log lines (Elasticsearch) by text, service, level and request (trace ID), newest first.
// Filters live in the URL (?q=&service=&level=&trace=&from=&to=&page=), so the Anomalies page can link to "all logs
// of this minute" (?service=…&from=…&to=…). A trace ID opens the request's path through the services.
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, RefreshCw, X } from 'lucide-react'
import { LogFilters } from '../components/logs/LogFilters'
import { LogRow } from '../components/logs/LogRow'
import { TracePath } from '../components/logs/TracePath'
import '../components/anomalies/anomalies.css'
import '../components/logs/logs.css'
import { MAX_RESULTS, PAGE_SIZE, useLogSearch, useTrace } from '../hooks/useLogs'
import { useServiceNames } from '../hooks/useServiceNames'
import { formatClock, formatNumber, formatShortDateTime, formatTime } from '../lib/format'
import { rangeOption, useTimeRange } from '../lib/timeRange'
import type { LogEvent, LogLevel } from '../types/api'

const LEVELS: LogLevel[] = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']
const AROUND_MS = 60_000

function isLevel(value: string): value is LogLevel {
  return (LEVELS as string[]).includes(value)
}

function isTime(value: string | null): value is string {
  return value !== null && !Number.isNaN(Date.parse(value))
}

export function Logs() {
  const { range } = useTimeRange()
  const [params, setParams] = useSearchParams()
  const services = useServiceNames()
  const [refresh, setRefresh] = useState(0)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  const q = params.get('q') ?? ''
  const service = params.get('service') ?? ''
  const levels = (params.get('level') ?? '').split(',').filter(isLevel)
  const trace = params.get('trace') ?? ''
  const rawFrom = params.get('from')
  const rawTo = params.get('to')
  const fixedWindow = isTime(rawFrom) && isTime(rawTo) ? { from: rawFrom, to: rawTo } : null
  const page = Math.max(1, Number(params.get('page')) || 1)

  const search = useLogSearch({
    q, service, levels, trace, from: fixedWindow?.from ?? '', to: fixedWindow?.to ?? '', page, refresh,
  })
  const path = useTrace(trace)

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

  const toggle = (id: string) => setExpanded((current) => {
    const next = new Set(current)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })

  const followTrace = (id: string) => {
    update({ trace: id, q: null, level: null, service: null })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const around = (log: LogEvent) => {
    const t = Date.parse(log.timestamp)
    update({
      service: log.service, q: null, level: null, trace: null,
      from: new Date(t - AROUND_MS).toISOString(), to: new Date(t + AROUND_MS).toISOString(),
    })
  }

  const total = search.page?.total ?? 0
  const items = search.page?.items ?? []
  const reachable = Math.min(total, MAX_RESULTS)
  const pages = Math.max(1, Math.ceil(reachable / PAGE_SIZE))
  const first = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const last = Math.min(reachable, page * PAGE_SIZE)
  const showDay = fixedWindow ? new Date(fixedWindow.from).toDateString() !== new Date(fixedWindow.to).toDateString()
    : range === '24h' || range === '7d'
  const filtered = q !== '' || service !== '' || levels.length > 0 || trace !== ''

  return (
    <section>
      <div className="page-head">
        <div>
          <h1>Logs</h1>
          <p className="lead">
            Search what the services wrote. Open a line to see all its fields, or follow its request through the
            services.
          </p>
        </div>
      </div>

      <LogFilters
        key={q}
        services={services}
        q={q}
        service={service}
        levels={levels}
        onSearch={(value) => update({ q: value })}
        onService={(value) => update({ service: value })}
        onLevels={(value) => update({ level: value.join(',') })}
      />

      {(fixedWindow || trace) && (
        <div className="active-scope">
          {fixedWindow && (
            <span className="scope-chip">
              Time window {formatShortDateTime(fixedWindow.from)} – {formatClock(fixedWindow.to)}
              <small>(instead of the last {rangeOption(range).phrase})</small>
              <button type="button" aria-label="Remove the time window" onClick={() => update({ from: null, to: null })}>
                <X size={14} aria-hidden="true" />
              </button>
            </span>
          )}
          {trace && (
            <span className="scope-chip">
              Request <code>{trace}</code>
              <button type="button" aria-label="Stop following this request" onClick={() => update({ trace: null })}>
                <X size={14} aria-hidden="true" />
              </button>
            </span>
          )}
        </div>
      )}

      {trace && (
        <TracePath trace={trace} logs={path.logs} loading={path.loading} error={path.error}
                   onClose={() => update({ trace: null })} />
      )}

      {search.error && <p className="error-note">Could not search the logs: {search.error}</p>}

      <div className={`panel log-panel${search.loading ? ' is-loading' : ''}`}>
        <div className="log-toolbar">
          <span className="muted number">
            {search.page ? `${formatNumber(total)} lines` : 'Searching…'}
            {search.until && ` · as of ${formatTime(search.until)}`}
          </span>
          <button type="button" className="text-button refresh" onClick={() => setRefresh((n) => n + 1)}
                  disabled={fixedWindow !== null} title={fixedWindow ? 'A fixed time window does not change' : 'Load the newest lines'}>
            <RefreshCw size={14} aria-hidden="true" /> Refresh
          </button>
        </div>

        {search.page !== null && items.length === 0 ? (
          <div className="empty">
            <p>{page > 1 ? 'This page is empty.' : filtered || fixedWindow
              ? 'No log lines match.' : `No log lines in the last ${rangeOption(range).phrase}.`}</p>
            {(filtered || fixedWindow) && (
              <button type="button" className="text-button"
                      onClick={() => update({ q: null, service: null, level: null, trace: null, from: null, to: null })}>
                Clear everything
              </button>
            )}
          </div>
        ) : (
          <ol className="log-list">
            {items.map((log) => (
              <LogRow key={log.event_id} log={log} showDay={showDay} expanded={expanded.has(log.event_id)}
                      onToggle={() => toggle(log.event_id)} onTrace={followTrace} onAround={around} />
            ))}
          </ol>
        )}

        {total > 0 && (
          <div className="pager">
            <span className="muted number">
              {formatNumber(first)}–{formatNumber(last)} of {formatNumber(total)}
              {total > MAX_RESULTS && ' (the first 10,000 can be paged; narrow the search for older lines)'}
            </span>
            <div className="pager-buttons">
              <button type="button" className="icon-button" aria-label="Previous page" disabled={page <= 1}
                      onClick={() => update({ page: page > 2 ? String(page - 1) : null }, true)}>
                <ChevronLeft size={18} aria-hidden="true" />
              </button>
              <span className="number">Page {page} of {formatNumber(pages)}</span>
              <button type="button" className="icon-button" aria-label="Next page" disabled={page >= pages}
                      onClick={() => update({ page: String(page + 1) }, true)}>
                <ChevronRight size={18} aria-hidden="true" />
              </button>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}