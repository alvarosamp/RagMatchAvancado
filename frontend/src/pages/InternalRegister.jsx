import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import PasswordRequirements from '../components/PasswordRequirements'
import { useAuth } from '../contexts/AuthContext'
import torLogo from '../images/Tor.jpeg'
import { persistTheme, readStoredTheme } from '../utils/themeStorage'

const passwordPolicy = {
  minLen: 8,
  hasLower: (value) => /[a-z]/.test(value),
  hasUpper: (value) => /[A-Z]/.test(value),
  hasNumber: (value) => /\d/.test(value),
  hasSymbol: (value) => /[^A-Za-z0-9]/.test(value),
}

function isPasswordValid(password) {
  if (!password) return false
  return (
    password.length >= passwordPolicy.minLen &&
    passwordPolicy.hasLower(password) &&
    passwordPolicy.hasUpper(password) &&
    passwordPolicy.hasNumber(password) &&
    passwordPolicy.hasSymbol(password)
  )
}

export default function InternalRegister() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [theme, setTheme] = useState(() => readStoredTheme())
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    email: '',
    password: '',
    tenant_slug: '',
    tenant_name: '',
    full_name: '',
  })

  useEffect(() => {
    persistTheme(theme)
  }, [theme])

  const isLight = theme === 'light'
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')

    if (!isPasswordValid(form.password)) {
      setError('A senha nao atende aos requisitos minimos.')
      return
    }

    setLoading(true)
    try {
      await register({
        email: form.email,
        password: form.password,
        tenant_slug: form.tenant_slug,
        tenant_name: form.tenant_name,
        full_name: form.full_name,
      })
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Nao foi possivel concluir o cadastro interno.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`min-h-screen flex items-center justify-center p-8 ${isLight ? 'bg-[#f7f1ea] text-stone-900' : 'bg-ink text-white'}`}>
      <div className={`w-full max-w-xl rounded-[32px] border p-8 shadow-xl ${isLight ? 'border-stone-200 bg-white/95' : 'border-slate-border bg-slate-card/95'}`}>
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <img src={torLogo} alt="Tor Tecnologias" className="w-11 h-11 rounded-xl object-cover" />
            <div>
              <p className={`font-display text-xl font-black ${isLight ? 'text-stone-900' : 'text-white'}`}>Tor Tecnologias</p>
              <p className={`text-[11px] font-mono uppercase tracking-[0.28em] ${isLight ? 'text-red-700' : 'text-azure-glow'}`}>
                Cadastro interno
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setTheme(isLight ? 'dark' : 'light')}
            className={`rounded-full border px-4 py-2 text-xs font-mono uppercase tracking-[0.24em] ${isLight ? 'border-stone-300 text-stone-700' : 'border-slate-border text-gray-300'}`}
          >
            {isLight ? 'Modo escuro' : 'Modo claro'}
          </button>
        </div>

        <div className="mt-8">
          <p className={`text-sm leading-7 ${isLight ? 'text-stone-600' : 'text-gray-400'}`}>
            Essa rota ficou separada da tela publica. Use este acesso apenas para abrir um tenant novo quando realmente precisar.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className={`block text-xs font-mono mb-1.5 uppercase tracking-wider ${isLight ? 'text-stone-500' : 'text-gray-400'}`}>Nome da empresa</label>
            <input
              className={`w-full rounded-lg px-4 py-2.5 text-sm ${isLight ? 'border border-stone-300 bg-stone-50 text-stone-900' : 'input'}`}
              value={form.tenant_name}
              onChange={(event) => set('tenant_name', event.target.value)}
              required
            />
          </div>
          <div className="sm:col-span-2">
            <label className={`block text-xs font-mono mb-1.5 uppercase tracking-wider ${isLight ? 'text-stone-500' : 'text-gray-400'}`}>Identificador</label>
            <input
              className={`w-full rounded-lg px-4 py-2.5 text-sm font-mono ${isLight ? 'border border-stone-300 bg-stone-50 text-stone-900' : 'input font-mono'}`}
              value={form.tenant_slug}
              onChange={(event) => set('tenant_slug', event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
              required
            />
          </div>
          <div className="sm:col-span-2">
            <label className={`block text-xs font-mono mb-1.5 uppercase tracking-wider ${isLight ? 'text-stone-500' : 'text-gray-400'}`}>Seu nome</label>
            <input
              className={`w-full rounded-lg px-4 py-2.5 text-sm ${isLight ? 'border border-stone-300 bg-stone-50 text-stone-900' : 'input'}`}
              value={form.full_name}
              onChange={(event) => set('full_name', event.target.value)}
            />
          </div>
          <div className="sm:col-span-2">
            <label className={`block text-xs font-mono mb-1.5 uppercase tracking-wider ${isLight ? 'text-stone-500' : 'text-gray-400'}`}>Email</label>
            <input
              className={`w-full rounded-lg px-4 py-2.5 text-sm ${isLight ? 'border border-stone-300 bg-stone-50 text-stone-900' : 'input'}`}
              type="email"
              value={form.email}
              onChange={(event) => set('email', event.target.value)}
              required
            />
          </div>
          <div className="sm:col-span-2">
            <label className={`block text-xs font-mono mb-1.5 uppercase tracking-wider ${isLight ? 'text-stone-500' : 'text-gray-400'}`}>Senha</label>
            <div className="relative">
              <input
                className={`w-full rounded-lg px-4 py-2.5 pr-20 text-sm ${isLight ? 'border border-stone-300 bg-stone-50 text-stone-900' : 'input pr-20'}`}
                type={showPassword ? 'text' : 'password'}
                value={form.password}
                onChange={(event) => set('password', event.target.value)}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((current) => !current)}
                className={`absolute right-2 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-md border text-xs font-mono ${isLight ? 'border-stone-300 text-stone-500' : 'border-slate-border text-gray-400'}`}
              >
                {showPassword ? 'Ocultar' : 'Mostrar'}
              </button>
            </div>
            <PasswordRequirements value={form.password} />
          </div>

          {error && <p className="sm:col-span-2 text-sm font-mono text-red-fail">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className={`sm:col-span-2 rounded-lg py-3 text-base font-display font-semibold transition-all disabled:opacity-40 ${
              isLight ? 'bg-red-700 text-white hover:bg-red-800' : 'btn-primary'
            }`}
          >
            {loading ? 'Criando...' : 'Criar tenant'}
          </button>
        </form>
      </div>
    </div>
  )
}
