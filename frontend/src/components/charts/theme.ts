// Chart colours. SVG attributes cannot use CSS variables reliably, so the values mirror index.css.
// Service colours are calm and distinct, and deliberately different from the severity colours.
export const CHART = {
  grid: 'rgba(196, 204, 230, 0.08)',
  axis: '#8a92ab',
  tooltip: {
    background: '#111a2e',
    border: '1px solid rgba(196, 204, 230, 0.15)',
    borderRadius: 10,
    color: '#dfe2ee',
    fontSize: 12,
  },
}

export const SERVICE_ORDER = ['api-gateway', 'auth-service', 'order-service', 'payment-service', 'inventory-service']

const PALETTE: Record<string, string> = {
  'api-gateway': '#9a8bd0',
  'auth-service': '#6fb7a8',
  'order-service': '#7fa2d6',
  'payment-service': '#c98fb0',
  'inventory-service': '#b9ab86',
}
const EXTRA = ['#8fb0a0', '#a39bd8', '#c2a5c9', '#93a7c2', '#a7b89a']

export function serviceColour(service: string): string {
  if (PALETTE[service]) return PALETTE[service]
  let hash = 0
  for (const ch of service) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  return EXTRA[hash % EXTRA.length]
}

/** Known services in topology order, then any others alphabetically. */
export function orderServices(names: string[]): string[] {
  const rank = (n: string) => (SERVICE_ORDER.includes(n) ? SERVICE_ORDER.indexOf(n) : SERVICE_ORDER.length)
  return [...new Set(names)].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b))
}