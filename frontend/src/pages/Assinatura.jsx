import { useMemo, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

const STORAGE_KEY = 'tor_subscription_plan'

const PLANS = [
  {
    id: 'starter',
    name: 'Starter',
    price: 'R$ 299',
    cadence: '/mes',
    description: 'Para testar o fluxo de captacao e analise inicial de editais.',
    limits: ['3 usuarios', '30 editais/mes', 'Radar PNCP basico', 'Exportacao CSV/XLSX'],
    features: ['Busca PNCP', 'Upload de edital', 'Resumo IA', 'Relatorio basico'],
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 'R$ 799',
    cadence: '/mes',
    description: 'Para operacao comercial completa, com matching tecnico e CRM.',
    limits: ['10 usuarios', '150 editais/mes', 'Catalogo tecnico', 'CRM de licitacoes'],
    features: ['Radar PNCP 24/7', 'Matching edital x catalogo', 'Propostas e documentos', 'Checklist de habilitacao', 'Precificacao'],
    recommended: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: 'Sob consulta',
    cadence: '',
    description: 'Para times maiores, multiunidade, integracoes e governanca.',
    limits: ['Usuarios ilimitados', 'Volume customizado', 'SLA dedicado', 'Integracoes externas'],
    features: ['WhatsApp/e-mail/calendario', 'Compras.gov/BLL', 'CRM externo', 'Auditoria', 'Suporte prioritario'],
  },
]

const PERMISSIONS = [
  ['Visualizar planos', 'Todos os usuarios autenticados'],
  ['Selecionar ou trocar plano', 'Apenas administradores'],
  ['Alterar limites comerciais', 'Apenas administradores'],
  ['Gerenciar faturamento', 'Apenas administradores'],
]

function readPlan() {
  return localStorage.getItem(STORAGE_KEY) || 'pro'
}

function PlanCard({ plan, selected, canSelect, onSelect }) {
  return (
    <article className={`rounded-lg border bg-white p-5 shadow-sm dark:bg-slate-800 ${
      selected
        ? 'border-blue-300 dark:border-blue-700'
        : 'border-slate-200 dark:border-slate-700'
    }`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-950 dark:text-white">{plan.name}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">{plan.description}</p>
        </div>
        {plan.recommended && (
          <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
            Recomendado
          </span>
        )}
      </div>

      <div className="mt-5 flex items-end gap-1">
        <span className="text-3xl font-bold text-slate-950 dark:text-white">{plan.price}</span>
        {plan.cadence && <span className="pb-1 text-sm text-slate-500 dark:text-slate-400">{plan.cadence}</span>}
      </div>

      <div className="mt-5 space-y-2">
        {plan.limits.map((item) => (
          <div key={item} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
            {item}
          </div>
        ))}
      </div>

      <div className="mt-5 border-t border-slate-200 pt-4 dark:border-slate-700">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Inclui</p>
        <div className="mt-3 space-y-2">
          {plan.features.map((item) => (
            <p key={item} className="text-sm text-slate-600 dark:text-slate-300">{item}</p>
          ))}
        </div>
      </div>

      <button
        type="button"
        disabled={!canSelect || selected}
        onClick={() => onSelect(plan.id)}
        className={`mt-5 w-full rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
          selected
            ? 'border border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-300'
            : 'bg-brand text-white hover:bg-brand-dark'
        }`}
      >
        {selected ? 'Plano atual' : canSelect ? 'Selecionar plano' : 'Sem permissao para selecionar'}
      </button>
    </article>
  )
}

export default function Assinatura() {
  const { user, isAdmin } = useAuth()
  const { toast } = useToast()
  const [selectedPlan, setSelectedPlan] = useState(() => readPlan())

  const currentPlan = useMemo(
    () => PLANS.find((plan) => plan.id === selectedPlan) || PLANS[1],
    [selectedPlan],
  )

  const selectPlan = (planId) => {
    if (!isAdmin) {
      toast({ type: 'error', message: 'Somente administradores podem selecionar ou trocar o plano.' })
      return
    }
    localStorage.setItem(STORAGE_KEY, planId)
    setSelectedPlan(planId)
    toast({ type: 'success', message: 'Plano atualizado para este ambiente.' })
  }

  return (
    <div className="space-y-6 p-6 lg:p-8">
      <section className="rounded-lg border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600 dark:text-blue-300">Assinatura</p>
            <h1 className="mt-2 text-2xl font-bold text-slate-950 dark:text-white">Planos e permissao de selecao</h1>
            <p className="mt-3 text-sm leading-6 text-slate-500 dark:text-slate-400">
              Consulte os planos disponiveis e controle qual pacote fica ativo no ambiente. A troca de plano fica restrita aos usuarios com permissao administrativa.
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-900">
            <p className="text-xs text-slate-500 dark:text-slate-400">Plano atual</p>
            <p className="mt-1 text-base font-bold text-slate-950 dark:text-white">{currentPlan.name}</p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{user?.tenant?.name || 'Ambiente atual'}</p>
          </div>
        </div>
      </section>

      {!isAdmin && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
          Voce pode visualizar os planos, mas apenas administradores podem selecionar ou trocar a assinatura.
        </div>
      )}

      <section className="grid gap-4 xl:grid-cols-3">
        {PLANS.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            selected={selectedPlan === plan.id}
            canSelect={isAdmin}
            onSelect={selectPlan}
          />
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-base font-semibold text-slate-950 dark:text-white">Permissoes</h2>
          <div className="mt-4 space-y-2">
            {PERMISSIONS.map(([action, permission]) => (
              <div key={action} className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-900">
                <p className="text-sm text-slate-700 dark:text-slate-200">{action}</p>
                <p className="text-right text-xs text-slate-500 dark:text-slate-400">{permission}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-base font-semibold text-slate-950 dark:text-white">Resumo comercial</h2>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {[
              ['Plano ativo', currentPlan.name],
              ['Preco', `${currentPlan.price}${currentPlan.cadence}`],
              ['Perfil do usuario', user?.role || 'viewer'],
              ['Pode selecionar', isAdmin ? 'Sim' : 'Nao'],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-900">
                <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
                <p className="mt-1 text-sm font-semibold text-slate-950 dark:text-white">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

