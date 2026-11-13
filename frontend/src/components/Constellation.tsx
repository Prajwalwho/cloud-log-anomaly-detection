// The services as a constellation: size = log volume, colour = health, halo = open alert, lines = who calls whom,
// a flare = a new anomaly arriving live. Click (or Enter) opens that service's anomalies.
import { useNavigate } from 'react-router-dom'
import type { Alert, Severity } from '../types/api'
import { formatCompact, formatPercent } from '../lib/format'

const WIDTH = 640
const HEIGHT = 420
const CENTRE = { x: 320, y: 195 }

// Layout of the simulated environment (contracts.md §3). Services not listed here are placed on a ring,
// because detection must not assume a fixed set of services.
const KNOWN_POSITIONS: Record<string, { x: number; y: number }> = {
  'api-gateway': { x: 320, y: 195 },
  'auth-service': { x: 140, y: 85 },
  'order-service': { x: 500, y: 90 },
  'payment-service': { x: 505, y: 300 },
  'inventory-service': { x: 150, y: 295 },
}
// The gateway calls every downstream service (generator request flows).
const KNOWN_LINKS: [string, string][] = [
  ['api-gateway', 'auth-service'],
  ['api-gateway', 'order-service'],
  ['api-gateway', 'payment-service'],
  ['api-gateway', 'inventory-service'],
]

type StarState = 'calm' | 'strained' | Severity
const STATE_COLOUR: Record<StarState, string> = {
  calm: 'var(--healthy)',
  strained: 'var(--sev-medium)',
  LOW: 'var(--sev-low)',
  MEDIUM: 'var(--sev-medium)',
  HIGH: 'var(--sev-high)',
  CRITICAL: 'var(--sev-critical)',
}
const STATES = Object.keys(STATE_COLOUR) as StarState[]

export interface Star {
  service: string
  logs: number
  errorRate: number | null
  alert: Alert | null
  flare?: number          // timestamp of the latest live anomaly; changes restart the animation
}

function stateOf(star: Star): StarState {
  if (star.alert) return star.alert.severity
  return (star.errorRate ?? 0) >= 0.05 ? 'strained' : 'calm'
}

function ringPosition(index: number, count: number) {
  const angle = -Math.PI / 2 + (index * 2 * Math.PI) / Math.max(count, 1)
  return { x: CENTRE.x + 255 * Math.cos(angle), y: CENTRE.y + 150 * Math.sin(angle) }
}

export function Constellation({ stars }: { stars: Star[] }) {
  const navigate = useNavigate()
  const maxLogs = Math.max(1, ...stars.map((s) => s.logs))
  const unknown = stars.filter((s) => !(s.service in KNOWN_POSITIONS)).map((s) => s.service)
  const position = (service: string) =>
    KNOWN_POSITIONS[service] ?? ringPosition(unknown.indexOf(service), unknown.length)
  const byService = Object.fromEntries(stars.map((s) => [s.service, s]))
  const open = (service: string) => navigate(`/anomalies?service=${encodeURIComponent(service)}`)

  return (
    <svg className="constellation" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img"
         aria-label="Services drawn as a constellation: size shows log volume, colour shows health">
      <defs>
        {STATES.map((state) => (
          <radialGradient key={state} id={`halo-${state}`}>
            <stop offset="0%" style={{ stopColor: STATE_COLOUR[state], stopOpacity: 0.42 }} />
            <stop offset="100%" style={{ stopColor: STATE_COLOUR[state], stopOpacity: 0 }} />
          </radialGradient>
        ))}
      </defs>

      {KNOWN_LINKS.filter(([a, b]) => byService[a] && byService[b]).map(([a, b]) => {
        const from = position(a)
        const to = position(b)
        return <line key={`${a}-${b}`} className="link" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
      })}

      {stars.map((star) => {
        const { x, y } = position(star.service)
        const radius = 5 + 13 * Math.sqrt(star.logs / maxLogs)
        const state = stateOf(star)
        const quiet = star.logs === 0
        const meta = quiet
          ? 'no logs in this range'
          : `${formatCompact(star.logs)} logs, ${formatPercent(star.errorRate)} errors`
        return (
          <g
            key={star.service}
            className={`star${quiet ? ' star-quiet' : ''}`}
            transform={`translate(${x} ${y})`}
            role="link"
            tabIndex={0}
            aria-label={`${star.service}: ${meta}${star.alert ? `, open alert: ${star.alert.title}` : ''}`}
            onClick={() => open(star.service)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') open(star.service)
            }}
          >
            <title>{`${star.service}\n${meta}${star.alert ? `\n${star.alert.severity}: ${star.alert.title}` : ''}`}</title>
            <circle r={radius * 3.2} fill={`url(#halo-${state})`} />
            {star.flare !== undefined && (
              <circle key={star.flare} className="flare" r={radius} style={{ stroke: STATE_COLOUR[state] }} />
            )}
            <circle className="star-core" r={radius}
                    style={{ fill: state === 'calm' ? 'var(--starlight)' : STATE_COLOUR[state] }} />
            <text className="star-name" y={radius + 20}>{star.service}</text>
            <text className="star-meta" y={radius + 36}>{meta}</text>
            {star.alert && (
              <text className="star-alert" y={radius + 52} style={{ fill: STATE_COLOUR[state] }}>
                {star.alert.title}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}