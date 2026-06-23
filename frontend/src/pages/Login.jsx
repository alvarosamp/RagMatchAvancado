import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import torLogo from '../images/Tor.jpeg'
import { persistTheme, readStoredTheme } from '../utils/themeStorage'

export default function Login() {
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [theme, setTheme]               = useState(() => readStoredTheme())
  const { login }                       = useAuth()
  const navigate                        = useNavigate()
  const [form, setForm]                 = useState({ email: '', password: '' })

  useEffect(() => { persistTheme(theme) }, [theme])

  const set = (key, val) => setForm(c => ({ ...c, [key]: val }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(form.email, form.password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Credenciais inválidas.')
    } finally {
      setLoading(false)
    }
  }

  const isLight = theme === 'light'

  return (
    <div className={`min-h-screen flex ${isLight ? 'bg-white' : 'bg-ink'}`}>

      {/* ── Painel esquerdo — branding ─────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-[52%] flex-col justify-between bg-[#b91c1c] p-14 select-none">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <img
            src={torLogo}
            alt="Tor Tecnologias"
            className="w-10 h-10 rounded-xl object-cover ring-2 ring-white/20"
          />
          <div>
            <p className="font-display font-bold text-white text-base leading-tight">Tor Tecnologias</p>
            <p className="text-red-200 text-[10px] font-mono uppercase tracking-widest">Portal de Licitações</p>
          </div>
        </div>

        {/* Headline */}
        <div>
          <h1 className="font-display font-extrabold text-white text-5xl leading-[1.15] mb-5">
            Gestão de<br />editais em<br />um só lugar.
          </h1>
          <p className="text-red-200 text-base leading-relaxed max-w-xs">
            Receba, organize e acompanhe licitações com o seu time comercial alinhado.
          </p>
        </div>

        {/* Rodapé */}
        <p className="text-red-300/60 text-xs font-mono">
          © {new Date().getFullYear()} Tor Tecnologias
        </p>
      </div>

      {/* ── Painel direito — formulário ───────────────────────────────── */}
      <div className={`flex-1 flex flex-col items-center justify-center p-8 ${isLight ? 'bg-white' : 'bg-ink'}`}>

        {/* Logo mobile */}
        <div className="flex items-center gap-2 mb-10 lg:hidden">
          <img src={torLogo} alt="Tor" className="w-8 h-8 rounded-lg object-cover" />
          <span className={`font-display font-bold ${isLight ? 'text-stone-900' : 'text-white'}`}>
            Tor Tecnologias
          </span>
        </div>

        <div className="w-full max-w-[340px]">
          <div className="mb-8">
            <h2 className={`font-display text-2xl font-bold mb-1 ${isLight ? 'text-stone-900' : 'text-white'}`}>
              Acessar portal
            </h2>
            <p className={`text-sm ${isLight ? 'text-stone-500' : 'text-gray-500'}`}>
              Entre com suas credenciais para continuar.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className={`block text-xs font-mono mb-1.5 ${isLight ? 'text-stone-500' : 'text-gray-500'}`}>
                E-mail
              </label>
              <input
                type="email"
                placeholder="voce@empresa.com"
                value={form.email}
                onChange={e => set('email', e.target.value)}
                required
                className={`w-full rounded-lg px-4 py-2.5 text-sm transition-all ${
                  isLight
                    ? 'border border-stone-200 bg-stone-50 text-stone-900 placeholder-stone-300 focus:outline-none focus:border-red-400 focus:bg-white focus:ring-1 focus:ring-red-100'
                    : 'input'
                }`}
              />
            </div>

            <div>
              <label className={`block text-xs font-mono mb-1.5 ${isLight ? 'text-stone-500' : 'text-gray-500'}`}>
                Senha
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="••••••••"
                  value={form.password}
                  onChange={e => set('password', e.target.value)}
                  required
                  className={`w-full rounded-lg px-4 py-2.5 pr-20 text-sm transition-all ${
                    isLight
                      ? 'border border-stone-200 bg-stone-50 text-stone-900 placeholder-stone-300 focus:outline-none focus:border-red-400 focus:bg-white focus:ring-1 focus:ring-red-100'
                      : 'input pr-20'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  className={`absolute right-2.5 top-1/2 -translate-y-1/2 text-[11px] font-mono transition-colors ${
                    isLight ? 'text-stone-400 hover:text-stone-600' : 'text-gray-600 hover:text-white'
                  }`}
                >
                  {showPassword ? 'Ocultar' : 'Mostrar'}
                </button>
              </div>
            </div>

            {error && (
              <p className={`text-xs font-mono ${isLight ? 'text-red-700' : 'text-red-fail'}`}>
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg py-2.5 text-sm font-semibold bg-[#b91c1c] text-white hover:bg-[#991b1b] transition-colors disabled:opacity-40"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Aguarde…
                </span>
              ) : 'Entrar'}
            </button>
          </form>

          {/* Tema */}
          <div className="mt-8 flex justify-center">
            <button
              type="button"
              onClick={() => setTheme(isLight ? 'dark' : 'light')}
              className={`text-xs font-mono transition-colors ${
                isLight ? 'text-stone-400 hover:text-stone-600' : 'text-gray-600 hover:text-gray-400'
              }`}
            >
              {isLight ? 'Mudar para modo escuro' : 'Mudar para modo claro'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
