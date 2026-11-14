import { serviceColour } from './theme'

export function SeriesLegend({ services }: { services: string[] }) {
  return (
    <div className="series-legend">
      {services.map((s) => (
        <span key={s} style={{ ['--dot' as string]: serviceColour(s) }}>{s}</span>
      ))}
    </div>
  )
}