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
import { clearPortalSessionStorage } from '../utils/authStorage'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user,    setUser]    = useState(null)
  const [loading, setLoading] = useState(true)   // true enquanto verifica token salvo

  // Ao montar, verifica se há token salvo e carrega o usuário
  useEffect(() => {
    if (localStorage.getItem('demo_mode') === '1') {
      setUser({
        id: 'demo-user',
        email: 'demo@empresa.com.br',
        full_name: 'Demo Produto',
        role: 'admin',
        tenant_id: 'demo',
      })
      setLoading(false)
      return
    }

    authApi.me()
      .then(res => setUser(res.data))
      .catch(() => clearPortalSessionStorage())
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email, password) => {
    const res = await authApi.login({ email, password })
    const { tenant_slug, role } = res.data

    localStorage.removeItem('access_token')
    localStorage.setItem('tenant_slug',  tenant_slug)
    localStorage.setItem('user_role',    role)

    // Carrega dados completos do usuário
    const meRes = await authApi.me()
    setUser(meRes.data)
    return meRes.data
  }, [])

  const enterDemo = useCallback(() => {
    const demoUser = {
      id: 'demo-user',
      email: 'demo@empresa.com.br',
      full_name: 'Demo Produto',
      role: 'admin',
      tenant_id: 'demo',
    }

    localStorage.removeItem('access_token')
    localStorage.setItem('demo_mode', '1')
    localStorage.setItem('tenant_slug', 'demo')
    localStorage.setItem('user_role', 'admin')
    setUser(demoUser)
    return demoUser
  }, [])

  const register = useCallback(async (payload) => {
    const res = await authApi.register(payload)
    const { tenant_slug, role } = res.data

    localStorage.removeItem('access_token')
    localStorage.setItem('tenant_slug',  tenant_slug)
    localStorage.setItem('user_role',    role)

    const meRes = await authApi.me()
    setUser(meRes.data)
    return meRes.data
  }, [])

  const logout = useCallback(async () => {
    await authApi.logout().catch(() => null)
    clearPortalSessionStorage()
    setUser(null)
    window.location.href = '/login'
  }, [])

  const isAdmin  = user?.role === 'admin'
  const isEditor = user?.role === 'admin' || user?.role === 'editor'

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register, enterDemo, isAdmin, isEditor }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider')
  return ctx
}
