import { STATUS_COLOURS, STATUS_NAMES } from '../../lib/format'
import type { AlertStatus } from '../../types/api'

/** Alert status with a coloured dot; an open alert's dot breathes. */
export function StatusPill({ status }: { status: AlertStatus }) {
  return (
    <span className={`status-pill status-${status.toLowerCase()}`} style={{ ['--dot' as string]: STATUS_COLOURS[status] }}>
      {STATUS_NAMES[status]}
    </span>
  )
}