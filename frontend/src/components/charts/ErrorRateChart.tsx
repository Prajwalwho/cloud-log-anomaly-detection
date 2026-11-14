// Error rate per service over time (sum of errors / sum of logs per bucket), one line per service.
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { buckets, formatBucket, lookupBySeries } from '../../lib/buckets'
import { CHART, orderServices, serviceColour } from './theme'
import { SeriesLegend } from './SeriesLegend'
import type { Interval, Timeseries } from '../../types/api'

interface Props {
  series: Timeseries
  from: string
  to: string
  interval: Interval
}

/** Axis top and tick marks: steps of 5% up to 25%, then steps of 10%, so the ticks are always round numbers. */
function axisTicks(dataMax: number): number[] {
  const step = dataMax <= 0.25 ? 0.05 : 0.1
  const top = Math.max(step, Math.ceil(dataMax / step) * step)
  const ticks: number[] = []
  for (let v = 0; v <= top + 1e-9; v += step) ticks.push(Math.round(v * 100) / 100)
  return ticks
}

export function ErrorRateChart({ series, from, to, interval }: Props) {
  const times = buckets(from, to, interval)
  const services = orderServices(series.series.map((s) => s.service))
  if (services.length === 0) return <p className="muted">No analysed windows in this range yet.</p>
  const values = lookupBySeries(series.series)
  const rows = times.map((t) => {
    const row: Record<string, number | null> = { t }
    for (const s of services) row[s] = values.get(s)?.get(t) ?? null
    return row
  })
  // highest error rate in the range, computed after the rows are built (no variable changed inside map)
  const dataMax = rows.reduce(
    (max, row) => services.reduce((m, s) => Math.max(m, row[s] ?? 0), max),
    0,
  )
  const ticks = axisTicks(dataMax)

  return (
    <>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} minTickGap={48}
                 tickFormatter={(v: number) => formatBucket(v, interval)} tick={{ fill: CHART.axis, fontSize: 11 }}
                 tickLine={false} axisLine={{ stroke: CHART.grid }} />
          <YAxis domain={[0, ticks[ticks.length - 1]]} ticks={ticks} tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                 width={44} tick={{ fill: CHART.axis, fontSize: 11 }} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={CHART.tooltip} labelFormatter={(v) => formatBucket(Number(v), interval)}
                   formatter={(v) => (typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : 'no data')} />
          {services.map((s) => (
            <Line key={s} dataKey={s} name={s} stroke={serviceColour(s)} strokeWidth={1.6} dot={false}
                  connectNulls={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <SeriesLegend services={services} />
    </>
  )
}