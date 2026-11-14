// Filters of the Anomalies page: service, severity (several at once) and review state.
import { SEVERITY_COLOURS } from '../../lib/format'
import { SEVERITIES, type Severity } from '../../types/api'

const FEEDBACK_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'NONE', label: 'Not reviewed' },
  { value: 'CONFIRMED', label: 'Confirmed' },
  { value: 'FALSE_POSITIVE', label: 'False positive' },
]

const NAMES: Record<Severity, string> = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical' }

interface Props {
  services: string[]
  service: string
  severities: Severity[]
  feedback: string
  counts: Record<Severity, number> | null
  onService: (service: string) => void
  onSeverities: (severities: Severity[]) => void
  onFeedback: (feedback: string) => void
}

export function AnomalyFilters(props: Props) {
  const { services, service, severities, feedback, counts } = props

  const toggle = (s: Severity) => {
    const next = severities.includes(s) ? severities.filter((x) => x !== s) : [...severities, s]
    props.onSeverities(SEVERITIES.filter((x) => next.includes(x)))   // keep a fixed order in the URL
  }

  // a service from the URL that is not (yet) in the list still has to be selectable
  const options = service && !services.includes(service) ? [service, ...services] : services

  return (
    <div className="filters">
      <label className="field">
        <span>Service</span>
        <select value={service} onChange={(e) => props.onService(e.target.value)}>
          <option value="">All services</option>
          {options.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </label>

      <div className="field">
        <span id="severity-label">Severity</span>
        <div className="chips" role="group" aria-labelledby="severity-label">
          {[...SEVERITIES].reverse().map((s) => (
            <button key={s} type="button" className="chip" aria-pressed={severities.includes(s)}
                    style={{ ['--dot' as string]: SEVERITY_COLOURS[s] }} onClick={() => toggle(s)}>
              {NAMES[s]}
              <span className="number chip-count">{counts ? counts[s] : '·'}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="field">
        <span id="review-label">Review</span>
        <div className="range" role="radiogroup" aria-labelledby="review-label">
          {FEEDBACK_OPTIONS.map((o) => (
            <button key={o.value} type="button" role="radio" aria-checked={feedback === o.value}
                    onClick={() => props.onFeedback(o.value)}>
              {o.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
