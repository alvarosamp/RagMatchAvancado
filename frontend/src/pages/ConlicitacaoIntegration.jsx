import { useEffect, useState } from 'react'
import { Activity, Download, Play, RefreshCw, ShieldCheck, Square } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { conlicitacaoApi } from '../api/client'
import PageHeader from '../components/ui/PageHeader'
import SectionCard from '../components/ui/SectionCard'
import { useToast } from '../contexts/ToastContext'

const EMPTY_STATUS = { enabled: false, configured: false, read_only_available: false, authorized: false }

function apiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join('; ')
  return fallback
}

function StatusPill({ active, children }) {
  return (
    <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${
      active
        ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
        : 'bg-rose-100 text-rose-800 dark:bg-rose-950/40 dark:text-rose-300'
    }`}>
      {children}: {active ? 'sim' : 'não'}
    </span>
  )
}

function ResultCard({ result }) {
  const skipped = result.ok == null
  const tone = skipped
    ? 'border-amber-200 dark:border-amber-900'
    : result.ok
      ? 'border-emerald-200 dark:border-emerald-900'
      : 'border-rose-200 dark:border-rose-900'

  return (
    <article className={`rounded-xl border p-4 ${tone}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-100">{result.endpoint}</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {skipped ? 'Não executado' : result.ok ? 'Resposta válida' : 'Falhou'}
            {result.latency_ms != null && ` · ${result.latency_ms} ms`}
          </p>
        </div>
        {result.counts && (
          <div className="flex flex-wrap gap-1">
            {Object.entries(result.counts).map(([key, value]) => (
              <span key={key} className="rounded bg-slate-100 px-2 py-1 text-[11px] text-slate-600 dark:bg-slate-900 dark:text-slate-300">
                {key}: {value}
              </span>
            ))}
          </div>
        )}
      </div>
      {(result.error || result.skipped) && (
        <p className="mt-3 text-xs leading-5 text-slate-600 dark:text-slate-300">{result.error || result.skipped}</p>
      )}
      {result.shape && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-blue-700 dark:text-blue-300">Ver campos e tipos</summary>
          <pre className="mt-2 max-h-80 overflow-auto rounded-lg bg-slate-950 p-3 text-[11px] leading-5 text-slate-200">
            {JSON.stringify(result.shape, null, 2)}
          </pre>
        </details>
      )}
    </article>
  )
}

