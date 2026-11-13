import type { Severity } from '../types/api'
import { SEVERITY_COLOURS } from '../lib/format'

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className="badge" style={{ borderColor: SEVERITY_COLOURS[severity], color: SEVERITY_COLOURS[severity] }}>
      {severity}
    </span>
  )
}