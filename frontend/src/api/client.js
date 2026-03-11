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
      localStorage.removeItem('access_token')
      localStorage.removeItem('tenant_slug')
      localStorage.removeItem('user_role')
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
  get:  (jobId)          => api.get(`/jobs/${jobId}`),
  list: (params = {})    => api.get('/jobs/', { params }),
}

export const exportApi = {
  xlsx: (id) => api.get(`/editais/${id}/export/xlsx`, { responseType: 'blob' }),
  pdf:  (id) => api.get(`/editais/${id}/export/pdf`,  { responseType: 'blob' }),
  csv:  (id) => api.get(`/editais/${id}/export/csv`,  { responseType: 'blob' }),
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