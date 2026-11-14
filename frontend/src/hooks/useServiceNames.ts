// The registered service names in topology order (for filters). Loaded once; an empty list until then.
import { useEffect, useState } from 'react'
import { api } from '../services/api'
import { orderServices } from '../components/charts/theme'

export function useServiceNames(): string[] {
  const [names, setNames] = useState<string[]>([])

  useEffect(() => {
    let active = true
    api.services()
      .then((services) => {
        if (active) setNames(orderServices(services.map((s) => s.name)))
      })
      .catch(() => {
        // the page shows its own error for the main request; an empty filter list is enough here
      })
    return () => {
      active = false
    }
  }, [])

  return names
}
