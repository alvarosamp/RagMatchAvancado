import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/client'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const response = await authApi.requestPasswordReset({ email: email.trim().toLowerCase() })
      setMessage(response.data.message)
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Nao foi possivel processar a solicitacao.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#f5f7fb] p-6 dark:bg-slate-950">
      <section className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <Link to="/login" className="text-sm font-semibold text-brand dark:text-blue-300">← Voltar ao login</Link>
        <h1 className="mt-6 text-3xl font-bold text-slate-950 dark:text-white">Recuperar senha</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">Informe seu e-mail. Se houver uma conta ativa, enviaremos um link de uso único.</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">E-mail
            <input className="input mt-1.5" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" />
          </label>
          {message && <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{message}</p>}
          {error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <button className="btn-primary w-full" type="submit" disabled={loading || Boolean(message)}>
            {loading ? 'Enviando...' : 'Enviar instruções'}
          </button>
        </form>
      </section>
    </main>
  )
}
