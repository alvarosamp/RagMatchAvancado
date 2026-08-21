/**
 * api/client.js
 * ─────────────
 * Wrapper do Axios com:
 *   - Base URL apontando para a API (via proxy Vite em dev)
 *   - Interceptor que injeta o JWT em todo request automaticamente
 *   - Interceptor de resposta que redireciona para /login em 401
 *
 * CONCEITO: Por que interceptors?
 *   Sem interceptor, você precisaria fazer:
 *     axios.get('/editais', { headers: { Authorization: `Bearer ${token}` } })
 *   em CADA chamada. Com interceptor, o token é injetado automaticamente.
 */

import axios from 'axios'
import { clearPortalSessionStorage } from '../utils/authStorage'

const api = axios.create({
  baseURL: '/api',            // proxy Vite → http://localhost:8000 em dev
  timeout: 30_000,            // 30s timeout
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

// ── Interceptor de REQUEST — injeta JWT ──────────────────────────────────────
// ── Interceptor de RESPONSE — trata 401 ─────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const currentPath = window.location.pathname
      const requestPath = error.config?.url || ''

      // Login e checagem inicial podem receber 401 sem forcar reload da pagina.
      clearPortalSessionStorage()
      if (currentPath !== '/login' && !requestPath.includes('/auth/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api

// ── Helpers por domínio ───────────────────────────────────────────────────────

export const authApi = {
  register: (data)  => api.post('/auth/register', data),
  login:    (data)  => api.post('/auth/login', data),
  logout:   ()      => api.post('/auth/logout'),
  me:       ()      => api.get('/auth/me'),
  createUser: (data) => api.post('/auth/users', data),
  listUsers:  ()    => api.get('/auth/users'),
}

export const editaisApi = {
  list:    ()                   => api.get('/editais/'),
  upload:  (formData, options = {}) => {
    if (options.analysisOnly != null && !formData.has('analysis_only')) {
      formData.append('analysis_only', options.analysisOnly ? 'true' : 'false')
    }
    if (options.importBatchId != null && !formData.has('import_batch_id')) {
      formData.append('import_batch_id', String(options.importBatchId))
    }
    if (options.sourcePath && !formData.has('source_path')) {
      formData.append('source_path', options.sourcePath)
    }
    return api.post('/editais/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
    })
  },
  remove:  (id)                 => api.delete(`/editais/${id}`),
  addRequirements: (id, reqs)   => api.post(`/editais/${id}/requirements`, reqs),
  match:   (id)                 => api.post(`/editais/${id}/match`),
  results: (id)                 => api.get(`/editais/${id}/results`),
  lock:    (id)                 => api.get(`/editais/${id}/lock`),
  heartbeatLock: (id, tabId)    => api.post(`/editais/${id}/lock`, { tab_id: tabId }),
  releaseLock:   (id, tabId)    => api.delete(`/editais/${id}/lock`, { data: { tab_id: tabId } }),
}

export const jobsApi = {
  get:    (jobId)       => api.get(`/jobs/${jobId}`),
  list:   (params = {}) => api.get('/jobs/', { params }),
  summary: ()           => api.get('/jobs/summary'),
  cancel: (jobId)       => api.delete(`/jobs/${jobId}`),
}

export const opsApi = {
  summary: () => api.get('/ops/summary'),
}

export const reportsApi = {
  executive: () => api.get('/reports/executive'),
}

export const documentsApi = {
  listSigners: () => api.get('/documents/signers'),
  listFiles: (params = {}) => api.get('/documents/files', { params }),
  uploadFile: (formData) => api.post('/documents/files', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
  }),
  uploadVersion: (documentId, formData) => api.post(`/documents/files/${documentId}/versions`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
  }),
  attachFile: (documentId, payload) => api.post(`/documents/files/${documentId}/attach`, payload),
  requestSignature: (documentId, payload) => api.post(`/documents/files/${documentId}/signature-requests`, payload),
  listSignatureRequests: (params = {}) => api.get('/documents/signature-requests', { params }),
  signatureAlert: () => api.get('/documents/signature-alert'),
  dismissSignatureAlert: (requestId) => api.post(`/documents/signature-requests/${requestId}/dismiss`),
  uploadSigned: (requestId, formData) => api.post(`/documents/signature-requests/${requestId}/signed`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
  }),
  downloadFile: (documentId) => api.get(`/documents/files/${documentId}/download`, { responseType: 'blob' }),
}

export const crmApi = {
  importSalesProcesses: (formData) =>
    api.post('/crm/imports/sales-processes', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120_000,
    }),
  attachedProductsReport: (params = {}) =>
    api.get('/crm/matches/attached-products/report', { params }),
  decisionIntelligence: (noticeId) =>
    api.get(`/crm/notices/${noticeId}/decision-intelligence`),
  runDecisionIntelligence: (noticeId) =>
    api.post(`/crm/notices/${noticeId}/decision-intelligence/run`, {}, { timeout: 60_000 }),
}

export const marketApi = {
  profile: () => api.get('/market/profile'),
}

