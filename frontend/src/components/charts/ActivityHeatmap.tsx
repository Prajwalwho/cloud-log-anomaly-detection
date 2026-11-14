// Services x time, each cell coloured by the highest anomaly score of the service in that bucket.
// Dark blue = normal, gold = at the model threshold (score 0.5), amber -> red = increasingly anomalous.
import { buckets, formatBucket, lookupBySeries } from '../../lib/buckets'
import { orderServices } from './theme'
import type { Interval, Timeseries } from '../../types/api'

type Rgb = [number, number, number]
const NORMAL_LOW: Rgb = [23, 32, 56]
const NORMAL_HIGH: Rgb = [52, 66, 106]
const WARM: [number, Rgb][] = [[0.5, [217, 196, 127]], [0.75, [227, 162, 95]], [0.9, [221, 110, 98]]]

function mix(a: Rgb, b: Rgb, f: number): string {
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * Math.min(Math.max(f, 0), 1)))
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`
}

function scoreColour(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'rgba(196, 204, 230, 0.04)'
  if (score < 0.5) return mix(NORMAL_LOW, NORMAL_HIGH, score / 0.5)
  for (let i = 1; i < WARM.length; i++) {
    const [lo, a] = WARM[i - 1]
    const [hi, b] = WARM[i]
    if (score <= hi) return mix(a, b, (score - lo) / (hi - lo))
  }
  return mix(WARM[WARM.length - 1][1], WARM[WARM.length - 1][1], 0)
}

function describe(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'no data'
  return score > 0.5 ? `anomalous (score ${score.toFixed(2)})` : `normal (score ${score.toFixed(2)})`
}

const WIDTH = 1000
const LABEL = 150
const ROW = 24
const GAP = 3
const AXIS = 24

interface Props {
  series: Timeseries
  from: string
  to: string
  interval: Interval
}

export function ActivityHeatmap({ series, from, to, interval }: Props) {
  const times = buckets(from, to, interval)
  const services = orderServices(series.series.map((s) => s.service))
  if (services.length === 0 || times.length === 0) {
    return <p className="muted">No analysed windows in this range yet.</p>
  }
  const values = lookupBySeries(series.series)
  const cell = (WIDTH - LABEL) / times.length
  const height = services.length * (ROW + GAP) + AXIS
  const tickEvery = Math.max(1, Math.round(times.length / 6))

  return (
    <div className="heatmap">
      <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img"
           aria-label="Anomaly score per service over time; warmer cells are more anomalous">
        {services.map((service, row) => (
          <g key={service} transform={`translate(0 ${row * (ROW + GAP)})`}>
            <text className="hm-label" x={LABEL - 12} y={ROW / 2} textAnchor="end" dominantBaseline="middle">
              {service}
            </text>
            {times.map((t, col) => {
              const score = values.get(service)?.get(t)
              return (
                <rect key={t} x={LABEL + col * cell} y={0} width={Math.max(cell - 2, 0.6)} height={ROW}
                      rx={Math.min(3, cell / 4)} fill={scoreColour(score)}>
                  <title>{`${service}, ${formatBucket(t, interval)}: ${describe(score)}`}</title>
                </rect>
              )
            })}
          </g>
        ))}
        {times.map((t, col) =>
          col % tickEvery === 0 ? (
            <text key={t} className="hm-tick" x={LABEL + col * cell} y={height - 6}>{formatBucket(t, interval)}</text>
          ) : null,
        )}
      </svg>
      <div className="hm-legend">
        <span>Normal</span>
        <span className="hm-ramp" aria-hidden="true" />
        <span>Threshold, then increasingly anomalous</span>
      </div>
    </div>
  )
}