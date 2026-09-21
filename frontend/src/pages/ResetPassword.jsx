import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { authApi } from '../api/client'
import PasswordRequirements from '../components/PasswordRequirements'

function validPassword(value) {
  return value.length >= 8 && /[a-z]/.test(value) && /[A-Z]/.test(value) && /\d/.test(value) && /[^A-Za-z0-9]/.test(value)
}

export default function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setError('')
    if (!token) return setError('Link de recuperação inválido.')
    if (!validPassword(password)) return setError('A nova senha não atende aos requisitos.')
    if (password !== confirmation) return setError('As senhas não coincidem.')
    setLoading(true)
    try {
      await authApi.confirmPasswordReset({ token, new_password: password })
      setSuccess(true)
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Não foi possível redefinir a senha.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#f5f7fb] p-6 dark:bg-slate-950">
      <section className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <h1 className="text-3xl font-bold text-slate-950 dark:text-white">Criar nova senha</h1>
        {success ? (
          <div className="mt-6 space-y-4">
            <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">Senha redefinida e sessões anteriores encerradas.</p>
            <Link to="/login" className="btn-primary block w-full text-center">Entrar</Link>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Nova senha
              <input className="input mt-1.5" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required autoComplete="new-password" />
            </label>
            <PasswordRequirements value={password} />
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Confirmar nova senha
              <input className="input mt-1.5" type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required autoComplete="new-password" />
            </label>
            {error && <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</p>}
            <button className="btn-primary w-full" type="submit" disabled={loading}>{loading ? 'Salvando...' : 'Redefinir senha'}</button>
          </form>
        )}
      </section>
    </main>
  )
}