export default function ConlicitacaoIntegration() {
  const navigate = useNavigate()
  const { toast, confirm } = useToast()
  const [status, setStatus] = useState(EMPTY_STATUS)
  const [loadingStatus, setLoadingStatus] = useState(true)
  const [busy, setBusy] = useState('')
  const [diagnostics, setDiagnostics] = useState(null)
  const [ids, setIds] = useState({ filterId: '', bulletinId: '', biddingId: '', userId: '' })

  const readOnlyReady = status.read_only_available || (status.enabled && status.configured)
  const writeReady = readOnlyReady && status.authorized

  const loadStatus = async () => {
    setLoadingStatus(true)
    try {
      const response = await conlicitacaoApi.status()
      setStatus(response.data)
    } catch (error) {
      toast({ type: 'error', title: 'ConLicitação', message: apiError(error, 'Não foi possível consultar o status.') })
    } finally {
      setLoadingStatus(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const runDiagnostics = async () => {
    setBusy('diagnostics')
    try {
      const payload = {}
      if (ids.filterId) payload.filter_id = Number(ids.filterId)
      if (ids.bulletinId) payload.bulletin_id = Number(ids.bulletinId)
      const response = await conlicitacaoApi.diagnostics(payload)
      setDiagnostics(response.data)
      const failures = response.data.summary?.failed || 0
      toast({
        type: failures ? 'warning' : 'success',
        title: 'Diagnóstico concluído',
        message: failures ? `${failures} chamada(s) falharam. Veja os detalhes.` : 'Todas as chamadas possíveis responderam.',
      })
    } catch (error) {
      toast({ type: 'error', title: 'Diagnóstico', message: apiError(error, 'Não foi possível testar a API.') })
    } finally {
      setBusy('')
    }
  }

  const exportDiagnostics = () => {
    if (!diagnostics) return
    const blob = new Blob([JSON.stringify(diagnostics, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `conlicitacao-diagnostico-${new Date().toISOString().replaceAll(':', '-')}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const sync = async () => {
    setBusy('sync')
    try {
      const response = await conlicitacaoApi.sync()
      toast({ type: 'success', title: 'Sincronização enfileirada', message: `Correlação: ${response.data.correlation_id}` })
    } catch (error) {
      toast({ type: 'error', title: 'Sincronização', message: apiError(error, 'Não foi possível iniciar a sincronização.') })
    } finally {
      setBusy('')
    }
  }

  const monitoring = async (action) => {
    const biddingId = Number(ids.biddingId)
    const userId = Number(ids.userId)
    if (!biddingId || !userId) {
      toast({ type: 'warning', title: 'IDs obrigatórios', message: 'Informe IDs válidos da licitação e do usuário.' })
      return
    }
    const verb = action === 'start' ? 'iniciar' : 'parar'
    const accepted = await confirm(
      `Deseja ${verb} o acompanhamento da licitação ${biddingId} para o usuário ${userId}? Esta ação altera dados na ConLicitação.`,
      { title: `${verb[0].toUpperCase()}${verb.slice(1)} acompanhamento` },
    )
    if (!accepted) return
    setBusy(action)
    try {
      const response = action === 'start'
        ? await conlicitacaoApi.startMonitoring(biddingId, userId)
        : await conlicitacaoApi.stopMonitoring(biddingId, userId)
      toast({ type: 'success', title: 'Operação concluída', message: `Correlação: ${response.data.correlation_id}` })
    } catch (error) {
      toast({ type: 'error', title: 'Acompanhamento', message: apiError(error, 'A operação foi recusada.') })
    } finally {
      setBusy('')
    }
  }

  const updateId = (field) => (event) => setIds((current) => ({ ...current, [field]: event.target.value }))

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <PageHeader
        eyebrow="Integrações · acesso administrativo"
        title="Laboratório ConLicitação"
        description="Teste a API a partir do IP da VPS, confira os formatos das respostas e exporte um relatório sem valores sensíveis."
        secondaryAction={{ label: 'Voltar ao Bling', onClick: () => navigate('/integracoes/bling') }}
      >
        <div className="flex flex-wrap gap-2">
          <StatusPill active={status.enabled}>Habilitada</StatusPill>
          <StatusPill active={status.configured}>Token configurado</StatusPill>
          <StatusPill active={readOnlyReady}>Leitura disponível</StatusPill>
          <StatusPill active={status.authorized}>Sincronização autorizada</StatusPill>
          {loadingStatus && <span className="text-xs text-slate-500">Consultando...</span>}
        </div>
      </PageHeader>

      {!readOnlyReady && !loadingStatus && (
        <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          Na VPS, configure <code>CONLICITACAO_ENABLED=1</code> e o token. O IP autorizado deve ser o IP público de saída da VPS.
        </div>
      )}

      {readOnlyReady && !status.authorized && !loadingStatus && (
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900 dark:border-blue-900 dark:bg-blue-950/30 dark:text-blue-200">
          O diagnóstico somente leitura está disponível. Sincronização e acompanhamento permanecem bloqueados até o ID da empresa ser incluído em <code>CONLICITACAO_TENANT_IDS</code>.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
        <SectionCard title="Diagnóstico somente leitura" description="Consulta automaticamente filtros, boletins, licitações, acompanhamentos, mensagens e usuários. Nenhum preenchimento é necessário e valores sensíveis não são devolvidos ao navegador.">
          <details className="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
            <summary className="cursor-pointer text-xs font-semibold text-slate-600 dark:text-slate-300">Opções avançadas (IDs opcionais)</summary>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
                ID do filtro
                <input className="input mt-1.5" type="number" min="1" value={ids.filterId} onChange={updateId('filterId')} placeholder="Detectar automaticamente" />
              </label>
              <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
                ID do boletim
                <input className="input mt-1.5" type="number" min="1" value={ids.bulletinId} onChange={updateId('bulletinId')} placeholder="Detectar automaticamente" />
              </label>
            </div>
          </details>
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" className="btn-primary flex items-center gap-2" disabled={!readOnlyReady || Boolean(busy)} onClick={runDiagnostics}>
              {busy === 'diagnostics' ? <RefreshCw size={16} className="animate-spin" /> : <Activity size={16} />}
              {busy === 'diagnostics' ? 'Testando...' : 'Testar todos os GETs'}
            </button>
            <button type="button" className="btn-ghost flex items-center gap-2" disabled={!diagnostics} onClick={exportDiagnostics}>
              <Download size={16} /> Exportar JSON sanitizado
            </button>
          </div>
        </SectionCard>

        <SectionCard title="Sincronizar com o RagMatch" description="Enfileira a importação dos boletins disponíveis para esta empresa.">
          <div className="rounded-lg bg-blue-50 p-3 text-xs leading-5 text-blue-900 dark:bg-blue-950/30 dark:text-blue-200">
            <ShieldCheck size={17} className="mb-2" /> O processamento ocorre no worker dedicado e mantém o isolamento por empresa.
          </div>
          <button type="button" className="btn-primary mt-4 w-full" disabled={!writeReady || Boolean(busy)} onClick={sync}>
            {busy === 'sync' ? 'Enfileirando...' : 'Sincronizar agora'}
          </button>
        </SectionCard>
      </div>

      {diagnostics && (
        <SectionCard title="Resultado dos endpoints" description={`${diagnostics.summary.completed} concluídos · ${diagnostics.summary.failed} falharam · ${diagnostics.summary.skipped} ignorados`}>
          <div className="grid gap-3 lg:grid-cols-2">
            {diagnostics.results.map((result) => <ResultCard key={result.endpoint} result={result} />)}
          </div>
          <p className="mt-4 text-xs text-slate-500">Correlação: {diagnostics.correlation_id} · Gerado em {new Date(diagnostics.generated_at).toLocaleString('pt-BR')}</p>
        </SectionCard>
      )}

      <SectionCard title="Teste de acompanhamento" description="Operações de escrita. Use IDs reais retornados pela conta e confirme cada mudança.">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
            ID da licitação
            <input className="input mt-1.5" type="number" min="1" value={ids.biddingId} onChange={updateId('biddingId')} />
          </label>
          <label className="text-xs font-medium text-slate-600 dark:text-slate-300">
            ID do usuário ConLicitação
            <input className="input mt-1.5" type="number" min="1" value={ids.userId} onChange={updateId('userId')} />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" className="btn-primary flex items-center gap-2" disabled={!writeReady || Boolean(busy)} onClick={() => monitoring('start')}>
            <Play size={15} /> Iniciar acompanhamento
          </button>
          <button type="button" className="btn-ghost flex items-center gap-2" disabled={!writeReady || Boolean(busy)} onClick={() => monitoring('stop')}>
            <Square size={15} /> Parar acompanhamento
          </button>
        </div>
      </SectionCard>
    </div>
  )
}
