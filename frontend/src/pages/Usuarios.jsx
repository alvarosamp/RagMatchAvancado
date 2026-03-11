/**
 * pages/Usuarios.jsx
 * ───────────────────
 * Gerenciamento de usuários do tenant (só admin vê).
 */

import { useEffect, useState } from 'react'
import { authApi } from '../api/client'

const ROLE_CFG = {
  admin:  { label: 'Admin',  cls: 'badge-atende'    },
  editor: { label: 'Editor', cls: 'badge-verificar' },
  viewer: { label: 'Viewer', cls: 'badge-pending'   },
}

export default function Usuarios() {
  const [users,   setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const [form,    setForm]    = useState({ email: '', password: '', full_name: '', role: 'editor' })
  const [creating,setCreating]= useState(false)
  const [showForm,setShowForm]= useState(false)

  const load = () => {
    authApi.listUsers()
      .then(r => setUsers(r.data))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleCreate = async (e) => {
    e.preventDefault()
    setError(''); setCreating(true)
    try {
      await authApi.createUser(form)
      setForm({ email: '', password: '', full_name: '', role: 'editor' })
      setShowForm(false)
      load()
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao criar usuário.')
    } finally { setCreating(false) }
  }

  return (
    <div className="p-8 max-w-3xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <p className="text-xs font-mono text-gray-500 uppercase tracking-widest mb-1">Admin</p>
          <h1 className="font-display font-bold text-3xl text-white">Usuários</h1>
          <p className="text-gray-400 text-sm mt-1">{users.length} usuário{users.length !== 1 && 's'} neste tenant</p>
        </div>
        <button onClick={() => setShowForm(f => !f)} className="btn-primary">
          {showForm ? 'Cancelar' : '+ Novo usuário'}
        </button>
      </div>

      {/* Formulário */}
      {showForm && (
        <div className="card mb-6 animate-fade-up">
          <p className="font-display font-semibold text-white mb-4">Criar novo usuário</p>
          <form onSubmit={handleCreate} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-mono text-gray-400 mb-1.5">Email</label>
                <input className="input" type="email" placeholder="usuario@empresa.com" value={form.email} onChange={e => set('email', e.target.value)} required />
              </div>
              <div>
                <label className="block text-xs font-mono text-gray-400 mb-1.5">Senha</label>
                <input className="input" type="password" placeholder="mínimo 8 caracteres" value={form.password} onChange={e => set('password', e.target.value)} required />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-mono text-gray-400 mb-1.5">Nome completo</label>
                <input className="input" placeholder="Maria Silva" value={form.full_name} onChange={e => set('full_name', e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-mono text-gray-400 mb-1.5">Role</label>
                <select className="input" value={form.role} onChange={e => set('role', e.target.value)}>
                  <option value="editor">Editor</option>
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
            {error && <p className="text-sm text-red-fail font-mono">{error}</p>}
            <button type="submit" disabled={creating} className="btn-primary w-full">
              {creating ? 'Criando…' : 'Criar usuário'}
            </button>
          </form>
        </div>
      )}

      {/* Lista */}
      {loading ? (
        <div className="space-y-3">
          {[1,2].map(i => <div key={i} className="h-16 bg-slate-card rounded-xl border border-slate-border animate-pulse" />)}
        </div>
      ) : (
        <div className="space-y-2">
          {users.map((u, i) => {
            const cfg = ROLE_CFG[u.role] || ROLE_CFG.viewer
            return (
              <div key={u.id} className="card flex items-center gap-4 py-4 animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                <div className="w-9 h-9 rounded-full bg-azure/10 border border-azure/20 flex items-center justify-center text-azure-glow font-display font-bold text-sm flex-shrink-0">
                  {(u.full_name || u.email)[0].toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-body font-medium text-white text-sm">{u.full_name || '—'}</p>
                  <p className="text-xs text-gray-500 font-mono truncate">{u.email}</p>
                </div>
                <span className={cfg.cls}>{cfg.label}</span>
                <div className={`w-2 h-2 rounded-full ${u.is_active ? 'bg-green-match' : 'bg-red-fail'}`} />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
