/**
 * pages/Configuracoes.jsx
 * ────────────────────────
 * Preferencias de conta, modelo padrao e informacoes do tenant.
 */

import { useEffect, useState } from 'react'
import { authApi, opsApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

const ROLE_LABELS = {
  admin:  { label: 'Administrador', color: 'text-amber border-amber/30 bg-amber/10'           },
  editor: { label: 'Editor',        color: 'text-red-400 border-red-600/30 bg-red-600/10'      },
  viewer: { label: 'Visualizador',  color: 'text-gray-400 border-slate-700 bg-slate-800'  },
}
const AI_FEATURES_ENABLED = import.meta.env.VITE_AI_FEATURES_ENABLED === '1'

function Section({ title, description, children }) {
  return (
    <div className="card space-y-4">
      <div className="border-b border-slate-700 pb-3">
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
  const [quota, setQuota] = useState(null)
  const [quotaInput, setQuotaInput] = useState('')
  const [quotaSaving, setQuotaSaving] = useState(false)
  const [aiUsage, setAiUsage] = useState(null)
  const [aiUsageError, setAiUsageError] = useState(false)

  useEffect(() => {
    if (user?.role !== 'admin') return
    authApi.getAiJobQuota()
      .then(({ data }) => {
        setQuota(data)
        setQuotaInput(data.monthly_job_limit == null ? '' : String(data.monthly_job_limit))
      })
      .catch(() => toast({ type: 'error', message: 'Nao foi possivel carregar a quota de jobs.' }))
  }, [user?.role])

  useEffect(() => {
    if (user?.role !== 'admin') return
    opsApi.aiUsage()
      .then(({ data }) => setAiUsage(data))
      .catch(() => setAiUsageError(true))
  }, [user?.role])

  const saveQuota = async () => {
    const value = quotaInput.trim()
    const parsed = value === '' ? null : Number(value)
    if (parsed !== null && (!Number.isInteger(parsed) || parsed < 0 || parsed > 1_000_000)) {
      toast({ type: 'error', message: 'Informe um inteiro entre 0 e 1.000.000, ou deixe vazio para sem limite.' })
      return
    }
    setQuotaSaving(true)
    try {
      const { data } = await authApi.updateAiJobQuota(parsed)
      setQuota(data)
      toast({ type: 'success', message: 'Limite mensal atualizado.' })
    } catch (error) {
      toast({ type: 'error', message: error.response?.data?.detail || 'Nao foi possivel atualizar o limite.' })
    } finally {
      setQuotaSaving(false)
    }
  }

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

      {user?.role === 'admin' && (
        <Section title="Limite mensal de processamento" description="Controla novos jobs assíncronos desta empresa; periodo em UTC">
          {quota && (
            <p className="text-sm text-gray-300">
              Usados: <span className="font-semibold text-white">{quota.jobs_created}</span>
              {quota.monthly_job_limit != null ? ` / ${quota.monthly_job_limit}` : ' · sem limite'}
              {quota.remaining != null ? ` · restantes: ${quota.remaining}` : ''}
            </p>
          )}
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-gray-400">
              Novos jobs por mês
              <input
                type="number"
                min="0"
                max="1000000"
                step="1"
                value={quotaInput}
                onChange={(event) => setQuotaInput(event.target.value)}
                placeholder="Sem limite"
                className="input mt-1 block w-44 text-sm"
              />
            </label>
            <button onClick={saveQuota} disabled={quotaSaving || !quota} className="btn-primary px-4 py-2 disabled:opacity-40">
              {quotaSaving ? 'Salvando...' : 'Salvar limite'}
            </button>
          </div>
          <p className="text-xs text-gray-500">Vazio = sem limite; 0 = bloquear novos jobs. Reenvios idempotentes e retries do mesmo job não contam novamente.</p>
        </Section>
      )}

      {user?.role === 'admin' && (
        <Section title="Consumo de IA" description="Chamadas concluídas no mês UTC, somente desta empresa">
          {aiUsageError && <p className="text-xs text-red-400">Não foi possível carregar o consumo de IA.</p>}
          {!aiUsage && !aiUsageError && <p className="text-xs text-gray-500">Carregando consumo...</p>}
          {aiUsage && (
            <div className="space-y-3">
              <p className="text-sm text-gray-300">
                <span className="font-semibold text-white">{aiUsage.total_calls}</span> chamadas ·{' '}
                <span className={aiUsage.total_failed_calls ? 'text-red-400' : ''}>
                  {aiUsage.total_failed_calls} falhas
                </span> ·{' '}
                {aiUsage.input_tokens_reported.toLocaleString('pt-BR')} tokens de entrada ·{' '}
                {aiUsage.output_tokens_reported.toLocaleString('pt-BR')} tokens de saída
              </p>
              {aiUsage.calls_without_token_counts > 0 && (
                <p className="text-xs text-amber-400">
                  {aiUsage.calls_without_token_counts} chamada(s) sem contagem completa de tokens; os totais podem estar incompletos.
                </p>
              )}
              {aiUsage.groups.length === 0 ? (
                <p className="text-xs text-gray-500">Nenhuma chamada registrada neste mês.</p>
              ) : (
                <div className="space-y-1 text-xs font-mono">
                  {aiUsage.groups.map((group) => (
                    <div key={`${group.provider}:${group.model}:${group.operation}`} className="flex justify-between gap-2 text-gray-400">
                      <span className="truncate">{group.operation} · {group.provider}/{group.model}</span>
                      <span className="shrink-0 text-white">
                        {group.calls} concluídas{group.failed_calls ? ` · ${group.failed_calls} falhas` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-xs text-gray-500">Sem estimativa de custo. Tokens ausentes não são estimados.</p>
            </div>
          )}
        </Section>
      )}

      {AI_FEATURES_ENABLED && (
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
                className={`w-full text-left px-4 py-3.5 rounded-lg border transition-all ${
                  defaultModel === val
                    ? 'border-red-600 bg-red-600/10'
                    : 'border-slate-700 hover:border-red-600/40 hover:bg-slate-hover'
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
                      defaultModel === val ? 'border-red-600' : 'border-slate-700'
                    }`}>
                      {defaultModel === val && (
                        <div className="w-2 h-2 rounded-full bg-red-600" />
                      )}
                    </div>
                  </div>
                </div>
                <p className="text-xs text-gray-500 font-mono">{desc}</p>
              </button>
            ))}
          </div>
        </Section>
      )}

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
                  value ? 'bg-red-600' : 'bg-slate-border'
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
          <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-red-600 to-amber flex items-center justify-center flex-shrink-0">
            <span className="text-white text-xl">★</span>
          </div>
          <div>
            <p className="font-display font-bold text-white">Plano Pro</p>
            <p className="text-xs text-gray-400 font-mono mt-0.5">
              CRM comercial · Analytics · documentos · PNCP
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-600 font-mono mt-2 pt-3 border-t border-slate-700/40">
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
