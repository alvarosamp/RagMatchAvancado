/**
 * pages/Login.jsx
 * ────────────────
 * Tela de login e cadastro de novo tenant.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import PasswordRequirements from '../components/PasswordRequirements'

const passwordPolicy = {
  minLen: 8,
  hasLower: (s) => /[a-z]/.test(s),
  hasUpper: (s) => /[A-Z]/.test(s),
  hasNumber: (s) => /\d/.test(s),
  hasSymbol: (s) => /[^A-Za-z0-9]/.test(s),
}

function isPasswordValid(pw) {
  if (!pw) return false
  return (
    pw.length >= passwordPolicy.minLen &&
    passwordPolicy.hasLower(pw) &&
    passwordPolicy.hasUpper(pw) &&
    passwordPolicy.hasNumber(pw) &&
    passwordPolicy.hasSymbol(pw)
  )
}

export default function Login() {
  const [mode,    setMode]    = useState('login')   // 'login' | 'register'
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const { login, register }   = useAuth()
  const navigate              = useNavigate()

  const [form, setForm] = useState({
    email: '', password: '',
    tenant_slug: '', tenant_name: '', full_name: '',
  })

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    // Evita round-trip desnecessário: validação rápida no cliente.
    if (mode === 'register' && !isPasswordValid(form.password)) {
      setLoading(false)
      setError('Sua senha não atende aos requisitos. Verifique a lista abaixo do campo.')
      return
    }

    try {
      if (mode === 'login') {
        await login(form.email, form.password)
      } else {
        await register({
          email:       form.email,
          password:    form.password,
          tenant_slug: form.tenant_slug,
          tenant_name: form.tenant_name,
          full_name:   form.full_name,
        })
      }
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao autenticar. Verifique suas credenciais.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex">

      {/* ── Painel esquerdo — branding ──────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 border-r border-slate-border relative overflow-hidden">
        {/* Grade de fundo */}
        <div className="absolute inset-0 opacity-5"
          style={{ backgroundImage: 'linear-gradient(rgba(59,130,246,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.5) 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-9 h-9 rounded-xl bg-azure flex items-center justify-center text-white font-mono font-bold">EM</div>
            <span className="font-display font-bold text-xl text-white">Edital Matcher</span>
          </div>

          <h1 className="font-display font-extrabold text-5xl text-white leading-tight mb-4">
            Matching<br />
            <span className="text-azure-glow">inteligente</span><br />
            de licitações
          </h1>
          <p className="text-gray-400 font-body text-lg leading-relaxed max-w-xs">
            OCR, embeddings e LLM trabalhando juntos para encontrar os produtos certos em cada edital.
          </p>
        </div>

        {/* Stats decorativas */}
        <div className="relative z-10 grid grid-cols-3 gap-4">
          {[['RAG', 'Retrieval'], ['LLM', 'Reasoning'], ['MLOps', 'Tracking']].map(([title, sub]) => (
            <div key={title} className="card py-4">
              <p className="font-display font-bold text-azure-glow text-lg">{title}</p>
              <p className="font-mono text-xs text-gray-500">{sub}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Painel direito — formulário ──────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm animate-fade-up">

          {/* Tabs */}
          <div className="flex gap-1 p-1 bg-ink-50 rounded-xl mb-8 border border-slate-border">
            {[['login', 'Entrar'], ['register', 'Cadastrar']].map(([m, label]) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError('') }}
                className={`flex-1 py-2 rounded-lg text-sm font-display font-semibold transition-all duration-200
                  ${mode === m ? 'bg-azure text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
              >
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">

            {mode === 'register' && (
              <>
                <div>
                  <label className="block text-xs font-mono text-gray-400 mb-1.5 uppercase tracking-wider">Nome da empresa</label>
                  <input className="input" placeholder="Prefeitura de São Paulo"
                    value={form.tenant_name} onChange={e => set('tenant_name', e.target.value)} required />
                </div>
                <div>
                  <label className="block text-xs font-mono text-gray-400 mb-1.5 uppercase tracking-wider">Identificador <span className="text-gray-600">(slug)</span></label>
                  <input className="input font-mono" placeholder="prefeitura-sp"
                    value={form.tenant_slug} onChange={e => set('tenant_slug', e.target.value.toLowerCase().replace(/[^a-z0-9-]/g,''))} required />
                  <p className="text-xs text-gray-600 mt-1 font-mono">apenas letras minúsculas, números e hífens</p>
                </div>
                <div>
                  <label className="block text-xs font-mono text-gray-400 mb-1.5 uppercase tracking-wider">Seu nome</label>
                  <input className="input" placeholder="João Silva"
                    value={form.full_name} onChange={e => set('full_name', e.target.value)} />
                </div>
              </>
            )}

            <div>
              <label className="block text-xs font-mono text-gray-400 mb-1.5 uppercase tracking-wider">Email</label>
              <input className="input" type="email" placeholder="admin@empresa.com.br"
                value={form.email} onChange={e => set('email', e.target.value)} required />
            </div>

            <div>
              <label className="block text-xs font-mono text-gray-400 mb-1.5 uppercase tracking-wider">Senha</label>
              <div className="relative">
                <input className="input pr-20" type={showPassword ? 'text' : 'password'} placeholder="••••••••"
                  value={form.password} onChange={e => set('password', e.target.value)} required />
                <button
                  type="button"
                  onClick={() => setShowPassword(s => !s)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-md border border-slate-border text-xs font-mono text-gray-400 hover:text-white hover:border-azure/40 transition-colors"
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                >
                  {showPassword ? 'Ocultar' : 'Mostrar'}
                </button>
              </div>
              {mode === 'register' && (
                <PasswordRequirements value={form.password} />
              )}
            </div>

            {error && (
              <div className="bg-red-dim/30 border border-red-fail/30 rounded-lg px-4 py-2.5">
                <p className="text-sm text-red-fail font-mono">{error}</p>
              </div>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full mt-2 py-3 text-base">
              {loading
                ? <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Aguarde…
                  </span>
                : mode === 'login' ? 'Entrar' : 'Criar conta'
              }
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
