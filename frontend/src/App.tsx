// Routes. Each page is its own chunk, loaded the first time it is opened (React.lazy), so the first load only
// fetches the shell and the page being opened; the charts library is only needed by the Overview.
import { lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'

const Dashboard = lazy(() => import('./pages/Dashboard').then((m) => ({ default: m.Dashboard })))
const Anomalies = lazy(() => import('./pages/Anomalies').then((m) => ({ default: m.Anomalies })))
const Alerts = lazy(() => import('./pages/Alerts').then((m) => ({ default: m.Alerts })))
const Logs = lazy(() => import('./pages/Logs').then((m) => ({ default: m.Logs })))
const Models = lazy(() => import('./pages/Models').then((m) => ({ default: m.Models })))

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="anomalies" element={<Anomalies />} />
          <Route path="alerts" element={<Alerts />} />
          <Route path="logs" element={<Logs />} />
          <Route path="models" element={<Models />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App