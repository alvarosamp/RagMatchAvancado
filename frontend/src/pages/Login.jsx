import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useMarket } from '../contexts/MarketContext'
import torLogo from '../images/Tor.jpeg'
import { persistTheme, readStoredTheme } from '../utils/themeStorage'

export default function Login() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [theme, setTheme] = useState(() => readStoredTheme('light'))
  const [form, setForm] = useState({ email: '', password: '' })
  const { login } = useAuth()
  const market = useMarket()
  const navigate = useNavigate()

  const isLight = theme === 'light'

  useEffect(() => {
    persistTheme(theme)
    document.documentElement.classList.toggle('light', isLight)
    document.documentElement.classList.toggle('dark', !isLight)
    document.body.classList.toggle('theme-light', isLight)
  }, [theme, isLight])

  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }))

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(form.email, form.password)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Credenciais invalidas.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f5f7fb] text-slate-950 dark:bg-slate-950 dark:text-white">
      <div className="grid min-h-screen lg:grid-cols-[0.95fr_1.05fr]">
        <section className="hidden border-r border-blue-100 bg-[#edf3fa] px-12 py-10 lg:flex lg:flex-col lg:justify-between dark:border-slate-800 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <img src={torLogo} alt={market.app.product_name} className="h-11 w-11 rounded-lg object-cover" />
            <div>
              <p className="text-base font-semibold text-slate-950 dark:text-white">{market.app.product_name}</p>
              <p className="text-xs font-medium uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">{market.app.tagline}</p>
            </div>
          </div>

          <div className="max-w-xl">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-500 dark:text-slate-400">Business Intelligence</p>
            <h1 className="mt-4 text-5xl font-bold leading-tight tracking-tight text-slate-950 dark:text-white">
              {market.app.description}
            </h1>
            <p className="mt-5 max-w-md text-base leading-7 text-slate-600 dark:text-slate-300">
              {market.app.footer_secondary}
            </p>

            <div className="mt-10 grid max-w-lg grid-cols-3 gap-3">
              {[
                ['BI', 'Itens categorizados'],
                ['CRM', 'Funil comercial'],
                ['PDF', 'Relatorios executivos'],
              ].map(([value, label]) => (
                <div key={value} className="rounded-lg border border-blue-100 bg-white px-4 py-4 dark:border-slate-800 dark:bg-slate-950">
                  <p className="text-xl font-bold text-brand dark:text-blue-300">{value}</p>
                  <p className="mt-1 text-xs leading-4 text-slate-500 dark:text-slate-400">{label}</p>
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs text-slate-500 dark:text-slate-400">
            {new Date().getFullYear()} {market.app.product_name}
          </p>
        </section>

        <section className="flex items-center justify-center px-6 py-10">
          <div className="w-full max-w-[420px]">
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              <img src={torLogo} alt={market.app.product_name} className="h-10 w-10 rounded-lg object-cover" />
              <div>
                <p className="font-semibold text-slate-950 dark:text-white">{market.app.product_name}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">{market.app.tagline}</p>
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-7">
                <p className="text-sm font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-slate-400">Acesso</p>
                <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-950 dark:text-white">Entrar no portal</h2>
                <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Use suas credenciais para continuar.</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">E-mail</label>
                  <input
                    type="email"
                    placeholder="voce@empresa.com"
                    value={form.email}
                    onChange={(event) => set('email', event.target.value)}
                    required
                    className="input"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-300">Senha</label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      placeholder="Digite sua senha"
                      value={form.password}
                      onChange={(event) => set('password', event.target.value)}
                      required
                      className="input pr-24"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((value) => !value)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-500 hover:text-brand dark:text-slate-400 dark:hover:text-blue-300"
                    >
                      {showPassword ? 'Ocultar' : 'Mostrar'}
                    </button>
                  </div>
                </div>

                {error && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
                    {error}
                  </div>
                )}

                <button type="submit" disabled={loading} className="btn-primary w-full">
                  {loading ? 'Entrando...' : 'Entrar'}
                </button>
              </form>

              <button
                type="button"
                onClick={() => setTheme(isLight ? 'dark' : 'light')}
                className="mt-6 w-full text-center text-xs font-medium text-slate-500 hover:text-brand dark:text-slate-400 dark:hover:text-blue-300"
              >
                {isLight ? 'Usar modo escuro' : 'Usar modo claro'}
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
