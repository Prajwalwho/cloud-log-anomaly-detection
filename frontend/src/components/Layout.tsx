// Sidebar (name, navigation, backend health and live-feed signals) and a top bar with the time range picker.
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { BellRing, Cpu, LayoutDashboard, ScrollText, TriangleAlert } from 'lucide-react'
import { api } from '../services/api'
import { useLiveFeed } from '../live/context'
import { RANGES, useTimeRange } from '../lib/timeRange'
import type { Health } from '../types/api'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/anomalies', label: 'Anomalies', icon: TriangleAlert },
  { to: '/alerts', label: 'Alerts', icon: BellRing },
  { to: '/logs', label: 'Logs', icon: ScrollText },
  { to: '/models', label: 'Models', icon: Cpu },
]

function HealthSignal() {
  const [health, setHealth] = useState<Health | 'unreachable' | null>(null)

  useEffect(() => {
    let active = true
    const check = () =>
      api.health()
        .then((h) => active && setHealth(h))
        .catch(() => active && setHealth('unreachable'))
    check()
    const timer = window.setInterval(check, 30_000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  if (health === null) return <span className="indicator">Checking backend</span>
  if (health === 'unreachable') return <span className="indicator down">Backend unreachable</span>
  const down = Object.entries(health.components).filter(([, s]) => s === 'down').map(([name]) => name)
  return (
    <span className={`indicator ${down.length ? 'down' : 'ok'}`}>
      {down.length ? `${down.join(', ')} down` : 'All systems running'}
    </span>
  )
}

function LiveSignal() {
  const { status } = useLiveFeed()
  if (status === 'open') return <span className="indicator ok live">Live updates on</span>
  return <span className="indicator warn">{status === 'connecting' ? 'Connecting' : 'Reconnecting'}</span>
}

function RangePicker() {
  const { range, setRange } = useTimeRange()
  return (
    <div className="range" role="radiogroup" aria-label="Time range">
      {RANGES.map((r) => (
        <button key={r.key} type="button" role="radio" aria-checked={r.key === range} onClick={() => setRange(r.key)}>
          {r.label}
        </button>
      ))}
    </div>
  )
}

export function Layout() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-name">Observatory</div>
          <div className="brand-sub">Cloud log anomaly detection</div>
        </div>
        <nav aria-label="Main">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => (isActive ? 'active' : '')}>
              <Icon size={18} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="signals">
          <HealthSignal />
          <LiveSignal />
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <RangePicker />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}