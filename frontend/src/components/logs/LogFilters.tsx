// Filters of the Logs page: full-text search (on Enter / Search), service and level.
import { useState } from 'react'
import { Search } from 'lucide-react'
import { LEVEL_COLOURS } from '../../lib/format'
import type { LogLevel } from '../../types/api'

const LEVELS: LogLevel[] = ['FATAL', 'ERROR', 'WARN', 'INFO', 'DEBUG']

interface Props {
  services: string[]
  q: string
  service: string
  levels: LogLevel[]
  onSearch: (q: string) => void
  onService: (service: string) => void
  onLevels: (levels: LogLevel[]) => void
}

export function LogFilters(props: Props) {
  const { services, service, levels } = props
  // The text box is local until the search is submitted; the page remounts this component when the URL's q changes.
  const [text, setText] = useState(props.q)

  const toggle = (level: LogLevel) => {
    const next = levels.includes(level) ? levels.filter((l) => l !== level) : [...levels, level]
    props.onLevels(LEVELS.filter((l) => next.includes(l)))
  }

  const options = service && !services.includes(service) ? [service, ...services] : services

  return (
    <div className="filters">
      <form className="field search-field" role="search"
            onSubmit={(e) => {
              e.preventDefault()
              props.onSearch(text.trim())
            }}>
        <label htmlFor="log-search">Search messages</label>
        <div className="search-box">
          <Search size={16} aria-hidden="true" />
          <input id="log-search" type="search" value={text} placeholder="e.g. timeout payment"
                 onChange={(e) => setText(e.target.value)} />
          <button type="submit">Search</button>
        </div>
      </form>

      <label className="field">
        <span>Service</span>
        <select value={service} onChange={(e) => props.onService(e.target.value)}>
          <option value="">All services</option>
          {options.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
      </label>

      <div className="field">
        <span id="level-label">Level</span>
        <div className="chips" role="group" aria-labelledby="level-label">
          {LEVELS.map((level) => (
            <button key={level} type="button" className="chip" aria-pressed={levels.includes(level)}
                    style={{ ['--dot' as string]: LEVEL_COLOURS[level] }} onClick={() => toggle(level)}>
              {level.charAt(0) + level.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}