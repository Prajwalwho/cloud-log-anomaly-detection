import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Anomalies } from './pages/Anomalies'
import { Alerts } from './pages/Alerts'
import { Logs } from './pages/Logs'
import { Models } from './pages/Models'

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