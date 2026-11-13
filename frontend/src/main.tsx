import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { LiveFeedProvider } from './live/LiveFeedProvider'
import { TimeRangeProvider } from './lib/TimeRangeProvider'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <LiveFeedProvider>
      <TimeRangeProvider>
        <App />
      </TimeRangeProvider>
    </LiveFeedProvider>
  </StrictMode>,
)