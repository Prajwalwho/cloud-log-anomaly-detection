// The services as a small galaxy. The API gateway, which receives every request, sits at the centre on a slowly
// turning spiral; the other services orbit it on tilted ellipses (inner orbits faster). Small dots travel from the
// centre to each service: requests flowing, more of them for services that log more, in the service's colour.
// Size = log volume, colour = health, halo = open alert, a flare = a new anomaly arriving live.
// Hovering or focusing a service pauses the motion, so it is easy to click; a click opens its anomalies.
// With "reduce motion" set in the operating system, everything stands still.
import { useEffect, useMemo, useRef, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Alert, Severity } from '../types/api'
import { formatCompact, formatPercent } from '../lib/format'
import { orderServices } from './charts/theme'

const WIDTH = 640
const HEIGHT = 420
const C = { x: 320, y: 200 }
const TILT = -0.2                      // radians: the plane of the orbits is tipped like a ring seen at an angle
const SQUASH = 0.4                     // ry / rx of every orbit
const CORE_SERVICE = 'api-gateway'
const PACKETS = 3

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

interface Orbit {
  service: string
  rx: number
  ry: number
  period: number          // seconds per revolution
  phase: number           // starting angle
}

function stateOf(star: Star): StarState {
  if (star.alert) return star.alert.severity
  return (star.errorRate ?? 0) >= 0.05 ? 'strained' : 'calm'
}

function buildOrbits(services: string[]): Orbit[] {
  const n = services.length
  return services.map((service, i) => {
    const rx = n === 1 ? 210 : 158 + (i * 130) / (n - 1)
    return { service, rx, ry: rx * SQUASH, period: 70 + i * 24, phase: 0.6 + (i * 2 * Math.PI) / Math.max(n, 1) }
  })
}

/** A point on a tilted orbit; depth is +1 at the front (bottom) and -1 at the back. */
function orbitPoint(orbit: Orbit, angle: number) {
  const ex = orbit.rx * Math.cos(angle)
  const ey = orbit.ry * Math.sin(angle)
  return {
    x: C.x + ex * Math.cos(TILT) - ey * Math.sin(TILT),
    y: C.y + ex * Math.sin(TILT) + ey * Math.cos(TILT),
    depth: Math.sin(angle),
  }
}

const planetTransform = (p: { x: number; y: number; depth: number }) =>
  `translate(${p.x.toFixed(1)} ${p.y.toFixed(1)}) scale(${(0.9 + 0.1 * p.depth).toFixed(3)})`

// Two spiral arms of faint stars (fixed pseudo-random scatter, so the picture is the same on every load).
const ARM_STARS = (() => {
  const stars: { x: number; y: number; r: number; o: number }[] = []
  let seed = 7
  const rand = () => {
    seed = (seed * 16807) % 2147483647
    return seed / 2147483647
  }
  for (let arm = 0; arm < 2; arm += 1) {
    for (let k = 0; k < 70; k += 1) {
      const t = k / 70
      const theta = arm * Math.PI + t * 3.4 * Math.PI
      const radius = 14 + 230 * t ** 1.15
      const spread = 6 + 22 * t
      stars.push({
        x: C.x + radius * Math.cos(theta) + (rand() - 0.5) * spread,
        y: C.y + radius * Math.sin(theta) + (rand() - 0.5) * spread,
        r: 0.9 + rand() * 1.6 * (1 - t * 0.5),
        o: 0.3 + rand() * 0.6 * (1 - t * 0.6),
      })
    }
  }
  return stars
})()

function Galaxy() {
  const tiltDeg = (TILT * 180) / Math.PI
  return (
    <g className="galaxy" aria-hidden="true"
       transform={`translate(${C.x} ${C.y}) rotate(${tiltDeg}) scale(1 ${SQUASH}) translate(${-C.x} ${-C.y})`}>
      <g className="galaxy-spin" style={{ transformOrigin: `${C.x}px ${C.y}px` }}>
        <circle cx={C.x} cy={C.y} r={250} fill="url(#galaxy-disc)" />
        {ARM_STARS.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} className="arm-star" style={{ opacity: s.o }} />
        ))}
      </g>
    </g>
  )
}

