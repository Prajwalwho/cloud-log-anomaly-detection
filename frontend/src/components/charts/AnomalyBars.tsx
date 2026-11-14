// Number of anomalous windows per bucket, stacked by service.
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
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

export function AnomalyBars({ series, from, to, interval }: Props) {
  const times = buckets(from, to, interval)
  const services = orderServices(series.series.map((s) => s.service))
  const values = lookupBySeries(series.series)
  const rows = times.map((t) => {
    const row: Record<string, number> = { t }
    for (const s of services) row[s] = values.get(s)?.get(t) ?? 0
    return row
  })
  const total = rows.reduce((sum, r) => sum + services.reduce((n, s) => n + r[s], 0), 0)
  if (total === 0) return <p className="muted">No anomalies in this range.</p>

  return (
    <>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={CHART.grid} vertical={false} />
          <XAxis dataKey="t" minTickGap={48} tickFormatter={(v: number) => formatBucket(v, interval)}
                 tick={{ fill: CHART.axis, fontSize: 11 }} tickLine={false} axisLine={{ stroke: CHART.grid }} />
          <YAxis allowDecimals={false} width={32} tick={{ fill: CHART.axis, fontSize: 11 }}
                 tickLine={false} axisLine={false} />
          <Tooltip contentStyle={CHART.tooltip} cursor={{ fill: 'rgba(196, 204, 230, 0.05)' }}
                   labelFormatter={(v) => formatBucket(Number(v), interval)} />
          {services.map((s) => (
            <Bar key={s} dataKey={s} name={s} stackId="services" fill={serviceColour(s)} maxBarSize={18}
                 isAnimationActive={false} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <SeriesLegend services={services} />
    </>
  )
}