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
})

// ── Interceptor de REQUEST — injeta JWT ──────────────────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Interceptor de RESPONSE — trata 401 ─────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expirado ou inválido → limpa storage e redireciona para login
      clearPortalSessionStorage()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

// ── Helpers por domínio ───────────────────────────────────────────────────────

export const authApi = {
  register: (data)  => api.post('/auth/register', data),
  login:    (data)  => api.post('/auth/login', data),
  me:       ()      => api.get('/auth/me'),
  createUser: (data) => api.post('/auth/users', data),
  listUsers:  ()    => api.get('/auth/users'),
}

export const editaisApi = {
  list:    ()                   => api.get('/editais/'),
  upload:  (formData)           => api.post('/editais/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60_000,
  }),
  addRequirements: (id, reqs)   => api.post(`/editais/${id}/requirements`, reqs),
  match:   (id)                 => api.post(`/editais/${id}/match`),
  results: (id)                 => api.get(`/editais/${id}/results`),
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

export const crmApi = {
  importSalesProcesses: (formData) =>
    api.post('/crm/imports/sales-processes', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120_000,
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
  chat: (editalId, body) => api.post(`/editais/${editalId}/chat`, body, { timeout: 60_000 }),
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
   * Importa um edital do PNCP para o sistema (enfileira job).
   * @param {string} idPncp
   */
  importEdital: (idPncp) => api.post('/pncp/import', { id_pncp: idPncp }, { timeout: 30_000 }),

  /**
   * Retorna detalhes de um edital PNCP específico.
   */
  detail:       (idPncp) => api.get(`/pncp/${encodeURIComponent(idPncp)}`),
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
