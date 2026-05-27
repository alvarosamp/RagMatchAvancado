import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import torLogo from '../images/Tor.jpeg'
import { persistTheme, readStoredTheme } from '../utils/themeStorage'

function ThemeToggle({ theme, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`rounded-full border px-4 py-2 text-xs font-mono uppercase tracking-[0.24em] transition-colors ${
        theme === 'light'
          ? 'border-stone-300 bg-white text-stone-700 hover:border-red-400 hover:text-red-700'
          : 'border-slate-border bg-ink-50 text-gray-300 hover:border-azure/40 hover:text-white'
      }`}
    >
      {theme === 'light' ? 'Modo escuro' : 'Modo claro'}
    </button>
  )
}

export default function Login() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [theme, setTheme] = useState(() => readStoredTheme())
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })

  useEffect(() => {
    persistTheme(theme)
  }, [theme])

  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)

    try {
      await login(form.email, form.password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao autenticar. Verifique suas credenciais.')
    } finally {
      setLoading(false)
    }
  }

  const isLight = theme === 'light'

  return (
    <div className={`min-h-screen flex ${isLight ? 'bg-[#f7f1ea] text-stone-900' : 'bg-ink text-white'}`}>
      <div
        className={`hidden lg:flex lg:w-1/2 flex-col justify-between p-12 border-r relative overflow-hidden ${
          isLight ? 'border-stone-200 bg-[#f8f2ea]' : 'border-slate-border'
        }`}
      >
        <div
          className="absolute inset-0 opacity-[0.05]"
          style={{
            backgroundImage: isLight
              ? 'linear-gradient(rgba(185,28,28,0.55) 1px, transparent 1px), linear-gradient(90deg, rgba(185,28,28,0.55) 1px, transparent 1px)'
              : 'linear-gradient(rgba(220,38,38,1) 1px, transparent 1px), linear-gradient(90deg, rgba(220,38,38,1) 1px, transparent 1px)',
            backgroundSize: '40px 40px',
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            background: isLight
              ? 'radial-gradient(ellipse 60% 50% at 30% 40%, rgba(220,38,38,0.10) 0%, transparent 70%)'
              : 'radial-gradient(ellipse 60% 50% at 30% 40%, rgba(220,38,38,0.06) 0%, transparent 70%)',
          }}
        />

        <div className="relative z-10">
          <div className="flex items-center justify-between gap-3 mb-16">
            <div className="flex items-center gap-3">
              <div className="relative">
                <div className={`absolute inset-0 rounded-xl blur-md ${isLight ? 'bg-red-300 opacity-30' : 'bg-azure opacity-30'}`} />
                <img
                  src={torLogo}
                  alt="Tor Tecnologias"
                  className={`relative w-11 h-11 rounded-xl object-cover ring-1 ${isLight ? 'ring-red-300/70' : 'ring-azure/50'}`}
                />
              </div>
              <div>
                <span className={`font-display font-bold text-xl block leading-tight ${isLight ? 'text-stone-900' : 'text-white'}`}>
                  Tor Tecnologias
                </span>
                <span className={`font-mono text-[10px] tracking-widest uppercase ${isLight ? 'text-red-700' : 'text-azure-glow'}`}>
                  Plataforma de Licitacoes
                </span>
              </div>
            </div>
            <ThemeToggle theme={theme} onToggle={() => setTheme(isLight ? 'dark' : 'light')} />
          </div>

          <h1 className={`font-display font-extrabold text-5xl leading-tight mb-4 ${isLight ? 'text-stone-900' : 'text-white'}`}>
            Licitacoes
            <br />
            <span className={isLight ? 'text-red-700' : 'text-azure-glow'}>inteligentes</span>
            <br />
            para sua empresa
          </h1>
          <p className={`font-body text-lg leading-relaxed max-w-xs ${isLight ? 'text-stone-600' : 'text-gray-400'}`}>
            Analise automatizada de editais com OCR, IA e matching de produtos.
          </p>
        </div>

        <div className="relative z-10 grid grid-cols-3 gap-4">
          {[['RAG', 'Retrieval'], ['LLM', 'Reasoning'], ['MLOps', 'Tracking']].map(([title, sub]) => (
            <div
              key={title}
              className={`rounded-xl border p-4 transition-colors ${
                isLight
                  ? 'border-stone-200 bg-white/80 hover:border-red-300'
                  : 'border-slate-border bg-slate-card hover:border-azure/30'
              }`}
            >
              <p className={`font-display font-bold text-lg ${isLight ? 'text-red-700' : 'text-azure-glow'}`}>{title}</p>
              <p className={`font-mono text-xs ${isLight ? 'text-stone-500' : 'text-gray-500'}`}>{sub}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm animate-fade-up">
          <div className="flex items-center justify-between gap-3 mb-8 lg:hidden">
            <div className="flex items-center gap-2">
              <img src={torLogo} alt="Tor" className="w-8 h-8 rounded-lg object-cover" />
              <span className={`font-display font-bold ${isLight ? 'text-stone-900' : 'text-white'}`}>Tor Tecnologias</span>
            </div>
            <ThemeToggle theme={theme} onToggle={() => setTheme(isLight ? 'dark' : 'light')} />
          </div>

          <div
            className={`rounded-[28px] border p-6 shadow-xl ${
              isLight
                ? 'border-stone-200 bg-white/95 shadow-stone-200/50'
                : 'border-slate-border bg-slate-card/95 shadow-black/20'
            }`}
          >
            <div className="mb-8">
              <p className={`text-[11px] font-mono uppercase tracking-[0.28em] ${isLight ? 'text-stone-500' : 'text-gray-500'}`}>
                Acesso ao portal
              </p>
              <h1 className={`mt-3 font-display text-3xl font-black ${isLight ? 'text-stone-900' : 'text-white'}`}>Entrar</h1>
              <p className={`mt-2 text-sm leading-7 ${isLight ? 'text-stone-600' : 'text-gray-400'}`}>
                O cadastro inicial foi separado da tela publica. Novos usuarios continuam sendo criados pelo administrador dentro do portal.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className={`block text-xs font-mono mb-1.5 uppercase tracking-wider ${isLight ? 'text-stone-500' : 'text-gray-400'}`}>
                  Email
                </label>
                <input
                  className={`w-full rounded-lg px-4 py-2.5 text-sm transition-all ${
                    isLight
                      ? 'border border-stone-300 bg-stone-50 text-stone-900 placeholder-stone-400 focus:outline-none focus:border-red-400 focus:ring-1 focus:ring-red-200'
                      : 'input'
                  }`}
                  type="email"
                  placeholder="admin@empresa.com.br"
                  value={form.email}
                  onChange={(event) => set('email', event.target.value)}
                  required
                />
              </div>

              <div>
                <label className={`block text-xs font-mono mb-1.5 uppercase tracking-wider ${isLight ? 'text-stone-500' : 'text-gray-400'}`}>
                  Senha
                </label>
                <div className="relative">
                  <input
                    className={`w-full rounded-lg px-4 py-2.5 pr-20 text-sm transition-all ${
                      isLight
                        ? 'border border-stone-300 bg-stone-50 text-stone-900 placeholder-stone-400 focus:outline-none focus:border-red-400 focus:ring-1 focus:ring-red-200'
                        : 'input pr-20'
                    }`}
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={form.password}
                    onChange={(event) => set('password', event.target.value)}
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    className={`absolute right-2 top-1/2 -translate-y-1/2 px-2.5 py-1.5 rounded-md border text-xs font-mono transition-colors ${
                      isLight
                        ? 'border-stone-300 text-stone-500 hover:border-red-400 hover:text-red-700'
                        : 'border-slate-border text-gray-400 hover:text-white hover:border-azure/40'
                    }`}
                  >
                    {showPassword ? 'Ocultar' : 'Mostrar'}
                  </button>
                </div>
              </div>

              {error && (
                <div className={`rounded-lg px-4 py-2.5 border ${isLight ? 'bg-red-50 border-red-200' : 'bg-red-dim/30 border-red-fail/30'}`}>
                  <p className={`text-sm font-mono ${isLight ? 'text-red-700' : 'text-red-fail'}`}>{error}</p>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className={`w-full rounded-lg py-3 text-base font-display font-semibold transition-all disabled:opacity-40 ${
                  isLight
                    ? 'bg-red-700 text-white hover:bg-red-800'
                    : 'btn-primary'
                }`}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Aguarde...
                  </span>
                ) : 'Entrar'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
