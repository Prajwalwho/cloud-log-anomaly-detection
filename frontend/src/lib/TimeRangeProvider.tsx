import { useMemo, useState, type ReactNode } from 'react'
import { TimeRangeContext, type RangeKey } from './timeRange'

export function TimeRangeProvider({ children }: { children: ReactNode }) {
  const [range, setRange] = useState<RangeKey>('1h')
  const value = useMemo(() => ({ range, setRange }), [range])
  return <TimeRangeContext.Provider value={value}>{children}</TimeRangeContext.Provider>
}