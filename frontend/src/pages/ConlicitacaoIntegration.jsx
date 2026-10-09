import { useEffect, useState } from 'react'
import { Activity, Download, FileText, Play, RefreshCw, Search, ShieldCheck, Square } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { conlicitacaoApi } from '../api/client'
import ConlicitacaoLab from '../components/conlicitacao/ConlicitacaoLab'
import PageHeader from '../components/ui/PageHeader'
import SectionCard from '../components/ui/SectionCard'
import { useToast } from '../contexts/ToastContext'
import { tenderExportJson } from '../utils/conlicitacaoTenderExport'

const EMPTY_STATUS = {
  enabled: false,
  configured: false,
  read_only_available: false,
  authorized: false,
  manual_import_authorized: false,
}

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

function formatMoney(value) {
  if (value == null || value === '') return 'Não informado'
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(value))
}

function formatDate(value) {
  if (!value) return 'Não informada'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('pt-BR')
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
  const [lookupId, setLookupId] = useState('')
  const [preview, setPreview] = useState(null)
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

  const lookupOpportunity = async () => {
    const externalId = Number(lookupId)
    if (!Number.isInteger(externalId) || externalId <= 0) {
      toast({ type: 'warning', title: 'Número inválido', message: 'Informe o número ConLicitação.' })
      return
    }
    setBusy('lookup')
    setPreview(null)
    try {
      const response = await conlicitacaoApi.previewOpportunity(externalId)
      setPreview(response.data)
      toast({ type: 'success', title: 'Licitação encontrada', message: 'Dados consultados pela VPS.' })
    } catch (error) {
      toast({ type: 'error', title: 'Consulta', message: apiError(error, 'Não foi possível localizar a licitação.') })
    } finally {
      setBusy('')
    }
  }

  const exportOpportunity = async () => {
    const externalId = Number(preview?.opportunity?.external_id)
    if (!externalId) return
    setBusy('export')
    try {
      const response = await conlicitacaoApi.labBulletin(preview.bulletin_id)
      const source = response.data.data.licitacoes.find(item => Number(item.id) === externalId)
      const blob = new Blob([tenderExportJson(preview, source)], { type: 'application/json;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `conlicitacao-edital-${externalId}.json`
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      toast({
        type: 'success',
        title: 'JSON exportado',
        message: 'Dados originais e campos do edital prontos para análise.',
      })
    } catch (error) {
      toast({ type: 'error', title: 'Exportação', message: apiError(error, 'Não foi possível exportar os dados do edital.') })
    } finally {
      setBusy('')
    }
  }

  const downloadDocument = async (document, index) => {
    setBusy(`download-${index}`)
    try {
      const response = await conlicitacaoApi.labDocument(preview.bulletin_id, preview.opportunity.external_id, document.index ?? index)
      const url = URL.createObjectURL(response.data)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = (document.filename || `documento-${index + 1}`).split(/[\\/]/).pop()
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      toast({ type: 'success', title: 'Documento baixado', message: document.filename })
    } catch {
      toast({ type: 'error', title: 'Download', message: 'Não foi possível baixar o arquivo. Confira o acesso da VPS à ConLicitação.' })
    } finally { setBusy('') }
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
          <StatusPill active={importReady}>Importação manual</StatusPill>
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

      <ConlicitacaoLab enabled={readOnlyReady && !loadingStatus} />

      <SectionCard
        title="Teste: baixar edital e exportar dados"
        description="Informe somente o número ConLicitação. A VPS localiza automaticamente o filtro e o boletim, sem expor o token ao navegador."
      >
        <div className="flex flex-col gap-3 sm:flex-row">
          <label className="flex-1 text-xs font-medium text-slate-600 dark:text-slate-300">
            Número ConLicitação
            <input
              className="input mt-1.5"
              type="number"
              min="1"
              value={lookupId}
              onChange={(event) => setLookupId(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && lookupOpportunity()}
              placeholder="Ex.: 19399420"
            />
          </label>
          <button
            type="button"
            className="btn-primary self-end sm:mb-0"
            disabled={!readOnlyReady || Boolean(busy)}
            onClick={lookupOpportunity}
          >
            {busy === 'lookup' ? <RefreshCw size={16} className="animate-spin" /> : <Search size={16} />}
            {busy === 'lookup' ? 'Localizando...' : 'Consultar pela VPS'}
          </button>
        </div>

        {preview && (() => {
          const opportunity = preview.opportunity
          const documents = opportunity.documents || []
          return (
            <article className="mt-5 rounded-xl border border-blue-200 bg-blue-50/60 p-4 dark:border-blue-900 dark:bg-blue-950/20">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-blue-700 dark:text-blue-300">ConLicitação {opportunity.external_id}</p>
                  <h3 className="mt-1 text-base font-semibold text-slate-900 dark:text-white">{opportunity.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-200">{opportunity.object || 'Objeto não informado.'}</p>
                </div>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm dark:bg-slate-900 dark:text-slate-200">
                  {opportunity.status || 'Status não informado'}
                </span>
              </div>
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div><dt className="text-xs text-slate-500">Edital</dt><dd className="font-medium">{opportunity.edital_number || 'Não informado'}</dd></div>
                <div><dt className="text-xs text-slate-500">Órgão</dt><dd className="font-medium">{opportunity.public_body_name || 'Não informado'}</dd></div>
                <div><dt className="text-xs text-slate-500">Local</dt><dd className="font-medium">{[opportunity.public_body_city, opportunity.public_body_state].filter(Boolean).join(' / ') || 'Não informado'}</dd></div>
                <div><dt className="text-xs text-slate-500">Valor estimado</dt><dd className="font-medium">{formatMoney(opportunity.estimated_value)}</dd></div>
                <div><dt className="text-xs text-slate-500">Abertura</dt><dd className="font-medium">{formatDate(opportunity.opening_at)}</dd></div>
                <div><dt className="text-xs text-slate-500">Prazo</dt><dd className="font-medium">{formatDate(opportunity.proposal_deadline_at)}</dd></div>
                <div><dt className="text-xs text-slate-500">Boletim</dt><dd className="font-medium">{preview.bulletin_number || preview.bulletin_id}</dd></div>
                <div><dt className="text-xs text-slate-500">Documentos</dt><dd className="font-medium">{documents.length}</dd></div>
              </dl>
              {documents.length > 0 && (
                <details className="mt-4 rounded-lg border border-blue-200 bg-white p-3 dark:border-blue-900 dark:bg-slate-950">
                  <summary className="cursor-pointer text-xs font-semibold text-blue-700 dark:text-blue-300">Ver documentos encontrados</summary>
                  <ul className="mt-3 space-y-2">
                    {documents.map((document, index) => (
                      <li key={`${document.filename}-${index}`} className="flex items-center gap-2 text-xs text-slate-700 dark:text-slate-200">
                        <FileText size={14} /> {document.filename || `Documento ${index + 1}`}
                        <button type="button" className="btn-ghost" disabled={Boolean(busy)} onClick={() => downloadDocument(document, index)}>
                          <Download size={14} /> {busy === `download-${index}` ? 'Baixando…' : 'Baixar arquivo'}
                        </button>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <button type="button" className="btn-primary" disabled={!readOnlyReady || Boolean(busy)} onClick={exportOpportunity}>
                  <Download size={16} /> {busy === 'export' ? 'Exportando…' : 'Exportar JSON do edital'}
                </button>
                <span className="text-xs text-slate-500">Exporta os campos da API e do edital, sem criar um registro no CRM.</span>
              </div>
            </article>
          )
        })()}
      </SectionCard>

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
