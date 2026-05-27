/**
 * pages/Configuracoes.jsx
 * ────────────────────────
 * Preferencias de conta, modelo padrao e informacoes do tenant.
 */

import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

const ROLE_LABELS = {
  admin:  { label: 'Administrador', color: 'text-amber border-amber/30 bg-amber/10'           },
  editor: { label: 'Editor',        color: 'text-azure-glow border-azure/30 bg-azure/10'      },
  viewer: { label: 'Visualizador',  color: 'text-gray-400 border-slate-border bg-slate-card'  },
}

function Section({ title, description, children }) {
  return (
    <div className="card space-y-4">
      <div className="border-b border-slate-border pb-3">
        <p className="font-display font-bold text-white text-sm">{title}</p>
        {description && <p className="text-xs text-gray-500 font-mono mt-0.5">{description}</p>}
      </div>
      {children}
    </div>
  )
}

export default function Configuracoes() {
  const { user }  = useAuth()
  const { toast } = useToast()

  const [defaultModel, setDefaultModel]       = useState(
    () => localStorage.getItem('default_model') || 'gpt'
  )
  const [autoRefresh, setAutoRefresh]         = useState(
    () => localStorage.getItem('auto_refresh') !== 'false'
  )
  const [compactMode, setCompactMode]         = useState(
    () => localStorage.getItem('compact_mode') === 'true'
  )

  const savePreferences = () => {
    localStorage.setItem('default_model',  defaultModel)
    localStorage.setItem('auto_refresh',   String(autoRefresh))
    localStorage.setItem('compact_mode',   String(compactMode))
    toast({ type: 'success', title: 'Preferências salvas', message: 'Configurações atualizadas com sucesso.' })
  }

  const roleCfg = ROLE_LABELS[user?.role] || ROLE_LABELS.viewer

  return (
    <div className="p-6 max-w-2xl space-y-6">

      {/* Header */}
      <div>
        <h1 className="font-display font-black text-2xl text-white">Configurações</h1>
        <p className="text-sm text-gray-500 font-mono mt-1">Preferências da conta e opções do sistema</p>
      </div>

      {/* ── Conta ──────────────────────────────────────────────────────────── */}
      <Section title="Conta" description="Informações do seu usuário e empresa">
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">Nome</p>
              <p className="text-sm text-white font-body">{user?.full_name || '—'}</p>
            </div>
            <div>
              <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">E-mail</p>
              <p className="text-sm text-white font-body truncate">{user?.email || '—'}</p>
            </div>
            <div>
              <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">Empresa (tenant)</p>
              <p className="text-sm text-white font-body">{user?.tenant?.name || '—'}</p>
              <p className="text-xs text-gray-600 font-mono mt-0.5">slug: {user?.tenant?.slug || '—'}</p>
            </div>
            <div>
              <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mb-1">Perfil</p>
              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono border ${roleCfg.color}`}>
                {roleCfg.label}
              </span>
            </div>
          </div>
        </div>
      </Section>

      {/* ── Modelo ─────────────────────────────────────────────────────────── */}
      <Section title="Modelo" description="Modelo padrao usado no ChatBot">
        <div className="space-y-3">
          {[
            {
              val:   'gpt',
              label: 'GPT-4o mini',
              desc:  'OpenAI · cloud · mais preciso · requer chave de API',
              badge: 'Recomendado',
            },
            {
              val:   'ollama',
              label: 'Llama 3 (Local)',
              desc:  'Ollama · roda localmente · sem custo de API · requer GPU/CPU',
              badge: null,
            },
          ].map(({ val, label, desc, badge }) => (
            <button
              key={val}
              onClick={() => setDefaultModel(val)}
              className={`w-full text-left px-4 py-3.5 rounded-xl border transition-all ${
                defaultModel === val
                  ? 'border-azure bg-azure/10'
                  : 'border-slate-border hover:border-azure/40 hover:bg-slate-hover'
              }`}
            >
              <div className="flex items-center justify-between mb-0.5">
                <p className="text-sm font-display font-bold text-white">{label}</p>
                <div className="flex items-center gap-2">
                  {badge && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded border border-green-match/30 bg-green-match/10 text-green-match">
                      {badge}
                    </span>
                  )}
                  <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
                    defaultModel === val ? 'border-azure' : 'border-slate-border'
                  }`}>
                    {defaultModel === val && (
                      <div className="w-2 h-2 rounded-full bg-azure" />
                    )}
                  </div>
                </div>
              </div>
              <p className="text-xs text-gray-500 font-mono">{desc}</p>
            </button>
          ))}
        </div>
      </Section>

      {/* ── Interface ──────────────────────────────────────────────────────── */}
      <Section title="Interface" description="Preferências de exibição">
        <div className="space-y-3">
          {[
            {
              key:   'autoRefresh',
              label: 'Atualização automática',
              desc:  'Atualizar Jobs e Controle automaticamente em segundo plano',
              value: autoRefresh,
              set:   setAutoRefresh,
            },
            {
              key:   'compactMode',
              label: 'Modo compacto',
              desc:  'Reduzir espaçamento nas tabelas e listas',
              value: compactMode,
              set:   setCompactMode,
            },
          ].map(({ key, label, desc, value, set }) => (
            <div key={key} className="flex items-center justify-between py-2">
              <div>
                <p className="text-sm text-white font-body">{label}</p>
                <p className="text-xs text-gray-500 font-mono mt-0.5">{desc}</p>
              </div>
              <button
                onClick={() => set(v => !v)}
                className={`relative w-11 h-6 rounded-full transition-all duration-200 flex-shrink-0 ${
                  value ? 'bg-azure' : 'bg-slate-border'
                }`}
              >
                <div className={`absolute top-1 w-4 h-4 bg-white rounded-full shadow-sm transition-all duration-200 ${
                  value ? 'left-6' : 'left-1'
                }`} />
              </button>
            </div>
          ))}
        </div>
      </Section>

      {/* ── Plano ──────────────────────────────────────────────────────────── */}
      <Section title="Plano atual">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-azure to-amber flex items-center justify-center flex-shrink-0">
            <span className="text-white text-xl">★</span>
          </div>
          <div>
            <p className="font-display font-bold text-white">Plano Pro</p>
            <p className="text-xs text-gray-400 font-mono mt-0.5">
              Upload ilimitado · ChatBot RAG · Analytics · Análise LLM · PNCP
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-600 font-mono mt-2 pt-3 border-t border-slate-border/40">
          Para alterar o plano ou gerenciar faturamento, entre em contato com suporte@tortec.com.br
        </p>
      </Section>

      {/* Salvar */}
      <div className="flex justify-end">
        <button onClick={savePreferences} className="btn-primary px-6 py-2.5">
          Salvar preferências
        </button>
      </div>
    </div>
  )
}
