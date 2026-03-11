import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'

import './index.css'

import Login        from './pages/Login'
import Dashboard    from './pages/Dashboard'
import Upload       from './pages/Upload'
import EditalDetail from './pages/EditalDetail'
import Jobs         from './pages/Jobs'
import Usuarios     from './pages/Usuarios'
import Analytics    from './pages/Analytics'       // ← NOVO
import Layout       from './components/Layout'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-azure/30 border-t-azure rounded-full animate-spin" />
    </div>
  )
  return user ? <Layout>{children}</Layout> : <Navigate to="/login" replace />
}

function AdminRoute({ children }) {
  const { isAdmin } = useAuth()
  if (!isAdmin) return <Navigate to="/dashboard" replace />
  return children
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/dashboard"    element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/upload"       element={<PrivateRoute><Upload /></PrivateRoute>} />
          <Route path="/jobs"         element={<PrivateRoute><Jobs /></PrivateRoute>} />
          <Route path="/analytics"    element={<PrivateRoute><Analytics /></PrivateRoute>} />
          <Route path="/editais/:id"  element={<PrivateRoute><EditalDetail /></PrivateRoute>} />

          <Route path="/usuarios" element={
            <PrivateRoute><AdminRoute><Usuarios /></AdminRoute></PrivateRoute>
          } />

          <Route path="/"  element={<Navigate to="/dashboard" replace />} />
          <Route path="*"  element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>
)
