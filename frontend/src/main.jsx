import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ToastProvider }         from './contexts/ToastContext'
import { MarketProvider }        from './contexts/MarketContext'

import './index.css'

import Login          from './pages/Login'
import InternalRegister from './pages/InternalRegister'
import Dashboard      from './pages/Dashboard'
import Suite          from './pages/Suite'
import ProcurementExpansion from './pages/ProcurementExpansion'
import Assinatura    from './pages/Assinatura'
import Upload         from './pages/Upload'
import EditalDetail   from './pages/EditalDetail'
import EditalChat     from './pages/EditalChat'
import Jobs           from './pages/Jobs'
import Usuarios       from './pages/Usuarios'
import Analytics      from './pages/Analytics'
import Reports        from './pages/Reports'
import Chatbot        from './pages/Chatbot'
import Controle       from './pages/Controle'
import AnaliseAta     from './pages/AnaliseAta'
import AnaliseJson    from './pages/AnaliseJson'
import AnalysisDashboard from './pages/AnalysisDashboard'
import PncpSearch     from './pages/PncpSearch'
import OpportunityRadar from './pages/OpportunityRadar'
import CompetitiveIntelligence from './pages/CompetitiveIntelligence'
import Configuracoes  from './pages/Configuracoes'
import CrmHub         from './pages/CrmHub'
import DatasheetCompare from './pages/DatasheetCompare'
import Layout         from './components/Layout'

const INTERNAL_REGISTER_PATH = import.meta.env.VITE_INTERNAL_REGISTER_PATH || '/cadastro-tor-gestao-interna'

function PrivateRoute({ children, withLayout = true }) {
  const { user, loading } = useAuth()
  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-azure/30 border-t-azure rounded-full animate-spin" />
    </div>
  )
  if (!user) return <Navigate to="/login" replace />
  return withLayout ? <Layout>{children}</Layout> : children
}

function AdminRoute({ children }) {
  const { isAdmin } = useAuth()
  if (!isAdmin) return <Navigate to="/dashboard" replace />
  return children
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <MarketProvider>
          <AuthProvider>
            <Routes>
            <Route path="/login" element={<Login />} />
            <Route path={INTERNAL_REGISTER_PATH} element={<InternalRegister />} />

            <Route path="/dashboard"              element={<PrivateRoute><Dashboard     /></PrivateRoute>} />
            <Route path="/suite"                  element={<PrivateRoute><Suite         /></PrivateRoute>} />
            <Route path="/assinatura"             element={<PrivateRoute><Assinatura    /></PrivateRoute>} />
            <Route path="/monitoramento-pncp"     element={<PrivateRoute><ProcurementExpansion moduleId="pncp_monitor" /></PrivateRoute>} />
            <Route path="/propostas"              element={<PrivateRoute><ProcurementExpansion moduleId="proposal_studio" /></PrivateRoute>} />
            <Route path="/habilitacao"            element={<PrivateRoute><ProcurementExpansion moduleId="compliance_checklist" /></PrivateRoute>} />
            <Route path="/precificacao"           element={<PrivateRoute><ProcurementExpansion moduleId="pricing" /></PrivateRoute>} />
            <Route path="/monitor-pregao"         element={<PrivateRoute><ProcurementExpansion moduleId="auction_monitor" /></PrivateRoute>} />
            <Route path="/pos-vitoria"            element={<PrivateRoute><ProcurementExpansion moduleId="post_award" /></PrivateRoute>} />
            <Route path="/onboarding-planos"      element={<PrivateRoute><ProcurementExpansion moduleId="onboarding_plans" /></PrivateRoute>} />
            <Route path="/integracoes"            element={<PrivateRoute><ProcurementExpansion moduleId="integrations" /></PrivateRoute>} />
            <Route path="/upload"                 element={<PrivateRoute><Upload        /></PrivateRoute>} />
            <Route path="/jobs"                   element={<PrivateRoute><Jobs          /></PrivateRoute>} />
            <Route path="/analytics"              element={<PrivateRoute><Analytics     /></PrivateRoute>} />
            <Route path="/relatorios"             element={<PrivateRoute><Reports       /></PrivateRoute>} />
            <Route path="/chat"                   element={<PrivateRoute><Chatbot       /></PrivateRoute>} />
            <Route path="/controle"               element={<PrivateRoute><Controle      /></PrivateRoute>} />
            <Route path="/radar"                  element={<PrivateRoute><OpportunityRadar /></PrivateRoute>} />
            <Route path="/pncp"                   element={<PrivateRoute><PncpSearch    /></PrivateRoute>} />
            <Route path="/crm"                    element={<PrivateRoute withLayout={false}><CrmHub /></PrivateRoute>} />
            <Route path="/configuracoes"          element={<PrivateRoute><Configuracoes /></PrivateRoute>} />
            <Route path="/editais/:id"            element={<PrivateRoute><EditalDetail  /></PrivateRoute>} />
            <Route path="/editais/:id/chat"       element={<PrivateRoute><EditalChat    /></PrivateRoute>} />
            <Route path="/editais/:id/analise-llm" element={<PrivateRoute><AnaliseAta   /></PrivateRoute>} />
            <Route path="/analise/documentos/:id"  element={<PrivateRoute><AnaliseJson  /></PrivateRoute>} />
            <Route path="/analise/upload"          element={<Navigate to="/upload" replace />} />
            <Route path="/analise/dashboard"       element={<PrivateRoute><AnalysisDashboard /></PrivateRoute>} />
            <Route path="/inteligencia/datasheets" element={<PrivateRoute><DatasheetCompare /></PrivateRoute>} />
            <Route path="/inteligencia/competitiva" element={<PrivateRoute><CompetitiveIntelligence /></PrivateRoute>} />

            <Route path="/usuarios" element={
              <PrivateRoute><AdminRoute><Usuarios /></AdminRoute></PrivateRoute>
            } />

            <Route path="/"  element={<Navigate to="/dashboard" replace />} />
            <Route path="*"  element={<Navigate to="/dashboard" replace />} />
            </Routes>
          </AuthProvider>
        </MarketProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>
)