export const bidRobotApi = {
  listSessions: () => api.get('/bid-robot/sessions'),
  createSession: (payload) => api.post('/bid-robot/sessions', payload),
  getSession: (sessionId) => api.get(`/bid-robot/sessions/${sessionId}`),
  updateMarketBid: (sessionId, lotId, currentBestBid) =>
    api.post(`/bid-robot/sessions/${sessionId}/lots/${lotId}/market-bid`, {
      current_best_bid: currentBestBid,
    }),
  confirmBid: (sessionId, lotId, bidValue, source = 'manual') =>
    api.post(`/bid-robot/sessions/${sessionId}/lots/${lotId}/confirm`, {
      bid_value: bidValue,
      source,
    }),
  autoBid: (sessionId, lotId, dryRun = false) =>
    api.post(`/bid-robot/sessions/${sessionId}/lots/${lotId}/auto-bid`, {
      dry_run: dryRun,
    }),
  addChatMessage: (sessionId, message) =>
    api.post(`/bid-robot/sessions/${sessionId}/chat`, { message }),
  syncPortal: (sessionId, lotId, portalSessionUrl) =>
    api.post(`/bid-robot/sessions/${sessionId}/lots/${lotId}/sync-portal`, {
      portal_session_url: portalSessionUrl,
    }),
}

export const healthApi = {
  status: () => api.get('/health'),
}

export const exportApi = {
  xlsx: (id) => api.get(`/editais/${id}/export/xlsx`, { responseType: 'blob' }),
  pdf:  (id) => api.get(`/editais/${id}/export/pdf`,  { responseType: 'blob' }),
  csv:  (id) => api.get(`/editais/${id}/export/csv`,  { responseType: 'blob' }),
}

// ── RAG Chat ─────────────────────────────────────────────────────────────────
export const ragApi = {
  /**
   * Envia uma pergunta sobre um edital específico.
   * @param {number|string} editalId
   * @param {{ question: string, model: 'gpt'|'ollama', history: Array }} body
   */
  chat: (editalId, body) => api.post(`/editais/${editalId}/chat`, body, { timeout: 180_000 }),
}

// ── Análise LLM (pipeline pipelinellm.py) ────────────────────────────────────
// Integração com Pncp/AnaliseAtaLLM/pipelinellm.py
// ResultadoAnalise: { id_pncp, numero_ata, orgao, data_assinatura, vigencia,
//                    objeto, itens: ItemAta[], tokens_usados, aviso }
export const llmApi = {
  results: (editalId) => api.get(`/editais/${editalId}/llm-results`),
  analyze: (editalId) => api.post(`/editais/${editalId}/analyze`, {}, { timeout: 120_000 }),
}

// ── PNCP — Portal Nacional de Contratações Públicas ──────────────────────────
export const pncpApi = {
  /**
   * Pesquisa editais no PNCP.
   * @param {{ texto?, cnpj?, modalidade?, dataInicio?, dataFim?, pagina? }} params
   */
  search:       (params) => api.get('/pncp/search', { params, timeout: 30_000 }),

  /**
   * Pesquisa oportunidades no PNCP e aplica score de prioridade.
   */
  radar:        (params) => api.get('/pncp/radar', { params, timeout: 45_000 }),

  refreshRadar: (params = {}) => api.post('/pncp/radar/refresh', null, { params, timeout: 90_000 }),

  decisions:    (params = {}) => api.get('/pncp/opportunities/decisions', { params }),

  decide:       (payload) => api.post('/pncp/opportunities/decision', payload),

  /**
   * Importa um edital do PNCP para o sistema (enfileira job).
   * @param {string} idPncp
   */
  importEdital: (idPncp) => api.post('/pncp/import', { id_pncp: idPncp }, { timeout: 30_000 }),

  /**
   * Retorna detalhes de um edital PNCP específico.
   */
  detail:       (idPncp) => api.get(`/pncp/${encodeURIComponent(idPncp)}`),
}

// ── Análise via JSON estruturado (schema v7.3) ──────────────────────────────
// Ingestão de editais/itens a partir de JSONs (substitui a planilha).
export const analysisApi = {
  list:      (params = {}) => api.get('/analysis/documents', { params }),
  get:       (id)          => api.get(`/analysis/documents/${id}`),
  exportPdf: (id)          => api.get(`/analysis/documents/${id}/export/pdf`, { responseType: 'blob' }),
  exportReportPdf: (params = {}) => api.get('/analysis/reports/export/pdf', { params, responseType: 'blob' }),
  create:    (payload)     => api.post('/analysis/documents', payload, { timeout: 180_000 }),
  remove:    (id)          => api.delete(`/analysis/documents/${id}`),
  batches:   ()            => api.get('/analysis/import-batches'),
  createBatch: (payload)   => api.post('/analysis/import-batches', payload),
  removeBatch: (id, payload) => api.delete(`/analysis/import-batches/${id}`, { data: payload }),
  dashboard: (params = {}) => api.get('/analysis/dashboard', { params }),
  editaisListagem: (params = {}) => api.get('/analysis/editais-listagem', { params }),
}

export const datasheetsApi = {
  extract:  (formData) => api.post('/datasheets/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 90_000,
  }),
  torPreview: (formData) => api.post('/datasheets/tor/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120_000,
  }),
  torExportPdf: (payload) => api.post('/datasheets/tor/export/pdf', payload, {
    responseType: 'blob',
    timeout: 60_000,
  }),
  import:   (payload)  => api.post('/datasheets/import', payload),
  products: (params = {}) => api.get('/datasheets/products', { params }),
  compare:  (productAId, productBId) => api.get('/datasheets/compare', {
    params: { product_a_id: productAId, product_b_id: productBId },
  }),
  gaps: (params = {}) => api.get('/datasheets/gaps', { params }),
  competitiveIntelligence: (params = {}) => api.get('/datasheets/competitive-intelligence', { params }),
}

// ── Utilidade para download de blob ──────────────────────────────────────────
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a   = document.createElement('a')
  a.href     = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
