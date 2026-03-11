/**
 * contexts/AuthContext.jsx
 * ─────────────────────────
 * Estado global de autenticação.
 *
 * CONCEITO: Context API do React
 *   Permite compartilhar estado (usuário logado, token, tenant)
 *   entre qualquer componente sem precisar passar props manualmente.
 *
 *   Qualquer componente pode chamar:
 *     const { user, login, logout } = useAuth()
 */

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { authApi } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null)
  const [loading, setLoading] = useState(true)   // true enquanto verifica token salvo

  // Ao montar, verifica se há token salvo e carrega o usuário
  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) { setLoading(false); return }

    authApi.me()
      .then(res => setUser(res.data))
      .catch(() => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('tenant_slug')
        localStorage.removeItem('user_role')
      })
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email, password) => {
    const res = await authApi.login({ email, password })
    const { access_token, tenant_slug, role } = res.data

    localStorage.setItem('access_token', access_token)
    localStorage.setItem('tenant_slug',  tenant_slug)
    localStorage.setItem('user_role',    role)

    // Carrega dados completos do usuário
    const meRes = await authApi.me()
    setUser(meRes.data)
    return meRes.data
  }, [])

  const register = useCallback(async (payload) => {
    const res = await authApi.register(payload)
    const { access_token, tenant_slug, role } = res.data

    localStorage.setItem('access_token', access_token)
    localStorage.setItem('tenant_slug',  tenant_slug)
    localStorage.setItem('user_role',    role)

    const meRes = await authApi.me()
    setUser(meRes.data)
    return meRes.data
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('tenant_slug')
    localStorage.removeItem('user_role')
    setUser(null)
    window.location.href = '/login'
  }, [])

  const isAdmin  = user?.role === 'admin'
  const isEditor = user?.role === 'admin' || user?.role === 'editor'

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register, isAdmin, isEditor }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider')
  return ctx
}
