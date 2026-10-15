import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import AgentDetail from './pages/AgentDetail'
import Agents from './pages/Agents'
import Ask from './pages/Ask'
import AuthPage from './pages/AuthPage'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import HoldingDetail from './pages/HoldingDetail'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="holdings/:id" element={<HoldingDetail />} />
          <Route path="ask" element={<Ask />} />
          <Route path="agents" element={<Agents />} />
          <Route path="agents/:id" element={<AgentDetail />} />
          <Route path="documents" element={<Documents />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
