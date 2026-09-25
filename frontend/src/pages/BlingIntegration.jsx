import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ExternalLink, FileText, Link2, PackagePlus, Unplug } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'

import { blingApi } from '../api/client'
import PageHeader from '../components/ui/PageHeader'
import SectionCard from '../components/ui/SectionCard'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

const today = () => new Date().toISOString().slice(0, 10)

const EMPTY_STATUS = {
  configured: false,
  connected: false,
  clientIdHint: null,
  tokenExpiresAt: null,
  scopes: [],
}

function apiError(error, fallback) {
  const detail = error.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join('; ')
  return fallback
}

function Field({ label, hint, children }) {
  return (
    <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
      {label}
      {children}
      {hint && <span className="mt-1 block text-xs font-normal text-slate-500 dark:text-slate-400">{hint}</span>}
    </label>
  )
}

export default function BlingIntegration() {
  const { isAdmin, isEditor } = useAuth()
  const { toast, confirm } = useToast()
  const location = useLocation()
  const navigate = useNavigate()
  const [status, setStatus] = useState(EMPTY_STATUS)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [credentials, setCredentials] = useState({ clientId: '', clientSecret: '' })
  const [orderId, setOrderId] = useState(null)
  const [invoiceId, setInvoiceId] = useState(null)
  const [sendEmail, setSendEmail] = useState(false)
  const [form, setForm] = useState({
    orderDate: today(),
    departureDate: today(),
    expectedDate: today(),
    contactId: '',
    productId: '',
    description: '',
    quantity: '1',
    unitValue: '',
    paymentMethodId: '',
    dueDate: today(),
  })

  const total = useMemo(() => {
    const value = Number(form.quantity) * Number(form.unitValue)
    return Number.isFinite(value) ? value : 0
  }, [form.quantity, form.unitValue])

  const loadStatus = async () => {
    try {
      const response = await blingApi.status()
      setStatus(response.data)
    } catch (error) {
      toast({ type: 'error', title: 'Bling', message: apiError(error, 'Não foi possível consultar a integração.') })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    if (params.get('bling') !== 'connected') return
    toast({ type: 'success', title: 'Bling conectado', message: 'A autorização OAuth foi concluída para esta empresa.' })
    navigate('/integracoes/bling', { replace: true })
  }, [location.search, navigate, toast])

  const updateForm = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }))
  }

  const saveCredentials = async (event) => {
    event.preventDefault()
    setBusy('credentials')
    try {
      const response = await blingApi.saveCredentials(credentials)
      setStatus(response.data)
      setCredentials((current) => ({ ...current, clientSecret: '' }))
      toast({ type: 'success', title: 'Credenciais protegidas', message: 'Client Secret salvo de forma criptografada para esta empresa.' })
    } catch (error) {
      toast({ type: 'error', title: 'Credenciais', message: apiError(error, 'Não foi possível salvar as credenciais.') })
    } finally {
      setBusy('')
    }
  }

  const connect = async () => {
    setBusy('oauth')
    try {
      const response = await blingApi.startOAuth()
      window.location.assign(response.data.authorizationUrl)
    } catch (error) {
      toast({ type: 'error', title: 'Conexão Bling', message: apiError(error, 'Não foi possível iniciar a autorização.') })
      setBusy('')
    }
  }

  const disconnect = async () => {
    const accepted = await confirm('Remover as credenciais e tokens do Bling desta empresa?', { title: 'Desconectar Bling' })
    if (!accepted) return
    setBusy('disconnect')
    try {
      await blingApi.disconnect()
      setStatus(EMPTY_STATUS)
      setOrderId(null)
      setInvoiceId(null)
      toast({ type: 'success', title: 'Bling desconectado', message: 'As credenciais criptografadas foram removidas.' })
    } catch (error) {
      toast({ type: 'error', title: 'Bling', message: apiError(error, 'Não foi possível desconectar.') })
    } finally {
      setBusy('')
    }
  }

  const createOrder = async (event) => {
    event.preventDefault()
    setBusy('order')
    setInvoiceId(null)
    try {
      const parcelas = form.paymentMethodId
        ? [{
            dataVencimento: form.dueDate,
            valor: total,
            formaPagamento: { id: Number(form.paymentMethodId) },
          }]
        : []
      const response = await blingApi.createSalesOrder({
        data: form.orderDate,
        dataSaida: form.departureDate,
        dataPrevista: form.expectedDate,
        contato: { id: Number(form.contactId) },
        itens: [{
          descricao: form.description,
          quantidade: Number(form.quantity),
          valor: Number(form.unitValue),
          valorLista: Number(form.unitValue),
          produto: { id: Number(form.productId) },
        }],
        parcelas,
      })
      const createdId = response.data?.data?.id ?? response.data?.id
      if (!createdId) throw new Error('Resposta do Bling sem ID do pedido')
      setOrderId(createdId)
      toast({ type: 'success', title: 'Pedido criado', message: `Pedido ${createdId} criado no Bling.` })
    } catch (error) {
      toast({ type: 'error', title: 'Pedido de venda', message: apiError(error, error.message || 'Não foi possível criar o pedido.') })
    } finally {
      setBusy('')
    }
  }

  const generateInvoice = async () => {
    setBusy('invoice')
    try {
      const response = await blingApi.createInvoiceFromOrder(orderId)
      const generatedId = response.data?.data?.idNotaFiscal
        ?? response.data?.idNotaFiscal
        ?? response.data?.data?.id
      if (!generatedId) throw new Error('Resposta do Bling sem ID da nota fiscal')
      setInvoiceId(generatedId)
      toast({ type: 'success', title: 'NF-e criada', message: `Nota fiscal ${generatedId} gerada como rascunho no Bling.` })
    } catch (error) {
      toast({ type: 'error', title: 'Gerar NF-e', message: apiError(error, error.message || 'Não foi possível gerar a nota.') })
    } finally {
      setBusy('')
    }
  }

  const authorizeInvoice = async () => {
    const accepted = await confirm('Enviar esta NF-e para autorização na Sefaz? Esta é uma operação fiscal real.', { title: 'Autorizar NF-e' })
    if (!accepted) return
    setBusy('authorize')
    try {
      await blingApi.authorizeInvoice(invoiceId, sendEmail)
      toast({ type: 'success', title: 'NF-e enviada', message: 'A nota foi enviada ao Bling para autorização na Sefaz.' })
    } catch (error) {
      toast({ type: 'error', title: 'Autorizar NF-e', message: apiError(error, 'Não foi possível enviar a nota.') })
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <PageHeader
        eyebrow="Integrações"
        title="Bling ERP"
        description="Conecte a conta da empresa e execute o fluxo de pedido de venda até a emissão da NF-e."
      >
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 font-medium ${status.connected ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300' : 'bg-amber-100 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300'}`}>
            {status.connected ? <CheckCircle2 size={16} /> : <Unplug size={16} />}
            {loading ? 'Consultando...' : status.connected ? 'Conta conectada' : 'Não conectado'}
          </span>
          {status.clientIdHint && <span className="text-slate-500 dark:text-slate-400">Client ID {status.clientIdHint}</span>}
        </div>
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.5fr]">
        <div className="space-y-6">
          <SectionCard title="Conexão OAuth" description="As credenciais e os tokens ficam criptografados e isolados por empresa.">
            {isAdmin ? (
              <div className="space-y-4">
                <form onSubmit={saveCredentials} className="space-y-3">
                  <Field label="Client ID">
                    <input className="input mt-1.5" value={credentials.clientId} onChange={(event) => setCredentials((current) => ({ ...current, clientId: event.target.value }))} placeholder={status.clientIdHint || 'Client ID do aplicativo Bling'} required />
                  </Field>
                  <Field label="Client Secret" hint="Salvar novas credenciais desconecta tokens anteriores.">
                    <input className="input mt-1.5" type="password" value={credentials.clientSecret} onChange={(event) => setCredentials((current) => ({ ...current, clientSecret: event.target.value }))} placeholder="Nunca será exibido novamente" required autoComplete="new-password" />
                  </Field>
                  <button className="btn-ghost w-full" disabled={busy === 'credentials'}>{busy === 'credentials' ? 'Protegendo...' : 'Salvar credenciais'}</button>
                </form>
                <button type="button" className="btn-primary flex w-full items-center justify-center gap-2" onClick={connect} disabled={!status.configured || busy === 'oauth'}>
                  <Link2 size={16} /> {status.connected ? 'Reconectar no Bling' : 'Conectar ao Bling'} <ExternalLink size={14} />
                </button>
                {status.configured && (
                  <button type="button" className="w-full text-xs text-red-500 hover:text-red-400" onClick={disconnect} disabled={busy === 'disconnect'}>Remover integração desta empresa</button>
                )}
              </div>
            ) : (
              <p className="text-sm leading-6 text-slate-500 dark:text-slate-400">Somente um administrador pode cadastrar ou trocar as credenciais. Depois da conexão, editores podem criar pedidos e notas.</p>
            )}
          </SectionCard>

          <SectionCard title="Etapas" description="A autorização fiscal permanece separada para evitar emissões acidentais.">
            <ol className="space-y-3 text-sm">
              {[
                ['1', 'Criar pedido de venda', orderId ? `Pedido ${orderId}` : 'Pendente'],
                ['2', 'Gerar rascunho da NF-e', invoiceId ? `NF-e ${invoiceId}` : 'Pendente'],
                ['3', 'Enviar para a Sefaz', 'Confirmação obrigatória'],
              ].map(([number, label, detail]) => (
                <li key={number} className="flex items-center gap-3">
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-blue-50 font-semibold text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">{number}</span>
                  <span><span className="block font-medium text-slate-800 dark:text-white">{label}</span><span className="text-xs text-slate-500 dark:text-slate-400">{detail}</span></span>
                </li>
              ))}
            </ol>
          </SectionCard>
        </div>

        <SectionCard title="Novo pedido de venda" description="Use os IDs cadastrados no Bling para contato, produto e forma de pagamento.">
          <form onSubmit={createOrder} className="space-y-5">
            <fieldset disabled={!status.connected || !isEditor || Boolean(busy)} className="space-y-5 disabled:opacity-60">
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Data do pedido"><input className="input mt-1.5" type="date" value={form.orderDate} onChange={updateForm('orderDate')} required /></Field>
                <Field label="Data de saída"><input className="input mt-1.5" type="date" value={form.departureDate} onChange={updateForm('departureDate')} required /></Field>
                <Field label="Entrega prevista"><input className="input mt-1.5" type="date" value={form.expectedDate} onChange={updateForm('expectedDate')} required /></Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="ID do contato no Bling"><input className="input mt-1.5" type="number" min="1" value={form.contactId} onChange={updateForm('contactId')} required /></Field>
                <Field label="ID do produto no Bling"><input className="input mt-1.5" type="number" min="1" value={form.productId} onChange={updateForm('productId')} required /></Field>
              </div>
              <Field label="Descrição do item"><input className="input mt-1.5" value={form.description} onChange={updateForm('description')} required /></Field>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Quantidade"><input className="input mt-1.5" type="number" min="0.001" step="0.001" value={form.quantity} onChange={updateForm('quantity')} required /></Field>
                <Field label="Valor unitário"><input className="input mt-1.5" type="number" min="0.01" step="0.01" value={form.unitValue} onChange={updateForm('unitValue')} required /></Field>
                <Field label="Total"><div className="input mt-1.5 bg-slate-50 dark:bg-slate-900/40">{total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</div></Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="ID da forma de pagamento" hint="Opcional; deixe vazio para criar sem parcela."><input className="input mt-1.5" type="number" min="1" value={form.paymentMethodId} onChange={updateForm('paymentMethodId')} /></Field>
                <Field label="Vencimento"><input className="input mt-1.5" type="date" value={form.dueDate} onChange={updateForm('dueDate')} disabled={!form.paymentMethodId} /></Field>
              </div>
              <button className="btn-primary flex w-full items-center justify-center gap-2" type="submit"><PackagePlus size={17} />{busy === 'order' ? 'Criando pedido...' : 'Criar pedido no Bling'}</button>
            </fieldset>
          </form>

          {orderId && (
            <div className="mt-6 rounded-xl border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-blue-950/30">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div><p className="font-semibold text-slate-900 dark:text-white">Pedido {orderId} criado</p><p className="text-xs text-slate-500 dark:text-slate-400">Agora gere a nota fiscal vinculada ao pedido.</p></div>
                <button type="button" className="btn-primary flex items-center gap-2" onClick={generateInvoice} disabled={Boolean(busy)}><FileText size={16} />{busy === 'invoice' ? 'Gerando...' : 'Gerar NF-e'}</button>
              </div>
            </div>
          )}

          {invoiceId && (
            <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
              <p className="font-semibold text-slate-900 dark:text-white">NF-e {invoiceId} criada como rascunho</p>
              <label className="my-3 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300"><input type="checkbox" checked={sendEmail} onChange={(event) => setSendEmail(event.target.checked)} /> Enviar e-mail após a emissão</label>
              <button type="button" className="btn-primary w-full" onClick={authorizeInvoice} disabled={Boolean(busy)}>{busy === 'authorize' ? 'Enviando à Sefaz...' : 'Autorizar NF-e na Sefaz'}</button>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  )
}