export function Constellation({ stars }: { stars: Star[] }) {
  const navigate = useNavigate()
  const planets = useRef(new Map<string, SVGGElement>())
  const links = useRef(new Map<string, SVGLineElement>())
  const packets = useRef(new Map<string, SVGCircleElement[]>())
  const paused = useRef(false)

  const byService = Object.fromEntries(stars.map((s) => [s.service, s]))
  const core = byService[CORE_SERVICE] ?? null
  const orbitKey = orderServices(stars.map((s) => s.service).filter((s) => s !== CORE_SERVICE)).join(',')
  const orbits = useMemo(() => buildOrbits(orbitKey ? orbitKey.split(',') : []), [orbitKey])

  const maxLogs = Math.max(1, ...stars.map((s) => s.logs))
  const totalLogs = Math.max(1, stars.reduce((sum, s) => sum + s.logs, 0))
  // Packet speed per service (round trips per second), from its share of the traffic; kept in a ref for the loop.
  const rates = useRef(new Map<string, number>())
  useEffect(() => {
    rates.current = new Map(stars.map((s) => [s.service, s.logs === 0 ? 0 : 0.18 + 0.5 * (s.logs / totalLogs)]))
  }, [stars, totalLogs])

  // The animation loop moves the planets, links and packets directly in the DOM (no React re-render per frame).
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let frame = 0
    let last = performance.now()
    let time = 0
    const tick = (now: number) => {
      const dt = Math.min(now - last, 100) / 1000          // a hidden tab must not make planets jump
      last = now
      if (!paused.current) time += dt
      for (const orbit of orbits) {
        const p = orbitPoint(orbit, orbit.phase + (time * 2 * Math.PI) / orbit.period)
        planets.current.get(orbit.service)?.setAttribute('transform', planetTransform(p))
        const link = links.current.get(orbit.service)
        if (link) {
          link.setAttribute('x2', p.x.toFixed(1))
          link.setAttribute('y2', p.y.toFixed(1))
        }
        const rate = rates.current.get(orbit.service) ?? 0
        ;(packets.current.get(orbit.service) ?? []).forEach((dot, k) => {
          const progress = (time * rate + k / PACKETS) % 1
          dot.setAttribute('cx', (C.x + (p.x - C.x) * progress).toFixed(1))
          dot.setAttribute('cy', (C.y + (p.y - C.y) * progress).toFixed(1))
          dot.setAttribute('opacity', rate === 0 ? '0' : (0.85 * Math.sin(Math.PI * progress)).toFixed(2))
        })
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [orbits])

  const open = (service: string) => navigate(`/anomalies?service=${encodeURIComponent(service)}`)
  const hold = (on: boolean) => () => {
    paused.current = on
  }

  const body = (star: Star, radius: number) => {
    const state = stateOf(star)
    const quiet = star.logs === 0
    const meta = quiet ? 'no logs in this range' : `${formatCompact(star.logs)} logs, ${formatPercent(star.errorRate)} errors`
    return {
      label: `${star.service}: ${meta}${star.alert ? `, open alert: ${star.alert.title}` : ''}`,
      quiet,
      content: (
        <>
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
            <text className="star-alert" y={radius + 52} style={{ fill: STATE_COLOUR[state] }}>{star.alert.title}</text>
          )}
        </>
      ),
    }
  }

  const interactive = (service: string, label: string) => ({
    role: 'link',
    tabIndex: 0,
    'aria-label': label,
    onClick: () => open(service),
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === 'Enter') open(service)
    },
    onPointerEnter: hold(true),
    onPointerLeave: hold(false),
    onFocus: hold(true),
    onBlur: hold(false),
  })

  return (
    <svg className="constellation" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img"
         aria-label="Services as a galaxy: the API gateway at the centre, the other services orbiting it; size shows log volume, colour shows health">
      <defs>
        {STATES.map((state) => (
          <radialGradient key={state} id={`halo-${state}`}>
            <stop offset="0%" style={{ stopColor: STATE_COLOUR[state], stopOpacity: 0.42 }} />
            <stop offset="100%" style={{ stopColor: STATE_COLOUR[state], stopOpacity: 0 }} />
          </radialGradient>
        ))}
        <radialGradient id="galaxy-disc">
          <stop offset="0%" style={{ stopColor: '#f1e6c8', stopOpacity: 0.7 }} />
          <stop offset="10%" style={{ stopColor: '#d9c47f', stopOpacity: 0.32 }} />
          <stop offset="40%" style={{ stopColor: '#9a8bd0', stopOpacity: 0.14 }} />
          <stop offset="100%" style={{ stopColor: '#9a8bd0', stopOpacity: 0 }} />
        </radialGradient>
      </defs>

      <Galaxy />

      {orbits.map((o) => (
        <ellipse key={`orbit-${o.service}`} className="orbit" cx={C.x} cy={C.y} rx={o.rx} ry={o.ry}
                 transform={`rotate(${(TILT * 180) / Math.PI} ${C.x} ${C.y})`} />
      ))}

      {orbits.map((o) => {
        const start = orbitPoint(o, o.phase)
        const state = byService[o.service] ? stateOf(byService[o.service]) : 'calm'
        return (
          <g key={`flow-${o.service}`}>
            <line className="link" x1={C.x} y1={C.y} x2={start.x} y2={start.y}
                  ref={(el) => {
                    if (el) links.current.set(o.service, el)
                    else links.current.delete(o.service)
                  }} />
            {Array.from({ length: PACKETS }, (_, k) => (
              <circle key={k} className="packet" r={1.8} cx={C.x} cy={C.y} opacity={0}
                      style={{ fill: STATE_COLOUR[state] }}
                      ref={(el) => {
                        const list = packets.current.get(o.service) ?? []
                        if (el) list[k] = el
                        packets.current.set(o.service, list)
                      }} />
            ))}
          </g>
        )
      })}

      <circle className="core-glow" cx={C.x} cy={C.y} r={46} fill="url(#galaxy-disc)" aria-hidden="true" />

      {core && (() => {
        const radius = 7 + 13 * Math.sqrt(core.logs / maxLogs)
        const { label, quiet, content } = body(core, radius)
        return (
          <g className={`star star-centre${quiet ? ' star-quiet' : ''}`} transform={`translate(${C.x} ${C.y})`}
             {...interactive(core.service, label)}>
            {content}
          </g>
        )
      })()}

      {orbits.map((o) => {
        const star = byService[o.service]
        if (!star) return null
        const radius = 5 + 13 * Math.sqrt(star.logs / maxLogs)
        const { label, quiet, content } = body(star, radius)
        return (
          <g key={o.service} className={`star${quiet ? ' star-quiet' : ''}`}
             transform={planetTransform(orbitPoint(o, o.phase))}
             ref={(el) => {
               if (el) planets.current.set(o.service, el)
               else planets.current.delete(o.service)
             }}
             {...interactive(o.service, label)}>
            {content}
          </g>
        )
      })}
    </svg>
  )
}