import { lazy, StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { ToastProvider }         from './contexts/ToastContext'
import { MarketProvider }        from './contexts/MarketContext'

import './index.css'

import PageLoader from './components/PageLoader'
const Login = lazy(() => import('./pages/Login'))
const InternalRegister = lazy(() => import('./pages/InternalRegister'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Suite = lazy(() => import('./pages/Suite'))
const ProcurementExpansion = lazy(() => import('./pages/ProcurementExpansion'))
const Assinatura = lazy(() => import('./pages/Assinatura'))
const Upload = lazy(() => import('./pages/Upload'))
const EditalDetail = lazy(() => import('./pages/EditalDetail'))
const EditalChat = lazy(() => import('./pages/EditalChat'))
const Jobs = lazy(() => import('./pages/Jobs'))
const Usuarios = lazy(() => import('./pages/Usuarios'))
const Analytics = lazy(() => import('./pages/Analytics'))
const Reports = lazy(() => import('./pages/Reports'))
const Chatbot = lazy(() => import('./pages/Chatbot'))
const Controle = lazy(() => import('./pages/Controle'))
const AnaliseAta = lazy(() => import('./pages/AnaliseAta'))
const AnaliseJson = lazy(() => import('./pages/AnaliseJson'))
const AnalysisDashboard = lazy(() => import('./pages/AnalysisDashboard'))
const PncpSearch = lazy(() => import('./pages/PncpSearch'))
const OpportunityRadar = lazy(() => import('./pages/OpportunityRadar'))
const CompetitiveIntelligence = lazy(() => import('./pages/CompetitiveIntelligence'))
const BidRobot = lazy(() => import('./pages/BidRobot'))
const Configuracoes = lazy(() => import('./pages/Configuracoes'))
const CrmHub = lazy(() => import('./pages/CrmHub'))
const DatasheetCompare = lazy(() => import('./pages/DatasheetCompare'))
import Layout         from './components/Layout'

const INTERNAL_REGISTER_PATH = import.meta.env.VITE_INTERNAL_REGISTER_PATH || '/cadastro-tor-gestao-interna'
const AI_FEATURES_ENABLED = import.meta.env.VITE_AI_FEATURES_ENABLED === '1'

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
            <Suspense fallback={<PageLoader />}>
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
            <Route path="/robo-lances"            element={<PrivateRoute><BidRobot /></PrivateRoute>} />
            <Route path="/pos-vitoria"            element={<PrivateRoute><ProcurementExpansion moduleId="post_award" /></PrivateRoute>} />
            <Route path="/onboarding-planos"      element={<PrivateRoute><ProcurementExpansion moduleId="onboarding_plans" /></PrivateRoute>} />
            <Route path="/integracoes"            element={<PrivateRoute><ProcurementExpansion moduleId="integrations" /></PrivateRoute>} />
            <Route path="/upload"                 element={<PrivateRoute><Upload        /></PrivateRoute>} />
            <Route path="/jobs"                   element={AI_FEATURES_ENABLED ? <PrivateRoute><Jobs /></PrivateRoute> : <Navigate to="/dashboard" replace />} />
            <Route path="/analytics"              element={<PrivateRoute><Analytics     /></PrivateRoute>} />
            <Route path="/relatorios"             element={<PrivateRoute><Reports       /></PrivateRoute>} />
            <Route path="/chat"                   element={AI_FEATURES_ENABLED ? <PrivateRoute><Chatbot /></PrivateRoute> : <Navigate to="/dashboard" replace />} />
            <Route path="/controle"               element={<PrivateRoute><Controle      /></PrivateRoute>} />
            <Route path="/radar"                  element={<PrivateRoute><OpportunityRadar /></PrivateRoute>} />
            <Route path="/pncp"                   element={<PrivateRoute><PncpSearch    /></PrivateRoute>} />
            <Route path="/crm"                    element={<PrivateRoute withLayout={false}><CrmHub /></PrivateRoute>} />
            <Route path="/configuracoes"          element={<PrivateRoute><Configuracoes /></PrivateRoute>} />
            <Route path="/editais/:id"            element={<PrivateRoute><EditalDetail  /></PrivateRoute>} />
            <Route path="/editais/:id/chat"       element={AI_FEATURES_ENABLED ? <PrivateRoute><EditalChat /></PrivateRoute> : <Navigate to="/dashboard" replace />} />
            <Route path="/editais/:id/analise-llm" element={AI_FEATURES_ENABLED ? <PrivateRoute><AnaliseAta /></PrivateRoute> : <Navigate to="/dashboard" replace />} />
            <Route path="/analise/documentos/:id"  element={<PrivateRoute><AnaliseJson  /></PrivateRoute>} />
            <Route path="/analise/upload"          element={<Navigate to="/upload" replace />} />
            <Route path="/analise/dashboard"       element={AI_FEATURES_ENABLED ? <PrivateRoute><AnalysisDashboard /></PrivateRoute> : <Navigate to="/dashboard" replace />} />
            <Route path="/inteligencia/datasheets" element={AI_FEATURES_ENABLED ? <PrivateRoute><DatasheetCompare /></PrivateRoute> : <Navigate to="/dashboard" replace />} />
            <Route path="/inteligencia/competitiva" element={AI_FEATURES_ENABLED ? <PrivateRoute><CompetitiveIntelligence /></PrivateRoute> : <Navigate to="/dashboard" replace />} />

            <Route path="/usuarios" element={
              <PrivateRoute><AdminRoute><Usuarios /></AdminRoute></PrivateRoute>
            } />

            <Route path="/"  element={<Navigate to="/dashboard" replace />} />
            <Route path="*"  element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </Suspense>
          </AuthProvider>
        </MarketProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>
)
