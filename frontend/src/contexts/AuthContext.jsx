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
  const [logoutError, setLogoutError] = useState('')
  const [loading, setLoading] = useState(true)   // true enquanto verifica token salvo

  // Ao montar, verifica se há token salvo e carrega o usuário
  useEffect(() => {
    authApi.me()
      .then(res => setUser(res.data))
      .catch(() => clearPortalSessionStorage())
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (email, password, rememberMe = false) => {
    const res = await authApi.login({ email, password, remember_me: rememberMe })
    window.ragmatchSession?.resume()
    const { tenant_slug, role } = res.data

    localStorage.removeItem('access_token')
    localStorage.setItem('tenant_slug',  tenant_slug)
    localStorage.setItem('user_role',    role)

    // Carrega dados completos do usuário
    const meRes = await authApi.me()
    setUser(meRes.data)
    return meRes.data
  }, [])

  const register = useCallback(async (payload) => {
    const res = await authApi.register(payload)
    window.ragmatchSession?.resume()
    const { tenant_slug, role } = res.data

    localStorage.removeItem('access_token')
    localStorage.setItem('tenant_slug',  tenant_slug)
    localStorage.setItem('user_role',    role)

    const meRes = await authApi.me()
    setUser(meRes.data)
    return meRes.data
  }, [])

  const updateProfile = useCallback(async (payload) => {
    const response = await authApi.updateProfile(payload)
    setUser(response.data)
    return response.data
  }, [])

  const logout = useCallback(async () => {
    window.ragmatchSession?.stop()
    setLogoutError('')
    try {
      await authApi.logout()
    } catch {
      window.ragmatchSession?.resume()
      setLogoutError('Não foi possível encerrar a sessão. Confira sua conexão e tente sair novamente.')
      return
    }
    clearPortalSessionStorage()
    setUser(null)
    window.location.href = '/login'
  }, [])

  const isAdmin  = user?.role === 'admin'
  const isEditor = user?.role === 'admin' || user?.role === 'editor'

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, register, updateProfile, isAdmin, isEditor }}>
      {logoutError && <div role="alert" className="fixed bottom-4 left-4 right-4 z-[100] rounded-lg bg-red-50 p-4 text-sm text-red-800 shadow-lg">{logoutError}</div>}
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider')
  return ctx
}
