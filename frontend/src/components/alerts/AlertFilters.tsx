// Filters of the Alerts page: status group (active / resolved / all, with counts), service and severity.
import { SEVERITY_COLOURS } from '../../lib/format'
import { SEVERITIES, type Severity } from '../../types/api'
import type { StatusGroup } from '../../hooks/useAlerts'

const GROUPS: { value: StatusGroup; label: string }[] = [
  { value: 'active', label: 'Active' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'all', label: 'All' },
]

const NAMES: Record<Severity, string> = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical' }

interface Props {
  services: string[]
  group: StatusGroup
  service: string
  severities: Severity[]
  counts: Record<StatusGroup, number> | null
  onGroup: (group: StatusGroup) => void
  onService: (service: string) => void
  onSeverities: (severities: Severity[]) => void
}

export function AlertFilters(props: Props) {
  const { services, group, service, severities, counts } = props

  const toggle = (s: Severity) => {
    const next = severities.includes(s) ? severities.filter((x) => x !== s) : [...severities, s]
    props.onSeverities(SEVERITIES.filter((x) => next.includes(x)))
  }

  const options = service && !services.includes(service) ? [service, ...services] : services

  return (
    <div className="filters">
      <div className="field">
        <span id="status-label">Status</span>
        <div className="range" role="radiogroup" aria-labelledby="status-label">
          {GROUPS.map((g) => (
            <button key={g.value} type="button" role="radio" aria-checked={group === g.value}
                    onClick={() => props.onGroup(g.value)}>
              {g.label}
              {counts && <span className="number group-count">{counts[g.value]}</span>}
            </button>
          ))}
        </div>
      </div>

      <label className="field">
        <span>Service</span>
        <select value={service} onChange={(e) => props.onService(e.target.value)}>
          <option value="">All services</option>
          {options.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </label>

      <div className="field">
        <span id="alert-severity-label">Severity</span>
        <div className="chips" role="group" aria-labelledby="alert-severity-label">
          {[...SEVERITIES].reverse().map((s) => (
            <button key={s} type="button" className="chip" aria-pressed={severities.includes(s)}
                    style={{ ['--dot' as string]: SEVERITY_COLOURS[s] }} onClick={() => toggle(s)}>
              {NAMES[s]}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}