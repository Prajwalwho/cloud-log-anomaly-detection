// The severity spectrum of anomalies in the range: one bar, segment width = share of anomalies.
import { SEVERITY_COLOURS } from '../lib/format'
import { SEVERITIES, type Severity } from '../types/api'

const NAMES: Record<Severity, string> = { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High', CRITICAL: 'Critical' }

export function SeverityBar({ counts }: { counts: Record<Severity, number> }) {
  const total = SEVERITIES.reduce((sum, s) => sum + (counts[s] ?? 0), 0)
  const order = [...SEVERITIES].reverse()        // critical first
  return (
    <div className="spectrum">
      <div className="spectrum-bar" role="img"
           aria-label={order.map((s) => `${NAMES[s]} ${counts[s] ?? 0}`).join(', ')}>
        {total > 0 && order.map((s) => (
          <span key={s} style={{ width: `${(100 * (counts[s] ?? 0)) / total}%`, background: SEVERITY_COLOURS[s] }} />
        ))}
      </div>
      <div className="spectrum-legend">
        {order.map((s) => (
          <span key={s} className="number" style={{ ['--dot' as string]: SEVERITY_COLOURS[s] }}>
            {NAMES[s]} {counts[s] ?? 0}
          </span>
        ))}
      </div>
    </div>
  )
}